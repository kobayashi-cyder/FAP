from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
from typing import Callable


class BundleError(RuntimeError):
    pass


@dataclass(frozen=True)
class BundlePlan:
    bundle_id: str
    repo_id: str
    revision: str
    checkpoint_name: str
    checkpoint_sha256: str
    checkpoint_size: int
    license_id: str
    model_id: str
    distillation_kind: str
    pipeline: str
    inference_steps: int
    config_allow_patterns: tuple[str, ...]

    def validate(self) -> None:
        if self.license_id.lower() != "apache-2.0":
            raise ValueError("V87.24 reference bundle requires Apache-2.0")
        if len(self.checkpoint_sha256) != 64:
            raise ValueError("checkpoint sha256 invalid")
        int(self.checkpoint_sha256, 16)
        if self.checkpoint_size <= 0:
            raise ValueError("checkpoint size invalid")
        if not self.revision or not self.repo_id or not self.checkpoint_name:
            raise ValueError("bundle source fields required")


SSD1B_BUNDLE = BundlePlan(
    bundle_id="ssd1b-apache2-distilled-v1",
    repo_id="segmind/SSD-1B",
    revision="3bbad7fb72248b876d839e6bd0950aa09e3b8bce",
    checkpoint_name="SSD-1B-A1111.safetensors",
    checkpoint_sha256="1895a00bfc769a00b0c0c43a95e433e79e9db8a85402b45a33e8448785bde94d",
    checkpoint_size=4465671322,
    license_id="apache-2.0",
    model_id="segmind/SSD-1B",
    distillation_kind="knowledge-distillation",
    pipeline="StableDiffusionXLPipeline",
    inference_steps=20,
    config_allow_patterns=(
        "model_index.json",
        "scheduler/*.json",
        "text_encoder/*.json",
        "text_encoder_2/*.json",
        "tokenizer/*.json",
        "tokenizer/*.txt",
        "tokenizer_2/*.json",
        "tokenizer_2/*.txt",
        "unet/*.json",
        "vae/*.json",
    ),
)


DownloadFile = Callable[[str, str, str, Path], Path]
DownloadSnapshot = Callable[[str, str, tuple[str, ...], Path], Path]


def _sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _default_download_file(repo_id: str, revision: str, filename: str, dest: Path) -> Path:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise BundleError("huggingface_hub is required only for bundle preparation") from exc
    return Path(
        hf_hub_download(
            repo_id=repo_id,
            revision=revision,
            filename=filename,
            local_dir=str(dest),
        )
    )


def _default_download_snapshot(
    repo_id: str,
    revision: str,
    allow_patterns: tuple[str, ...],
    dest: Path,
) -> Path:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise BundleError("huggingface_hub is required only for bundle preparation") from exc
    return Path(
        snapshot_download(
            repo_id=repo_id,
            revision=revision,
            allow_patterns=list(allow_patterns),
            local_dir=str(dest),
        )
    )


