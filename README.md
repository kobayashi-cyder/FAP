# FAP

FAP is the public 1.x mainline. Legacy V2+ versioned implementations are intentionally excluded from the active tree.

## Current line

- Version: **1.0.01**
- Adaptive budget: `fap_revision_r001.py`
- Unified runtime: `fap_1x_runtime.py`
- Dynamic sparse routing: `fap_dynamic_sparse_routing.py` + `fap_interaction_fabric.py`
- Local speech: `fap_speech.py` / `fap_speech_fluent.py`
- Browser self-improvement: `fap_self_improvement_controller.py`
- Native deterministic core: `native_cpp/`
- Android adapter: `android/`

## Integration rule

Only 1.x paths may be promoted to main. Canonical CI rejects tracked paths carrying legacy V2+ version names.

Performance claims are evidence-gated: component tests do not establish GPT-5.6 Sol-class model equivalence.

See `docs/PUBLIC_1_0_01_CLEAN_INTEGRATION.md` and `docs/1X_CAPABILITY_MATRIX.md`.
