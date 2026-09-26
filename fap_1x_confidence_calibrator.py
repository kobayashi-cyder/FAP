from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CalibrationResult:
    confidence: float
    tier: str
    components: dict[str, float]
    capped: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConfidenceCalibrator:
    """Conservative confidence mapping for heterogeneous reasoning lanes.

    The value is not presented as a proven empirical probability until an
    external calibration set is available. Tier caps prevent provisional or
    merely-supported candidates from inheriting generator overconfidence.
    """

    CAPS = {
        "verified": 0.985,
        "supported": 0.78,
        "provisional": 0.48,
        "unresolved": 0.10,
        "rejected": 0.02,
    }

    def calibrate(
        self,
        *,
        verification: str,
        generator_confidence: float,
        verifier_score: float = 0.0,
        evidence_count: int = 0,
        repeated_verification: bool = False,
        disagreement: bool = False,
    ) -> CalibrationResult:
        tier = str(verification or "unresolved")
        cap = self.CAPS.get(tier, 0.30)
        generator = max(0.0, min(1.0, float(generator_confidence)))
        verifier = max(0.0, min(1.0, float(verifier_score)))
        evidence = min(1.0, max(0.0, int(evidence_count)) / 6.0)

        if tier == "verified":
            raw = 0.56 + 0.18 * generator + 0.20 * verifier + 0.04 * evidence
            if repeated_verification:
                raw += 0.025
        elif tier == "supported":
            raw = 0.36 + 0.20 * generator + 0.15 * verifier + 0.05 * evidence
        elif tier == "provisional":
            raw = 0.20 + 0.15 * generator + 0.05 * evidence
        elif tier == "rejected":
            raw = 0.0
        else:
            raw = 0.04 + 0.05 * generator

        if disagreement:
            raw -= 0.18 if tier == "verified" else 0.12

        confidence = max(0.0, min(cap, raw))
        return CalibrationResult(
            confidence=round(confidence, 4),
            tier=tier,
            components={
                "generator": round(generator, 4),
                "verifier": round(verifier, 4),
                "evidence": round(evidence, 4),
                "repeat_bonus": 0.025 if repeated_verification and tier == "verified" else 0.0,
                "disagreement_penalty": 0.18 if disagreement and tier == "verified" else (0.12 if disagreement else 0.0),
            },
            capped=raw > cap,
        )
