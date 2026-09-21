# FAP V87.11 — Sol-gap reduction report

This release does **not** claim model parity with GPT-5.6 Sol. It targets harness-level gaps that can be improved without installing a frontier model on the Pixel.

## Gaps addressed

- raw conversation window: 24 -> 160 turns;
- persistent explicit goal/constraint/fact ledger beyond raw history;
- multiple independent intents in one turn can execute multiple organs and integrate results;
- distilled circuits now produce multiple candidate plans with an explicit selected plan;
- a coverage critic supplements the legacy verifier;
- one deterministic replan round is available for failed procedural chat with a retained goal;
- unknown factual questions preserve the existing no-fabrication boundary;
- V87.10 Program IR code generation remains available.

## Gaps not solved by this release

- frontier-scale world knowledge;
- million-token semantic attention;
- neural semantic generalization comparable to a large reasoning model;
- arbitrary multi-file software engineering from unrestricted natural language;
- rich vision/computer-use perception;
- learned tool selection over an open-ended tool ecosystem.

Those require either substantially more learned state/model capacity, external retrieval/tools, or additional distilled capabilities. V87.11 deliberately does not pretend otherwise.
