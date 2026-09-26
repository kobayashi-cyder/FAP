#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NATIVE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$NATIVE_DIR/.." && pwd)"

command -v em++ >/dev/null 2>&1 || {
  echo "em++ not found. Install/activate Emscripten first." >&2
  exit 2
}

PRELOAD=()
if [[ -d "$REPO_ROOT/knowledge" ]]; then
  PRELOAD=(--preload-file "$REPO_ROOT/knowledge@/knowledge")
fi

em++   -std=c++20 -O3   -I "$NATIVE_DIR/include"   "$NATIVE_DIR/src/native_core.cpp"   "$NATIVE_DIR/src/c_api.cpp"   --no-entry   -sMODULARIZE=1   -sEXPORT_NAME=createFapNativeModule   -sALLOW_MEMORY_GROWTH=1   -sENVIRONMENT=web   -sEXPORTED_FUNCTIONS='["_malloc","_free","_fap_native_version","_fap_native_engine_create","_fap_native_engine_destroy","_fap_native_engine_analyze_json","_fap_native_string_free"]'   -sEXPORTED_RUNTIME_METHODS='["cwrap","UTF8ToString"]'   "${PRELOAD[@]}"   -o "$SCRIPT_DIR/fap_native.js"

echo "WASM UI runtime built:"
echo "  $SCRIPT_DIR/fap_native.js"
echo "  $SCRIPT_DIR/fap_native.wasm"
