# FAP latest development snapshot

Current additive development release: **V90 — Rebased Autonomous Improvement Core**.

Source, tests and integration notes are stored under [`releases/v90/`](releases/v90/).

V90 is the independently audited rebase of the Library artifact `FAP_V90_AUTONOMOUS_IMPROVEMENT_CORE.zip` onto the current mainline.

It does not copy the artifact's older duplicate V82-era subsystems. Instead it composes:
- V84 AbilityMap / Self Curriculum state;
- V86 Generic Skill Inventor + Generic Skill Graph;
- V82 sparse verifier-gated routing;
- current V78-V85 persistence and visual hardening.

V90 adds:
- FAP-Eval before/after benchmarking;
- failure clustering and bounded repair attempts;
- replay-protected autonomous improvement cycle IDs;
- local V86 Skill promotion followed by a second global evaluation gate;
- sparse deployment only when target ability improves and no measured ability regresses;
- revoke/rollback when staged or deployed Skills regress;
- bounded Skill Evolution over declarative verified-binding DAGs.

```text
FAP-Eval
  -> failure cluster
  -> V86 Skill candidate
  -> local verifier
  -> staged deployment
  -> global FAP-Eval
  -> accept into V82 sparse runtime OR revoke
  -> final scorecard / V84 AbilityMap
```

**Execution boundary:** V90 invents or mutates declarative Skill graphs only. It does not generate or execute arbitrary Python source.
