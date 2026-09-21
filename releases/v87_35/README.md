# FAP V87.35 — Morphology + Cat Coat Pattern Engine

V87.35 adds composable appearance traits to the existing cat morphology.

Implemented cat coat patterns:
- calico / 三毛
- hachiware / 八割れ face mask
- tabby / キジトラ
- silver tabby / サバトラ
- orange tabby / 茶トラ
- tortoiseshell / サビ

These are attributes on a cat node rather than separate cat object classes.

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

The coat painter operates directly on the native cat mesh. Calico uses broad,
deterministic low-frequency black/orange patches over a white base. Hachiware
adds a coordinate-based white facial blaze. Requested patterns are verified by
the morphology critic.

No Qwen component is used.
