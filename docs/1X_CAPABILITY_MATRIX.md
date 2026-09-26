# FAP 1.x capability matrix

| Area | 1.0.01 state | Evidence / limit |
|---|---|---|
| Adaptive compute | integrated | public r001 bounded budget |
| Dynamic sparse routing | integrated core | mechanism tests/benchmark; not model-equivalence evidence |
| Session continuity | integrated | bounded per-session history enters routing demand/context |
| Semantic memory | integrated optional layer | explicit goals/constraints/preferences/facts are compacted and retrieved by session |
| Verified tool routing | integrated | failed verification rejects the route and allows fallback |
| Repository coding | integrated adapter | RepositoryCodingCoordinator enters the same routing contract; source/main mutation remains separately gated |
| Speech | integrated boundary | local TTS + bounded/trainable STT; open dictation remains evidence-gated |
| Browser self-improvement | integrated tool | bounded worktree proposal/verification; browser reasoning may depend on an external ChatGPT session |
| Native C/C++ | integrated r008 subtree | deterministic core, 128-lane response planner, C ABI and native UI trace; Python/tool/platform surfaces remain adapter boundaries |
| Android voice | integrated adapter | package/path normalized to 1.x; device latency/reliability still needs real-device measurement |
| Response intelligence | integrated | adaptive 6–128 response lanes, 16 read-only specialist/exploration paths, coverage auditing and bounded synthesis; not equivalent to 128 independent models |\n| Request deliberation routing | integrated on r009 side branch | infers intent/constraint/verification/counterexample/correction pressure and feeds routing + lane ordering; broad intelligence gain still requires holdout measurement |
| Generated E2E evaluation | integrated | fresh per-run arithmetic, memory tokens, session lengths and coding goals; validates plumbing, not broad intelligence |
| General intelligence | unverified target | requires independent unseen task benchmarks against named baselines |

Promotion policy: unmeasured capabilities stay labelled unverified.
