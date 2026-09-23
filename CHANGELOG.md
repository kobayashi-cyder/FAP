# Changelog

## V87.80 — 2026-09-23

Current stable mainline.

- Multi-turn discourse consistency fuzz hardening.
- Stale-topic resurrection blocking after a newer unknown subject.
- Declarative transparent acknowledgements.
- Grammar-level explicit correction focus shared across conversation paths.
- V87.80 unified chat gateway and latest launchers.
- FCA remains optional; FAP remains standalone.
- PR #107 promoted V87.80 to `main`.
- PR #108 finalized canonical version synchronization.

Version-management convention from V87.80 onward:

1. `VERSION` is the canonical short version identifier.
2. `FAP_LATEST.md` is the detailed rolling engineering record.
3. `README.md` shows the stable release and links to the canonical files.
4. A version bump is complete only when runtime/gateway, latest launchers, `VERSION`, and release notes agree.

For detailed V87 history, see `FAP_LATEST.md`.
