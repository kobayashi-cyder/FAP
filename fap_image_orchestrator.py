from __future__ import annotations

import base64
import datetime as dt
import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Any


_STYLE_PATTERNS = (
    ("photorealistic", re.compile(r"(写真風|写真みたい|実写|フォトリアル|photoreal|photo[- ]?real|realistic photo)", re.I)),
    ("illustration", re.compile(r"(イラスト|illustration|絵本|drawing)", re.I)),
    ("anime", re.compile(r"(アニメ|anime|manga|マンガ)", re.I)),
    ("watercolor", re.compile(r"(水彩|watercolor)", re.I)),
    ("oil-painting", re.compile(r"(油彩|油絵|oil painting)", re.I)),
    ("3d", re.compile(r"(3d|CG|レンダー|render)", re.I)),
)

_FRAMING_PATTERNS = (
    ("full-body", re.compile(r"(全身|full body|full-body)", re.I)),
    ("close-up", re.compile(r"(アップ|接写|close[- ]?up)", re.I)),
    ("portrait", re.compile(r"(ポートレート|portrait|胸上|バストアップ)", re.I)),
    ("wide", re.compile(r"(広角|wide shot|引き|全景)", re.I)),
)

_LIGHT_PATTERNS = (
    ("golden-hour", re.compile(r"(夕暮れ|夕焼|夕日|ゴールデンアワー|golden hour|sunset)", re.I)),
    ("night", re.compile(r"(夜|夜景|星空|night|midnight)", re.I)),
    ("daylight", re.compile(r"(昼|日中|自然光|daylight|natural light)", re.I)),
    ("studio", re.compile(r"(スタジオ|studio lighting|softbox)", re.I)),
)

_SUBJECT_ALIASES = {
    "beagle": ("ビーグル", "beagle"),
    "dog": ("犬", "dog", "わんこ", "ワンコ"),
    "cat": ("猫", "cat"),
    "woman": ("女性", "女の人", "woman", "girl", "少女"),
    "man": ("男性", "男の人", "man", "boy", "少年"),
    "person": ("人物", "人", "person", "human"),
    "car": ("車", "自動車", "car"),
}

_BACKGROUND_ALIASES = {
    "mountains": ("山", "山々", "mountain", "mountains"),
    "lake": ("湖", "湖畔", "lake"),
    "forest": ("森", "林", "forest", "woods"),
    "city": ("街", "町", "都市", "city", "town"),
    "outdoor": ("屋外", "外", "outdoor", "草原", "丘", "hill"),
    "studio": ("スタジオ", "studio"),
}

_COUNT_PATTERNS = (
    (1, re.compile(r"(一人|1人|一匹|1匹|一頭|1頭|一つ|1つ|single|one )", re.I)),
    (2, re.compile(r"(二人|2人|二匹|2匹|二頭|2頭|二つ|2つ|two )", re.I)),
    (3, re.compile(r"(三人|3人|三匹|3匹|三頭|3頭|three )", re.I)),
)


@dataclass(frozen=True)
class ImageRequestSpec:
    raw_text: str
    subjects: tuple[str, ...]
    count: int | None
    style: str
    framing: str
    lighting: str
    backgrounds: tuple[str, ...]
    must_have: tuple[str, ...]
    must_not_have: tuple[str, ...]
    width: int
    height: int
    photorealistic: bool


@dataclass(frozen=True)
class ImageCandidate:
    round_no: int
    candidate_no: int
    path: str
    prompt: str
    negative_prompt: str
    caption: str
    score: float
    visual_verified: bool
    missing_terms: tuple[str, ...]


