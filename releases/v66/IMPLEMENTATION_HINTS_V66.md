# FAP V66 — Implementation Hints

This file is intended as a concrete handoff for the next ChatGPT/Codex implementation cycle.

## 1. Start with the verification boundary, not new features

The first V66 change should make evidence independently machine-checkable.

Suggested minimal objects:

```python
@dataclass(frozen=True)
class EvidenceManifest:
    source_sha: str
    candidate_digest: str
    suite_id: str
    tests_total: int
    tests_passed: int
    compile_ok: bool
    warnings_as_errors_ok: bool
    canary_ok: bool
    rollback_ok: bool
    quarantine_ok: bool
    generated_at: str
    tool_version: str
```

Treat this as a transport format, not as truth by itself. Promotion logic must verify that the manifest matches independently observed candidate/source identifiers.

## 2. Fail closed on every identity mismatch

Recommended checks before any stage advancement:

- candidate digest equals the artifact actually evaluated,
- source SHA equals the checked-out commit,
- suite ID is recognized,
- all required fields exist,
- test totals are nonzero and internally consistent,
- manifest timestamp is within an explicit validity window if freshness matters,
- no stage references evidence produced for another stage/candidate.

A single mismatch should produce `REJECTED_EVIDENCE`, not a warning-and-continue path.

## 3. Make CI the independent witness

Add a GitHub Actions workflow dedicated to V66 candidate validation.

Suggested sequence:

1. checkout exact candidate SHA,
2. run `compileall` / syntax checks,
3. run warnings-as-errors checks,
4. run the V66 unit test suite,
5. run healthy staged-canary synthetic scenario,
6. run bad-candidate rollback scenario,
7. run repeated-regression quarantine scenario,
8. run evidence-tamper negative tests,
9. emit `evidence_manifest.json`,
10. upload the manifest and test logs as Actions artifacts.

Do not let the candidate itself choose or rewrite the CI command sequence.

## 4. Add negative tests before adding autonomy

High-value tests:

- valid manifest + wrong candidate digest -> reject,
- valid manifest + wrong source SHA -> reject,
- reused 5% evidence at 20% -> reject,
- stale telemetry after reconnect -> reject,
- duplicate failure event -> no double increment,
- rollback failure -> no promotion and explicit terminal error,
- quarantined family -> cannot silently re-enter canary,
- missing evidence artifact -> no promotion.

Negative tests are more important than another synthetic happy-path demo at this stage.

## 5. Preserve V65 trust boundaries

Do not weaken these properties while implementing V66:

- `SkillFactoryHandoff` accepts non-executable capability specifications only.
- candidate output cannot select the host command.
- `TrustedSandboxRunner` remains a transport to a separately trusted isolation boundary; do not describe it as a complete sandbox unless OS/container isolation is actually enforced.
- unverified telemetry must not affect promotion.
- Android state export must not reveal host slot paths.

## 6. Keep branch integration selective

When reviewing non-main branches, prefer cherry-picking/recreating the smallest coherent change over blind branch merging when histories contain listener metadata or unrelated generated release trees.

Before main integration, compare at least:

- changed executable files,
- tests added/changed,
- workflows changed,
- generated release metadata,
- inherited duplicate files.

Listener-only changes (`.fap-listener`, `MAIN_UPDATE_TRIGGER.md`) should not count as product value.

## 7. Android path hints

After V66 evidence is solid, prioritize the Android path.

Recommended harness properties:

- deterministic package/version identification,
- explicit device serial selection,
- timeout on every ADB operation,
- reconnect handling without treating reconnect as success,
- state export includes candidate digest and stage but excludes host paths,
- raw telemetry marked `verified=False` by default until identity checks complete.

The key invariant is: **device communication failure may pause or rollback deployment, but must never manufacture positive evidence**.

## 8. Failure Memory should become an evaluation source

Do not train/adjust directly against every failure record and then score on the same records.

Recommended split:

- `train/dev`: may inform candidate generation,
- `regression`: must remain passing,
- `holdout`: hidden from candidate-generation logic where feasible.

Store stable case IDs and hashes so later releases can prove which cases were evaluated.

## 9. Compression should be measured, not assumed

For future sparse/KC-style representations, collect these baselines first:

- total serialized bytes,
- cold-start time,
- resident RAM after activation,
- lookup latency p50/p95,
- exact-recall accuracy where exact recovery is required,
- semantic task score where lossy representation is allowed.

Only keep a new compressed representation if it wins against the current representation on a defined metric budget.

## 10. Suggested next concrete commit sequence

A low-risk implementation order:

1. `EvidenceManifest` schema + parser/validator.
2. Unit tests for malformed/tampered evidence.
3. Promotion gate wired to validator.
4. V66 GitHub Actions validation workflow.
5. Artifact emission from CI.
6. Integration test that binds candidate digest to evidence.
7. Android verification harness skeleton.
8. Replay corpus schema.

Each commit should be independently testable and avoid mixing refactors with behavior changes.

## 11. Main promotion checklist

Before proposing V66 for `main`, produce a short report containing:

- source branch and exact commit SHA,
- changed executable files,
- test command(s),
- exact pass/fail counts,
- CI run reference,
- `EvidenceManifest` digest,
- rollback/quarantine demo result,
- known limitations,
- proof that listener-only metadata is not the substantive reason for promotion.

If one of these is unavailable, leave V66 on its integration branch until the missing evidence exists.

## 12. Useful design principle

FAP should become more autonomous by reducing the amount of trust each autonomous step requires.

A good V66 outcome is not "FAP can change more things." It is:

> FAP can propose, test, reject, rollback, quarantine, and eventually promote more changes while every promotion requires less human guesswork and more reproducible evidence.
