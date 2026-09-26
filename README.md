# FAP

FAP is the public mainline of the project.

## Current release candidate

- Stable mainline: **V1.0.01**
- Public base retained: **1.0.0**
- Included adaptive-budget revision: **1.0.0-r001**
- Canonical version file: [`VERSION`](VERSION)
- Development branch before promotion: `side/1.0.01-dynamic-sparse-routing`

## 1.0.01 dynamic sparse routing

FAP 1.0.01 keeps the public-safe r001 adaptive reasoning budget and adds a
learned dynamic-sparse routing layer above it.

The routing graph begins mildly dense so several reusable routes can compete.
After warm-up, routine work sparsifies toward a bounded target. Uncertainty,
novelty, verifier disagreement, and reusable failure evidence can temporarily
re-densify the graph or replace weak active edges with more relevant dormant
edges.

The actual `InteractionFabric` is integrated with this router. Existing endpoint
probe scores remain per-turn routing hints, while reusable route utility,
task/capability affinity, failure specialization, graph propagation, and bounded
beam search determine which route or fallback sequence is tried.

The router may export/import only bounded generic learning state such as route
utility, abstract affinities, edge weights, and usage counts. Benchmark question
text, exact answers, question IDs, and answer fingerprints are not stored.

## Public verification

- Dynamic sparse core: `fap_dynamic_sparse_routing.py`
- Runtime integration: `fap_interaction_fabric.py`
- Latest gateway: `fap_v1_0_01_dynamic_sparse_routing_gateway.py`
- Mechanism benchmark: `fap_v1_0_01_sparse_benchmark.py`
- r001 bounded adaptive budget: `fap_revision_r001.py`
- Design: `docs/DYNAMIC_SPARSE_ROUTING_1_0_01.md`
- Intelligence target: `docs/INTELLIGENCE_TARGET_1_0_01.md`

## Intelligence target

GPT-5.6 Sol-class task performance is a target, not a current claim. Routing
mechanism tests cannot establish model-level equivalence. Such a claim requires
independent unseen holdouts, per-domain accuracy, calibration, tool/routing
accuracy, route-selection regret, latency/compute accounting, timeout rates, and
regression gates.
