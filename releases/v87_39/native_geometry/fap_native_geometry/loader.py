from __future__ import annotations

import ctypes
import os
from pathlib import Path
import platform

ROOT=Path(__file__).resolve().parents[1]
BIN=ROOT/"bin"
_LIB=None
_ERROR=None

def candidates():
    out=[]
    if os.environ.get("FAP_NATIVE_GEOMETRY_LIB"):
        out.append(Path(os.environ["FAP_NATIVE_GEOMETRY_LIB"]))
    s=platform.system().lower()
    if s=="windows": out.append(BIN/"fap_native_geometry.dll")
    elif s=="darwin": out.append(BIN/"libfap_native_geometry.dylib")
    else: out.append(BIN/"libfap_native_geometry.so")
    return out

def _configure(lib):
    dp=ctypes.POINTER(ctypes.c_double)
    i32p=ctypes.POINTER(ctypes.c_int32)
    u8p=ctypes.POINTER(ctypes.c_uint8)
    lib.fap_prepare_geometry.argtypes=[
        dp,ctypes.c_int,i32p,u8p,ctypes.c_int,
        ctypes.c_int,ctypes.c_int,ctypes.c_double,ctypes.c_double,ctypes.c_int,
        dp,dp,dp,i32p,ctypes.c_int,
    ]
    lib.fap_prepare_geometry.restype=ctypes.c_int
    lib.fap_apply_cat_pattern.argtypes=[
        dp,ctypes.c_int,i32p,u8p,ctypes.c_int,
        ctypes.c_int,ctypes.c_int,u8p,
    ]
    lib.fap_apply_cat_pattern.restype=ctypes.c_int
    lib.fap_lbs_sparse.argtypes=[
        dp,ctypes.c_int,i32p,dp,dp,ctypes.c_int,u8p,dp,dp,
    ]
    lib.fap_lbs_sparse.restype=ctypes.c_int
    lib.fap_native_geometry_version.argtypes=[]
    lib.fap_native_geometry_version.restype=ctypes.c_char_p
    return lib

def load_native_geometry(required=False):
    global _LIB,_ERROR
    if _LIB is not None: return _LIB
    errs=[]
    for p in candidates():
        if not p.is_file(): continue
        try:
            _LIB=_configure(ctypes.CDLL(str(p)))
            _ERROR=None
            return _LIB
        except Exception as exc:
            errs.append(f"{p}: {exc}")
    _ERROR="; ".join(errs) if errs else "native geometry library not found"
    if required: raise RuntimeError(_ERROR)
    return None

def native_geometry_status():
    lib=load_native_geometry(False)
    version=None
    if lib:
        raw=lib.fap_native_geometry_version()
        version=raw.decode("ascii","replace") if raw else None
    return {
        "available":lib is not None,
        "version":version,
        "error":_ERROR,
        "candidates":[str(x) for x in candidates()],
    }

def doubles(values):
    vals=[float(x) for x in values]
    return (ctypes.c_double*len(vals))(*vals)

def i32(values):
    vals=[int(x) for x in values]
    return (ctypes.c_int32*len(vals))(*vals)

def u8(values):
    vals=[int(x)&255 for x in values]
    return (ctypes.c_uint8*len(vals))(*vals)
