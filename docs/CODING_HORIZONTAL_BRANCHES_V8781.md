# FAP V87.81 Horizontal Coding Branch Registry

Base/integration branch: `integration/coding-horizontal-v8781`

All branches below fork from the same integration-policy baseline. They are parallel workstreams, not release versions.

| Branch | Primary scope |
|---|---|
| `horiz/coding-plan-quality` | task decomposition, path/operation planning quality |
| `horiz/coding-context-retrieval` | repository context selection, symbol/file retrieval |
| `horiz/coding-dependency-impact` | reverse dependency and affected-test analysis |
| `horiz/coding-multifile-transaction` | coherent multi-file edit transactions |
| `horiz/coding-symbol-edit` | symbol-level AST/code transformations |
| `horiz/coding-diff-minimizer` | smallest safe patch/diff generation |
| `horiz/coding-repair-loop` | bounded repair quality and failure feedback |
| `horiz/coding-test-selection` | automatic focused/regression test selection |
| `horiz/coding-test-generation` | bounded test generation for changed behavior |
| `horiz/coding-python` | Python-specific coding capability |
| `horiz/coding-js-ts` | JavaScript/TypeScript coding capability |
| `horiz/coding-shell` | shell/PowerShell/cmd editing and validation |
| `horiz/coding-config` | JSON/YAML/TOML/config transformations |
| `horiz/coding-docs` | Markdown/docs/code-documentation changes |
| `horiz/coding-chat-bridge` | conversation -> coding-task routing and handoff |
| `horiz/coding-session-handoff` | cross-chat state/plan continuity |
| `horiz/coding-fuzz` | randomized coding/correction corpus and robustness |
| `horiz/coding-benchmark` | coding benchmarks, measurements and scorecards |
| `horiz/coding-performance` | latency, indexing and execution efficiency |
| `horiz/coding-security` | safety gates, path policy, command policy |
| `horiz/coding-api-contract` | shared schemas/interfaces across coding modules |
| `horiz/coding-release-packaging` | packaging/integration artifacts without main promotion |

## Status convention

- **active**: branch exists and may be worked on.
- **ready**: focused scope is implemented and CI is green.
- **integrated**: selected work has merged into `integration/coding-horizontal-v8781`.
- **deferred**: branch stays available but is intentionally not part of the current integration set.

The repository branch itself is the source of truth for existence. This registry defines scope and integration intent.
