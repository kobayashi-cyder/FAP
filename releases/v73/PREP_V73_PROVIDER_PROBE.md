# V73 candidate — Provider capability probe

Status: implementation candidate, non-main.
Base/rollback anchor: main V72 `69f04a36efb33287542d58cff88ff27440db334d`.

## Goal
Distinguish provider "configured" from provider "responding and protocol-compatible" without
sending user content.

## Scope
- protocol-versioned `probe` operation;
- provider ID and explicit image/STT/TTS capability list;
- fail-closed duplicate/unknown/malformed capability responses;
- ready/not-ready distinction;
- derived gate for image, STT, TTS and half-duplex voice.

## Privacy
Probe request contains only `op` and protocol version. No prompt, transcript, audio, image,
credential, device ID, or conversation content is sent.

## Non-claims
A healthy probe proves control-plane responsiveness only. It is not proof that real image
generation/STT/TTS output quality is acceptable. Concrete data-plane adapter evidence remains
required for those claims.

## Promotion
Require focused tests, V72/V71/V70/V69 regressions, V66-V68 core regressions, compileall and
same-HEAD Python 3.11/3.12 CI.
