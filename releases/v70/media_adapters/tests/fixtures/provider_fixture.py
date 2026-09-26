from __future__ import annotations

import base64
import json
import os
import sys
import time


mode = sys.argv[1] if len(sys.argv) > 1 else "ok"

if mode == "sleep":
    time.sleep(2.0)
if mode == "error":
    raise SystemExit(7)
if mode == "badjson":
    sys.stdout.write("not-json")
    raise SystemExit(0)
if mode == "oversize":
    sys.stdout.write(json.dumps({"padding": "x" * 8192}))
    raise SystemExit(0)

request = json.loads(sys.stdin.buffer.read().decode("utf-8"))

if mode == "env":
    sys.stdout.write(json.dumps({"secret_seen": "FAP_TEST_SECRET" in os.environ}))
    raise SystemExit(0)

op = request.get("op")
if mode == "badartifact":
    sys.stdout.write(json.dumps({"kind": op, "mime_type": "image/png"}))
elif op == "image":
    sys.stdout.write(json.dumps({
        "kind": "image",
        "mime_type": "image/png",
        "data_base64": base64.b64encode(b"PNGDATA").decode("ascii"),
        "metadata": {"fixture": True},
    }))
elif op == "stt":
    sys.stdout.write(json.dumps({"text": "こんにちは"}))
elif op == "tts":
    sys.stdout.write(json.dumps({
        "kind": "audio",
        "mime_type": "audio/wav",
        "data_base64": base64.b64encode(b"WAVDATA").decode("ascii"),
        "metadata": {"fixture": True},
    }))
else:
    sys.stdout.write(json.dumps({"error": "unknown operation"}))
