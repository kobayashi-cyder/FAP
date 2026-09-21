# FAP latest development snapshot

Current mainline: **V87.33 — Scene Object Registry**.

V87.33 fixes the object-coverage and UI-constraint problems exposed by the
Media Lab prompt `鳥と犬`.

Root causes:
- V87.31/V87.32 could parse bird/cat/car/horse as required objects;
- the actual supported set was hard-coded to human + dog only;
- gray text in the Hard constraints box was HTML placeholder text, so it looked
  active even though it was not submitted.

V87.33 replaces the fixed pair with an Object Registry.

Native object coverage:
- human
- dog
- bird
- cat
- horse
- car

Exact screenshot-case verification:

```text
Prompt: 鳥と犬
Constraints actually entered:
  被写体を中央に保つ
  写真風

required objects: bird, dog
generated objects: bird, dog
object score: 1.0
layout score: 1.0
requested style: photorealistic
photo-look style sub-score: 0.58
accepted: no
reason: photorealism_not_yet_verified
```

The bird is now explicit native geometry with body, head, beak, eye, wing,
tail, legs and feet. The generated Actions sample was visually inspected and
shows both dog and bird in the same scene.

UI correction:
- constraint placeholder now explicitly says it is an example;
- note states that only typed lines are submitted;
- result panel shows `constraints sent` so the user can confirm what actually
  reached the backend.

Verification:
- GitHub Actions V87.33 workflow PASS on Python 3.11 and 3.12;
- exact bird+dog regression PASS;
- all current registry categories build without unsupported gaps;
- V87.32 regression PASS;
- generated bird+dog sample visually inspected.

Run:

```text
RUN_FAP_V87_33_OBJECT_REGISTRY_LAB.cmd
```

Boundary:
- object geometry is still native procedural geometry;
- this release broadens semantic/object coverage, not photorealistic synthesis;
- a real photo request remains fail-closed until a verified learned refiner is
  available.

Compatibility:
- V87.32 photo-look renderer remains underneath;
- V87.31 Scene Graph and compliance logic remain;
- V87.30 Human LBS remains;
- V87.29 native raster remains;
- chat-speed restoration remains;
- Qwen is not used.
