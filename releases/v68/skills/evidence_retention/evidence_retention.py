from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Set


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    capability_id: str
    created_at: float
    protected: bool = False


@dataclass(frozen=True)
class RetentionPlan:
    keep_ids: tuple[str, ...]
    compact_ids: tuple[str, ...]


def plan_retention(
    records: Iterable[EvidenceRef],
    *,
    keep_latest_per_capability: int = 100,
    protected_ids: Iterable[str] = (),
) -> RetentionPlan:
    """Plan compaction without deleting protected or recent evidence."""
    if keep_latest_per_capability < 1:
        raise ValueError("keep_latest_per_capability must be >= 1")

    explicit: Set[str] = {str(x) for x in protected_ids}
    by_cap = defaultdict(list)
    seen = set()
    for rec in records:
        if not rec.evidence_id or not rec.capability_id:
            raise ValueError("evidence_id and capability_id are required")
        if rec.evidence_id in seen:
            raise ValueError(f"duplicate evidence_id: {rec.evidence_id}")
        seen.add(rec.evidence_id)
        by_cap[rec.capability_id].append(rec)

    keep = set(explicit)
    for rows in by_cap.values():
        rows.sort(key=lambda r: (float(r.created_at), r.evidence_id), reverse=True)
        keep.update(r.evidence_id for r in rows[:keep_latest_per_capability])
        keep.update(r.evidence_id for r in rows if r.protected)

    compact = sorted(seen - keep)
    return RetentionPlan(tuple(sorted(keep & seen)), tuple(compact))
