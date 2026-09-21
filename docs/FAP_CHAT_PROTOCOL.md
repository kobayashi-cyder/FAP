# FAP Chat Protocol 1.0

## Purpose

`web/FAP_Chat.html` is a permanent, capability-agnostic UI. It must not contain FAP reasoning, intent classification, weather logic, image-generation logic, model selection, memory policy, or version-specific behavior.

All capability decisions belong to FAP Core.

## Endpoints

### GET /api/v1/status

Example:

```json
{
  "name": "FAP",
  "version": "87.02",
  "state": "ready",
  "model": "gemma4:e2b",
  "capabilities": ["intent", "weather", "image-routing", "verification"],
  "protocol": "1.0"
}
```

### POST /api/v1/chat

Request:

```json
{
  "text": "今日の天気は？",
  "session": "s_123",
  "client": {
    "name": "FAP_Chat",
    "protocol": "1.0"
  }
}
```

Response:

```json
{
  "reply": "天気の質問だと判断しました。地域を指定してください。",
  "ability": "weather",
  "confidence": 0.93,
  "route": ["intent", "weather", "verify", "integrate"],
  "critic": "査定: PARTIAL\n意図は認識できていますが、必要情報が不足しています。",
  "verdict": "PARTIAL",
  "artifacts": []
}
```

## Artifact contract

The UI renders artifacts generically. New FAP abilities can therefore be added without changing the HTML.

Supported generic fields:

```json
{
  "type": "image | audio | video | file",
  "src": "/artifacts/example.png",
  "name": "example.png"
}
```

The UI does not need to know which FAP organ created the artifact.

## Routing rule

FAP Core must classify the whole intent before considering generic modifiers.

Examples:

- `今日は何日ですか？` -> `datetime`
- `今日の天気は？` -> `weather`, not `datetime`
- `リンゴを画像生成できますか？` -> `image_capability`, not memory/context search
- `赤いリンゴを写真風で生成して` -> `image_generate`

## Separation boundary

```text
FAP_Chat.html
    |
    | protocol 1.0
    v
FAP V87.02 Gateway
    |
    +-- Intent Organ
    +-- Ability Router
    +-- Memory Organ
    +-- Weather Organ
    +-- Image Organ
    +-- Gemma4:E2B Organ
    +-- Verification Organ
    +-- FAP-Eval log
```

Future capability work should modify Core/organs/providers, not `web/FAP_Chat.html`, unless the protocol itself needs a new generic presentation primitive.

## Model policy

The default reasoning model is `gemma4:e2b`. Qwen is not used by this gateway.
