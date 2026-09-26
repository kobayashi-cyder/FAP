# FAP V87.34 — Scene Graph 2

V87.34 moves image prompting from an object-name list to an explicit scene graph.

Supported semantic fields:
- exact object counts;
- basic color attributes;
- object state / pose;
- spatial and semantic relations;
- negative constraints;
- camera viewpoint;
- style requirements.

Example:

```text
2羽の白い鳥が犬の上を飛んでいて、
犬は鳥を見ている。
側面から。
猫は入れない。
写真風。
```

becomes approximately:

```text
bird_1: bird, white, flying
bird_2: bird, white, flying
dog_1: dog
relations:
  bird above dog
  dog looking_at bird
forbidden:
  cat
viewpoint:
  side
style:
  photorealistic
```

Acceptance is split into count, attribute, state, relation, negative-object,
viewpoint, layout and style checks.

The V87.32 photo-look renderer remains underneath, so a true photorealistic
request is still fail-closed until a verified learned refiner exists.

Illustration/anime requests are no longer allowed to pass through the
photo-look renderer as if the requested style had been satisfied.

Run:

```text
RUN_FAP_V87_34_SCENE_GRAPH2_LAB.cmd
```

Qwen is not used.
