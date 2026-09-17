import json
import os
import tempfile
import unittest
from pathlib import Path

from fap_autonomy.skill_factory_adapter import SkillFactoryOutputAdapter


def setup_workspace(d):
    root = Path(d)
    croot = root / "candidates"; eroot = root / "eval"
    cand = croot / "cap1"; cand.mkdir(parents=True)
    eroot.mkdir()
    (cand / "skill.py").write_text("def solve(x): return x\n", encoding="utf-8")
    (eroot / "evaluator.py").write_text("print('{\"score\":1.0,\"cases\":1,\"passed\":1}')\n", encoding="utf-8")
    (eroot / "dev.jsonl").write_text("{}\n", encoding="utf-8")
    for i in range(5):
        (eroot / f"h{i}.jsonl").write_text(f"{{\"i\":{i}}}\n", encoding="utf-8")
    return croot, eroot


def manifest(croot, eroot, path, **updates):
    obj = {
        "schema": 1,
        "request_id": "req-1",
        "capability_id": "MATH_GAP:test",
        "candidate_relpath": "cap1",
        "evaluator_relpath": ".",
        "unit_command": ["{python}", "-m", "unittest", "discover"],
        "dev_command": ["{python}", "evaluator.py", "dev.jsonl"],
        "trials": [
            {"trial_id": f"t{i}", "holdout_paths": [f"h{i}.jsonl"],
             "holdout_command": ["{python}", "evaluator.py", f"h{i}.jsonl"]}
            for i in range(5)
        ],
    }
    obj.update(updates)
    Path(path).write_text(json.dumps(obj), encoding="utf-8")
    return obj


class SkillFactoryAdapterTests(unittest.TestCase):
    def test_valid_manifest_normalized(self):
        with tempfile.TemporaryDirectory() as d:
            croot, eroot = setup_workspace(d)
            p = Path(d) / "m.json"
            manifest(croot, eroot, p)
            a = SkillFactoryOutputAdapter(candidate_root=str(croot), evaluator_root=str(eroot))
            out = a.load(str(p))
            self.assertEqual(len(out["trials"]), 5)
            self.assertTrue(Path(out["candidate_dir"]).is_dir())
            self.assertTrue(out["unit_command"][0].endswith(("python", "python3")) or "python" in out["unit_command"][0].lower())

    def test_rejects_shell_command(self):
        with tempfile.TemporaryDirectory() as d:
            croot, eroot = setup_workspace(d)
            p = Path(d) / "m.json"
            manifest(croot, eroot, p, unit_command=["bash", "test.sh"])
            a = SkillFactoryOutputAdapter(candidate_root=str(croot), evaluator_root=str(eroot))
            with self.assertRaises(ValueError):
                a.load(str(p))

    def test_rejects_candidate_escape(self):
        with tempfile.TemporaryDirectory() as d:
            croot, eroot = setup_workspace(d)
            outside = Path(d) / "outside"; outside.mkdir()
            p = Path(d) / "m.json"
            manifest(croot, eroot, p, candidate_relpath="../outside")
            a = SkillFactoryOutputAdapter(candidate_root=str(croot), evaluator_root=str(eroot))
            with self.assertRaises(ValueError):
                a.load(str(p))

    def test_rejects_duplicate_trial_id(self):
        with tempfile.TemporaryDirectory() as d:
            croot, eroot = setup_workspace(d)
            p = Path(d) / "m.json"
            obj = manifest(croot, eroot, p)
            obj["trials"][1]["trial_id"] = obj["trials"][0]["trial_id"]
            p.write_text(json.dumps(obj), encoding="utf-8")
            a = SkillFactoryOutputAdapter(candidate_root=str(croot), evaluator_root=str(eroot))
            with self.assertRaises(ValueError):
                a.load(str(p))

    def test_rejects_python_dash_c(self):
        with tempfile.TemporaryDirectory() as d:
            croot, eroot = setup_workspace(d)
            p = Path(d) / "m.json"
            manifest(croot, eroot, p, unit_command=["{python}", "-c", "print(1)"])
            a = SkillFactoryOutputAdapter(candidate_root=str(croot), evaluator_root=str(eroot))
            with self.assertRaises(ValueError):
                a.load(str(p))


if __name__ == "__main__":
    unittest.main()
