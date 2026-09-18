# Decision — V75 Managed Chat

Decision: KEEP for main integration review.

Independent GitHub Actions passed on Python 3.11 and 3.12 after fixing the small-context
default-limit bug without weakening tests:
- V75 focused managed-chat tests: PASS;
- V74/V73/V72/V71/V70/V69 regressions: PASS;
- V66 operational 28/28 PASS;
- V67 code-factory 28/28 PASS;
- V68 code-factory 34/34 PASS;
- compileall PASS.

Verified behavior:
- :clear, :undo, :status and :mode controls;
- legacy :brief/:normal/:rich/:verbose controls remain compatible;
- exchange and character budgets preserve complete user/assistant pairs;
- full assistant response is returned while retained history may be deterministically clipped;
- oversized input is rejected;
- status exposes counts/budgets but not message content.

This improves bounded conversation management, not model intelligence or answer quality.

Rollback anchor: main V74 `0c5e04941986597014bf2e1141958be28bd82e23`.
