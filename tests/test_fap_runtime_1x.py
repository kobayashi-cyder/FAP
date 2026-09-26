from pathlib import Path
import re, unittest
import fap_runtime_1x
import fap_v1_0_01_dynamic_sparse_routing_gateway as gateway
ROOT = Path(__file__).resolve().parents[1]

class IntegratedRuntime1xTests(unittest.TestCase):
    def test_status(self):
        status=fap_runtime_1x.CORE.chat_status()
        self.assertEqual(status["mainline_version"],"1.0.01")
        self.assertFalse(status["legacy_version_dependencies"])
        self.assertTrue(status["dynamic_sparse_routing"]["interaction_fabric_integrated"])
    def test_arithmetic(self):
        result=fap_runtime_1x.CORE.chat_result("2 + 3 * 4")
        self.assertEqual(result["endpoint_id"],"arithmetic")
        self.assertEqual(result["payload"]["reply"],"14")
    def test_unknown_fails_closed(self):
        result=fap_runtime_1x.CORE.chat_result("未知の未接続知識について断定して")
        self.assertEqual(result["endpoint_id"],"fail_closed")
        self.assertFalse(result["payload"]["ok"])
        self.assertTrue(result["payload"]["needs_tool"])
    def test_no_legacy_import(self):
        for path in (ROOT/"fap_runtime_1x.py",ROOT/"fap_v1_0_01_dynamic_sparse_routing_gateway.py"):
            self.assertIsNone(re.search(r"fap_v[4-9]\\d",path.read_text(encoding="utf-8"),re.I))
        self.assertEqual(gateway.VERSION,"1.0.01-unified-chat")
    def test_string_handler_contract(self):
        self.assertEqual(fap_runtime_1x.chat("6/2"),"3")
if __name__=="__main__": unittest.main()