class ImageRequestParser:
    """Conservative parser for image-generation constraints.

    It extracts only signals it can identify reliably and preserves the original
    request in the composed prompt so unknown concepts are not discarded.
    """

    def parse(self, text: str) -> ImageRequestSpec:
        raw = str(text or "").strip()
        low = raw.lower()

        subjects = []
        for canonical, aliases in _SUBJECT_ALIASES.items():
            if any(alias.lower() in low for alias in aliases):
                subjects.append(canonical)
        # Prefer the more specific breed over the generic dog tag.
        if "beagle" in subjects and "dog" in subjects:
            subjects.remove("dog")

        count = None
        for n, pat in _COUNT_PATTERNS:
            if pat.search(raw):
                count = n
                break

        style = "unspecified"
        for name, pat in _STYLE_PATTERNS:
            if pat.search(raw):
                style = name
                break

        framing = "unspecified"
        for name, pat in _FRAMING_PATTERNS:
            if pat.search(raw):
                framing = name
                break

        lighting = "unspecified"
        for name, pat in _LIGHT_PATTERNS:
            if pat.search(raw):
                lighting = name
                break

        backgrounds = []
        for canonical, aliases in _BACKGROUND_ALIASES.items():
            if any(alias.lower() in low for alias in aliases):
                backgrounds.append(canonical)

        must_have = list(subjects)
        must_have += backgrounds
        if style != "unspecified":
            must_have.append(style)
        if framing != "unspecified":
            must_have.append(framing)
        if lighting != "unspecified":
            must_have.append(lighting)

        must_not = [
            "watermark", "text overlay", "logo", "blurry", "low resolution",
            "deformed anatomy", "extra limbs", "duplicate subject",
        ]
        if count == 1:
            must_not += ["multiple subjects", "two dogs", "two people"]

        width = int(os.environ.get("FAP_IMAGE_WIDTH", "768"))
        height = int(os.environ.get("FAP_IMAGE_HEIGHT", "768"))
        width = min(1536, max(256, width))
        height = min(1536, max(256, height))

        return ImageRequestSpec(
            raw_text=raw,
            subjects=tuple(dict.fromkeys(subjects)),
            count=count,
            style=style,
            framing=framing,
            lighting=lighting,
            backgrounds=tuple(dict.fromkeys(backgrounds)),
            must_have=tuple(dict.fromkeys(must_have)),
            must_not_have=tuple(dict.fromkeys(must_not)),
            width=width,
            height=height,
            photorealistic=(style == "photorealistic"),
        )


def _english_hints(spec: ImageRequestSpec) -> list[str]:
    out = []
    out.extend(spec.subjects)
    if spec.count:
        out.append(f"exactly {spec.count} main subject" + ("" if spec.count == 1 else "s"))
    if spec.style == "photorealistic":
        out += ["photorealistic photography", "natural skin/fur detail", "real camera optics"]
    elif spec.style != "unspecified":
        out.append(spec.style)
    if spec.framing != "unspecified":
        out.append(spec.framing.replace("-", " "))
    if spec.lighting != "unspecified":
        out.append(spec.lighting.replace("-", " "))
    out.extend(spec.backgrounds)
    return out


def compose_prompt(spec: ImageRequestSpec, repairs: tuple[str, ...] = (), variant: int = 0) -> str:
    hints = _english_hints(spec)
    if repairs:
        hints += [f"clearly show {x}" for x in repairs]
    hints += [
        "coherent composition",
        "anatomically plausible subjects",
        "clean details",
    ]
    if variant % 3 == 1:
        hints += ["balanced composition", "natural perspective"]
    elif variant % 3 == 2:
        hints += ["cinematic composition", "strong subject separation"]
    return ", ".join([spec.raw_text] + hints)


def compose_negative(spec: ImageRequestSpec) -> str:
    return ", ".join(spec.must_not_have)


def _caption_terms(text: str) -> set[str]:
    t = re.sub(r"[^a-z0-9一-龥ぁ-んァ-ンー]+", " ", str(text or "").lower())
    return {x for x in t.split() if len(x) >= 2}


