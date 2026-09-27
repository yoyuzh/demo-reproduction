"""A small classroom reproduction of the paper's two-stage decision flow."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterator, Protocol

from .cases import CASES, DIRECT_CONFIG, DIRECT_LOG, INDIRECT_CONFIG, INDIRECT_LOG
from .prompts import FIGURE_3_VERIFICATION, FIGURE_4_INDIRECT

NEGATIVE_WORDS = (
    "error", "exception", "invalid", "failure", "disable",
    "false", "fault", "warn", "because", "exit",
)
COMMON_NAME_PARTS = {
    "hadoop", "mapred", "mapreduce", "dfs", "yarn", "security", "group",
    "mapping", "job", "local", "fs", "client", "service", "max", "size",
    "timeout", "enabled", "namenode", "datanode",
}


@dataclass(frozen=True)
class Event:
    message: str
    full_log: str
    template: str


class ModelClient(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> str: ...


class OpenAIClient:
    def __init__(self, api_key: str, model: str = "gpt-4.1") -> None:
        self.api_key = api_key
        self.model = model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise ValueError("请设置 OPENAI_API_KEY，或勾选测试响应模式。")
        payload = json.dumps({
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }).encode("utf-8")
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"OpenAI API 返回 HTTP {error.code}") from error
        except urllib.error.URLError as error:
            raise RuntimeError("无法连接 OpenAI API") from error
        content = result["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("OpenAI API 未返回文本内容")
        return content


class ReplayClient:
    """Clearly marked local responses for case and branch testing."""

    def __init__(self, example: str) -> None:
        if example not in CASES:
            raise ValueError("测试响应只支持页面预置案例。")
        self.example = example

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if system_prompt == FIGURE_3_VERIFICATION:
            return "Probability is 30." if self.example == "complete_test" else "Probability is 95."
        if system_prompt != FIGURE_4_INDIRECT:
            raise ValueError("未知的 system prompt")
        if self.example in {"direct", "complete_test"}:
            return (
                "name:mapred.local.dir value:<missing> "
                "relevant log:1-java.io.IOException: No valid local directories in property: mapred.local.dir "
                "explanation:The log explicitly names mapred.local.dir and reports no valid local directories."
            )
        return (
            "name:hadoop.security.group.mapping.ldap.search.group.hierarchy.levels "
            "value:<missing> relevant log:1-java.lang.NullPointerException "
            "explanation:The LdapGroupsMapping stack trace points to group hierarchy processing."
        )


def parse_configuration(text: str) -> list[dict[str, str]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"配置 JSON 无效：{error.msg}") from error
    if not isinstance(data, dict) or not data or len(data) > 30:
        raise ValueError("配置必须是含 1–30 个配置项的 JSON 对象。")
    configurations = []
    for name, supplied in data.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("配置项名称必须是非空字符串。")
        if isinstance(supplied, dict):
            value = supplied.get("value", "<missing>")
            description = supplied.get("description", supplied.get("des", "<missing>"))
        else:
            value, description = supplied, "<missing>"
        configurations.append({
            "name": name.strip(),
            "value": "<missing>" if value is None else str(value),
            "description": "<missing>" if description is None else str(description),
        })
    return configurations


def template_for(message: str) -> str:
    # These two cases are hand-parsed from Figure 1; other pasted logs use a
    # deliberately small normalizer, not a claim to implement enhanced Drain.
    if message.startswith("java.io.IOException: No valid local directories in property:"):
        return "java.io.IOException: No valid local directories in property: <*>"
    if message.startswith("java.lang.NullPointerException"):
        return "java.lang.NullPointerException"
    message = re.sub(r"^\d{6}\s+\d{6}\s+", "", message)
    message = re.sub(r"\[[^\]]+\]", "[<*>]", message)
    message = re.sub(r"\b\d+(?:\.\d+)*\b", "<*>", message)
    return message


def parse_events(log_text: str) -> list[Event]:
    if not log_text.strip() or len(log_text) > 20_000:
        raise ValueError("请粘贴 1–20,000 字符的故障日志。")
    groups: list[list[str]] = []
    for raw_line in log_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("at ", "... ")) and groups:
            groups[-1].append(line)
        else:
            groups.append([line])
    return [
        Event(message=group[0], full_log="\n".join(group), template=template_for(group[0]))
        for group in groups
    ]


def anomaly_degree(template: str) -> float:
    lower = template.lower()
    return round(sum(word in lower for word in NEGATIVE_WORDS) * 0.1, 1)


def stage_one(log_text: str, normal_templates: list[str]) -> list[dict[str, object]]:
    results = []
    for event in parse_events(log_text):
        specific = event.template not in normal_templates
        score = anomaly_degree(event.template) if specific else 0.0
        results.append({
            "template": event.template,
            "specific": specific,
            "anomaly_degree": score,
            "key_log": event.full_log if score > 0 else "",
            "matching_log": event.message if score > 0 else "",
        })
    return results


def direct_inference(
    stage1: list[dict[str, object]], configurations: list[dict[str, str]]
) -> list[dict[str, str]]:
    candidates = []
    for event in stage1:
        if not event["key_log"]:
            continue
        log = str(event["matching_log"])
        for config in configurations:
            name, value = config["name"], config["value"]
            if name.lower() in log.lower():
                reason = "完整配置名匹配"
            elif value not in {"", "<missing>"} and value in log:
                reason = "配置值匹配"
            else:
                fragments = [
                    part for part in name.split(".")
                    if len(part) > 2 and part.lower() not in COMMON_NAME_PARTS
                    and re.search(rf"(?<![\w]){re.escape(part)}(?![\w])", log, re.IGNORECASE)
                ]
                if not fragments:
                    continue
                reason = "配置名片段匹配：" + ", ".join(fragments)
            candidates.append({**config, "relevant_log": str(event["key_log"]), "match_reason": reason})
    return candidates


def verification_prompt(candidate: dict[str, str]) -> str:
    return (
        f"{candidate['relevant_log'].splitlines()[0]}\n"
        "root-cause configuration option:\n"
        f"<name:{candidate['name']} value:{candidate['value']} desc:{candidate['description']} >"
    )


def indirect_prompt(
    stage1: list[dict[str, object]], configurations: list[dict[str, str]]
) -> str:
    key_logs = [str(event["key_log"]) for event in stage1 if event["key_log"]]
    log_lines = "\n".join(f"{index}-{log}" for index, log in enumerate(key_logs, 1))
    config_lines = "\n".join(
        f"name:{item['name']} value:{item['value']} des:{item['description']}"
        for item in configurations
    )
    return f"Log:\n{log_lines}\nConfiguration:\n{config_lines}"


def parse_probability(response: str) -> int:
    match = re.fullmatch(r"\s*Probability is (\d{1,3})\.\s*", response)
    if not match or int(match.group(1)) > 100:
        raise ValueError(f"图 3 响应格式不符：{response[:160]}")
    return int(match.group(1))


def parse_indirect_report(
    response: str, configurations: list[dict[str, str]]
) -> list[dict[str, str]]:
    names = {item["name"] for item in configurations}
    pattern = re.compile(
        r"name:\s*(.*?)\s+value:\s*(.*?)\s+relevant log:\s*(.*?)\s+explanation:\s*(.*?)(?=\n\s*name:|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    reports = []
    for match in pattern.finditer(response.strip()):
        name, value, relevant_log, explanation = (part.strip() for part in match.groups())
        if name in names:
            reports.append({
                "name": name,
                "value": value,
                "relevant_log": relevant_log,
                "explanation": explanation,
            })
    if not reports:
        raise ValueError(f"图 4 未返回可解析的配置项：{response[:200]}")
    return reports[:3]


def identify_replay_example(log_text: str, config_text: str, case_id: str) -> str | None:
    if case_id not in CASES:
        return None
    case = CASES[case_id]
    try:
        config = parse_configuration(config_text)
        expected = parse_configuration(str(case["config"]))
    except ValueError:
        return None
    if log_text.strip() == case["log"] and config == expected:
        return case_id
    return None


def diagnose(
    log_text: str, config_text: str, client: ModelClient, normal_templates: list[str]
) -> Iterator[dict[str, object]]:
    configurations = parse_configuration(config_text)
    stage1 = stage_one(log_text, normal_templates)
    snapshot: dict[str, object] = {
        "stage1": stage1,
        "stage2_status": "等待 Stage 2",
        "flow": None,
        "report": [],
        "trace": [],
    }
    yield snapshot.copy()

    if not any(event["key_log"] for event in stage1):
        snapshot.update(stage2_status="未检出关键异常日志", flow="no-anomaly")
        yield snapshot.copy()
        return

    candidates = direct_inference(stage1, configurations)
    trace: list[str] = [f"直接推理得到 {len(candidates)} 个候选项"]
    snapshot.update(stage2_status="直接推理完成", trace=trace.copy(), candidates=candidates)
    yield snapshot.copy()

    verified: list[dict[str, object]] = []
    if candidates:
        snapshot.update(stage2_status="调用图 3 原始 prompt 验证候选项")
        yield snapshot.copy()
        for candidate in candidates:
            response = client.complete(FIGURE_3_VERIFICATION, verification_prompt(candidate))
            probability = parse_probability(response)
            trace.append(f"{candidate['name']}：图 3 验证概率 {probability}")
            if probability > 90:
                verified.append({**candidate, "probability": probability})
        snapshot.update(trace=trace.copy())
        yield snapshot.copy()

    if verified:
        flow = "fast-flow"
        trace.append("图 3 验证通过，进入 fast-flow")
    elif candidates:
        flow = "complete-flow"
        trace.append("图 3 验证未通过，进入 complete-flow")
    else:
        flow = "direct-flow"
        trace.append("无直接匹配项，进入 direct-flow")

    snapshot.update(flow=flow, stage2_status=f"{flow}：调用图 4 原始 prompt 获取诊断解释", trace=trace.copy())
    yield snapshot.copy()
    response = client.complete(FIGURE_4_INDIRECT, indirect_prompt(stage1, configurations))
    indirect_reports = parse_indirect_report(response, configurations)

    if verified:
        explanations = {item["name"]: item["explanation"] for item in indirect_reports}
        report = [
            {
                "name": item["name"],
                "value": item["value"],
                "relevant_log": item["relevant_log"],
                "explanation": explanations.get(item["name"], "图 4 未解释该配置项"),
                "verification_probability": item["probability"],
                "match_reason": item["match_reason"],
                "flow": flow,
            }
            for item in verified
        ]
        trace.append("图 4 仅补充解释，不改变 fast-flow 的根因选择")
    else:
        report = [{**item, "flow": flow} for item in indirect_reports]
        trace.append("图 4 完成间接推理")
    snapshot.update(stage2_status=f"{flow}：完成", report=report, trace=trace.copy())
    yield snapshot.copy()


def make_client(log_text: str, config_text: str, replay: bool, case_id: str) -> ModelClient:
    if replay:
        example = identify_replay_example(log_text, config_text, case_id)
        if not example:
            raise ValueError("测试响应只支持未修改的预置案例；自定义输入请关闭测试响应并设置 API Key。")
        return ReplayClient(example)
    return OpenAIClient(os.environ.get("OPENAI_API_KEY", ""), os.environ.get("OPENAI_MODEL", "gpt-4.1"))
