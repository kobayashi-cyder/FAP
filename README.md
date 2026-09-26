# FAP

FAP is the public 1.x mainline. Legacy V2+ versioned implementations are intentionally excluded from the active tree.

## Current line

- Version: **1.0.01**
- Adaptive budget: `fap_revision_r001.py`
- Unified runtime: `fap_1x_runtime.py` — bounded sessions, semantic memory, verified tools and repository coding
- Ready-to-use local runtime: `fap_1x_standard_runtime.py` — factual QA, rule derivation, contextual reasoning, reflective conversation, and adaptive response intelligence
- Dynamic sparse routing: `fap_dynamic_sparse_routing.py` + `fap_interaction_fabric.py`
- Adaptive response intelligence: up to **128 response lanes**, **16 read-only specialist/exploration paths**, and a **16-lane synthesis committee**\n- Request deliberation routing: infers multi-intent, constraints, verification/counterexample pressure, correction/repair signals, and prioritizes response lanes accordingly
- Local speech: `fap_speech.py` / `fap_speech_fluent.py`
- Browser self-improvement: `fap_self_improvement_controller.py`
- Native deterministic core: `native_cpp/` — r008 response planning/C ABI/UI trace
- Android adapter: `android/`

## Integration rule

Only 1.x paths may be promoted to main. Canonical CI rejects tracked paths carrying legacy V2+ version names.

Generated E2E evaluation: `fap_1x_e2e_benchmark.py` uses fresh per-run cases for runtime plumbing. Performance claims remain evidence-gated: component/E2E mechanism tests do not establish GPT-5.6 Sol-class model equivalence.

See `docs/PUBLIC_1_0_01_CLEAN_INTEGRATION.md` and `docs/1X_CAPABILITY_MATRIX.md`.