def _term_aliases(term: str) -> tuple[str, ...]:
    aliases = {
        "beagle": ("beagle",),
        "dog": ("dog", "canine", "hound"),
        "cat": ("cat", "feline"),
        "woman": ("woman", "female", "girl"),
        "man": ("man", "male", "boy"),
        "person": ("person", "human", "people"),
        "mountains": ("mountain", "mountains", "hill", "hills"),
        "mountain": ("mountain", "mountains", "hill", "hills"),
        "lake": ("lake", "water", "waterside"),
        "forest": ("forest", "trees", "woods", "woodland"),
        "city": ("city", "town", "buildings"),
        "outdoor": ("outdoor", "outside", "field", "landscape"),
        "studio": ("studio",),
        "photorealistic": ("photo", "photograph", "photorealistic", "realistic"),
        "full-body": ("full", "body", "standing"),
        "close-up": ("close", "closeup", "portrait"),
        "portrait": ("portrait", "face", "person"),
        "wide": ("wide", "landscape", "scene"),
        "golden-hour": ("sunset", "golden", "warm", "evening"),
        "night": ("night", "dark", "stars"),
        "daylight": ("daylight", "daytime", "natural"),
        "studio": ("studio",),
    }
    return aliases.get(term, (term.replace("-", " "), term.replace("-", "")))


def score_caption(spec: ImageRequestSpec, caption: str) -> tuple[float, tuple[str, ...]]:
    if not caption.strip():
        return 0.25, tuple(spec.must_have)

    words = _caption_terms(caption)
    missing = []
    matched = 0
    important = list(spec.subjects) + list(spec.backgrounds)
    if spec.style != "unspecified":
        important.append(spec.style)
    if spec.framing != "unspecified":
        important.append(spec.framing)
    if spec.lighting != "unspecified":
        important.append(spec.lighting)

    important = list(dict.fromkeys(important))
    for term in important:
        aliases = _term_aliases(term)
        if any(any(a in w or w in a for w in words) for a in aliases):
            matched += 1
        else:
            missing.append(term)

    if not important:
        return 0.72, ()
    score = 0.35 + 0.65 * (matched / len(important))
    # Missing a requested primary subject is a hard quality penalty.
    if any(x in missing for x in spec.subjects):
        score = min(score, 0.48)
    return round(max(0.0, min(1.0, score)), 4), tuple(missing)


