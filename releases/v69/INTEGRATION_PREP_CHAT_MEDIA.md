# Integration prep — V69 Chat + Media

User-priority candidate. Do not merge older media branches wholesale.

Selective source of truth for this candidate:
- releases/v69/interaction/fap_interaction/**
- releases/v69/interaction/tests/**
- V69 chat/media prep/test/decision documents
- dedicated CI workflow

Compatibility:
- additive only; does not mutate V68 code-factory state;
- no Android package/applicationId change;
- no persistence/schema migration;
- no provider secret or external dependency.

Rollback anchor: main V68 `929c419b3fcff55720e159b8f7f7f1d602dec305`.
Rollback action: remove/disable the additive V69 interaction package.

The older `skill/v69-android-provenance` branch is not part of this unit.
