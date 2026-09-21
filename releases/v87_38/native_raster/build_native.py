#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "native" / "fap_native_raster.c"
BIN = ROOT / "bin"


def target_path() -> Path:
    system = platform.system().lower()
    if system == "windows":
        return BIN / "fap_native_raster.dll"
    if system == "darwin":
        return BIN / "libfap_native_raster.dylib"
    return BIN / "libfap_native_raster.so"


def run(cmd, *, cwd=None, shell=False, quiet=False):
    if not quiet:
        print("[build]", cmd if isinstance(cmd, str) else " ".join(map(str, cmd)))
    return subprocess.run(cmd, cwd=cwd, shell=shell, check=True)


def build_windows(target: Path, quiet: bool):
    cl = shutil.which("cl")
    if cl:
        run(
            [
                cl,
                "/nologo",
                "/O2",
                "/LD",
                "/TC",
                str(SRC),
                f"/Fe:{target}",
            ],
            cwd=BIN,
            quiet=quiet,
        )
        return "msvc"

    for cc_name in ("gcc", "clang"):
        cc = shutil.which(cc_name)
        if cc:
            run(
                [
                    cc,
                    "-O3",
                    "-std=c99",
                    "-shared",
                    "-s",
                    str(SRC),
                    "-o",
                    str(target),
                ],
                cwd=BIN,
                quiet=quiet,
            )
            return cc_name

    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    vswhere = Path(pf86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if vswhere.exists():
        proc = subprocess.run(
            [
                str(vswhere),
                "-latest",
                "-products",
                "*",
                "-requires",
                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                "-property",
                "installationPath",
            ],
            check=True,
            text=True,
            capture_output=True,
        )
        install = proc.stdout.strip()
        if install:
            vcvars = Path(install) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
            if vcvars.exists():
                cmd = (
                    f'call "{vcvars}" >nul && '
                    f'cl /nologo /O2 /LD /TC "{SRC}" /Fe:"{target}"'
                )
                run(
                    ["cmd.exe", "/d", "/s", "/c", cmd],
                    cwd=BIN,
                    quiet=quiet,
                )
                return "msvc-vswhere"

    raise RuntimeError(
        "No supported C compiler found. Install MSVC Build Tools, GCC, or Clang. "
        "FAP can still run with the V87.37 Python fallback."
    )


def build_unix(target: Path, quiet: bool):
    cc = shutil.which(os.environ.get("CC", "")) if os.environ.get("CC") else None
    if not cc:
        cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        raise RuntimeError("No C compiler found (cc/gcc/clang).")

    system = platform.system().lower()
    if system == "darwin":
        cmd = [
            cc,
            "-O3",
            "-std=c99",
            "-dynamiclib",
            str(SRC),
            "-o",
            str(target),
            "-lm",
        ]
    else:
        cmd = [
            cc,
            "-O3",
            "-std=c99",
            "-shared",
            "-fPIC",
            str(SRC),
            "-o",
            str(target),
            "-lm",
        ]
    run(cmd, cwd=BIN, quiet=quiet)
    return Path(cc).name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    BIN.mkdir(parents=True, exist_ok=True)
    target = target_path()

    if target.exists() and not args.force:
        if not args.quiet:
            print(f"[ok] native raster already built: {target}")
        return 0

    try:
        if platform.system().lower() == "windows":
            compiler = build_windows(target, args.quiet)
        else:
            compiler = build_unix(target, args.quiet)
    except Exception as exc:
        if not args.quiet:
            print(f"[warn] native build unavailable: {exc}")
        return 2

    if not target.exists():
        if not args.quiet:
            print("[error] compiler completed but library was not created")
        return 3

    if not args.quiet:
        print(f"[ok] compiler={compiler}")
        print(f"[ok] library={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
