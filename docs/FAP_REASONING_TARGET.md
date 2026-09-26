# FAP reasoning target

FAPの目標超過は、バージョン名や自己申告ではなく、未知問題・生成問題・実利用での検証を通して判断する。

## 必須要素

1. 適応計算量
   - 強い既知回答は1パスで止める。
   - 低信頼、矛盾、数値、厳密検証、最新性が必要な問いだけ追加パスへ昇格する。

2. 独立候補生成
   - 複数の読み取り専用specialistが独立候補を出す。
   - 副作用のあるツールは冗長実行しない。

3. 反例・矛盾探索
   - 高リスク時はcounterexample / contradiction laneを自動投入する。
   - 検証済み候補同士が矛盾した場合は平均化せず不確実性を上げる。

4. 検証優先選択
   - 弱いprimaryより、検証済みspecialistを優先できる。
   - 既に強く検証済みのprimaryは無意味に書き換えない。

5. 信頼度校正
   - 未検証回答のconfidenceを上限付きにする。
   - 最新性が必要な情報をローカル知識だけで現在値として断定しない。
   - ローカル根拠不足では needs_teacher / 外部調査要求を維持する。

6. fail-closed
   - 不透明な未知語・根拠なしの対象は、知ったふりをしない。
   - ベンチマークの答え表を実装しない。

7. 知識を語る能力
   - FAPが保持する知識は自然言語で説明できる。
   - 複数のローカル知識断片を統合して説明する。
   - 保存知識・日付付き知識・現在情報を区別する。
   - 知らない対象はKnowledgeNarratorが回答を作らない。

8. 長期状態
   - 会話履歴、明示制約、semantic memory、検証済み経験、epistemic conflictを分離管理する。

9. ツール検証境界
   - ツール出力はverification contractを通す。
   - 副作用を伴う操作と推論候補生成を分離する。

10. 動的スパースルーティング
   - 全経路を常時実行せず、task family / form / capability / 過去のutilityから経路選択する。

11. anti-overfit評価
   - commit SHAから生成内容が変わる算術・方程式・未知語テストを昇格ゲートにする。
   - 固定問題だけの満点は昇格条件にしない。

12. 長期推論
   - plan → execute → verify → repair → re-verify を明示的に扱う。
   - 途中失敗を最終成功扱いしない。

13. 複合依頼・多意図推論
   - 1つの発話に複数の独立した依頼がある場合は、部分問題へ分解して個別に検証する。
   - 1項目だけ厳密に正しい部分回答が、未回答の残りを隠して全体回答として昇格しない。
   - 分解結果は元の順序を保って再統合し、未解決部分は知ったふりをせず明示する。

## 現在の昇格ゲート

- Public 1.x canonical verify
- Pixel APK Verify
- generated anti-overfit reasoning target gate
- focused reasoning unit tests
- sparse routing mechanism benchmark
- generated 1.x E2E benchmark

## 超過判定

GPT-5.6 Sol等の外部モデルを「超えた」と判断するには、同じ条件・同じ問題集合・同じ採点規則での外部比較実測が必要。
FAP内の自己評価値だけでは超過判定しない。
