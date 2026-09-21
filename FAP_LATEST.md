# FAP latest development snapshot

Current mainline candidate: **V87.34 — Scene Graph 2**.

V87.34 upgrades V87.33's object registry into a structured scene representation.

Implemented:
- exact object counts;
- basic color attributes;
- object state / pose tracking;
- spatial relations: above, below, left/right, next-to;
- semantic relation: looking-at;
- negative constraints such as `猫は入れない`;
- front / side / back / oblique camera viewpoints;
- style gating for photorealistic and illustration/anime requests;
- V87.34 unified chat routing.

Example:

```text
2羽の白い鳥が犬の上を飛んでいて、
犬は鳥を見ている。
側面から。
猫は入れない。
写真風。
```

Scene Graph 2 records:
- bird count = 2;
- bird color = white;
- bird state = flying;
- dog count = 1;
- bird above dog;
- dog looking_at bird;
- cat forbidden;
- side viewpoint;
- photorealistic requested.

Verification is split into:
- count;
- attributes;
- state;
- relations;
- negative constraints;
- viewpoint;
- layout;
- style.

A structurally correct scene can pass all scene-semantic gates while still being
rejected for an unmet hard style requirement. In particular, V87.32's native
photo-look renderer remains underneath, so true photorealistic requests still
fail closed until a verified learned refiner exists.

Illustration/anime requests are also fail-closed rather than being falsely
accepted by the photo-look renderer.

Run the dedicated lab:

```text
RUN_FAP_V87_34_SCENE_GRAPH2_LAB.cmd
```

Run standard latest chat:

```text
RUN_FAP_CHAT_LATEST.cmd
```

Compatibility:
- V87.33 Object Registry remains underneath;
- V87.32 photo-look renderer remains;
- V87.30 Human LBS remains;
- V87.29 native raster remains;
- V87.28 and earlier reasoning/physics paths remain;
- chat-speed restoration remains;
- Qwen is not used.
