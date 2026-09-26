from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .runtime import MediaLabRuntime


class MediaLabServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler_cls, *, runtime, web_file):
        super().__init__(server_address, handler_cls)
        self.runtime = runtime
        self.web_file = Path(web_file)


class Handler(BaseHTTPRequestHandler):
    server_version = "FAPMediaLab/87.20"

    def log_message(self, fmt, *args):
        print("[FAP MEDIA LAB] " + (fmt % args))

    def _json(self, value: Any, code: int = 200):
        raw = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def _bytes(self, raw: bytes, content_type: str, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in {"/", "/index.html", "/FAP_Media_Lab.html"}:
            try:
                raw = self.server.web_file.read_bytes()
            except FileNotFoundError:
                self._json({"error": "FAP_Media_Lab.html not found"}, 404)
                return
            self._bytes(raw, "text/html; charset=utf-8")
            return
        if path == "/api/v1/status":
            self._json(self.server.runtime.status())
            return
        if path.startswith("/artifacts/"):
            filename = path[len("/artifacts/") :]
            try:
                file = self.server.runtime.artifact_path(filename)
                raw = file.read_bytes()
            except (FileNotFoundError, OSError):
                self._json({"error": "artifact not found"}, 404)
                return
            content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            self._bytes(raw, content_type)
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/v1/generate":
            self._json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length < 1 or length > 1_000_000:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            self._json(self.server.runtime.generate(payload))
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, 400)
        except RuntimeError as exc:
            self._json({"error": str(exc)}, 503)
        except Exception as exc:
            self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)


def create_server(
    host: str,
    port: int,
    *,
    runtime: MediaLabRuntime,
    web_file: str | Path,
):
    return MediaLabServer((host, port), Handler, runtime=runtime, web_file=web_file)


def main():
    here = Path(__file__).resolve()
    repo_root = here.parents[4]
    host = os.environ.get("FAP_MEDIA_LAB_HOST", "127.0.0.1")
    port = int(os.environ.get("FAP_MEDIA_LAB_PORT", "11440"))
    runtime_dir = Path(
        os.environ.get(
            "FAP_MEDIA_LAB_RUNTIME",
            str(repo_root / "runtime" / "v87_20_media_lab"),
        )
    )
    web_file = repo_root / "web" / "FAP_Media_Lab.html"
    runtime = MediaLabRuntime(runtime_dir=runtime_dir)
    server = create_server(host, port, runtime=runtime, web_file=web_file)
    print("FAP V87.20 MEDIA LAB")
    print(f"UI: http://{host}:{port}/")
    print(f"Artifacts: {runtime.artifact_dir}")
    print("Generator discovery: FAP_MEDIA_ENGINES_JSON")
    print("Qwen: not used")
    server.serve_forever()
