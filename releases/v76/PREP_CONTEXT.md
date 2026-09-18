# V76 preparation context

Status: preparation only; never write directly to main.
Inherited main SHA: `64619fbfe3967868a88085c4c4084ddcce4759ac` (V75).
Rollback anchor: same SHA.

## Changed surfaces inherited from V75
- managed bounded chat package and focused tests;
- V75 managed-chat verification workflow;
- explicit chat controls, bounded exchange/history storage, clipping/pruning and input rejection.

## Compatibility constraints
- Preserve V75 `:clear`, `:undo`, `:status`, `:mode <name>` semantics and legacy `:brief/:normal/:rich/:verbose` modes.
- Preserve complete user/assistant exchange boundaries while pruning.
- Keep full returned assistant output distinct from clipped stored history.
- Do not claim model-intelligence gains from history/control management.
- Retain V69-V75 behavior and V66-V68 core compatibility unless V76 explicitly versions an interface.

## Likely implementation targets
- harden managed-chat persistence/restart behavior and deterministic budget accounting;
- expose a narrow integration contract suitable for Android callers without coupling UI lifecycle to chat state;
- add provenance/version metadata where persisted state or packaged artifacts cross process boundaries.

## Regression hazards
- half-exchange pruning or undo after pruning;
- responder invocation for control commands;
- mode compatibility regressions;
- clipping the user-visible response instead of only stored history;
- status leaking message content;
- unbounded allocations from oversized input/history;
- persistence schema drift across app/process restart.

## Android / packaging implications
- keep history budgets explicit for low-RAM devices;
- make state serialization bounded and restart-safe before wiring into APK lifecycle;
- avoid Android-specific dependencies in the core Python behavior;
- package/version any persisted schema so APK upgrades can reject or migrate incompatible state deterministically.

## Required verification
- V75 focused managed-chat tests;
- control commands bypass responder;
- pair-preserving count/character pruning, clipping, undo and oversized/empty input rejection;
- restart/serialization round trip if persistence is introduced;
- V69-V75 regressions plus V66-V68 core regressions;
- compileall and independent Python 3.11/3.12 CI;
- Android/package smoke check for any new integration artifact.

## Likely next planned experiment
Persist a maximally-budgeted managed-chat session, restart/reload it, execute undo/status/mode operations, then compare deterministic state/accounting with an uninterrupted session while confirming bounded memory and no content leakage in status.
