from __future__ import annotations

import base64
import json
from pathlib import Path
import threading
import urllib.request

from fap_autonomous_media import EngineConfig, MediaSkillRegistry, TransportResponse
from fap_media_lab import MediaLabRuntime, create_server


class SequenceTransport:
    def __init__(self, values):
        self.values = list(values)

    def __call__(self, method, url, headers, body, timeout_s, max_bytes):
        value = self.values.pop(0)
        return TransportResponse(
            200,
            {"content-type": "application/json"},
            json.dumps(value).encode("utf-8"),
        )


def completed(mime, data):
    return {
        "status": "completed",
        "mime_type": mime,
        "data_base64": base64.b64encode(data).decode("ascii"),
    }


def make_runtime(tmp_path, monkeypatch, media_type="image", responses=None):
    token_env = "LAB_TOKEN"
    monkeypatch.setenv(token_env, "secret")
    registry = MediaSkillRegistry(tmp_path / "registry.json")
    registry.register_engine(
        EngineConfig(
            "lab-engine",
            media_type,
            "https://engine.example/generate",
            token_env,
            poll_interval_s=0.0,
        )
    )
    transport = SequenceTransport(responses or [])
    runtime = MediaLabRuntime(
        runtime_dir=tmp_path / "runtime",
        registry=registry,
        transports={"lab-engine": transport},
        sleep_fn=lambda _: None,
    )
    return runtime


def test_status_reports_engine_without_secret(tmp_path, monkeypatch):
    runtime = make_runtime(
        tmp_path,
        monkeypatch,
        responses=[completed("image/png", b"x")],
    )
    status = runtime.status()
    assert status["state"] == "ready"
    assert status["skills"][0]["engine_id"] == "lab-engine"
    assert status["skills"][0]["credential_present"] is True
    assert "secret" not in json.dumps(status)


def test_image_generation_returns_browser_artifact_url(tmp_path, monkeypatch):
    runtime = make_runtime(
        tmp_path,
        monkeypatch,
        responses=[completed("image/png", b"REAL-IMAGE-BYTES")],
    )
    result = runtime.generate(
        {"prompt": "beagle", "media_type": "image", "max_attempts": 1}
    )
    assert result["accepted"] is True
    assert result["artifact"]["url"].startswith("/artifacts/")
    path = runtime.artifact_path(result["artifact"]["filename"])
    assert path.read_bytes() == b"REAL-IMAGE-BYTES"
    assert result["artifact"]["verification_kind"] == "artifact-integrity"


def test_async_video_generation_returns_mp4_url(tmp_path, monkeypatch):
    runtime = make_runtime(
        tmp_path,
        monkeypatch,
        media_type="video",
        responses=[
            {
                "status": "queued",
                "poll_url": "https://engine.example/jobs/1",
            },
            completed("video/mp4", b"REAL-VIDEO-BYTES"),
        ],
    )
    result = runtime.generate(
        {
            "prompt": "beagle running",
            "media_type": "video",
            "duration_s": 3.0,
            "fps": 24,
            "max_attempts": 1,
        }
    )
    assert result["accepted"] is True
    assert result["artifact"]["mime_type"] == "video/mp4"
    assert runtime.artifact_path(result["artifact"]["filename"]).read_bytes() == b"REAL-VIDEO-BYTES"


def test_artifact_path_blocks_traversal(tmp_path, monkeypatch):
    runtime = make_runtime(
        tmp_path,
        monkeypatch,
        responses=[completed("image/png", b"x")],
    )
    try:
        runtime.artifact_path("../secret.txt")
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError:
        pass


def test_http_server_serves_ui_status_and_generated_artifact(tmp_path, monkeypatch):
    runtime = make_runtime(
        tmp_path,
        monkeypatch,
        responses=[completed("image/png", b"BROWSER-IMAGE")],
    )
    web = tmp_path / "lab.html"
    web.write_text("<!doctype html><title>lab</title>", encoding="utf-8")
    server = create_server("127.0.0.1", 0, runtime=runtime, web_file=web)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urllib.request.urlopen(base + "/", timeout=3) as r:
            assert b"<title>lab</title>" in r.read()
        with urllib.request.urlopen(base + "/api/v1/status", timeout=3) as r:
            status = json.loads(r.read().decode("utf-8"))
            assert status["version"] == "87.20"

        body = json.dumps(
            {"prompt": "beagle", "media_type": "image", "max_attempts": 1}
        ).encode("utf-8")
        req = urllib.request.Request(
            base + "/api/v1/generate",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            result = json.loads(r.read().decode("utf-8"))
        with urllib.request.urlopen(base + result["artifact"]["url"], timeout=3) as r:
            assert r.read() == b"BROWSER-IMAGE"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
