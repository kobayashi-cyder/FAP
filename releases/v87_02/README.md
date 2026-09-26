# FAP V87.02 — Capability Gateway / Stable Chat Boundary

V87.02 extends the V87 Autonomous Improvement Core with a stable chat boundary.

The central rule is:

> Improve FAP capabilities in Core; do not keep adding intelligence to the HTML.

## Added

- `web/FAP_Chat.html` — permanent capability-agnostic chat UI
- `fap_v87_02_gateway.py` — same-origin API gateway and capability router
- `RUN_FAP_V87_02_WEB.cmd` — Windows launcher
- `docs/FAP_CHAT_PROTOCOL.md` — protocol contract
- `tests/test_v87_02_gateway.py` — regression tests for the observed routing failures

## Current routing corrections

```text
今日は何日ですか？
  -> datetime

今日の天気は？
  -> weather
  -> request location when none is configured

リンゴを画像生成できますか？
  -> image_capability
  -> report actual image-provider availability

赤いリンゴを写真風で生成して
  -> image_generate
```

The word `今日` no longer overrides a stronger weather intent.

## Architecture

```text
web/FAP_Chat.html
        |
        | /api/v1/*
        v
FAP V87.02 Gateway
        |
        +-- Intent Organ
        +-- Ability Router
        +-- Session Memory
        +-- Date/Time Organ
        +-- Calculator Organ
        +-- Weather Organ
        +-- Image Organ
        +-- Gemma4:E2B Organ
        +-- Verification Organ
        +-- FAP-Eval log
```

The UI reads the running FAP version from `GET /api/v1/status`. It contains no hard-coded FAP version and no local fallback reasoning.

## Start

Windows:

```text
RUN_FAP_V87_02_WEB.cmd
```

Then open:

```text
http://127.0.0.1:11439/
```

For Android over ADB:

```text
adb reverse tcp:11439 tcp:11439
```

and open the same URL on the Android browser.

## Optional providers

General reasoning uses:

```text
FAP_MODEL=gemma4:e2b
FAP_OLLAMA_BASE=http://127.0.0.1:11434
```

Image generation can use an AUTOMATIC1111-compatible API:

```text
FAP_IMAGE_API=http://127.0.0.1:7860
```

A default weather place can be set without changing HTML:

```text
FAP_DEFAULT_LOCATION=<place>
```

No Qwen dependency is used.
