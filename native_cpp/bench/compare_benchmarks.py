from __future__ import annotations

import json
import sys
from pathlib import Path

METRICS = [
    ("budget", "Adaptive budget"),
    ("routing", "Semantic routing"),
    ("memory", "Semantic memory recall"),
    ("intent", "Multi-intent detect"),
]

def load(path: str) -> dict:
    rows = Path(path).read_text(encoding="utf-8").strip().splitlines()
    if not rows:
        raise SystemExit(f"empty result: {path}")
    return json.loads(rows[-1])

def fmt_ns(v: float) -> str:
    if v < 1_000:
        return f"{v:.1f} ns"
    if v < 1_000_000:
        return f"{v / 1_000:.2f} µs"
    return f"{v / 1_000_000:.2f} ms"

def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: compare_benchmarks.py CPP.json PYTHON.json OUTPUT.md")
    cpp = load(sys.argv[1])
    py = load(sys.argv[2])

    rows = [
        "# FAP C++ vs Python microbenchmark",
        "",
        f"- iterations per operation: **{cpp['iterations']:,}**",
        "- same GitHub Actions runner; sequential execution",
        "- lower latency is better",
        "- microbenchmark only: this does not measure language-model intelligence or end-to-end chat latency",
        "",
        "| Operation | C++ | Python | C++ speedup |",
        "|---|---:|---:|---:|",
    ]

    speedups = {}
    for key, label in METRICS:
        c = float(cpp[f"{key}_ns_per_op"])
        p = float(py[f"{key}_ns_per_op"])
        ratio = p / c if c else float("inf")
        speedups[key] = ratio
        rows.append(f"| {label} | {fmt_ns(c)} | {fmt_ns(p)} | **{ratio:.2f}×** |")

    rows.extend([
        "",
        "## Machine-readable summary",
        "",
        json.dumps(
            {"iterations": cpp["iterations"], "cpp": cpp, "python": py, "cpp_speedup": speedups},
            ensure_ascii=False,
            indent=2,
        ),
        "",
    ])
    Path(sys.argv[3]).write_text("\n".join(rows), encoding="utf-8")
    print("\n".join(rows))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
