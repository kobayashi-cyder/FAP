# FAP V87.36 — Scientific Geometry: DNA

V87.36 adds a parametric scientific geometry path for DNA.

Verified B-DNA parameters:
- two antiparallel backbone strands;
- right-handed helix;
- diameter: 2.0 nm;
- rise: 0.34 nm per base pair;
- 10.5 base pairs per turn;
- pitch: 3.57 nm;
- exact requested base-pair count;
- exact A/T/G/C sequence when supplied;
- Watson-Crick complementary strand.

The scientific values are kept in nm. A separate render scale converts them to
the native 3D renderer, so the scientific metadata is not confused with screen
coordinates.

Example:

```text
20塩基対のB-DNA
配列: ATGCCGTAGCTAACGTTGCA
斜めから
```

A-DNA and Z-DNA parameter sets can be constructed, but V87.36 deliberately
fails them closed because the acceptance critic is currently calibrated for
B-DNA only.

Run:

```text
RUN_FAP_V87_36_SCIENTIFIC_DNA_LAB.cmd
```

No external model or Qwen component is used.