def prepare_bundle(
    destination: str | Path,
    *,
    plan: BundlePlan = SSD1B_BUNDLE,
    download_file: DownloadFile | None = None,
    download_snapshot: DownloadSnapshot | None = None,
    accept_license: bool = False,
) -> dict:
    plan.validate()
    if not accept_license:
        raise BundleError("license acceptance is required before downloading the bundle")

    root = Path(destination).expanduser().resolve()
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".fap-bundle-", dir=str(root.parent)))
    get_file = download_file or _default_download_file
    get_snapshot = download_snapshot or _default_download_snapshot

    try:
        get_snapshot(plan.repo_id, plan.revision, plan.config_allow_patterns, staging)
        checkpoint = Path(
            get_file(plan.repo_id, plan.revision, plan.checkpoint_name, staging)
        )

        if checkpoint.stat().st_size != plan.checkpoint_size:
            raise BundleError("checkpoint size does not match pinned bundle plan")
        actual_sha = _sha256(checkpoint)
        if actual_sha != plan.checkpoint_sha256:
            raise BundleError("checkpoint SHA-256 does not match pinned bundle plan")
        if not (staging / "model_index.json").is_file():
            raise BundleError("downloaded local config is missing model_index.json")

        config_dir = staging / "ssd1b-config"
        config_dir.mkdir(exist_ok=True)
        _move_config_files(staging, config_dir, checkpoint.name)

        final_checkpoint = staging / plan.checkpoint_name
        if checkpoint != final_checkpoint:
            shutil.copy2(checkpoint, final_checkpoint)

        sidecar = final_checkpoint.with_suffix(final_checkpoint.suffix + ".fap.json")
        sidecar.write_text(
            json.dumps(
                {
                    "model_id": plan.model_id,
                    "license_id": plan.license_id,
                    "source": "https://huggingface.co/" + plan.repo_id,
                    "source_revision": plan.revision,
                    "source_checkpoint_sha256": plan.checkpoint_sha256,
                    "config_dir": "ssd1b-config",
                    "distilled": True,
                    "distillation_kind": plan.distillation_kind,
                    "pipeline": plan.pipeline,
                    "inference_steps": plan.inference_steps,
                    "prepared_by": "FAP V87.24",
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        (staging / "BUNDLE_LICENSE.txt").write_text(
            "Model license identifier: Apache-2.0\n"
            "Source: https://huggingface.co/segmind/SSD-1B\n"
            "Review the source license and terms before use.\n",
            encoding="utf-8",
        )
        (staging / "bundle.json").write_text(
            json.dumps(
                {
                    "schema": "fap.offline-bundle.v1",
                    "bundle_id": plan.bundle_id,
                    "checkpoint": plan.checkpoint_name,
                    "checkpoint_sha256": plan.checkpoint_sha256,
                    "checkpoint_size": plan.checkpoint_size,
                    "license_id": plan.license_id,
                    "source_revision": plan.revision,
                    "offline_ready": True,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)
        for child in staging.iterdir():
            shutil.move(str(child), str(root / child.name))

        return verify_bundle(root, plan=plan)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def _move_config_files(staging: Path, config_dir: Path, checkpoint_name: str) -> None:
    for child in list(staging.iterdir()):
        if child.name in {checkpoint_name, "ssd1b-config"}:
            continue
        target = config_dir / child.name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        shutil.move(str(child), str(target))


def verify_bundle(
    destination: str | Path,
    *,
    plan: BundlePlan = SSD1B_BUNDLE,
) -> dict:
    root = Path(destination).expanduser().resolve()
    checkpoint = root / plan.checkpoint_name
    sidecar = checkpoint.with_suffix(checkpoint.suffix + ".fap.json")
    config = root / "ssd1b-config"

    missing = [
        str(path.name)
        for path in (checkpoint, sidecar, root / "bundle.json", config / "model_index.json")
        if not path.is_file()
    ]
    if missing:
        raise BundleError("offline bundle incomplete: " + ", ".join(missing))
    if checkpoint.stat().st_size != plan.checkpoint_size:
        raise BundleError("offline bundle checkpoint size mismatch")
    actual_sha = _sha256(checkpoint)
    if actual_sha != plan.checkpoint_sha256:
        raise BundleError("offline bundle checkpoint SHA-256 mismatch")

    raw = json.loads(sidecar.read_text(encoding="utf-8"))
    if raw.get("license_id") != plan.license_id:
        raise BundleError("offline bundle license sidecar mismatch")
    if raw.get("source_checkpoint_sha256") != plan.checkpoint_sha256:
        raise BundleError("offline bundle source checksum mismatch")

    return {
        "bundle_id": plan.bundle_id,
        "root": str(root),
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": actual_sha,
        "checkpoint_size": checkpoint.stat().st_size,
        "license_id": plan.license_id,
        "offline_ready": True,
    }
