# FAP

FAP is the public, reset mainline of the project.

## Current release

- Stable public base: **1.0.0**
- Current revision: **1.0.0-r001**
- Canonical version file: [`VERSION`](VERSION)

The public repository was intentionally reset in September 2026. Historical development remains in Git history; active private development continues separately.

## Public scope

This repository is kept intentionally public-safe. Its role is to host reproducible experiments, lightweight verification, and GitHub Actions checks without exposing private-only implementation details.

Revision r001 adds a clean-room, answer-independent adaptive reasoning budget inspired by mechanisms that were first exercised on the private line: sparse-by-default routing, bounded compute growth under difficulty, deeper verification under uncertainty, and extra-path activation on low confidence, verifier disagreement, or counterexamples.

Private source code is not copied into the public repository. Only public-safe generalized mechanisms are reimplemented and independently testable here.
