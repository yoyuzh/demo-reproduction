"""Single-page Streamlit demo for the paper's two log examples."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from light_demo.cases import CASES
from light_demo.core import diagnose, make_client


st.set_page_config(page_title="配置错误定位 · 论文轻量复现", layout="wide")
st.title("配置错误定位 · 论文轻量复现")
st.caption("论文图 1 的两个案例；手工日志模板；图 3、图 4 的原文 system prompt。")

case_id = st.selectbox(
    "选择案例",
    options=list(CASES),
    format_func=lambda item: str(CASES[item]["title"]),
)
case = CASES[case_id]
if st.session_state.get("loaded_case") != case_id:
    st.session_state["fault_log"] = str(case["log"])
    st.session_state["config_json"] = str(case["config"])
    st.session_state["loaded_case"] = case_id

if case["test_only"]:
    st.warning("这是单独标注的测试案例：测试响应固定让图 3 验证失败，用于检查 complete-flow。")
else:
    st.info(f"论文案例预期配置项：`{case['expected_property']}`；测试响应预期路径：`{case['expected_flow']}`。")

left, right = st.columns(2)
with left:
    log_text = st.text_area("输入框 1：故障日志", key="fault_log", height=240)
with right:
    config_text = st.text_area("输入框 2：用户配置（JSON）", key="config_json", height=240)

with st.expander("本案例手写的 fault-free 模板库"):
    for template in case["normal_templates"]:
        st.code(str(template), language=None)

test_responses = st.checkbox("使用测试响应（不调用 OpenAI；仅支持未修改的预置案例）", value=True)
if test_responses:
    st.caption("测试响应只验证流程和页面；诊断解释是本地模拟文本，不是论文或 OpenAI 的输出。")
else:
    st.caption("实际调用 OpenAI API。请在启动服务的终端设置 OPENAI_API_KEY；可选 OPENAI_MODEL。")

start = st.button("开始定位配置错误", type="primary")
st.divider()
stage1_column, stage2_column = st.columns(2)
with stage1_column:
    st.subheader("Stage 1 · 关键日志")
    stage1_slot = st.empty()
with stage2_column:
    st.subheader("Stage 2 · 流转状态")
    stage2_slot = st.empty()
st.subheader("诊断报告")
report_slot = st.empty()

if start:
    try:
        client = make_client(log_text, config_text, test_responses, case_id)
        final = None
        for step in diagnose(log_text, config_text, client, list(case["normal_templates"])):
            final = step
            stage1_slot.json([
                {
                    "日志模板": event["template"],
                    "异常度": event["anomaly_degree"],
                    "选中的原始日志": event["key_log"],
                    "故障日志独有": event["specific"],
                }
                for event in step["stage1"]
            ])
            stage2_slot.text("\n".join([str(step["stage2_status"]), *map(str, step["trace"])]))
        if final and final["report"]:
            report_slot.json({
                "响应来源": "本地测试响应" if test_responses else "OpenAI API",
                "实际路径": final["flow"],
                "可疑配置": final["report"],
            })
            predicted = {item["name"] for item in final["report"]}
            if case["expected_property"] in predicted:
                st.success("报告包含本案例的已知配置项。")
            else:
                st.warning("报告未包含本案例的已知配置项；请核对模型输出。")
        elif final:
            report_slot.info("未生成可疑配置报告。")
    except (ValueError, RuntimeError, KeyError, IndexError) as error:
        report_slot.empty()
        st.error(f"模型调用或诊断失败：{error} 本次未生成诊断报告。")
