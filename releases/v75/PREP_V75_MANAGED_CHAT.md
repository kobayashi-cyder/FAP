# V75 candidate — Managed bounded chat

Status: implementation candidate, non-main.
Base/rollback anchor: main V74 `0c5e04941986597014bf2e1141958be28bd82e23`.

## Goal
Add practical chat controls while preserving FAP's low-RAM objective.

## Scope
- explicit `:clear`, `:undo`, `:status`, and `:mode <name>` controls;
- preserve existing `:brief/:normal/:rich/:verbose` behavior;
- bound history by exchange count and character budget;
- return full assistant response while storing a clipped copy when necessary;
- prune oldest complete user/assistant pairs, never half an exchange;
- reject oversized user input;
- status reports counts only, not message content.

## Non-claims
This is history/control management, not a new language model or proof of better answer quality.

## Promotion
Require focused tests, V74-V69 regressions, V66-V68 core regressions, compileall, and same-HEAD
Python 3.11/3.12 CI.
