from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import importlib
import json
import os
from pathlib import Path
import socket
import tempfile
from typing import Any, Callable, Sequence

from fap_media_generation import GenerationRequest, MediaArtifact


class OfflineEngineError(RuntimeError):
    pass


ALLOWED_LICENSES = {
    "apache-2.0",
    "apache 2.0",
    "apache-2",
    "mit",
    "bsd-3-clause",
    "bsd-2-clause",
    "cc0-1.0",
}


@dataclass(frozen=True)
class OfflineModelManifest:
    model_id: str
    media_type: str
    license_id: str
    source: str
    distilled: bool
    distillation_kind: str
    pipeline: str = "DiffusionPipeline"
    inference_steps: int = 4

    def validate(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id is required")
        if self.media_type not in {"image", "video"}:
            raise ValueError("media_type must be image or video")
        if self.license_id.strip().lower() not in ALLOWED_LICENSES:
            raise ValueError("model license is not in FAP offline allowlist")
        if not self.source.strip():
            raise ValueError("source is required")
        if not isinstance(self.distilled, bool):
            raise ValueError("distilled must be boolean")
        if self.distilled and not self.distillation_kind.strip():
            raise ValueError("distillation_kind required for distilled models")
        if not (1 <= int(self.inference_steps) <= 100):
            raise ValueError("inference_steps out of bounds")


def load_manifest(model_dir: str | Path) -> OfflineModelManifest:
    path = Path(model_dir) / "fap_model_manifest.json"
    if not path.is_file():
        raise OfflineEngineError(
            "missing fap_model_manifest.json; FAP will not execute unverified local weights"
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        manifest = OfflineModelManifest(
            model_id=str(raw["model_id"]),
            media_type=str(raw["media_type"]),
            license_id=str(raw["license_id"]),
            source=str(raw["source"]),
            distilled=bool(raw["distilled"]),
            distillation_kind=str(raw.get("distillation_kind", "")),
            pipeline=str(raw.get("pipeline", "DiffusionPipeline")),
            inference_steps=int(raw.get("inference_steps", 4)),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise OfflineEngineError("invalid fap_model_manifest.json") from exc
    manifest.validate()
    return manifest


@contextmanager
def _offline_environment():
    keys = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "DO_NOT_TRACK": "1",
    }
    old = {k: os.environ.get(k) for k in keys}
    os.environ.update(keys)
    try:
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def _block_non_loopback_network():
    original_create = socket.create_connection

    def guarded(address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else str(address)
        normalized = str(host).strip().lower()
        if normalized not in {"127.0.0.1", "localhost", "::1"}:
            raise OSError("FAP offline inference blocked a non-loopback network connection")
        return original_create(address, *args, **kwargs)

    socket.create_connection = guarded
    try:
        yield
    finally:
        socket.create_connection = original_create


class OfflineDiffusersEngine:
    """Load only local Diffusers-compatible weights and prohibit network fallback."""

    def __init__(
        self,
        model_dir: str | Path,
        *,
        artifact_dir: str | Path,
        pipeline_loader: Callable[[str, OfflineModelManifest], Any] | None = None,
        video_encoder: Callable[[Sequence[Any], Path, int], None] | None = None,
    ):
        self.model_dir = Path(model_dir).resolve()
        if not self.model_dir.is_dir():
            raise OfflineEngineError("offline model directory does not exist")
        self.manifest = load_manifest(self.model_dir)
        self.engine_id = "offline-" + _safe_id(self.manifest.model_id)
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.pipeline_loader = pipeline_loader or self._default_pipeline_loader
        self.video_encoder = video_encoder or self._default_video_encoder
        self._pipeline = None

    def probe(self) -> dict:
        required = self.model_dir / "model_index.json"
        if not required.is_file():
            raise OfflineEngineError("model_index.json missing from offline model directory")
        return {
            "engine_id": self.engine_id,
            "model_id": self.manifest.model_id,
            "media_type": self.manifest.media_type,
            "license_id": self.manifest.license_id,
            "distilled": self.manifest.distilled,
            "distillation_kind": self.manifest.distillation_kind,
            "offline": True,
        }

    def generate(self, request: GenerationRequest, *, prompt: str, previous, critique) -> MediaArtifact:
        request.validate()
        if request.media_type != self.manifest.media_type:
            raise OfflineEngineError("request media type does not match offline model manifest")

        with _offline_environment(), _block_non_loopback_network():
            pipe = self._pipeline_instance()
            kwargs = self._generation_kwargs(request, prompt)
            result = pipe(**kwargs)

        if request.media_type == "image":
            return self._persist_image(result)
        return self._persist_video(result, request.fps)

    def _pipeline_instance(self):
        if self._pipeline is None:
            self._pipeline = self.pipeline_loader(str(self.model_dir), self.manifest)
        return self._pipeline

    def _default_pipeline_loader(self, path: str, manifest: OfflineModelManifest):
        try:
            diffusers = importlib.import_module("diffusers")
            torch = importlib.import_module("torch")
        except ImportError as exc:
            raise OfflineEngineError(
                "offline engine requires locally installed diffusers and torch"
            ) from exc

        pipeline_cls = getattr(diffusers, manifest.pipeline, None)
        if pipeline_cls is None:
            pipeline_cls = getattr(diffusers, "DiffusionPipeline", None)
        if pipeline_cls is None:
            raise OfflineEngineError("requested Diffusers pipeline class is unavailable")

        dtype = None
        if getattr(torch, "cuda", None) is not None and torch.cuda.is_available():
            dtype = getattr(torch, "float16", None)

        kwargs = {
            "local_files_only": True,
        }
        if dtype is not None:
            kwargs["torch_dtype"] = dtype

        pipe = pipeline_cls.from_pretrained(path, **kwargs)
        if getattr(torch, "cuda", None) is not None and torch.cuda.is_available():
            pipe = pipe.to("cuda")
        else:
            pipe = pipe.to("cpu")
        return pipe

    def _generation_kwargs(self, request: GenerationRequest, prompt: str) -> dict:
        kwargs = {
            "prompt": prompt,
            "num_inference_steps": self.manifest.inference_steps,
        }
        if request.media_type == "image":
            kwargs.update({"width": request.width, "height": request.height})
            if "flux.1-schnell" in self.manifest.model_id.lower():
                kwargs["guidance_scale"] = 0.0
        else:
            kwargs.update(
                {
                    "width": request.width,
                    "height": request.height,
                    "num_frames": max(2, int(round(request.duration_s * request.fps))),
                }
            )
        return kwargs

    def _persist_image(self, result) -> MediaArtifact:
        images = getattr(result, "images", None)
        if not images:
            raise OfflineEngineError("offline image pipeline returned no images")
        image = images[0]

        fd, tmp = tempfile.mkstemp(suffix=".png", dir=str(self.artifact_dir))
        os.close(fd)
        tmp_path = Path(tmp)
        try:
            image.save(tmp_path, format="PNG")
            data = tmp_path.read_bytes()
            if not data:
                raise OfflineEngineError("offline image artifact is empty")
            digest = sha256(data).hexdigest()
            destination = self.artifact_dir / f"{digest}.png"
            os.replace(tmp_path, destination)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        return MediaArtifact(
            media_type="image",
            digest=digest,
            mime_type="image/png",
            locator=str(destination),
            metadata=self._metadata(len(data)),
        )

    def _persist_video(self, result, fps: int) -> MediaArtifact:
        frames = getattr(result, "frames", None)
        if frames is None:
            raise OfflineEngineError("offline video pipeline returned no frames")
        if frames and isinstance(frames[0], (list, tuple)):
            frames = frames[0]
        frames = list(frames or [])
        if not frames:
            raise OfflineEngineError("offline video pipeline returned empty frames")

        fd, tmp = tempfile.mkstemp(suffix=".mp4", dir=str(self.artifact_dir))
        os.close(fd)
        tmp_path = Path(tmp)
        try:
            self.video_encoder(frames, tmp_path, fps)
            data = tmp_path.read_bytes()
            if not data:
                raise OfflineEngineError("offline video artifact is empty")
            digest = sha256(data).hexdigest()
            destination = self.artifact_dir / f"{digest}.mp4"
            os.replace(tmp_path, destination)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        return MediaArtifact(
            media_type="video",
            digest=digest,
            mime_type="video/mp4",
            locator=str(destination),
            metadata=self._metadata(len(data)),
        )

    def _default_video_encoder(self, frames: Sequence[Any], path: Path, fps: int):
        try:
            imageio = importlib.import_module("imageio.v2")
        except ImportError as exc:
            raise OfflineEngineError(
                "offline video encoding requires locally installed imageio and ffmpeg support"
            ) from exc
        with imageio.get_writer(str(path), fps=fps, codec="libx264") as writer:
            for frame in frames:
                if hasattr(frame, "convert"):
                    import numpy as np
                    writer.append_data(np.asarray(frame.convert("RGB")))
                else:
                    writer.append_data(frame)

    def _metadata(self, byte_count: int) -> dict:
        return {
            "engine_id": self.engine_id,
            "adapter": "offline-diffusers",
            "model_id": self.manifest.model_id,
            "license_id": self.manifest.license_id,
            "distilled": self.manifest.distilled,
            "distillation_kind": self.manifest.distillation_kind,
            "offline": True,
            "bytes": byte_count,
        }


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in value)[:100]
