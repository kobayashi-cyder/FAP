# FAP latest development snapshot

Current additive development release: **V64 — Verified Runtime Dispatch + Canary A/B**.

Source, cumulative tests and validation reports are stored under [`releases/v64/`](releases/v64/).

V64 verifies active skill slot integrity at load time, supports deterministic canary routing through a trusted sandbox-runner bridge, compares verified baseline/active outcomes, rolls back regressions, feeds demoted candidates to Failure Memory, and exports a sanitized Android active-state manifest.

Validation performed for this increment: **19/19 V64 delta tests PASS**, compileall PASS, warnings-as-errors PASS. V63 baseline remained recorded as 63/63 PASS. Synthetic demo results are mechanism validation only, not a public benchmark or Sol-parity claim.

Project continuation context from the ChatGPT development session is stored in [`FAP_DEVELOPMENT_CHAT_CONTEXT.md`](FAP_DEVELOPMENT_CHAT_CONTEXT.md). It records the V61-V64 decisions, safety/verification contract, GitHub workflow policy, and the V65 continuation target.
