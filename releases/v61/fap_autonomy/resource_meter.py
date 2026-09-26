from __future__ import annotations

import os
import time
import tracemalloc
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator


@contextmanager
def measure_resources() -> Iterator[Dict[str, float]]:
    metrics: Dict[str, float] = {}
    tracemalloc.start()
    t0 = time.perf_counter()
    try:
        yield metrics
    finally:
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        metrics["elapsed_ms"] = (time.perf_counter() - t0) * 1000.0
        metrics["python_peak_mb"] = peak / (1024 * 1024)


def tree_size_kb(path: str) -> float:
    root = Path(path)
    total = 0
    for p in root.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total / 1024.0
