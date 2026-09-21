# V87.12 readable source tree

V87.12 runtime sources are expanded into the normal repository tree for direct GitHub review.

Core source files at repository root include:
- fap_semantic_memory.py
- fap_sol_gap_controller.py
- fap_program_synth.py
- fap_code_generator.py
- fap_spec_builder.py
- fap_v87_03_distilled_gateway.py through fap_v87_12_semantic_adaptive_gateway.py

Tests are under tests/, the chat UI is under web/, and protocol docs are under docs/.

The exact packaged runtime remains at:
releases/runtime_packages/FAP_V87_12_SEMANTIC_ADAPTIVE_RUNTIME.zip

Version-specific V87.12 documents are stored in releases/v87_12/.
The repository-level FAP_LATEST.md is intentionally left untouched so newer mainline releases are not rolled back.
