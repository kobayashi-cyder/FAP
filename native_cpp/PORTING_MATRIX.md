# FAP native porting matrix

Target: `1.0.01-cpp-native-r001`

| FAP capability | Native status | Notes |
|---|---|---|
| r001 adaptive compute budget | Native | Thresholds/bounds mirrored from public Python |
| low-confidence/disagreement/counterexample expansion | Native | Direct parity |
| semantic resource/action routing | Native | Reads `knowledge/*.jsonl`; dependency-free parser |
| semantic fabric route scoring | Partial native | Route match is native; endpoint handlers remain existing runtime concerns |
| persistent explicit goal/constraint/fact state | Native | JSON state, bounded histories |
| multi-intent planning | Native | Builder requests remain unfragmented |
| coverage critic | Native | Empty reply, missing artifact, weak constraint coverage, unknown boundary |
| compact semantic memory | Native core | UTF-8/Japanese bigram similarity, slots, merge, compaction, recall |
| distilled Python circuit activation | Adapter boundary | Python module data and dynamic import are not copied into C++ |
| repository planner/executor/verifier/promotion | Adapter boundary | Existing Python sandbox and AST tooling remain authoritative |
| Python AST / structured source rewriting | Python boundary | C++ parser substitution would change semantics; not silently replaced |
| research/frontier web workflows | Connector boundary | Network/API orchestration remains outside the native deterministic core |
| image/media generation | Runtime boundary | Native routing may select it; generator implementation is unchanged |
| Android UI / Chaquopy packaging | Platform boundary | C ABI is supplied for JNI/NDK migration |
| speech / browser / external tools | Platform boundary | Tool transport remains outside core |

## Migration rule

New deterministic algorithms should be implemented in `native_cpp` first when
they do not require Python reflection or Python-specific AST behavior. Python
can consume the stable C ABI during migration. Existing Python behavior remains
the compatibility oracle until equivalent native regression coverage exists.

## Next native slices

The highest-value next ports are:

1. semantic-fabric endpoint scoring and generic interaction scheduling;
2. repository security/path policy primitives;
3. repository dependency graph and test-selection logic;
4. deterministic diff/minimization utilities;
5. platform-neutral session serialization.

Promotion into the public mainline should happen only after cross-language
golden tests prove behavioral equivalence for the migrated surface.
