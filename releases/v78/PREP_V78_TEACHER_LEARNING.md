# V78 preparation — Teacher learning integration

Baseline: `main@3dc56198ed2c1a5fa59b4a8e3a93c0594a0d37be`.

The user-provided Gemma 4 direct-learning ZIP was inspected before integration. The source manifest reports PASS and the package contains the expected consolidated circuits, shadow memory, concept graph, and V54 overlay. V78 intentionally imports only the compact learned state plus provenance hashes; it does not commit Python cache files, the old V54 source copy, or raw model weights.

Acceptance criteria:

- artifact digests verify at runtime;
- all teacher memory remains shadow-labelled;
- repair, uncertainty and debugging probes activate expected circuits;
- V75 managed-chat controls and bounds remain intact;
- V71 interaction chat can use the learned responder;
- tampering fails closed;
- previous V69–V77 and V66–V68 regression gates remain green.
