from __future__ import annotations


def solve(task: str) -> str:
    """Tiny deterministic demo capability used only to validate the V62 pipeline."""
    parts = task.strip().split()
    if len(parts) == 3 and parts[0] == "percent":
        pct = float(parts[1])
        value = float(parts[2])
        out = pct * value / 100.0
        return str(int(out)) if out.is_integer() else str(out)
    if len(parts) == 3 and parts[0] == "ratio":
        a = float(parts[1])
        b = float(parts[2])
        if b == 0:
            return "ERROR"
        out = a / b
        return str(int(out)) if out.is_integer() else str(round(out, 8))
    return "UNKNOWN"
