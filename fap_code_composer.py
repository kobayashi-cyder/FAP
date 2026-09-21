from __future__ import annotations

from dataclasses import asdict
import html
import re
from typing import Any

from fap_code_generator import CodeGeneratorOrgan, CodeSpec, CodeGenerationError


class CompositionalCodeGenerator(CodeGeneratorOrgan):
    """FAP V87.09 compositional code generator.

    Extends V87.08's verified fixed targets with a small, explicit primitive
    composition layer. Natural-language requests are compiled to a CodeSpec,
    then to deterministic Python/HTML source. It does not use an external LLM
    and does not execute arbitrary user-provided code.
    """

    PY_OPS = (
        ("word_count", re.compile(r"(単語数|word\s*count|words?)", re.I)),
        ("char_count", re.compile(r"(文字数|char(?:acter)?\s*count|length)", re.I)),
        ("line_count", re.compile(r"(行数|line\s*count)", re.I)),
        ("reverse", re.compile(r"(逆順|反転|reverse)", re.I)),
        ("upper", re.compile(r"(大文字|uppercase|upper\b)", re.I)),
        ("lower", re.compile(r"(小文字|lowercase|lower\b)", re.I)),
        ("unique", re.compile(r"(重複.{0,4}(消|除)|ユニーク|unique|dedup)", re.I)),
        ("sort_desc", re.compile(r"(降順|descending)", re.I)),
        ("sort", re.compile(r"(並べ替|ソート|昇順|sort)", re.I)),
        ("sum", re.compile(r"(合計|総和|sum)", re.I)),
        ("mean", re.compile(r"(平均|mean|average)", re.I)),
        ("median", re.compile(r"(中央値|median)", re.I)),
        ("min", re.compile(r"(最小|min(?:imum)?\b)", re.I)),
        ("max", re.compile(r"(最大|max(?:imum)?\b)", re.I)),
        ("json_keys", re.compile(r"(キー一覧|key(?:s)?\s*(?:list)?|キーを表示)", re.I)),
        ("json_types", re.compile(r"(型を表示|値の型|types?|型一覧)", re.I)),
    )

    @classmethod
    def claims(cls, text: str) -> bool:
        if super().claims(text):
            return True
        src = str(text or "")
        if cls.GAME_WORD.search(src) or not cls.CREATE_WORD.search(src):
            return False
        return bool(re.search(r"(関数|ツール|処理|変換|集計|解析|読み込|保存)", src, re.I)) and bool(
            re.search(r"(python|スクリプト|html|web|ブラウザ|javascript|コード|json|markdown)", src, re.I)
        )

    def infer(self, text: str) -> CodeSpec:
        base = super().infer(text)
        if not base.missing:
            return base

        src = str(text or "").strip()
        language = self._language(src)
        ops = self._ops(src)

        if language == "python" and ops:
            input_mode = self._python_input_mode(src, ops)
            output_mode = "json" if re.search(r"(jsonで|json形式|jsonとして)", src, re.I) else "console"
            features = (f"input:{input_mode}", *ops, f"output:{output_mode}", "self_test")
            return CodeSpec(
                "python", "python_composed", "fap_composed_tool.py",
                tuple(features), ("compile", "ast_policy", "self_test", "size_limit"),
            )

        if language == "html" and ops:
            supported = tuple(x for x in ops if x in {"word_count", "char_count", "line_count", "reverse", "upper", "lower"})
            if supported:
                storage = bool(re.search(r"(保存|localstorage|ブラウザに保存)", src, re.I))
                features = ("html.shell", "textarea", *supported, *( ("local_storage",) if storage else () ), "offline")
                return CodeSpec(
                    "html", "html_composed", "fap_composed_text_tool.html",
                    tuple(features), ("html_structure", "offline", "size_limit"),
                )

        # More informative missing fields than V87.08 for partially recognized requests.
        if language in {"python", "html"}:
            return CodeSpec(language, "unknown", f"candidate.{ 'py' if language == 'python' else 'html'}", (), (), (
                "実行したい処理（例: 文字数、逆順、並べ替え、平均、JSONキー一覧）",
            ))
        return base

    @staticmethod
    def _language(src: str) -> str:
        if re.search(r"(python|\.py\b|スクリプト|cli|コマンドライン)", src, re.I):
            return "python"
        if re.search(r"(html|web|ウェブ|ブラウザ|javascript|\bjs\b)", src, re.I):
            return "html"
        if re.search(r"\bjson\b|設定ファイル", src, re.I):
            return "json"
        if re.search(r"markdown|マークダウン|\.md\b", src, re.I):
            return "markdown"
        return "unknown"

    def _ops(self, src: str) -> tuple[str, ...]:
        found: list[str] = []
        for name, pat in self.PY_OPS:
            if pat.search(src):
                if name == "sort" and "sort_desc" in found:
                    continue
                found.append(name)
        # If descending was requested, it already implies sorting.
        if "sort_desc" in found and "sort" in found:
            found.remove("sort")
        return tuple(found)

    @staticmethod
    def _python_input_mode(src: str, ops: tuple[str, ...]) -> str:
        if re.search(r"json.{0,12}(読|入力|ファイル)|jsonファイル", src, re.I) or any(x.startswith("json_") for x in ops):
            return "json_file"
        if re.search(r"csv", src, re.I):
            return "csv_file"
        numeric_ops = {"sort", "sort_desc", "unique", "sum", "mean", "median", "min", "max"}
        if numeric_ops.intersection(ops) or re.search(r"(数値|数字|整数|リスト|配列)", src, re.I):
            return "numbers"
        return "text"

    def generate(self, spec: CodeSpec, request: str) -> str:
        if spec.target == "python_composed":
            return self._python_composed(spec)
        if spec.target == "html_composed":
            return self._html_composed(spec, request)
        return super().generate(spec, request)

    @staticmethod
    def _python_composed(spec: CodeSpec) -> str:
        features = set(spec.features)
        input_mode = next((x.split(":", 1)[1] for x in features if x.startswith("input:")), "text")
        output_mode = next((x.split(":", 1)[1] for x in features if x.startswith("output:")), "console")
        ops = [x for x in spec.features if not x.startswith("input:") and not x.startswith("output:") and x != "self_test"]

        return f'''#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import statistics
from pathlib import Path

INPUT_MODE = {input_mode!r}
OPS = {ops!r}
OUTPUT_MODE = {output_mode!r}


def _numbers(value):
    if isinstance(value, str):
        parts = value.replace(",", " ").split()
    else:
        parts = list(value)
    return [float(x) for x in parts]


def transform(value):
    result = {{}}
    if INPUT_MODE == "json_file" and not isinstance(value, dict):
        raise TypeError("JSON input must be an object")
    data = value
    for op in OPS:
        if op == "word_count": result[op] = len(str(data).split())
        elif op == "char_count": result[op] = len(str(data))
        elif op == "line_count": result[op] = len(str(data).splitlines())
        elif op == "reverse": result[op] = str(data)[::-1]
        elif op == "upper": result[op] = str(data).upper()
        elif op == "lower": result[op] = str(data).lower()
        elif op == "json_keys": result[op] = sorted(map(str, data.keys()))
        elif op == "json_types": result[op] = {{str(k): type(v).__name__ for k, v in data.items()}}
        else:
            nums = _numbers(data)
            if op == "unique": result[op] = list(dict.fromkeys(nums))
            elif op == "sort": result[op] = sorted(nums)
            elif op == "sort_desc": result[op] = sorted(nums, reverse=True)
            elif op == "sum": result[op] = sum(nums)
            elif op == "mean": result[op] = statistics.fmean(nums)
            elif op == "median": result[op] = statistics.median(nums)
            elif op == "min": result[op] = min(nums)
            elif op == "max": result[op] = max(nums)
    return result


def load_input(raw: str):
    if INPUT_MODE == "json_file":
        return json.loads(Path(raw).read_text(encoding="utf-8"))
    if INPUT_MODE == "text" and Path(raw).is_file():
        return Path(raw).read_text(encoding="utf-8")
    return raw


def self_test() -> None:
    samples = {{
        "text": "hello world\\nsecond line",
        "numbers": "3 1 3 2",
        "csv_file": "1 2 3 4",
        "json_file": {{"a": 1, "b": "x"}},
    }}
    out = transform(samples[INPUT_MODE])
    assert isinstance(out, dict) and set(out) == set(OPS), (out, OPS)
    if "word_count" in OPS: assert out["word_count"] >= 2
    if "char_count" in OPS: assert out["char_count"] > 0
    if "sort" in OPS: assert out["sort"] == [1.0, 2.0, 3.0, 3.0]
    if "sort_desc" in OPS: assert out["sort_desc"] == [3.0, 3.0, 2.0, 1.0]
    if "unique" in OPS: assert out["unique"] == [3.0, 1.0, 2.0]
    if "json_keys" in OPS: assert out["json_keys"] == ["a", "b"]
    print("SELFTEST:PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generated by FAP V87.09")
    parser.add_argument("input", nargs="?", default="")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test(); return
    value = load_input(args.input)
    out = transform(value)
    if OUTPUT_MODE == "json": print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for key, value in out.items(): print(f"{{key}}: {{value}}")

if __name__ == "__main__":
    main()
'''

    @staticmethod
    def _html_composed(spec: CodeSpec, request: str) -> str:
        ops = [x for x in spec.features if x in {"word_count", "char_count", "line_count", "reverse", "upper", "lower"}]
        storage = "local_storage" in spec.features
        buttons = "".join(f'<button data-op="{html.escape(op)}">{html.escape(op)}</button>' for op in ops)
        storage_js = "localStorage.setItem('fap_text', input.value);" if storage else ""
        restore_js = "input.value = localStorage.getItem('fap_text') || '';" if storage else ""
        js_cases = {
            "word_count": "value.trim() ? value.trim().split(/\\s+/).length : 0",
            "char_count": "value.length",
            "line_count": "value ? value.split(/\\n/).length : 0",
            "reverse": "[...value].reverse().join('')",
            "upper": "value.toUpperCase()",
            "lower": "value.toLowerCase()",
        }
        branches = []
        for op in ops:
            branches.append(f"if (op === {op!r}) result = {js_cases[op]};")
        branch_js = " else ".join(branches)
        title = html.escape(str(request)[:120])
        return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FAP Composed Text Tool</title>
