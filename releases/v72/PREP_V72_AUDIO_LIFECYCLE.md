# V72 candidate — Half-duplex audio session lifecycle

Status: implementation candidate, non-main.
Base/rollback anchor: main V71 `5eaf8a7aa9ce30972ede0c025ee5e118132669b8`.
V71 is already integrated; this branch is rebased/transplanted onto the official predecessor.

## Scope
- explicit idle/listening/transcribing/thinking/speaking/cancelled/error states;
- microphone-permission and audio-focus gates;
- cancellation on focus loss or permission revocation;
- half-duplex prohibition on beginning capture while speaking;
- restart generation counter;
- privacy-safe snapshots that retain counts/metrics, not raw PCM/transcript/response text.

## Android boundary
This is the platform-neutral lifecycle contract that an Android AudioRecord/AudioManager
adapter can drive. It does not itself request Android permissions or open the microphone.

## Non-claims
No full duplex, barge-in, echo cancellation, wake word, streaming, Android AudioRecord, or
real device audio path is claimed.

## Promotion
Require focused tests, V71/V70/V69 regressions, V66-V68 core regressions, compileall, and
same-HEAD Python 3.11/3.12 CI after V71 becomes the main predecessor.
