# TEST PREP — V69 Chat + Image + Audio Interaction Surface

Required before main promotion:

- deterministic chat mode/state tests and bounded-history behavior;
- malformed/empty chat input and empty responder output;
- image request validation, missing provider, timeout/error, wrong MIME, empty artifact;
- deterministic artifact SHA-256;
- PCM16 odd-byte/empty/rate/channel rejection;
- STT missing-provider, timeout/error, empty transcript, successful fixture;
- TTS missing-provider, timeout/error, wrong MIME, empty artifact, successful fixture;
- half-duplex voice baseline and missing-provider propagation;
- assert raw PCM bytes are not copied into result metadata;
- compileall with warnings-as-errors where practical;
- current V68 cumulative regression from the same candidate HEAD;
- concrete provider/Android adapter evidence separately before any real-generation claim.

Promotion must be blocked by any regression or by a need to weaken existing tests.
