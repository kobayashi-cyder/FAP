from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fap_fmg_video_module import FMGImportedVideoModule
from fap_1x_standard_runtime import FAP1xStandardRuntime


class _FakeImage:
    def __init__(self, root: Path):
        self.root = root
        self.count = 0

    def generate(self, text: str):
        self.count += 1
        path = self.root / f"frame_{self.count}.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 256)
        return {
            "ok": True,
            "generator": "fake",
            "artifacts": [{"type": "image", "name": path.name, "path": str(path)}],
        }


class FMGVideoTests(unittest.TestCase):
    def test_video_module_builds_storyboard_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module = FMGImportedVideoModule(root, _FakeImage(root))
            result = module.generate("浮遊都市の動画を10秒で作って")
            self.assertTrue(result["ok"])
            self.assertEqual(result["video_profile"]["duration_seconds"], 10)
            artifact = result["artifacts"][0]
            self.assertEqual(artifact["type"], "video_storyboard")
            self.assertGreaterEqual(len(artifact["frames"]), 2)

    def test_runtime_routes_video_request(self):
        runtime = FAP1xStandardRuntime(root=Path(__file__).resolve().parents[1])
        runtime.fmg_video.generate = lambda text: {
            "ok": True,
            "reply": "video test",
            "confidence": 1.0,
            "artifacts": [{
                "type": "video_storyboard",
                "frames": ["/tmp/a.png"],
                "duration_seconds": 5,
                "fps": 12,
                "width": 512,
                "height": 512,
            }],
        }
        result = runtime.run_turn("動画を生成して", session_id="video-test")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "fmg_video_generation")
        self.assertEqual(result.payload["reply"], "video test")


if __name__ == "__main__":
    unittest.main()
