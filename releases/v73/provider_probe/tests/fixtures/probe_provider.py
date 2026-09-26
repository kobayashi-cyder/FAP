from __future__ import annotations

import json
import sys
import time


mode = sys.argv[1] if len(sys.argv) > 1 else "healthy"
if mode == "timeout":
    time.sleep(2.0)
if mode == "exit":
    raise SystemExit(9)

request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
if request != {"op": "probe", "protocol_version": 1}:
    sys.stdout.write(json.dumps({"error": "unexpected request"}))
    raise SystemExit(0)

if mode == "wrong-version":
    response = {
        "protocol_version": 2,
        "provider_id": "fixture",
        "capabilities": ["image", "stt", "tts"],
        "ready": True,
    }
elif mode == "not-ready":
    response = {
        "protocol_version": 1,
        "provider_id": "fixture",
        "capabilities": ["image"],
        "ready": False,
    }
elif mode == "duplicate":
    response = {
        "protocol_version": 1,
        "provider_id": "fixture",
        "capabilities": ["stt", "stt"],
        "ready": True,
    }
elif mode == "unknown":
    response = {
        "protocol_version": 1,
        "provider_id": "fixture",
        "capabilities": ["image", "video"],
        "ready": True,
    }
elif mode == "subset":
    response = {
        "protocol_version": 1,
        "provider_id": "fixture-subset",
        "capabilities": ["tts", "stt"],
        "ready": True,
    }
else:
    response = {
        "protocol_version": 1,
        "provider_id": "fixture-all",
        "capabilities": ["tts", "image", "stt"],
        "ready": True,
    }

sys.stdout.write(json.dumps(response))
