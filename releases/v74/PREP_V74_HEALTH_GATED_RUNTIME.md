# V74 candidate — Health-gated interaction runtime

Status: implementation candidate, non-main.
Base/rollback anchor: main V73 `86b4c04f90f3c6495ef3190d361bb33a7068acf4`.

## Goal
Connect V73 control-plane probe evidence to V71 media execution so unhealthy or undeclared
providers are never invoked by the runtime.

## Scope
- chat remains available independently of media state;
- unconfigured media -> needs_provider;
- configured but unprobed/unhealthy/incompatible media -> rejected before provider call;
- healthy but undeclared capability -> rejected;
- healthy declared image/STT/TTS -> existing V71/V70 execution path;
- half-duplex voice requires both healthy STT and TTS declarations.

## Non-claims
This gate improves fail-closed execution. It still does not make fixture providers into real
image/STT/TTS engines or prove output quality.

## Promotion
Require spy-based non-invocation tests, successful allowed-path tests, compileall, V73-V69
regressions, V66-V68 core regressions and same-HEAD Python 3.11/3.12 CI.
