#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"[version-check] {message}")


version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
if not re.fullmatch(r"\d+\.\d+", version):
    fail(f"invalid VERSION value: {version!r}")

runtime_version = f"{version}-unified-chat"

latest = (ROOT / "FAP_LATEST.md").read_text(encoding="utf-8")
if not latest.startswith(f"# FAP V{version} "):
    fail("FAP_LATEST.md does not start with the canonical VERSION")

ps1 = (ROOT / "RUN_FAP_CHAT_LATEST.ps1").read_text(encoding="utf-8")
if f"$LatestVersion = '{runtime_version}'" not in ps1:
    fail("PowerShell latest launcher version is out of sync")

sh = (ROOT / "RUN_FAP_CHAT_LATEST.sh").read_text(encoding="utf-8")
if f'LATEST_VERSION="{runtime_version}"' not in sh:
    fail("POSIX latest launcher version is out of sync")

prefix = f"fap_v{version.replace('.', '_')}_"
gateways = sorted(ROOT.glob(prefix + "*_gateway.py"))
if len(gateways) != 1:
    fail(f"expected exactly one current gateway matching {prefix}*_gateway.py, found {len(gateways)}")

gateway_text = gateways[0].read_text(encoding="utf-8")
if f'VERSION = "{runtime_version}"' not in gateway_text:
    fail(f"{gateways[0].name} runtime VERSION is out of sync")
if f'"mainline_version": "{version}"' not in gateway_text:
    fail(f"{gateways[0].name} mainline_version is out of sync")

print(f"[version-check] PASS FAP V{version} ({runtime_version})")
