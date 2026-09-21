#!/usr/bin/env sh
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT" || exit 1

LATEST_VERSION="87.41-unified-chat"
GATEWAY="$ROOT/fap_v87_41_low_latency_chat_gateway.py"

find_python() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi
  return 1
}

PY=$(find_python || true)
if [ -z "$PY" ]; then
  echo "[ERROR] Python 3 was not found."
  echo "[INFO] Debian/Ubuntu: sudo apt update && sudo apt install -y python3 build-essential"
  exit 1
fi

if [ ! -f "$GATEWAY" ]; then
  echo "[ERROR] Missing latest gateway: $GATEWAY"
  echo "[INFO] Run: git pull --ff-only"
  exit 1
fi

get_version() {
  "$PY" - "$1" <<'PY' 2>/dev/null
import json
import sys
import urllib.request

port = int(sys.argv[1])
try:
    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}/api/v1/status", timeout=0.7
    ) as response:
        payload = json.load(response)
    print(str(payload.get("version", "")))
except Exception:
    pass
PY
}

port_in_use() {
  "$PY" - "$1" <<'PY' >/dev/null 2>&1
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
  PORT=$("$PY" - <<'PY'
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PY
)
fi

echo "[INFO] Preparing FAP CHAT $LATEST_VERSION on port $PORT ..."

if [ -f "$ROOT/releases/v87_38/native_raster/build_native.py" ]; then
  "$PY" "$ROOT/releases/v87_38/native_raster/build_native.py" --quiet ||
    echo "[WARN] V87.38 native raster build unavailable; Python fallback will be used."
fi

if [ -f "$ROOT/releases/v87_39/native_geometry/build_native.py" ]; then
  "$PY" "$ROOT/releases/v87_39/native_geometry/build_native.py" --quiet ||
    echo "[WARN] V87.39 native geometry build unavailable; earlier fallback will be used."
fi

mkdir -p "$ROOT/runtime"
LOG="$ROOT/runtime/fap_chat_latest.log"
PIDFILE="$ROOT/runtime/fap_chat_latest.pid"

FAP_HOST=127.0.0.1 FAP_PORT="$PORT" nohup "$PY" "$GATEWAY" >"$LOG" 2>&1 &
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
      tail -n 40 "$LOG" 2>/dev/null || true
    fi
    exit 1
  fi

  i=$((i + 1))
  sleep 0.2
done

echo "[ERROR] FAP CHAT did not report $LATEST_VERSION within 25 seconds."
echo "[INFO] Log: $LOG"
if command -v tail >/dev/null 2>&1; then
  tail -n 40 "$LOG" 2>/dev/null || true
fi
exit 1
