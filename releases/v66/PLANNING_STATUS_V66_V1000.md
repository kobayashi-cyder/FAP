# FAP V66–V1000 Planning Status

This roadmap and its generated per-version queue are **non-binding plans only**.

They are hypotheses, sequencing suggestions, and experiment candidates. Inclusion in the roadmap does **not** authorize implementation, promotion, merge to `main`, deployment, or retention.

For every planned version:

1. Re-check whether the experiment is still useful given the current codebase and evidence.
2. Replace or skip obsolete plans rather than preserving them for version-number consistency.
3. Run the experiment on a non-main branch.
4. Require independent evidence before any promotion decision.
5. End with one of `KEEP`, `MODIFY`, `KILL`, `DEFER`, or `REPLACE`.
6. `KILL`, `DEFER`, and `REPLACE` are valid successful outcomes of a planning version.
7. No future version number guarantees that all earlier planned items were implemented.
8. `main` represents accepted evidence-backed state, not roadmap completion percentage.

The detailed queue generator exists to prevent missing/duplicate version numbers and to make future work easy to inspect. It is not an autonomous implementation command.
