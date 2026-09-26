# FAP V87.16 — Observed Media Portfolio Competition

V87.16 removes another single-model bottleneck.

Instead of trusting one image/video generator, FAP can now run multiple generation backends as candidate lanes under the same observation and critic stack.

Loop:

`prompt -> backend A/B/C -> observe each actual artifact -> same critics -> choose best -> repair best defects -> re-compete`

Properties:
- every candidate is observation-gated through V87.15;
- all candidates are judged by the same critic stack;
- the highest verified non-fatal candidate wins each round;
- one backend failure does not invalidate healthy alternatives;
- if all lanes fail, the round fails closed;
- the best historical candidate survives later regressions;
- repair instructions derive from the current best verified candidate;
- image and video requests use the same portfolio controller.

This does not claim any bundled backend exceeds a frontier generator. The purpose is to let FAP combine replaceable generators and select/refine the best evidence-backed output instead of inheriting the limitations of a single provider.
