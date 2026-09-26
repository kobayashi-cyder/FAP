#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "native" / "fap_native_geometry.c"
BIN = ROOT / "bin"

def target_path():
    s=platform.system().lower()
    if s=="windows": return BIN/"fap_native_geometry.dll"
    if s=="darwin": return BIN/"libfap_native_geometry.dylib"
    return BIN/"libfap_native_geometry.so"

def run(cmd,cwd=None,quiet=False):
    if not quiet: print("[build]"," ".join(map(str,cmd)))
    subprocess.run(cmd,cwd=cwd,check=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--force",action="store_true")
    ap.add_argument("--quiet",action="store_true")
    a=ap.parse_args()
    BIN.mkdir(parents=True,exist_ok=True)
    target=target_path()
    if target.exists() and not a.force:
        if not a.quiet: print("[ok]",target)
        return 0

    s=platform.system().lower()
    try:
        if s=="windows":
            cc=shutil.which("gcc") or shutil.which("clang")
            if cc:
                run([cc,"-O3","-std=c99","-shared","-s",str(SRC),"-o",str(target)],BIN,a.quiet)
            else:
                cl=shutil.which("cl")
                if not cl: raise RuntimeError("No GCC/Clang/MSVC compiler found")
                run([cl,"/nologo","/O2","/LD","/TC",str(SRC),f"/Fe:{target}"],BIN,a.quiet)
        else:
            cc=shutil.which(os.environ.get("CC","")) if os.environ.get("CC") else None
            cc=cc or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
            if not cc: raise RuntimeError("No C compiler found")
            if s=="darwin":
                cmd=[cc,"-O3","-std=c99","-dynamiclib",str(SRC),"-o",str(target),"-lm"]
            else:
                cmd=[cc,"-O3","-std=c99","-shared","-fPIC",str(SRC),"-o",str(target),"-lm"]
            run(cmd,BIN,a.quiet)
    except Exception as exc:
        if not a.quiet: print("[warn]",exc)
        return 2
    if not target.exists(): return 3
    if not a.quiet: print("[ok] library=",target)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
