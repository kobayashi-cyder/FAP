from __future__ import annotations

import base64
import json
import os
import random
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from fap_fmg_connectome import FlyConnectomeRouter
from fap_local_image_backend import LocalRasterGenerator
from fap_media_policy import ArtifactBudget, enhance_prompt, image_dimensions, image_profile, release_transient_memory, strip_control_directives


IMPORT_VERSION = "FAP-FMG-IMPORT-1"
FMG_SOURCE_COMMIT = "dd57b636f67a1279403048bcb75b66c0cbb50b04"
FMG_IMAGE_WIDTH = 1024
FMG_IMAGE_HEIGHT = 1024
FMG_STEPS = 50
FMG_GUIDANCE = 9.0
DEFAULT_NEGATIVE = (
    "low quality, blurry, distorted, deformed anatomy, extra fingers, "
    "extra limbs, duplicate subject, watermark, signature, logo, text overlay"
)


def _image_intent(text: str) -> bool:
    value = str(text or "").casefold()
    hints = (
        "画像生成",
        "画像を生成",
        "画像を作",
        "絵を生成",
        "絵を作",
        "イラストを",
        "写真を生成",
        "image generate",
        "generate image",
        "create image",
        "make an image",
    )
    return any(token in value for token in hints)


class FMGImportedImageModule:
    """FAP adapter for the FMG image-generation controller.

    Imported behavior:
    - fixed 1024x1024 production request profile
    - 50 default steps / CFG 9
    - FMG fly-connectome backend selection and DAN-like reward update

    FAP-specific behavior:
    - an explicitly configured A1111/Forge-compatible HTTP endpoint may be used
    - when no diffusion endpoint is available, FAP's schematic raster generator
      is used as a truthful low-quality fallback instead of pretending that an
      FMG diffusion model is running on the phone
    """

    def __init__(
        self,
        root: str | Path,
        artifact_dir: str | Path | None = None,
        image_base: str | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        fallback_dir = Path(tempfile.gettempdir()) / "fap-fmg-images"
        self.artifact_dir = Path(
            artifact_dir
            or os.environ.get("FAP_FMG_ARTIFACT_DIR")
            or fallback_dir
        ).resolve()
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

        self.image_base = (
            image_base
            or os.environ.get("FAP_FMG_IMAGE_BASE")
            or os.environ.get("FMG_A1111_URL")
            or ""
        ).strip().rstrip("/")

        state_dir = Path(
            os.environ.get("FAP_FMG_STATE_DIR")
            or (Path(tempfile.gettempdir()) / "fap-fmg-state")
        ).resolve()
        state_dir.mkdir(parents=True, exist_ok=True)
        self.connectome = FlyConnectomeRouter(state_dir / "connectome.json")
        self.local = LocalRasterGenerator(self.root, self.artifact_dir)
        self.artifact_budget = ArtifactBudget(self.artifact_dir)

    @staticmethod
    def matches(text: str) -> bool:
        return _image_intent(text)

    def _base_allowed(self) -> bool:
        if not self.image_base:
            return False
        try:
            parsed = urllib.parse.urlparse(self.image_base)
            return parsed.scheme in {"http", "https"} and bool(parsed.hostname)
        except Exception:
            return False

    def _json(
        self,
        path: str,
        *,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        timeout: float = 8.0,
    ) -> Any:
        if not self._base_allowed():
            raise RuntimeError("FMG image endpoint is not configured")
        raw = None
        if data is not None:
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.image_base + path,
            data=raw,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "FAP-FMG/1.0.01",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = response.read(48 * 1024 * 1024)
        return json.loads(payload.decode("utf-8"))

    def _probe_a1111(self) -> dict[str, Any]:
        if not self._base_allowed():
            return {
                "available": False,
                "reason": "FAP_FMG_IMAGE_BASE is not configured",
            }
        try:
            models = self._json("/sdapi/v1/sd-models", timeout=3.0)
            count = len(models) if isinstance(models, list) else 0
            return {
                "available": True,
                "models": count,
                "base": self.image_base,
            }
        except Exception as exc:
            return {
                "available": False,
                "reason": f"{type(exc).__name__}: {exc}",
                "base": self.image_base,
            }

    def status(self) -> dict[str, Any]:
        local_ok, local_note = self.local.available()
        return {
            "version": IMPORT_VERSION,
            "source": "kobayashi-cyder/FMG",
            "source_commit": FMG_SOURCE_COMMIT,
            "profile": {
                "width": FMG_IMAGE_WIDTH,
                "height": FMG_IMAGE_HEIGHT,
                "steps": FMG_STEPS,
                "guidance": FMG_GUIDANCE,
            },
            "profiles": {
                "draft": {"width": 512, "height": 512, "steps": 22, "guidance": 7.0},
                "standard": {"width": 768, "height": 768, "steps": 38, "guidance": 7.5},
                "high": {"width": 1024, "height": 1024, "steps": 56, "guidance": 8.0},
            },
            "connectome": self.connectome.status(),
            "a1111": {
                "configured": self._base_allowed(),
                "base": self.image_base if self._base_allowed() else "",
            },
            "fallback": {
                "available": bool(local_ok),
                "kind": "fap-local-raster",
                "note": local_note,
                "quality": "schematic-draft",
            },
        }

    def _refine_external(
        self,
        source: Path,
        prompt: str,
        profile,
        width: int,
        height: int,
    ) -> tuple[Path, dict[str, Any]]:
        source_b64 = base64.b64encode(source.read_bytes()).decode("ascii")
        started = time.perf_counter()
        value = self._json(
            "/sdapi/v1/img2img",
            method="POST",
            data={
                "init_images": [source_b64],
                "prompt": (
                    prompt
                    + ", preserve composition, refine visible details, "
                      "coherent anatomy, clean edges, natural texture"
                ),
                "negative_prompt": DEFAULT_NEGATIVE,
                "width": width,
                "height": height,
                "steps": max(20, int(profile.steps * 0.55)),
                "cfg_scale": profile.guidance,
                "seed": -1,
                "denoising_strength": 0.20,
                "batch_size": 1,
                "n_iter": 1,
            },
            timeout=profile.timeout_s,
        )
        images = value.get("images") if isinstance(value, dict) else None
        if not images:
            raise RuntimeError("FMG high-quality refine returned no image")
        raw = base64.b64decode(str(images[0]).split(",", 1)[-1], validate=False)
        del images, value, source_b64
        refined = self._save_external(raw, random.SystemRandom().randint(0, 2**31 - 1))
        if refined.stat().st_size <= 128:
            refined.unlink(missing_ok=True)
            raise RuntimeError("FMG high-quality refine artifact verification failed")
        return refined, {
            "applied": True,
            "operation": "global_img2img_refine",
            "denoising_strength": 0.20,
            "elapsed_s": round(time.perf_counter() - started, 3),
        }

    def _save_external(self, raw: bytes, seed: int) -> Path:
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            suffix = ".png"
        elif raw.startswith(b"\xff\xd8"):
            suffix = ".jpg"
        else:
            raise RuntimeError("FMG backend returned an unsupported image payload")
        name = f"fmg_import_{int(time.time()*1000)}_{seed}{suffix}"
        path = self.artifact_dir / name
        path.write_bytes(raw)
        return path

    def _generate_external(self, prompt: str, profile, width: int, height: int) -> dict[str, Any]:
        availability = {
            "a1111": bool(self._probe_a1111().get("available")),
            "diffusers": False,
        }
        decision = self.connectome.route(
            {
                "prompt": prompt,
                "steps": profile.steps,
                "guidance": profile.guidance,
            },
            availability,
        )
        if decision.selected_backend != "a1111":
            raise RuntimeError("No Android-compatible FMG image organ is available")

        seed = random.SystemRandom().randint(0, 2**31 - 1)
        started = time.perf_counter()
        value = self._json(
            "/sdapi/v1/txt2img",
            method="POST",
            data={
                "prompt": prompt,
                "negative_prompt": DEFAULT_NEGATIVE,
                "width": width,
                "height": height,
                "steps": profile.steps,
                "cfg_scale": profile.guidance,
                "seed": seed,
                "batch_size": 1,
                "n_iter": 1,
            },
            timeout=profile.timeout_s,
        )
        images = value.get("images") if isinstance(value, dict) else None
        if not images:
            self.connectome.reward(
                decision,
                -0.85,
                structural_verified=False,
            )
            raise RuntimeError("FMG A1111 backend returned no image")

        raw = base64.b64decode(str(images[0]).split(",", 1)[-1], validate=False)
        del images, value
        path = self._save_external(raw, seed)
        elapsed = max(0.0, time.perf_counter() - started)
        verified = path.stat().st_size > 128
        self.connectome.reward(
            decision,
            0.84 if verified else -0.55,
            structural_verified=verified,
            elapsed_s=elapsed,
        )
        if not verified:
            raise RuntimeError("FMG artifact structural verification failed")

        refine = {"applied": False}
        if profile.name == "high":
            try:
                refined_path, refine = self._refine_external(
                    path,
                    prompt,
                    profile,
                    width,
                    height,
                )
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
                path = refined_path
            except Exception as exc:
                refine = {
                    "applied": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }

        return {
            "ok": True,
            "reply": (
                f"FMG画像生成で{width}×{height}画像を生成しました。\n"
                f"quality={profile.name} · backend=a1111 · steps={profile.steps} · guidance={profile.guidance}"
            ),
            "confidence": 0.95,
            "generator": "fmg-import",
            "fmg_source_commit": FMG_SOURCE_COMMIT,
            "image_profile": {
                "width": width,
                "height": height,
                "steps": profile.steps,
                "guidance": profile.guidance,
                "quality": profile.name,
            },
            "connectome_route": decision.as_dict(),
            "refine": refine,
            "artifact_path": str(path),
            "artifacts": [
                {
                    "type": "image",
                    "name": path.name,
                    "path": str(path),
                }
            ],
        }

    def generate(self, text: str) -> dict[str, Any]:
        raw_prompt = str(text or "").strip()
        profile = image_profile(raw_prompt)
        width, height = image_dimensions(raw_prompt, profile)
        prompt = strip_control_directives(raw_prompt)
        external_prompt = enhance_prompt(raw_prompt, profile)
        if not prompt:
            return {
                "ok": False,
                "reply": "画像生成プロンプトが空です。",
                "confidence": 1.0,
                "generator": "fmg-import",
            }

        probe = self._probe_a1111()
        if probe.get("available"):
            try:
                result = self._generate_external(external_prompt, profile, width, height)
                self.artifact_budget.prune([result.get("artifact_path", "")])
                result["memory_release"] = release_transient_memory()
                return result
            except Exception as exc:
                external_error = f"{type(exc).__name__}: {exc}"
            else:
                external_error = ""
        else:
            external_error = str(probe.get("reason") or "FMG backend unavailable")

        local_size = 512 if profile.name == "draft" else 768
        local = self.local.generate(
            prompt,
            width=local_size,
            height=local_size,
        )
        if local.get("ok"):
            artifacts = local.get("artifacts")
            if isinstance(artifacts, list):
                for row in artifacts:
                    if not isinstance(row, dict):
                        continue
                    name = str(row.get("name") or "").strip()
                    if name and not row.get("path"):
                        candidate = self.artifact_dir / name
                        if candidate.is_file():
                            row["path"] = str(candidate)
            local["generator"] = "fmg-import:fap-fallback"
            local["fmg_source_commit"] = FMG_SOURCE_COMMIT
            local["fmg_external_error"] = external_error
            local["requested_fmg_profile"] = {
                "width": width,
                "height": height,
                "steps": profile.steps,
                "guidance": profile.guidance,
                "quality": profile.name,
            }
            local["reply"] = (
                "FMG画像生成モジュールはFAPへ輸入済みです。"
                "この端末ではFMG拡散バックエンドが未接続のため、"
                "現在はFAP内蔵の簡易ラスタ生成へフォールバックしました。\n"
                + str(local.get("reply") or "")
            )
            keep = []
            for row in local.get("artifacts") or []:
                if isinstance(row, dict) and row.get("path"):
                    keep.append(row["path"])
            local["quality_mode"] = profile.name
            local["artifact_prune"] = self.artifact_budget.prune(keep)
            local["memory_release"] = release_transient_memory()
            return local

        return {
            "ok": False,
            "reply": (
                "FMG画像生成モジュールは読み込まれていますが、"
                "拡散バックエンドもローカル簡易生成も利用できません。"
            ),
            "confidence": 0.96,
            "generator": "fmg-import",
            "fmg_external_error": external_error,
        }
