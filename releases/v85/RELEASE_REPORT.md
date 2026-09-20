# V85 Release Report — Production Vision Wiring

## Implemented

- explicit production Vision binding;
- mandatory wrapping through V83 `CallableVisionAdapter`;
- mapper support for non-`VisualIR` Vision outputs;
- fail-closed missing-backend behavior;
- no implicit `PrimitiveVision` production fallback;
- Visual Skill Graph execution through the externally supplied Vision on initial and repaired candidates;
- production manifest exposing backend name and feedback/fallback guarantees.

## Verification

The V85 suite checks missing-backend rejection, direct `VisualIR` callbacks, mapped raw outputs, invalid mapper rejection, manifest guarantees, and repeated Vision invocation after a repair.

CI also runs V84 through V78 regression suites on Python 3.11 and 3.12.
