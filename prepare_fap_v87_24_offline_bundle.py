#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "releases" / "v87_24" / "offline_bundle"))

from fap_offline_bundle import prepare_bundle, verify_bundle


def main():
    parser = argparse.ArgumentParser(
        description="Prepare or verify the pinned FAP V87.24 SSD-1B offline bundle."
    )
    parser.add_argument(
        "--destination",
        default=str(ROOT / "models" / "fap" / "ssd1b"),
    )
    parser.add_argument("--accept-license", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    result = (
        verify_bundle(args.destination)
        if args.verify_only
        else prepare_bundle(args.destination, accept_license=args.accept_license)
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
