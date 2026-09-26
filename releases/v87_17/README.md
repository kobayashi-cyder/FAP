# FAP V87.17 — Adaptive Media Fast Path

Goal: reduce the number of generation/observation transitions required to reach the same verified quality gate.

V87.16 always evaluates the whole candidate portfolio in a round. V87.17 adds an adaptive fast path:

`best-known lane first -> observe -> critic -> accept immediately if gate passes -> expand only on miss`

When repair is needed:

`repair best verified defects -> retry narrow lane set -> expand only if still insufficient`

The router learns lightweight per-lane profiles from actual verified outcomes:
- score EMA;
- acceptance reliability;
- failure rate.

This means a backend that repeatedly succeeds moves to the front automatically, while unreliable lanes are tried later.

Expected transition reduction:
- ideal/common case with N lanes: from N generator/observer calls to 1;
- difficult case: falls back to full portfolio behavior;
- quality gate is unchanged;
- every candidate still passes V87.15 observation and the configured critic stack.

This is the first optimization explicitly aimed at beating a stronger model/system on **verified completion efficiency** rather than raw one-shot generator quality. It does not claim a universal quality lead over GPT-5.6 Sol or any frontier image/video generator.
