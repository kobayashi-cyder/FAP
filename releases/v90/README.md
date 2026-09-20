# FAP V90 — Rebased Autonomous Improvement Core

V90 is the independently audited and rebased form of the Library artifact `FAP_V90_AUTONOMOUS_IMPROVEMENT_CORE.zip`.

The artifact was not merged wholesale. Its bundled capability map, self-curriculum, sparse router, primitive Skill Inventor and old `fap_v82` copy are superseded by the current verified mainline:

- V84 Persistent Self-Generated Curriculum / AbilityMap;
- V86 Generic Skill Inventor + Generic Skill Graph;
- V82 Sparse Adaptive Circuit Orchestrator;
- V81 Local Adaptive Predictive Core.

V90 retains and modernizes the artifact's unique value:

- FAP-Eval benchmark harness;
- failure clustering;
- autonomous repair selection;
- bounded Skill Evolution over declarative V86 DAGs;
- local V86 promotion followed by a second global benchmark gate;
- sparse deployment only after global acceptance;
- automatic deployment revoke when the global benchmark regresses;
- replay-protected improvement-cycle ledger.

## Closed loop

```text
FAP-Eval baseline
  -> failure clusters
  -> select target ability
  -> proposal provider
  -> V86 Skill Inventor
  -> unit/boundary/determinism/shadow verification
  -> locally active Skill
  -> V90 staged deployment
  -> FAP-Eval with staged Skill
  -> no-regression + target-improvement gate
      -> accept -> V82 sparse runtime
      -> reject -> revoke/quarantine
  -> final FAP-Eval
  -> update V84 AbilityMap from final independently evaluated state
```

## Two different meanings of active

A V86 Skill can be locally `active` after unit and shadow evidence. V90 does not treat that as global deployment permission. It first stages the Skill and runs the broader FAP-Eval suite. Only a globally accepted Skill enters the V90 enabled runtime set.

## Skill Evolution

V90 `SkillEvolution` mutates only the declarative binding graph. It can replace or append already-verified bindings. Mutants are candidates only and receive no execution or promotion rights until they pass the normal V86 verifier.

## Artifact audit

See `ARTIFACT_AUDIT.md` for the exact source ZIP digest, reproducible standalone test counts and the mapping from the historical prototype to the current mainline.
