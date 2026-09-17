# FAP latest development snapshot

Current additive development release: **V66 — Attested Production Evidence + Statistical Canary Repair Loop**.

Source, cumulative release files and validation reports are stored under [`releases/v66/`](releases/v66/).

V66 authenticates trusted-wrapper execution results with HMAC-SHA256 attestations, authenticates complete production telemetry rows with a separate FAP runtime HMAC, rejects duplicate attestation reuse and stale-stage evidence, advances 5% -> 20% -> 50% -> 100% only at conservative statistical evidence checkpoints, requires fresh verified untouched holdout evidence to clear quarantine, automatically emits Skill Factory repair requests after quarantined rollback, and feeds verified production evidence back into a descriptive Capability Matrix.

Validation performed for this increment: **28/28 V66 delta tests PASS**, **64/64 V65+V66 local cumulative tests PASS**, compileall PASS, warnings-as-errors PASS, synthetic V66 end-to-end mechanism demo PASS. The statistical gate is a practical conservative control mechanism, not a formal sequential clinical-trial procedure. The synthetic demo is not a public benchmark or Sol-parity claim.

Project continuation context from the ChatGPT development session is stored in [`FAP_DEVELOPMENT_CHAT_CONTEXT.md`](FAP_DEVELOPMENT_CHAT_CONTEXT.md).
