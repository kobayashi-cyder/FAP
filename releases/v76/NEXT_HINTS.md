# V76 next hints

Base: main V75 `64619fbfe3967868a88085c4c4084ddcce4759ac`.

Prioritize restart-safe bounded chat state rather than adding broader features. First prove that the V75 control/history invariants survive serialization and process restart with deterministic budget accounting. Keep Android integration behind a narrow schema/versioned boundary and avoid increasing resident memory merely to retain conversation history.

Promotion gate: focused V76 tests plus unchanged V75 managed-chat suite, V69-V75 regressions, V66-V68 core regressions, compileall, Python 3.11/3.12 CI, and Android/package smoke verification if a packaged integration surface changes.

Rollback immediately to the inherited main SHA if persistence changes alter visible response text, invoke the responder for controls, split an exchange during pruning, leak content through status, or make old mode commands incompatible.
