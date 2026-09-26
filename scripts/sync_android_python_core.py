#!/usr/bin/env python3
from pathlib import Path
import shutil
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "android" / "app" / "src" / "main" / "python"
FILES = ("fap_runtime_1x.py","fap_interaction_fabric.py",
         "fap_dynamic_sparse_routing.py","fap_exponential_linear.py")
DEST.mkdir(parents=True, exist_ok=True)
for name in FILES:
    src = ROOT / name
    if not src.is_file():
        raise SystemExit(f"missing Android core dependency: {name}")
    shutil.copy2(src, DEST / name)
print(f"synced {len(FILES)} FAP 1.x modules")
