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


## Current mainline chat

The standard FAP CHAT UI can now talk to the current V87.33 mainline facade
instead of reporting only the older V87.12 backend version.

Run:

```text
RUN_FAP_CHAT_LATEST.cmd
```

The launcher starts `fap_v87_33_unified_chat_gateway.py` and opens the same
`web/FAP_Chat.html` UI. The badge is populated from `/api/v1/status`,
so the active backend reports `v87.33-unified-chat`.

Routing:
- ordinary conversation and semantic/adaptive memory retain the optimized V87.12 fast path;
- structured MCQ/scientific/physics requests retain V87.25-V87.28;
- image capability/generation uses V87.33 Object Registry with the V87.32
  photo-look renderer underneath;
- native scene objects are human, dog, bird, cat, horse and car;
- rejected photo-style candidates remain visible but are not falsely reported
  as accepted;
- Qwen is not used.

The stable launcher also detects an older FAP Core already listening on port
11439. It leaves that process untouched and starts the current chat on port
11441 instead, then opens the correct browser URL.
