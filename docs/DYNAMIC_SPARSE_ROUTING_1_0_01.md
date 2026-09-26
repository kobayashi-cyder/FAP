# FAP 1.0.01 Dynamic Sparse Routing

## Purpose

FAP 1.0.01 introduces a public-safe routing core that treats sparsity as an
adaptive intelligence mechanism rather than only a memory or speed optimization.

The target is stronger general reasoning and routing quality. GPT-5.6 Sol level
is an aspiration and benchmark target, not a claimed current capability.

## Design

The route graph starts slightly dense. The default initial directed-edge density
is 0.38 with a minimum outgoing degree so each route has alternatives.

During warm-up, FAP keeps that exploratory graph relatively dense. After enough
observations, low-value edges decay and the graph moves toward a sparse target
around 0.22. Easy, familiar work can move closer to the configured sparse floor.

The graph is not permanently pruned. High uncertainty, novelty, verifier
disagreement, or repeated failure raises the target density and reactivates
dormant edges. This creates dynamic sparsity:

1. explore with a mildly dense graph;
2. reinforce useful routes and transitions;
3. sparsify routine work;
4. reopen alternatives when confidence falls;
5. reinforce the newly verified route if it succeeds.

## Smart routing layer

Each route score combines reusable evidence only:

- prior and learned route utility;
- task-family fit;
- task-form fit;
- required-capability fit;
- failure-class specialty;
- exploration bonus for under-used routes;
- bounded cost penalty;
- activation propagated from neighboring active routes.

The graph therefore learns both which node to use and which transition structure
is worth keeping active.

## Learning constraints

The router may learn from abstract reusable signals such as:

- task family;
- task form;
- capability requirements;
- failure class;
- verification success;
- reward;
- latency;
- uncertainty;
- novelty;
- verifier disagreement.

It does not store benchmark question text, answer strings, question IDs, or
answer-key fingerprints.

## Density policy

Default operating shape:

- initial density: 0.38;
- routine sparse target: 0.22;
- sparse floor: 0.16;
- temporary re-densification under risk: up to the initial density;
- minimum outgoing connectivity remains protected.

These values are bounded configuration, not measured optimal constants. They
should be tuned only through generalization and holdout benchmarks.

## Intelligence target

The routing objective is not merely lower compute. It is to allocate more of a
fixed compute budget to the routes that repeatedly produce verified results,
while retaining enough exploratory capacity to recover from unfamiliar tasks.

Claims of GPT-5.6 Sol equivalence or superiority require independent task-level
benchmarks, holdout isolation, latency/compute accounting, and regression gates.
A routing benchmark alone cannot establish model-level intelligence equivalence.
