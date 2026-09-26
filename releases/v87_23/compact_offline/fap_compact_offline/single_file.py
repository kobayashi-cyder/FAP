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


class CompactOfflineError(RuntimeError):
    pass


_ALLOWED = {
    "apache-2.0",
    "apache 2.0",
    "mit",
    "bsd-3-clause",
    "bsd-2-clause",
    "cc0-1.0",
}


@dataclass(frozen=True)
class CompactOfflineManifest:
    model_id: str
    license_id: str
    source: str
    config_dir: str
    distilled: bool
    distillation_kind: str
    pipeline: str = "StableDiffusionXLPipeline"
    inference_steps: int = 20

    def validate(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id required")
        if self.license_id.strip().lower() not in _ALLOWED:
            raise ValueError("license not allowed")
        if not self.source.strip():
            raise ValueError("source required")
        if not self.config_dir.strip():
            raise ValueError("config_dir required")
        if self.distilled and not self.distillation_kind.strip():
            raise ValueError("distillation_kind required")
        if not (1 <= int(self.inference_steps) <= 100):
            raise ValueError("inference_steps out of bounds")


def _sidecar_path(model_file: Path) -> Path:
    return model_file.with_suffix(model_file.suffix + ".fap.json")


def _load_manifest(model_file: Path) -> CompactOfflineManifest:
    sidecar = _sidecar_path(model_file)
    if not sidecar.is_file():
        raise CompactOfflineError(
            f"missing sidecar manifest: {sidecar.name}"
        )
    try:
        raw = json.loads(sidecar.read_text(encoding="utf-8"))
        manifest = CompactOfflineManifest(
            model_id=str(raw["model_id"]),
            license_id=str(raw["license_id"]),
            source=str(raw["source"]),
            config_dir=str(raw["config_dir"]),
            distilled=bool(raw["distilled"]),
            distillation_kind=str(raw.get("distillation_kind", "")),
            pipeline=str(raw.get("pipeline", "StableDiffusionXLPipeline")),
            inference_steps=int(raw.get("inference_steps", 20)),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise CompactOfflineError("invalid compact model manifest") from exc
    manifest.validate()
    return manifest


@contextmanager
def _offline_guard():
    env = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "DO_NOT_TRACK": "1",
    }
    previous = {k: os.environ.get(k) for k in env}
    original_create = socket.create_connection

    def guarded(address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else str(address)
        if str(host).lower() not in {"127.0.0.1", "localhost", "::1"}:
            raise OSError("offline compact engine blocked network access")
        return original_create(address, *args, **kwargs)

    os.environ.update(env)
    socket.create_connection = guarded
    try:
        yield
    finally:
        socket.create_connection = original_create
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class CompactOfflineImageEngine:
    """Single-file local checkpoint engine with local-only config and low-memory hints."""

    def __init__(
        self,
        model_file: str | Path,
        *,
        artifact_dir: str | Path,
        loader: Callable[[Path, Path, CompactOfflineManifest], Any] | None = None,
    ):
        self.model_file = Path(model_file).resolve()
        if not self.model_file.is_file():
            raise CompactOfflineError("single-file model does not exist")
        if self.model_file.suffix.lower() not in {".safetensors", ".ckpt"}:
            raise CompactOfflineError("unsupported single-file checkpoint extension")
        self.manifest = _load_manifest(self.model_file)
        self.config_dir = (self.model_file.parent / self.manifest.config_dir).resolve()
        if not self.config_dir.is_dir():
            raise CompactOfflineError("local config_dir does not exist")
        if not (self.config_dir / "model_index.json").is_file():
            raise CompactOfflineError("local config_dir missing model_index.json")
        self.engine_id = "compact-" + _safe(self.manifest.model_id)
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.loader = loader or self._default_loader
        self._pipe = None

    def probe(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "model_id": self.manifest.model_id,
            "license_id": self.manifest.license_id,
            "distilled": self.manifest.distilled,
            "distillation_kind": self.manifest.distillation_kind,
            "checkpoint_bytes": self.model_file.stat().st_size,
            "offline": True,
            "compact_single_file": True,
        }

    def generate(self, request: GenerationRequest, *, prompt: str, previous, critique) -> MediaArtifact:
        request.validate()
        if request.media_type != "image":
            raise CompactOfflineError("compact single-file engine supports images only")
        with _offline_guard():
            pipe = self._pipeline()
            result = pipe(
                prompt=prompt,
                width=request.width,
                height=request.height,
                num_inference_steps=self.manifest.inference_steps,
            )
        images = getattr(result, "images", None)
        if not images:
            raise CompactOfflineError("compact pipeline returned no image")
        image = images[0]

        fd, tmp = tempfile.mkstemp(suffix=".png", dir=str(self.artifact_dir))
        os.close(fd)
        tmp_path = Path(tmp)
        try:
            image.save(tmp_path, format="PNG")
            data = tmp_path.read_bytes()
            if not data:
                raise CompactOfflineError("generated image is empty")
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
            metadata={
                "engine_id": self.engine_id,
                "adapter": "compact-offline-single-file",
                "model_id": self.manifest.model_id,
                "license_id": self.manifest.license_id,
                "distilled": self.manifest.distilled,
                "distillation_kind": self.manifest.distillation_kind,
                "offline": True,
                "checkpoint_bytes": self.model_file.stat().st_size,
                "bytes": len(data),
            },
        )

    def _pipeline(self):
        if self._pipe is None:
            self._pipe = self.loader(self.model_file, self.config_dir, self.manifest)
        return self._pipe

    def _default_loader(self, model_file: Path, config_dir: Path, manifest: CompactOfflineManifest):
        try:
            diffusers = importlib.import_module("diffusers")
            torch = importlib.import_module("torch")
        except ImportError as exc:
            raise CompactOfflineError(
                "compact offline engine requires locally installed diffusers and torch"
            ) from exc

        cls = getattr(diffusers, manifest.pipeline, None)
        if cls is None:
            raise CompactOfflineError(f"Diffusers pipeline not available: {manifest.pipeline}")

        kwargs = {
            "config": str(config_dir),
            "local_files_only": True,
        }
        cuda = getattr(torch, "cuda", None)
        has_cuda = bool(cuda and cuda.is_available())
        if has_cuda and getattr(torch, "float16", None) is not None:
            kwargs["torch_dtype"] = torch.float16

        pipe = cls.from_single_file(str(model_file), **kwargs)

        if has_cuda and hasattr(pipe, "enable_model_cpu_offload"):
            pipe.enable_model_cpu_offload()
        elif hasattr(pipe, "to"):
            pipe = pipe.to("cpu")

        if hasattr(pipe, "enable_attention_slicing"):
            pipe.enable_attention_slicing()
        if hasattr(pipe, "enable_vae_slicing"):
            pipe.enable_vae_slicing()
        return pipe


def discover_compact_models(
    explicit: Sequence[str | Path] | None = None,
) -> list[Path]:
    values = []
    if explicit:
        values.extend(Path(x) for x in explicit)
    raw = os.environ.get("FAP_OFFLINE_SINGLE_FILES", "").strip()
    if raw:
        sep = ";" if os.name == "nt" else ":"
        values.extend(Path(x.strip()) for x in raw.split(sep) if x.strip())

    home = Path.home()
    common_dirs = [
        home / "stable-diffusion-webui" / "models" / "Stable-diffusion",
        home / "stable-diffusion-webui-forge" / "models" / "Stable-diffusion",
        home / "Downloads" / "stable-diffusion-webui" / "models" / "Stable-diffusion",
        home / "Downloads" / "stable-diffusion-webui-forge" / "models" / "Stable-diffusion",
    ]
    for directory in common_dirs:
        if directory.is_dir():
            values.extend(directory.glob("*.safetensors"))

    unique = []
    seen = set()
    for path in values:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file() and _sidecar_path(resolved).is_file():
            unique.append(resolved)
    return unique


def _safe(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in value)[:100]
