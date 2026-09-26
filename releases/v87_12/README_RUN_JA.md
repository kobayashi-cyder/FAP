# FAP V87.12

起動:

```bash
python3 fap_v87_12_semantic_adaptive_gateway.py
```

UI: `http://127.0.0.1:11439/`

追加API:

- `GET /api/v1/semantic-memory?session=default&q=重要情報`
- `GET /api/v1/routing-stats`

V87.12では生の会話履歴は48ターンです。重要な目標・制約・設定・明示情報は別の意味記憶へ圧縮して保持します。
