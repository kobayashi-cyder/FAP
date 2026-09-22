#!/usr/bin/env sh
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT" || exit 1

LATEST_VERSION="87.61-unified-chat"
GATEWAY="$ROOT/fap_v87_61_generic_recommendation_gateway.py"

# The Pixel/Debian path is deliberately stdlib-first.  A broken user-site,
# stale bytecode, or optional native build must not prevent local chat startup.
PY_SAFE_FLAGS="-S -B"

python_healthy() {
  candidate=$1
  "$candidate" -S -B -c 'import ast,json,marshal,pathlib,socket,urllib.request; print("ok")' >/dev/null 2>&1
}

find_python() {
  seen=""
  for candidate in python3.13 python3.12 python3.11 python3.10 python3 python /usr/bin/python3 /usr/local/bin/python3; do
    if echo " $seen " | grep -F " $candidate " >/dev/null 2>&1; then
      continue
    fi
    seen="$seen $candidate"

    if [ -x "$candidate" ]; then
      path=$candidate
    elif command -v "$candidate" >/dev/null 2>&1; then
      path=$(command -v "$candidate")
    else
      continue
    fi

    if python_healthy "$path"; then
      printf '%s\n' "$path"
      return 0
    fi
  done
  return 1
}

PY=$(find_python || true)
if [ -z "$PY" ]; then
  echo "[ERROR] No healthy Python 3 interpreter was found."
  echo "[INFO] The FAP source is intact; the local Python runtime is failing its stdlib self-check."
  echo "[INFO] Debian/Ubuntu repair: sudo apt update && sudo apt install --reinstall -y python3 python3-minimal"
  exit 1
fi

echo "[INFO] Python: $PY (safe stdlib mode)"

if [ ! -f "$GATEWAY" ]; then
  echo "[ERROR] Missing latest gateway: $GATEWAY"
  echo "[INFO] Run: git fetch --prune origin main && git reset --hard origin/main"
  exit 1
fi

clean_bytecode() {
  find "$ROOT" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
  find "$ROOT" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true
}

gateway_preflight() {
  PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 "$PY" -S -B -c     'import fap_v87_61_generic_recommendation_gateway as g; s=g.CORE.chat_status(); raise SystemExit(0 if s.get("version") == "87.61-unified-chat" else 4)'     >/dev/null 2>&1
}

# First try without touching anything.  If import fails, stale bytecode is
# removed once and the exact same generic preflight is retried.
if ! gateway_preflight; then
  echo "[INFO] Gateway preflight failed once; clearing Python bytecode cache and retrying."
  clean_bytecode
  if ! gateway_preflight; then
    echo "[ERROR] Python can run, but the FAP gateway import still fails in safe mode."
    echo "[INFO] Run: git fetch --prune origin main && git reset --hard origin/main"
    exit 1
  fi
fi

get_version() {
  "$PY" -S -B - "$1" <<'PY' 2>/dev/null
import json
import sys
import urllib.request

port = int(sys.argv[1])
for path in ("/api/v1/ready", "/api/v1/status"):
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}{path}", timeout=0.7
        ) as response:
            payload = json.load(response)
        value = str(payload.get("version", ""))
        if value:
            print(value)
            break
    except Exception:
        pass
PY
}

port_in_use() {
  "$PY" -S -B - "$1" <<'PY' >/dev/null 2>&1
import socket
import sys

port = int(sys.argv[1])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(0.25)
try:
    rc = sock.connect_ex(("127.0.0.1", port))
finally:
    sock.close()
raise SystemExit(0 if rc == 0 else 1)
PY
}

open_browser() {
  url=$1
  if command -v termux-open-url >/dev/null 2>&1; then
    termux-open-url "$url" >/dev/null 2>&1 || true
    return
  fi
  if command -v xdg-open >/dev/null 2>&1; then
    nohup xdg-open "$url" >/dev/null 2>&1 &
    return
  fi
  if command -v am >/dev/null 2>&1; then
    am start -a android.intent.action.VIEW -d "$url" >/dev/null 2>&1 || true
  fi
}

PORT=""
for candidate in 11439 11441 11443 11445; do
  existing=$(get_version "$candidate")
  if [ "$existing" = "$LATEST_VERSION" ]; then
    URL="http://127.0.0.1:$candidate/"
    echo "[OK] Latest FAP CHAT is already running: $LATEST_VERSION"
    echo "[OK] $URL"
    open_browser "$URL"
    exit 0
  fi
  if ! port_in_use "$candidate"; then
    PORT=$candidate
    break
  fi
  if [ -n "$existing" ]; then
    echo "[INFO] Port $candidate has FAP $existing; keeping it and trying another port."
  else
    echo "[INFO] Port $candidate is occupied by another process; trying another port."
  fi
done

if [ -z "$PORT" ]; then
  PORT=$("$PY" -S -B - <<'PY'
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PY
)
fi

echo "[INFO] Preparing FAP CHAT $LATEST_VERSION on port $PORT ..."

# Native acceleration is optional.  It is intentionally opt-in on the portable
# launcher so a compiler/toolchain/native-library problem cannot block chat.
# Enable explicitly with: FAP_NATIVE_BUILDS=1 ./RUN_FAP_CHAT_LATEST.sh
if [ "${FAP_NATIVE_BUILDS:-0}" = "1" ]; then
  if [ -f "$ROOT/releases/v87_38/native_raster/build_native.py" ]; then
    "$PY" -S -B "$ROOT/releases/v87_38/native_raster/build_native.py" --quiet ||
      echo "[WARN] V87.38 native raster unavailable; Python fallback will be used."
  fi
  if [ -f "$ROOT/releases/v87_39/native_geometry/build_native.py" ]; then
    "$PY" -S -B "$ROOT/releases/v87_39/native_geometry/build_native.py" --quiet ||
      echo "[WARN] V87.39 native geometry unavailable; earlier fallback will be used."
  fi
else
  echo "[INFO] Optional native builds skipped; portable Python fallback is active."
fi

mkdir -p "$ROOT/runtime"
LOG="$ROOT/runtime/fap_chat_latest.log"
PIDFILE="$ROOT/runtime/fap_chat_latest.pid"

PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONFAULTHANDLER=1 FAP_HOST=127.0.0.1 FAP_PORT="$PORT" nohup "$PY" -S -B "$GATEWAY" >"$LOG" 2>&1 &
PID=$!
printf '%s\n' "$PID" >"$PIDFILE"

i=0
while [ "$i" -lt 125 ]; do
  version=$(get_version "$PORT")
  if [ "$version" = "$LATEST_VERSION" ]; then
    URL="http://127.0.0.1:$PORT/"
    echo "[OK] FAP CHAT is ready: $version"
    echo "[OK] PID=$PID"
    echo "[OK] $URL"
    echo "[INFO] Log: $LOG"
    open_browser "$URL"
    exit 0
  fi

  if ! kill -0 "$PID" >/dev/null 2>&1; then
    echo "[ERROR] FAP CHAT stopped during startup."
    echo "[INFO] Log: $LOG"
    if command -v tail >/dev/null 2>&1; then
      tail -n 80 "$LOG" 2>/dev/null || true
    fi
    exit 1
  fi

  i=$((i + 1))
  sleep 0.2
done

echo "[ERROR] FAP CHAT did not report $LATEST_VERSION within 25 seconds."
echo "[INFO] Log: $LOG"
if command -v tail >/dev/null 2>&1; then
  tail -n 80 "$LOG" 2>/dev/null || true
fi
exit 1
