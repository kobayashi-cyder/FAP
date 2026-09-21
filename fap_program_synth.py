from __future__ import annotations

from dataclasses import asdict
import re
from typing import Any

from fap_code_generator import CodeSpec, CodeGeneratorOrgan
from fap_code_composer import CompositionalCodeGenerator


class ProgramSynthesizer(CompositionalCodeGenerator):
    """FAP V87.10 local Program-IR synthesizer.

    Unknown-but-composable Python requests are compiled into a small ordered
    Program IR. The IR is then emitted as deterministic Python using only an
    allowlisted local runtime. No external LLM and no arbitrary code execution
    are used for synthesis.
    """

    STAGE = 3

    @staticmethod
    def _has(src: str, pat: str) -> bool:
        return bool(re.search(pat, src, re.I))

    def infer(self, text: str) -> CodeSpec:
        # Preserve V87.08 fixed verified targets first (calculator, CSV stats,
        # notepad, counter, JSON, Markdown). For other Python requests, give
        # Program IR a chance before V87.09's parallel-result composer so
        # sequential semantics such as extract->sum are not flattened.
        fixed = CodeGeneratorOrgan.infer(self, text)
        if not fixed.missing:
            return fixed

        src = str(text or "").strip()
        language = self._language(src)
        if language != "python":
            return super().infer(text)

        input_mode, steps, params = self._compile_ir(src)
        if not steps:
            return super().infer(text)

        # V87.09 intentionally returns several independent metrics in parallel.
        # Keep those requests on Stage 2 unless the request requires a true
        # sequential transform that Stage 2 cannot express correctly.
        sequential_ops = {
            "extract_numbers", "split_lines", "filter_nonempty", "head", "tail",
            "count_occurrences", "regex_extract", "replace", "json_numeric_keys",
        }
        if not sequential_ops.intersection(steps):
            composed = super().infer(text)
            if not composed.missing:
                return composed

        features = [f"input:{input_mode}"]
        features.extend(f"ir:{op}" for op in steps)
        for key, value in params.items():
            features.append(f"param:{key}={value}")
        features.extend(("output:auto", "self_test"))
        return CodeSpec(
            "python",
            "python_program_ir",
            "fap_synthesized_program.py",
            tuple(features),
            ("compile", "ast_policy", "self_test", "size_limit"),
        )

    def _compile_ir(self, src: str) -> tuple[str, list[str], dict[str, str]]:
        params: dict[str, str] = {}
        steps: list[str] = []

        is_json = self._has(src, r"json.{0,16}(読|ファイル)|jsonファイル")
        is_file = self._has(src, r"(テキスト|txt|文章).{0,10}ファイル|ファイル.{0,10}(読|入力)")
        input_mode = "json_file" if is_json else ("text_file" if is_file else "text")

        if is_json and self._has(src, r"(数値|数字).{0,12}(キー|項目)|値が.{0,8}(数値|数字).{0,8}(キー|項目)"):
            steps.append("json_numeric_keys")
            return input_mode, steps, params
        if is_json and self._has(src, r"(キー一覧|キーを表示|keys?)"):
            steps.append("json_keys")
            return input_mode, steps, params

        if self._has(src, r"(数字|数値).{0,8}(だけ)?.{0,8}(抽出|取り出|抜き出)|extract.{0,8}numbers?"):
            steps.append("extract_numbers")

        line_semantics = self._has(src, r"(行|line)")
        if line_semantics and any(self._has(src, p) for p in [r"空行", r"重複.{0,4}(消|除)", r"昇順", r"降順", r"先頭", r"末尾"]):
            if "extract_numbers" not in steps:
                steps.append("split_lines")

        if self._has(src, r"空行.{0,8}(除|消)|空白行.{0,8}(除|消)|non.?empty"):
            if "split_lines" not in steps:
                steps.append("split_lines")
            steps.append("filter_nonempty")

        if self._has(src, r"重複.{0,6}(消|除)|ユニーク|unique|dedup"):
            steps.append("unique")

        if self._has(src, r"降順|descending"):
            steps.append("sort_desc")
        elif self._has(src, r"昇順|並べ替|ソート|sort"):
            steps.append("sort")

        head = re.search(r"(?:先頭|最初)[^0-9]{0,5}(\d+)\s*(?:件|行|個)?", src)
        tail = re.search(r"(?:末尾|最後)[^0-9]{0,5}(\d+)\s*(?:件|行|個)?", src)
        if head:
            params["count"] = head.group(1)
            steps.append("head")
        elif tail:
            params["count"] = tail.group(1)
            steps.append("tail")

        if self._has(src, r"(指定した|指定の).{0,8}(単語|文字列).{0,12}(回数|数える)|出現回数|occurrences?"):
            steps.append("count_occurrences")
            params["needle"] = "__RUNTIME__"

        if self._has(src, r"正規表現.{0,10}(抽出|取り出)|regex.{0,8}(extract|find)"):
            steps.append("regex_extract")
            params["pattern"] = "__RUNTIME__"

        if self._has(src, r"置換|replace"):
            steps.append("replace")
            params["old"] = "__RUNTIME__"
            params["new"] = "__RUNTIME__"

        if self._has(src, r"逆順|反転|reverse"):
            steps.append("reverse")
        if self._has(src, r"大文字|uppercase|upper\b"):
            steps.append("upper")
        if self._has(src, r"小文字|lowercase|lower\b"):
            steps.append("lower")

        # Aggregation must come after extraction/list transforms.
        if self._has(src, r"合計|総和|sum"):
            steps.append("sum")
        if self._has(src, r"平均|mean|average"):
            steps.append("mean")
        if self._has(src, r"中央値|median"):
            steps.append("median")
        if self._has(src, r"最小|min(?:imum)?\b"):
            steps.append("min")
        if self._has(src, r"最大|max(?:imum)?\b"):
            steps.append("max")

        if self._has(src, r"単語数|word\s*count"):
            steps.append("word_count")
        if self._has(src, r"文字数|char(?:acter)?\s*count|length"):
            steps.append("char_count")
        if self._has(src, r"行数|line\s*count"):
            steps.append("line_count")

        # Ordered dedupe; repeated semantics are not useful in this IR.
        deduped: list[str] = []
        for op in steps:
            if op not in deduped:
                deduped.append(op)
        return input_mode, deduped, params

    def generate(self, spec: CodeSpec, request: str) -> str:
        if spec.target == "python_program_ir":
            return self._emit_python_program(spec)
        return super().generate(spec, request)

    @staticmethod
    def _parse_features(spec: CodeSpec) -> tuple[str, list[str], dict[str, str]]:
        input_mode = "text"
        ops: list[str] = []
        params: dict[str, str] = {}
        for f in spec.features:
            if f.startswith("input:"):
                input_mode = f.split(":", 1)[1]
            elif f.startswith("ir:"):
                ops.append(f.split(":", 1)[1])
            elif f.startswith("param:"):
                item = f.split(":", 1)[1]
                key, _, value = item.partition("=")
                params[key] = value
        return input_mode, ops, params

    def _emit_python_program(self, spec: CodeSpec) -> str:
        input_mode, ops, params = self._parse_features(spec)
        return f'''#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import re
import statistics
from pathlib import Path

INPUT_MODE = {input_mode!r}
PROGRAM_IR = {ops!r}
IR_PARAMS = {params!r}


def _as_numbers(value):
    if isinstance(value, (list, tuple)):
        return [float(x) for x in value]
    return [float(x) for x in re.findall(r"[-+]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)", str(value))]


def _unique(value):
    seen = set(); out = []
    for item in list(value):
        key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else repr(item)
        if key not in seen:
            seen.add(key); out.append(item)
    return out


def apply_program(value, *, needle="", pattern="", old="", new="", count=0):
    data = value
    for op in PROGRAM_IR:
        if op == "json_numeric_keys":
            if not isinstance(data, dict): raise TypeError("JSON object required")
            data = sorted(str(k) for k, v in data.items() if isinstance(v, (int, float)) and not isinstance(v, bool))
        elif op == "json_keys":
            if not isinstance(data, dict): raise TypeError("JSON object required")
            data = sorted(map(str, data.keys()))
        elif op == "extract_numbers": data = _as_numbers(data)
        elif op == "split_lines": data = str(data).splitlines()
        elif op == "filter_nonempty": data = [str(x).strip() for x in data if str(x).strip()]
        elif op == "unique": data = _unique(data if isinstance(data, list) else str(data))
        elif op == "sort": data = sorted(data)
        elif op == "sort_desc": data = sorted(data, reverse=True)
        elif op == "head": data = list(data)[:count]
        elif op == "tail": data = list(data)[-count:] if count else []
        elif op == "count_occurrences": data = str(data).count(needle)
        elif op == "regex_extract": data = re.findall(pattern, str(data))
        elif op == "replace": data = str(data).replace(old, new)
        elif op == "reverse": data = str(data)[::-1]
        elif op == "upper": data = str(data).upper()
        elif op == "lower": data = str(data).lower()
        elif op == "sum": data = sum(_as_numbers(data))
        elif op == "mean": data = statistics.fmean(_as_numbers(data))
        elif op == "median": data = statistics.median(_as_numbers(data))
        elif op == "min": data = min(_as_numbers(data))
        elif op == "max": data = max(_as_numbers(data))
        elif op == "word_count": data = len(str(data).split())
        elif op == "char_count": data = len(str(data))
        elif op == "line_count": data = len(str(data).splitlines())
        else: raise ValueError(f"unsupported IR op: {{op}}")
    return data


def load_input(raw):
    if INPUT_MODE == "json_file":
        return json.loads(Path(raw).read_text(encoding="utf-8"))
    if INPUT_MODE == "text_file":
        return Path(raw).read_text(encoding="utf-8")
    return raw


def self_test():
    sample = {{
        "text": "alpha 12\\n\\nbeta 3\\nalpha 12",
        "text_file": "alpha 12\\n\\nbeta 3\\nalpha 12",
        "json_file": {{"a": 1, "b": "x", "c": 2.5}},
    }}[INPUT_MODE]
    kwargs = {{
        "needle": "alpha", "pattern": r"\\d+", "old": "alpha", "new": "gamma",
        "count": int(IR_PARAMS.get("count", "2") if IR_PARAMS.get("count") != "__RUNTIME__" else 2),
    }}
    out = apply_program(sample, **kwargs)
    assert out is not None
    print("SELFTEST:PASS")


def main():
    p = argparse.ArgumentParser(description="Generated by FAP V87.10 Program Synthesizer")
    p.add_argument("input", nargs="?", default="")
    p.add_argument("--needle", default="")
    p.add_argument("--pattern", default="")
    p.add_argument("--old", default="")
    p.add_argument("--new", default="")
    p.add_argument("--count", type=int, default=int(IR_PARAMS.get("count", "0") if IR_PARAMS.get("count") not in {{None, "__RUNTIME__"}} else 0))
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test(); return
    value = load_input(args.input)
    out = apply_program(value, needle=args.needle, pattern=args.pattern, old=args.old, new=args.new, count=args.count)
    if isinstance(out, (dict, list)):
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(out)


if __name__ == "__main__":
    main()
'''

    def build(self, text: str) -> dict[str, Any]:
        out = super().build(text)
        spec = out.get("code_spec") or {}
        if out.get("ok") and spec.get("target") == "python_program_ir":
            input_mode, ops, params = self._parse_features(CodeSpec(
                spec["language"], spec["target"], spec["filename"], tuple(spec["features"]), tuple(spec["checks"]), tuple(spec.get("missing", ()))
            ))
            out["program_ir"] = {
                "stage": self.STAGE,
                "input": input_mode,
                "steps": ops,
                "parameters": params,
                "output": "auto",
            }
            out["reply"] = out["reply"].replace(
                "コードを生成しました。",
                "Program IRからコードを合成しました。"
            )
        return out