<style>body{{font-family:system-ui;max-width:760px;margin:24px auto;padding:0 16px}}textarea{{width:100%;min-height:180px}}button{{margin:6px 6px 6px 0;padding:10px 14px}}pre{{white-space:pre-wrap;background:#eee;padding:12px;border-radius:8px}}</style></head>
<body><h1>FAP Composed Text Tool</h1><p>{title}</p><textarea id="input" placeholder="入力"></textarea><div>{buttons}</div><pre id="output">READY</pre>
<script>
const input=document.getElementById('input'), output=document.getElementById('output');
{restore_js}
input.addEventListener('input',()=>{{ {storage_js} }});
document.querySelectorAll('button[data-op]').forEach(btn=>btn.addEventListener('click',()=>{{
  const op=btn.dataset.op, value=input.value; let result='';
  {branch_js}
  output.textContent=String(result);
}}));
</script></body></html>
'''

    def build(self, text: str) -> dict[str, Any]:
        out = super().build(text)
        if isinstance(out, dict):
            out.setdefault("composition", {})
            spec = out.get("code_spec") or {}
            features = list(spec.get("features") or [])
            out["composition"] = {
                "stage": 2,
                "language": spec.get("language"),
                "target": spec.get("target"),
                "primitives": features,
                "external_llm": False,
            }
            if out.get("ok"):
                out["reply"] = str(out.get("reply", "")).replace("CODE BUILD:", "CODE COMPOSE:")
        return out
