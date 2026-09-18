# FAP latest development snapshot

Current additive development release: **V67 — Native Repository Code Factory Stage 1 + Scoped Persistence Identity**.

Source, cumulative release files and validation reports are stored under [`releases/v67/`](releases/v67/).

V67 adds the first native source-code generation path to FAP: read-only repository context and symbol indexing, restricted Code IR -> executable Python source generation, SHA-bound path-safe patching, deterministic missing-import repair from runtime diagnostics, bounded multi-round test/repair, and hash-chained generation lineage. Generated code remains in a quarantine candidate workspace and enters the existing V62-V66 verification/promotion path; it is never auto-activated.

V67 also retains the independently CI-verified persistence-identity delta: capability-scoped event identity with copy-on-write migration/rollback while keeping attestation IDs and holdout evidence globally single-use.

Code-factory validation for this increment: **28/28 V67 delta tests PASS**, compileall PASS, warnings-as-errors PASS, synthetic generation/repair demo PASS. The persistence-identity track separately passed its GitHub Actions Python 3.11/3.12 matrix and V66 regression checks before its KEEP decision. Stage 1 is deliberately constrained and is not yet an unrestricted natural-language repository coder. These mechanism tests are not a public coding benchmark or Sol-parity claim.

Project continuation context from the ChatGPT development session is stored in [`FAP_DEVELOPMENT_CHAT_CONTEXT.md`](FAP_DEVELOPMENT_CHAT_CONTEXT.md).
