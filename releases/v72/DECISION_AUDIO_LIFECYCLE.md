# Decision — V72 Audio Lifecycle

Decision: KEEP for main integration review, pending clean same-HEAD CI on the V71-main-based branch.

Prior equivalent-content CI on Python 3.11 and 3.12 passed:
- V72 focused lifecycle tests;
- V71 runtime regression;
- V70 adapter regression;
- V69 interaction regression;
- V66/V67/V68 core regressions;
- compileall.

The clean predecessor branch must reproduce those results before merge.

Scope remains platform-neutral half-duplex lifecycle only. Android AudioRecord/AudioManager,
real microphone/speaker I/O, full duplex, barge-in, echo cancellation, wake word and streaming
remain separately gated.

Rollback anchor: main V71 `5eaf8a7aa9ce30972ede0c025ee5e118132669b8`.
Rollback action: remove/disable the additive V72 audio lifecycle package.
