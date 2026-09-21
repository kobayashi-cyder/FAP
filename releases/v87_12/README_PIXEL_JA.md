# PixelでFAP V87.12を起動

1. ZIPをAndroidのDownloadに保存します。
2. 現在のFAPを `Ctrl+C` で停止します。
3. Debian Terminalで次を実行します。

```bash
cd ~
rm -rf FAP_V87_12_SEMANTIC_ADAPTIVE
python3 -m zipfile -e /mnt/shared/Download/FAP_V87_12_SEMANTIC_ADAPTIVE_RUNTIME.zip .
cd ~/FAP_V87_12_SEMANTIC_ADAPTIVE
python3 fap_v87_12_semantic_adaptive_gateway.py
```

Chrome: `http://127.0.0.1:11439/`

## 実機テスト

```text
標準の出力言語は日本語にする。
```

その後、長く会話してから:

```text
標準の出力言語は？
```

長期意味記憶から日本語を復元できれば成功です。

Routing学習は、明示的な作成/天気/計算などを上書きしません。成功履歴が十分ある曖昧な依頼だけを小さく補正します。
