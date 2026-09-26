from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Iterable

from .engine import EngineConfig


_STAGES = {"candidate", "testing", "shadow", "active", "rejected"}


@dataclass
class MediaSkillRecord:
    engine: EngineConfig
    stage: str = "candidate"
    verified_successes: int = 0
    verified_failures: int = 0
    distinct_digests: tuple[str, ...] = ()
    score_ema: float = 0.0
    last_reason: str = ""

    @property
    def skill_id(self) -> str:
        return f"media.generate.{self.engine.media_type}:{self.engine.engine_id}"

    def to_dict(self) -> dict:
        engine = asdict(self.engine)
        engine["token_env"] = self.engine.token_env
        return {
            "skill_id": self.skill_id,
            "engine": engine,
            "stage": self.stage,
            "verified_successes": self.verified_successes,
            "verified_failures": self.verified_failures,
            "distinct_digests": list(self.distinct_digests),
            "score_ema": self.score_ema,
            "last_reason": self.last_reason,
        }


class MediaSkillRegistry:
    """Persistent fail-closed lifecycle for side-effecting media generation skills."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.records: dict[str, MediaSkillRecord] = {}
        if self.path and self.path.is_file():
            self._load()

    def register_engine(self, config: EngineConfig) -> MediaSkillRecord:
        config.validate()
        skill_id = f"media.generate.{config.media_type}:{config.engine_id}"
        old = self.records.get(skill_id)
        if old:
            return old
        record = MediaSkillRecord(config)
        self.records[skill_id] = record
        self._save()
        return record

    def eligible(self, media_type: str) -> list[MediaSkillRecord]:
        rows = [
            record for record in self.records.values()
            if record.engine.media_type == media_type and record.stage != "rejected"
        ]
        rank = {"active": 0, "shadow": 1, "testing": 2, "candidate": 3}
        rows.sort(key=lambda r: (rank[r.stage], -r.score_ema, r.engine.engine_id))
        return rows

    def record_outcome(
        self,
        skill_id: str,
        *,
        digest: str,
        score: float,
        passed: bool,
        independent: bool,
        reason: str,
    ) -> MediaSkillRecord:
        record = self.records[skill_id]
        if not independent:
            record.verified_failures += 1
            record.last_reason = "non_independent_evidence"
            self._save()
            return record

        score = max(0.0, min(1.0, float(score)))
        record.score_ema = (
            score if record.verified_successes + record.verified_failures == 0
            else 0.35 * score + 0.65 * record.score_ema
        )
        fresh = bool(digest) and digest not in record.distinct_digests
        if passed and fresh:
            record.verified_successes += 1
            record.distinct_digests = tuple((*record.distinct_digests, digest)[-32:])
            if record.stage == "candidate":
                record.stage = "testing"
            elif record.stage == "testing" and record.verified_successes >= 2:
                record.stage = "shadow"
            elif (
                record.stage == "shadow"
                and record.verified_successes >= 3
                and record.score_ema >= 0.85
            ):
                record.stage = "active"
            record.last_reason = reason or "verified_success"
        elif not passed:
            record.verified_failures += 1
            record.last_reason = reason or "verified_failure"
            if record.verified_failures >= 3 and record.verified_successes == 0:
                record.stage = "rejected"
        else:
            record.last_reason = "duplicate_digest_not_counted"
        self._save()
        return record

    @classmethod
    def discover_from_environment(
        cls,
        registry: "MediaSkillRegistry",
        *,
        variable: str = "FAP_MEDIA_ENGINES_JSON",
    ) -> list[MediaSkillRecord]:
        raw = os.environ.get(variable, "").strip()
        if not raw:
            return []
        try:
            values = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{variable} is invalid JSON") from exc
        if not isinstance(values, list):
            raise ValueError(f"{variable} must contain a list")
        discovered = []
        for item in values:
            if not isinstance(item, dict):
                raise ValueError("media engine descriptor must be an object")
            allowed = {
                "engine_id", "media_type", "endpoint", "token_env",
                "timeout_s", "max_bytes", "max_polls", "poll_interval_s",
            }
            if not set(item).issubset(allowed):
                raise ValueError("media engine descriptor contains unknown fields")
            config = EngineConfig(**item)
            discovered.append(registry.register_engine(config))
        return discovered

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "fap.autonomous-media-skills.v1",
            "records": [self.records[k].to_dict() for k in sorted(self.records)],
        }
        fd, tmp = tempfile.mkstemp(prefix=self.path.name + ".", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def _load(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("schema") != "fap.autonomous-media-skills.v1":
            raise ValueError("unsupported media skill registry schema")
        rows = payload.get("records")
        if not isinstance(rows, list):
            raise ValueError("invalid media skill registry records")
        for raw in rows:
            engine = EngineConfig(**raw["engine"])
            engine.validate()
            stage = raw["stage"]
            if stage not in _STAGES:
                raise ValueError("invalid media skill stage")
            record = MediaSkillRecord(
                engine=engine,
                stage=stage,
                verified_successes=int(raw["verified_successes"]),
                verified_failures=int(raw["verified_failures"]),
                distinct_digests=tuple(str(x) for x in raw["distinct_digests"]),
                score_ema=float(raw["score_ema"]),
                last_reason=str(raw["last_reason"]),
            )
            if raw["skill_id"] != record.skill_id:
                raise ValueError("media skill identity mismatch")
            self.records[record.skill_id] = record
