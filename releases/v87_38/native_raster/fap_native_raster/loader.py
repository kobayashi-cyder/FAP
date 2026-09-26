from __future__ import annotations

import ctypes
import os
from pathlib import Path
import platform
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin"
_LIB = None
_LOAD_ERROR = None


def _candidate_paths() -> list[Path]:
    env = os.environ.get("FAP_NATIVE_RASTER_LIB")
    out: list[Path] = []
    if env:
        out.append(Path(env))
    system = platform.system().lower()
    if system == "windows":
        out.append(BIN / "fap_native_raster.dll")
    elif system == "darwin":
        out.append(BIN / "libfap_native_raster.dylib")
    else:
        out.append(BIN / "libfap_native_raster.so")
    return out


def _configure(lib):
    u8p = ctypes.POINTER(ctypes.c_uint8)
    fp = ctypes.POINTER(ctypes.c_float)
    dp = ctypes.POINTER(ctypes.c_double)
    i32p = ctypes.POINTER(ctypes.c_int32)

    lib.fap_raster_subject.argtypes = [
        u8p, fp, ctypes.c_int, ctypes.c_int,
        dp, dp, i32p, u8p, ctypes.c_int,
    ]
    lib.fap_raster_subject.restype = ctypes.c_uint64

    lib.fap_fxaa_tiles.argtypes = [
        u8p, ctypes.c_int, ctypes.c_int,
        i32p, ctypes.c_int, ctypes.c_int,
    ]
    lib.fap_fxaa_tiles.restype = ctypes.c_uint64

    lib.fap_filmic_subject.argtypes = [
        u8p, fp, ctypes.c_int, ctypes.c_int,
        i32p, ctypes.c_int, ctypes.c_int,
    ]
    lib.fap_filmic_subject.restype = ctypes.c_uint64

    lib.fap_native_raster_version.argtypes = []
    lib.fap_native_raster_version.restype = ctypes.c_char_p
    return lib


def load_native_core(required: bool = False):
    global _LIB, _LOAD_ERROR
    if _LIB is not None:
        return _LIB

    errors = []
    for path in _candidate_paths():
        if not path.is_file():
            continue
        try:
            _LIB = _configure(ctypes.CDLL(str(path)))
            _LOAD_ERROR = None
            return _LIB
        except Exception as exc:
            errors.append(f"{path}: {exc}")

    _LOAD_ERROR = "; ".join(errors) if errors else "native library not found"
    if required:
        raise RuntimeError(_LOAD_ERROR)
    return None


def native_available() -> bool:
    return load_native_core(False) is not None


def native_status() -> dict:
    lib = load_native_core(False)
    version = None
    if lib is not None:
        raw = lib.fap_native_raster_version()
        version = raw.decode("ascii", "replace") if raw else None
    return {
        "available": lib is not None,
        "version": version,
        "error": _LOAD_ERROR,
        "candidates": [str(x) for x in _candidate_paths()],
    }


def flatten_doubles(rows: Iterable[Iterable[float]]):
    values = [float(v) for row in rows for v in row]
    return (ctypes.c_double * len(values))(*values)


def flatten_i32(rows: Iterable[Iterable[int]]):
    values = [int(v) for row in rows for v in row]
    return (ctypes.c_int32 * len(values))(*values)


def flatten_u8(rows: Iterable[Iterable[int]]):
    values = [int(v) & 0xFF for row in rows for v in row]
    return (ctypes.c_uint8 * len(values))(*values)
