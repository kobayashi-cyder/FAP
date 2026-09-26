from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def load_skill(candidate_dir: str):
    path = Path(candidate_dir) / "skill.py"
    spec = importlib.util.spec_from_file_location("candidate_skill", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def main():
    dataset = Path(sys.argv[1])
    candidate_dir = sys.argv[2]
    mod = load_skill(candidate_dir)
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    passed = sum(1 for r in rows if mod.solve(r["task"]) == r["expected"])
    cases = len(rows)
    score = passed / cases if cases else 0.0
    print(json.dumps({"cases": cases, "passed": passed, "score": score}, sort_keys=True))


if __name__ == "__main__":
    main()
