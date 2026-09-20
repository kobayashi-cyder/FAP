# V85 Release Report — Production Vision Host Wiring

## Implemented

- explicit `VisionBackend` contract;
- fail-closed `ProductionVisionHost`;
- strict wrapper around V83 `CallableVisionAdapter`;
- concrete object-list -> `VisualIR` mapper;
- frame-dimension and geometry invariants;
- explicit rejection of `PrimitiveVision` as production;
- explicit bootstrap-only builder;
- production loop builder that requires backend configuration.

## Verification targets

1. production builder fails without a backend;
2. PrimitiveVision cannot be mislabeled as production;
3. bootstrap use remains explicitly available;
4. existing object-list Vision output maps into VisualIR;
5. production host drives the V83 render -> Vision -> diff loop;
6. out-of-frame production observations fail closed;
7. circle center/radius mapping is preserved.

The V85 workflow also runs V84, V83, V82, V81, V79/V80 and V78 regressions on Python 3.11 and 3.12.

## Boundary

V85 supplies production wiring, not a bundled external Vision model. A real backend must still be provided by the host application.
