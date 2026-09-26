# FAP V87.33 — Scene Object Registry

V87.33 fixes the object-coverage bug exposed by the prompt `鳥と犬`.

V87.32 could parse `bird` as a required object but the actual supported set
contained only `human` and `dog`. That meant the system understood that a
bird was required and then deliberately had no generator for it.

V87.33 replaces that hard-coded pair with an explicit Object Registry.

Supported native scene objects in this release:

- human
- dog
- bird
- cat
- horse
- car

The exact screenshot case is now expected to behave as follows:

```text
Prompt: 鳥と犬
Constraints: 被写体を中央に保つ / 写真風

required objects: bird, dog
generated objects: bird, dog
object score: 1.0
layout score: 1.0
style sub-score: 0.58
accepted: no
reason: photorealism_not_yet_verified
```

The rejection is therefore about the still-unverified photo style, not a missing
bird.

## UI fix

The older UI showed gray example text in the hard-constraints box. It looked
like active constraints even though HTML placeholder text is not submitted.

V87.33 changes the wording to:

```text
例（入力しない限り適用されません）
```

and shows the actual `constraints sent` in the result panel.

Run:

```text
RUN_FAP_V87_33_OBJECT_REGISTRY_LAB.cmd
```

Qwen is not used.
