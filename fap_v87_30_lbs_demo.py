#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "releases" / "v87_30" / "human_lbs"))

from fap_human_lbs import (
    build_human_mesh,
    default_human_skeleton,
    pose_from_prompt,
    render_human_png,
)


def main():
    out = ROOT / "runtime" / "v87_30_lbs_demo"
    out.mkdir(parents=True, exist_ok=True)
    skeleton = default_human_skeleton()
    mesh = build_human_mesh(skeleton)
    pose = pose_from_prompt("右腕を上げて手を振る")
    views = {
        "front": 0.0,
        "oblique": 35.0,
        "side": 88.0,
    }
    for name, yaw in views.items():
        data = render_human_png(
            mesh,
            skeleton,
            pose,
            width=512,
            height=640,
            yaw_deg=yaw,
            pitch_deg=-4.0,
        )
        path = out / f"human_lbs_{name}.png"
        path.write_bytes(data)
        print(path)
    print("HUMAN LBS DEMO PASS")


if __name__ == "__main__":
    main()
