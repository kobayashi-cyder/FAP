# FAP Chat Protocol — V87.04 Builder

- `GET /api/v1/status` — runtime status/capabilities
- `GET /api/v1/capabilities` — capability list
- `POST /api/v1/chat` — `{ "text": "...", "session": "..." }`
- `GET /artifacts/<name>` — validated artifact download/open endpoint

Builder response example:

```json
{
  "ability": "builder",
  "verdict": "OK",
  "artifacts": [
    {"type":"file","src":"/artifacts/fap_tetris.html","name":"fap_tetris.html","mime":"text/html"}
  ]
}
```