class ImageOrchestrator:
    """Generate -> inspect -> repair -> select loop over an A1111-compatible API.

    Visual verification uses the optional /sdapi/v1/interrogate endpoint. When
    that endpoint is unavailable, the image is still generated but the result is
    clearly marked as visually unverified instead of claiming semantic success.
    """

    def __init__(
        self,
        *,
        image_base: str,
        artifact_dir: str | Path,
        http_json: Callable[..., Any],
    ):
        self.image_base = image_base.rstrip("/")
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.http_json = http_json
        self.parser = ImageRequestParser()
        self.candidates = min(4, max(1, int(os.environ.get("FAP_IMAGE_CANDIDATES", "2"))))
        self.rounds = min(4, max(1, int(os.environ.get("FAP_IMAGE_ROUNDS", "2"))))
        self.steps = min(60, max(8, int(os.environ.get("FAP_IMAGE_STEPS", "28"))))
        self.cfg = float(os.environ.get("FAP_IMAGE_CFG", "7.0"))
        self.pass_score = min(0.98, max(0.50, float(os.environ.get("FAP_IMAGE_PASS_SCORE", "0.80"))))

    def available(self) -> tuple[bool, str]:
        try:
            models = self.http_json(self.image_base + "/sdapi/v1/sd-models", timeout=4)
            count = len(models) if isinstance(models, list) else 0
            return True, f"画像生成器官は接続済みです（models={count}, orchestrator=V87.56）。"
        except Exception:
            return False, (
                "画像生成意図は認識できますが、画像モデルが未接続です。"
                "FAP_IMAGE_APIへAUTOMATIC1111互換APIを接続してください。"
            )

    def _interrogate(self, image_b64: str) -> tuple[str, bool]:
        try:
            out = self.http_json(
                self.image_base + "/sdapi/v1/interrogate",
                method="POST",
                data={"image": image_b64, "model": "clip"},
                timeout=90,
            )
            caption = str((out or {}).get("caption", "")).strip()
            return caption, bool(caption)
        except Exception:
            return "", False

    def _save(self, raw: bytes, round_no: int, candidate_no: int) -> str:
        name = (
            "img_v8756_"
            + dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            + f"_r{round_no}_c{candidate_no}.png"
        )
        path = self.artifact_dir / name
        path.write_bytes(raw)
        return str(path)

    def generate(self, text: str) -> dict:
        ok, status = self.available()
        if not ok:
            return {"ok": False, "reply": status, "confidence": 0.96}

        spec = self.parser.parse(text)
        all_candidates: list[ImageCandidate] = []
        repairs: tuple[str, ...] = ()

        for round_no in range(1, self.rounds + 1):
            round_best: ImageCandidate | None = None
            for candidate_no in range(1, self.candidates + 1):
                variant = (round_no - 1) * self.candidates + candidate_no - 1
                prompt = compose_prompt(spec, repairs, variant)
                negative = compose_negative(spec)
                try:
                    out = self.http_json(
                        self.image_base + "/sdapi/v1/txt2img",
                        method="POST",
                        data={
                            "prompt": prompt,
                            "negative_prompt": negative,
                            "steps": self.steps,
                            "cfg_scale": self.cfg,
                            "width": spec.width,
                            "height": spec.height,
                            "seed": -1,
                            "batch_size": 1,
                            "n_iter": 1,
                        },
                        timeout=240,
                    )
                    images = (out or {}).get("images") or []
                    if not images:
                        continue
                    payload = str(images[0])
                    clean_b64 = payload.split(",", 1)[-1]
                    raw = base64.b64decode(clean_b64)
                    if not raw.startswith(b"\x89PNG\r\n\x1a\n") and not raw.startswith(b"\xff\xd8"):
                        continue
                    path = self._save(raw, round_no, candidate_no)
                    caption, verified = self._interrogate(clean_b64)
                    score, missing = score_caption(spec, caption)
                    if not verified:
                        # Generation succeeded, but do not invent a semantic
                        # inspection result when CLIP interrogation is absent.
                        score = 0.55
                        missing = ()
                    candidate = ImageCandidate(
                        round_no=round_no,
                        candidate_no=candidate_no,
                        path=path,
                        prompt=prompt,
                        negative_prompt=negative,
                        caption=caption,
                        score=score,
                        visual_verified=verified,
                        missing_terms=missing,
                    )
                    all_candidates.append(candidate)
                    if round_best is None or candidate.score > round_best.score:
                        round_best = candidate
                except Exception:
                    continue

            if round_best is None:
                continue
            if round_best.visual_verified and round_best.score >= self.pass_score:
                break
            repairs = round_best.missing_terms
            if round_best.visual_verified and not repairs:
                break

        if not all_candidates:
            return {
                "ok": False,
                "reply": "画像生成モデルには接続できましたが、有効な画像候補を生成できませんでした。",
                "confidence": 0.82,
                "image_orchestrated": True,
                "image_spec": asdict(spec),
            }

        best = max(all_candidates, key=lambda x: (x.score, x.visual_verified, -x.round_no))
        name = Path(best.path).name
        verified_note = (
            f"CLIP自己検査 score={best.score:.3f}"
            if best.visual_verified
            else "画像は生成済みですが、実画像の意味検査は未接続です"
        )
        return {
            "ok": True,
            "reply": (
                "FAP Image Orchestratorで画像を生成しました。\n"
                f"{verified_note}\n"
                f"round={best.round_no}, candidates={len(all_candidates)}"
            ),
            "confidence": 0.97 if best.visual_verified and best.score >= self.pass_score else 0.88,
            "image_orchestrated": True,
            "image_spec": asdict(spec),
            "image_score": best.score,
            "visual_verified": best.visual_verified,
            "visual_caption": best.caption,
            "repair_missing": list(best.missing_terms),
            "generation_rounds": max(x.round_no for x in all_candidates),
            "candidate_count": len(all_candidates),
            "artifacts": [{"type": "image", "src": "/artifacts/" + name, "name": name}],
        }
