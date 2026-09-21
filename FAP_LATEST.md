# FAP latest development snapshot

Current mainline: **V87.36 — Scientific Geometry: DNA + V87.35 Cat Morphology**.

V87.35 adds composable cat appearance traits:
- 三毛 / calico;
- 八割れ / hachiware;
- キジトラ;
- サバトラ;
- 茶トラ;
- サビ / tortoiseshell.

These are attributes on a cat node rather than separate cat classes. The
patterns are painted directly onto the native cat mesh and verified by the
morphology critic.

Example:

```text
三毛の八割れ猫
```

becomes:

```text
kind = cat
coat_pattern = calico
face_pattern = hachiware
```

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

Scientific values remain in nanometers. Rendering uses a separate scale so
scientific metadata is not confused with screen coordinates.

Example:

```text
20塩基対のB-DNA
配列: ATGCCGTAGCTAACGTTGCA
斜めから
```

A-DNA and Z-DNA parameter sets can be constructed, but V87.36 deliberately
fails them closed because acceptance verification is currently calibrated for
B-DNA only.

Latest unified chat routing:
- DNA requests -> V87.36 Scientific Geometry;
- 三毛 / 八割れ / tabby-pattern cat requests -> V87.35 Morphology;
- other image prompts -> V87.34 Scene Graph 2;
- rendering remains on the V87.32 native photo-look path underneath.

Run standard latest chat:

```text
RUN_FAP_CHAT_LATEST.cmd
```

Run DNA lab directly:

```text
RUN_FAP_V87_36_SCIENTIFIC_DNA_LAB.cmd
```

Compatibility:
- V87.34 Scene Graph 2 remains;
- V87.33 Object Registry remains;
- V87.32 photo-look renderer remains;
- V87.30 Human LBS remains;
- V87.29 native raster remains;
- reasoning/physics paths remain;
- chat-speed restoration remains;
- Qwen is not used.
