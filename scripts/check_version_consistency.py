#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^(?P<base>\d+\.\d+\.\d+)(?:-(?P<revision>r\d+))?$")


def fail(message: str) -> None:
    raise SystemExit(f"[version-check] {message}")


def parse_version(value: str) -> tuple[str, str | None]:
    match = VERSION_RE.fullmatch(value.strip())
    if not match:
        fail(f"invalid VERSION value: {value!r}")
    return match.group("base"), match.group("revision")


def validate(root: Path = ROOT) -> tuple[str, str, str | None]:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    base, revision = parse_version(version)
    readme = (root / "README.md").read_text(encoding="utf-8")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")

    if revision:
        if f"Current revision: **{version}**" not in readme:
            fail("README.md does not declare the canonical current revision")
        if f"Stable public base: **{base}**" not in readme:
            fail("README.md does not declare the stable public base")
        revision_module = root / f"fap_revision_{revision}.py"
        if not revision_module.is_file():
            fail(f"missing public revision module: {revision_module.name}")
        if f"## {base}" not in changelog:
            fail(f"CHANGELOG.md has no release entry for public base {base}")
        return version, base, revision

    if f"Stable mainline: **V{version}**" not in readme:
        fail("README.md does not declare the canonical 1.x mainline candidate")
    if f"## {version}" not in changelog:
        fail(f"CHANGELOG.md has no release entry for {version}")

    runtime_version = f"{version}-unified-chat"
    latest = (root / "FAP_LATEST.md").read_text(encoding="utf-8")
    if not latest.startswith(f"# FAP V{version} "):
        fail("FAP_LATEST.md does not start with the canonical VERSION")

    ps1 = (root / "RUN_FAP_CHAT_LATEST.ps1").read_text(encoding="utf-8")
    if f"$LatestVersion = '{runtime_version}'" not in ps1:
        fail("PowerShell latest launcher version is out of sync")

    sh = (root / "RUN_FAP_CHAT_LATEST.sh").read_text(encoding="utf-8")
    if f'LATEST_VERSION="{runtime_version}"' not in sh:
        fail("POSIX latest launcher version is out of sync")

    prefix = f"fap_v{version.replace('.', '_')}_"
    gateways = sorted(root.glob(prefix + "*_gateway.py"))
    if len(gateways) != 1:
        fail(f"expected exactly one current gateway matching {prefix}*_gateway.py, found {len(gateways)}")

    gateway_text = gateways[0].read_text(encoding="utf-8")
    if f'VERSION = "{runtime_version}"' not in gateway_text:
        fail(f"{gateways[0].name} runtime VERSION is out of sync")
    if f'"mainline_version": "{version}"' not in gateway_text:
        fail(f"{gateways[0].name} mainline_version is out of sync")

    return version, base, revision


def main() -> int:
    version, base, revision = validate(ROOT)
    suffix = f" revision={revision}" if revision else ""
    print(f"[version-check] PASS public FAP version={version} base={base}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
