#!/usr/bin/env python3
from __future__ import annotations
import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from fap_runtime_1x import CORE

VERSION = "1.0.01-unified-chat"
HOST = os.environ.get("FAP_HOST", "127.0.0.1")
PORT = int(os.environ.get("FAP_PORT", "8781"))

class Handler(BaseHTTPRequestHandler):
    server_version = "FAP1x"
    def _send(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self) -> None:
        if self.path == "/api/v1/ready":
            self._send(200, {"version": VERSION, "mainline_version": "1.0.01", "state": "ready"})
        elif self.path == "/api/v1/status":
            self._send(200, CORE.chat_status())
        else:
            self._send(404, {"error": "not_found"})
    def do_POST(self) -> None:
        if self.path != "/api/v1/chat":
            self._send(404, {"error": "not_found"}); return
        try: length = int(self.headers.get("Content-Length", "0"))
        except ValueError: length = 0
        if length < 0 or length > 131072:
            self._send(413, {"error": "payload_too_large"}); return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            text = str(body.get("text", ""))
        except Exception:
            self._send(400, {"error": "invalid_json"}); return
        self._send(200, CORE.chat_result(text))
    def log_message(self, fmt: str, *args) -> None:
        return

def main() -> int:
    print(f"FAP {VERSION} listening on http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
