# Public FAP 1.0.01 Clean Integration Spine — 2026-09-26

Base: `side/1.0.01-dynamic-sparse-routing` (PR #163).

This branch is the clean merge-preparation surface for public FAP 1.x. It exists
because older lateral branches have divergent ancestry and can expose hundreds
of unrelated historical files when compared directly.

Integrated in this spine:
- 1.0.01 dynamic-sparse routing candidate;
- reset-line-aware release/version contract;
- r001 malformed/non-finite boundary hardening;
- public capability/evidence manifest;
- explicit promotion order for additive ports.

Rules:
1. Do not merge old lateral branches directly into main when their ancestry
   produces unrelated historical diffs.
2. Port only the capability-specific files onto a branch created from this spine.
3. A port must not replace VERSION, FAP_LATEST.md, current launchers, or the
   1.0.01 gateway unless the change is explicitly release-related.
4. Every port must preserve the public release contract and r001 regression gate.
5. r002 reasoning/evaluation remains blocked from promotion until its randomized
   generalization gate and full sweep are green.
6. Capability claims remain evidence-gated.

Port order:
1. release contract + r001 hardening (this branch);
2. speech;
3. Android voice;
4. C/C++ native alternate runtime;
5. browser/OpenAI self-improvement controller;
6. r002 reasoning/evaluation after blocker closure.
