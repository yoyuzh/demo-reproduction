import json
import io
import unittest
from unittest.mock import patch

from light_demo.cases import CASES
from light_demo.core import (
    DIRECT_CONFIG,
    DIRECT_LOG,
    INDIRECT_CONFIG,
    INDIRECT_LOG,
    OpenAIClient,
    ReplayClient,
    diagnose,
    direct_inference,
    stage_one,
)
from light_demo.prompts import FIGURE_3_VERIFICATION, FIGURE_4_INDIRECT


class RecordingClient:
    def __init__(self):
        self.prompts = []

    def complete(self, system_prompt, user_prompt):
        self.prompts.append(system_prompt)
        if system_prompt == FIGURE_3_VERIFICATION:
            return "Probability is 30."
        return (
            "name:mapred.local.dir value:<missing> "
            "relevant log:1-No valid local directories in property: mapred.local.dir "
            "explanation:The log names the invalid local directory property."
        )


class DemoFlowTests(unittest.TestCase):
    def test_live_client_sends_original_system_prompt(self):
        payload = json.dumps({"choices": [{"message": {"content": "Probability is 95."}}]}).encode()
        with patch("urllib.request.urlopen", return_value=io.BytesIO(payload)) as urlopen:
            response = OpenAIClient("test-key").complete(FIGURE_3_VERIFICATION, "sample log")
        request = urlopen.call_args.args[0]
        sent = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.openai.com/v1/chat/completions")
        self.assertEqual(sent["messages"][0]["content"], FIGURE_3_VERIFICATION)
        self.assertEqual(sent["temperature"], 0)
        self.assertEqual(response, "Probability is 95.")

    def test_direct_paper_sample_reaches_report(self):
        normals = CASES["direct"]["normal_templates"]
        stage1 = stage_one(DIRECT_LOG, normals)
        self.assertEqual(stage1[0]["anomaly_degree"], 0.0)
        self.assertEqual(stage1[1]["anomaly_degree"], 0.1)
        result = list(diagnose(DIRECT_LOG, DIRECT_CONFIG, ReplayClient("direct"), normals))[-1]
        self.assertEqual(result["flow"], "fast-flow")
        self.assertEqual(result["report"][0]["name"], "mapred.local.dir")
        self.assertEqual(result["report"][0]["flow"], "fast-flow")
        self.assertIn("完整配置名匹配", result["report"][0]["match_reason"])

    def test_configuration_name_fragment_matching(self):
        config = '{"fs.viewfs.mounttable.default.name.key": "<missing>"}'
        log = "java.io.IOException: Invalid entry in Mount table in config: name.key"
        from light_demo.core import parse_configuration
        matches = direct_inference(stage_one(log, []), parse_configuration(config))
        self.assertEqual(len(matches), 1)
        self.assertIn("片段匹配", matches[0]["match_reason"])

    def test_indirect_paper_sample_excludes_stack_from_direct_match(self):
        normals = CASES["indirect"]["normal_templates"]
        stage1 = stage_one(INDIRECT_LOG, normals)
        configurations = [
            {"name": name, "value": data["value"], "description": data["description"]}
            for name, data in json.loads(INDIRECT_CONFIG).items()
        ]
        self.assertEqual(direct_inference(stage1, configurations), [])
        result = list(diagnose(INDIRECT_LOG, INDIRECT_CONFIG, ReplayClient("indirect"), normals))[-1]
        self.assertEqual(result["flow"], "direct-flow")
        self.assertIn("LdapGroupsMapping", result["stage1"][0]["key_log"])
        self.assertEqual(
            result["report"][0]["name"],
            "hadoop.security.group.mapping.ldap.search.group.hierarchy.levels",
        )

    def test_failed_verification_enters_complete_flow_with_original_prompts(self):
        client = RecordingClient()
        result = list(diagnose(DIRECT_LOG, DIRECT_CONFIG, client, CASES["complete_test"]["normal_templates"]))[-1]
        self.assertEqual(result["flow"], "complete-flow")
        self.assertEqual(client.prompts, [FIGURE_3_VERIFICATION, FIGURE_4_INDIRECT])
        self.assertIn("local directory", result["report"][0]["explanation"])

        replay = list(diagnose(
            DIRECT_LOG, DIRECT_CONFIG, ReplayClient("complete_test"),
            CASES["complete_test"]["normal_templates"],
        ))[-1]
        self.assertEqual(replay["flow"], CASES["complete_test"]["expected_flow"])
        self.assertEqual(replay["report"][0]["name"], CASES["complete_test"]["expected_property"])

    def test_no_anomaly_avoids_model_call(self):
        client = RecordingClient()
        result = list(diagnose("TaskTracker started successfully", DIRECT_CONFIG, client, CASES["direct"]["normal_templates"]))[-1]
        self.assertEqual(result["flow"], "no-anomaly")
        self.assertEqual(client.prompts, [])


if __name__ == "__main__":
    unittest.main()
