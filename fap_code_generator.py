from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import ast
import html
import json
import os
import re
import subprocess
import sys
from typing import Any


@dataclass(frozen=True)
class CodeSpec:
    language: str
    target: str
    filename: str
    features: tuple[str, ...]
    checks: tuple[str, ...]
    missing: tuple[str, ...] = ()


class CodeGenerationError(RuntimeError):
    pass


class CodeGeneratorOrgan:
    """FAP V87.08 constrained local code generator.

    The first stage maps natural-language requests to a small verified CodeSpec
    library. Generated candidates stay in a workspace until compile/static
    checks and deterministic self-tests pass. No shell execution is used.
    """

    CODE_WORD = re.compile(r"(python|\.py\b|スクリプト|コード|program|programming|html|javascript|\bjs\b|json|markdown|\.md\b)", re.I)
    CREATE_WORD = re.compile(r"(作って|作成|生成|書いて|実装|構築|build|create|make|generate)", re.I)
    GAME_WORD = re.compile(r"(ゲーム|game|テトリス|tetris|ブロック崩し|pong|snake|スネーク|マインスイーパー|2048|神経衰弱)", re.I)

    def __init__(self, artifacts_dir: Path, workspace_dir: Path):
        self.artifacts_dir = Path(artifacts_dir)
        self.workspace_dir = Path(workspace_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def claims(cls, text: str) -> bool:
        src = str(text or "")
        if cls.GAME_WORD.search(src):
            return False
        if not cls.CREATE_WORD.search(src):
            return False
        if cls.CODE_WORD.search(src):
            return True
        # Common coding artifacts can be requested without explicitly saying code.
        return bool(re.search(r"(電卓|CSV|メモ帳|ノート|カウンター|設定ファイル)", src, re.I))

    def infer(self, text: str) -> CodeSpec:
        src = str(text or "").strip()
        low = src.lower()

        wants_python = bool(re.search(r"python|\.py\b|py(?:thon)?スクリプト", src, re.I))
        wants_html = bool(re.search(r"html|web|ウェブ|ブラウザ|javascript|\bjs\b", src, re.I))
        wants_json = bool(re.search(r"\bjson\b|設定ファイル", src, re.I))
        wants_md = bool(re.search(r"markdown|\.md\b|マークダウン", src, re.I))

        if wants_python and re.search(r"(電卓|四則演算|計算機|calculator)", src, re.I):
            return CodeSpec(
                "python", "calculator", "fap_calculator.py",
                ("python.ast", "safe.expression", "cli", "self_test"),
                ("compile", "ast_policy", "self_test", "size_limit"),
            )

        if wants_python and re.search(r"csv", src, re.I) and re.search(r"(平均|中央値|最大|最小|統計|mean|median|max|min)", src, re.I):
            return CodeSpec(
                "python", "csv_stats", "fap_csv_stats.py",
                ("csv.read", "numeric.filter", "statistics", "cli", "self_test"),
                ("compile", "ast_policy", "self_test", "size_limit"),
            )

        if wants_html and re.search(r"(メモ帳|ノート|memo|notepad|notes?)", src, re.I):
            return CodeSpec(
                "html", "notepad", "fap_notepad.html",
                ("html.shell", "textarea", "local_storage", "clear", "offline"),
                ("html_structure", "offline", "notepad_features", "size_limit"),
            )

        if wants_html and re.search(r"(カウンター|counter|数える|増える)", src, re.I):
            return CodeSpec(
                "html", "counter", "fap_counter.html",
                ("html.shell", "dom.state", "click.event", "reset", "offline"),
                ("html_structure", "offline", "counter_features", "size_limit"),
            )

        if wants_json:
            return CodeSpec(
                "json", "config", "fap_generated_config.json",
                ("json.object", "metadata"),
                ("json_parse", "size_limit"),
            )

        if wants_md:
            return CodeSpec(
                "markdown", "document", "fap_generated_document.md",
                ("markdown.heading", "requirements", "verification"),
                ("markdown_structure", "size_limit"),
            )

        if wants_python:
            return CodeSpec("python", "unknown", "candidate.py", (), (), ("Pythonで実装する処理内容" ,))
        if wants_html:
            return CodeSpec("html", "unknown", "candidate.html", (), (), ("画面に必要な要素または動作",))
        if wants_json:
            return CodeSpec("json", "unknown", "candidate.json", (), (), ("JSONに含める項目",))
        if wants_md:
            return CodeSpec("markdown", "unknown", "candidate.md", (), (), ("文書の目的または章立て",))
        return CodeSpec("unknown", "unknown", "artifact.pending", (), (), ("生成する言語または形式（Python/HTML/JSON/Markdown）", "必要な処理"))

    def build(self, text: str, *, max_repairs: int = 2) -> dict[str, Any]:
        try:
            repair_limit = int(max_repairs)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("max_repairs must be an integer") from exc
        if not 0 <= repair_limit <= 4:
            raise ValueError("max_repairs must be in [0, 4]")
        spec = self.infer(text)
        if spec.missing:
            return {
                "ok": False,
                "reply": (
                    "Code Generatorとして要求を保持しています。安全にCodeSpecへ確定するため、次の情報だけ追加してください。\n"
                    + "\n".join(f"- {x}" for x in spec.missing)
                    + "\n回答後もCode Generator計画を継続します。"
                ),
                "confidence": 0.90,
                "code_spec": asdict(spec),
                "repair_rounds": 0,
                "artifacts": [],
            }

        content = self.generate(spec, text)
        candidate = self.workspace_dir / spec.filename
        candidate.write_text(content, encoding="utf-8")

        report = self.validate(spec, candidate)
        repair_rounds = 0
        while not report["ok"] and repair_rounds < repair_limit:
            repaired = self.repair(spec, candidate.read_text(encoding="utf-8"), report["errors"])
            if repaired == candidate.read_text(encoding="utf-8"):
                break
            candidate.write_text(repaired, encoding="utf-8")
            repair_rounds += 1
            report = self.validate(spec, candidate)

        if not report["ok"]:
            raise CodeGenerationError("validation failed: " + "; ".join(report["errors"]))

        final = self.artifacts_dir / spec.filename
        final.write_bytes(candidate.read_bytes())
        raw = final.read_bytes()
        digest = sha256(raw).hexdigest()
        mime = {
            ".py": "text/x-python",
            ".html": "text/html",
            ".json": "application/json",
            ".md": "text/markdown",
        }.get(final.suffix.lower(), "text/plain")
        return {
            "ok": True,
            "reply": (
                f"コードを生成しました。target={spec.target} / language={spec.language}\n"
                "CODE BUILD: 要求 → CodeSpec → 候補生成 → 構文/構造検証 → 自己テスト → 修復判定 → 成果物昇格\n"
                f"features: {', '.join(spec.features)}\n"
                f"検証: {', '.join(report['checks'])} / repair_rounds={repair_rounds} / {len(raw)} bytes\n"
                f"下の {spec.filename} を開いてください。"
            ),
            "confidence": 0.98,
            "code_spec": asdict(spec),
            "validation": report,
            "repair_rounds": repair_rounds,
            "artifacts": [{
                "type": "file",
                "src": f"/artifacts/{spec.filename}",
                "name": spec.filename,
                "sha256": digest,
                "mime": mime,
            }],
        }

    def generate(self, spec: CodeSpec, request: str) -> str:
        if spec.target == "calculator":
            return self._python_calculator()
        if spec.target == "csv_stats":
            return self._python_csv_stats()
        if spec.target == "notepad":
            return self._html_notepad()
        if spec.target == "counter":
            return self._html_counter()
        if spec.target == "config":
            return json.dumps({
                "created_by": "FAP V87.08 Code Generator",
                "request": str(request)[:1000],
                "version": "87.08",
                "status": "verified_candidate",
            }, ensure_ascii=False, indent=2) + "\n"
        if spec.target == "document":
            safe = str(request).strip()[:1000]
            return (
                "# FAP Generated Document\n\n"
                f"## Request\n\n{safe}\n\n"
                "## Requirements\n\n- 目的を満たす\n- 検証可能な形で記述する\n\n"
                "## Verification\n\n- [ ] 内容確認\n- [ ] 必要条件確認\n"
            )
        raise CodeGenerationError(f"unsupported target: {spec.target}")

    def validate(self, spec: CodeSpec, path: Path) -> dict[str, Any]:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        checks: list[str] = []
        errors: list[str] = []
        if len(raw) <= 300_000:
            checks.append("size_limit")
        else:
            errors.append("artifact exceeds 300KB")

        if spec.language == "python":
            try:
                tree = ast.parse(text, filename=path.name)
                compile(tree, path.name, "exec")
                checks.append("compile")
            except SyntaxError as exc:
                errors.append(f"python syntax: {exc.msg} line={exc.lineno}")
                tree = None
            if tree is not None:
                policy_errors = self._python_policy(tree)
                if policy_errors:
                    errors.extend(policy_errors)
                else:
                    checks.append("ast_policy")
            if not errors:
                ok, detail = self._run_python_self_test(path)
                if ok:
                    checks.append("self_test")
                else:
                    errors.append("self_test: " + detail)

        elif spec.language == "html":
            low = text.lower()
            if "<!doctype html>" in low and "<html" in low and "</html>" in low and "<script" in low and "</script>" in low:
                checks.append("html_structure")
            else:
                errors.append("HTML structure incomplete")
            if re.search(r"<(?:script|link)[^>]+(?:src|href)\s*=\s*[\"']https?://", text, re.I):
                errors.append("external dependency detected")
            else:
                checks.append("offline")
            if spec.target == "notepad":
                need = ["<textarea", "localStorage", "addEventListener", "clear"]
                missing = [x for x in need if x not in text]
                if missing:
                    errors.append("missing notepad features: " + ", ".join(missing))
                else:
                    checks.append("notepad_features")
            elif spec.target == "counter":
                need = ["id=\"count\"", "increment", "reset", "addEventListener"]
                missing = [x for x in need if x not in text]
                if missing:
                    errors.append("missing counter features: " + ", ".join(missing))
                else:
                    checks.append("counter_features")

        elif spec.language == "json":
            try:
                obj = json.loads(text)
                if isinstance(obj, dict):
                    checks.append("json_parse")
                else:
                    errors.append("JSON root must be object")
            except json.JSONDecodeError as exc:
                errors.append(f"JSON parse: {exc}")

        elif spec.language == "markdown":
            if text.lstrip().startswith("# ") and "## " in text:
                checks.append("markdown_structure")
            else:
                errors.append("Markdown headings missing")

        return {"ok": not errors, "checks": checks, "errors": errors, "bytes": len(raw)}

    @staticmethod
    def _python_policy(tree: ast.AST) -> list[str]:
        errors: list[str] = []
        forbidden_calls = {"eval", "exec", "compile", "__import__"}
        forbidden_import_roots = {"subprocess", "socket", "ctypes", "multiprocessing"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else [str(node.module or "").split(".")[0]]
                for name in names:
                    if name in forbidden_import_roots:
                        errors.append(f"forbidden import: {name}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                errors.append(f"forbidden call: {node.func.id}")
        return errors

    @staticmethod
    def _run_python_self_test(path: Path) -> tuple[bool, str]:
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"}
        try:
            cp = subprocess.run(
                [sys.executable, str(path), "--self-test"],
                cwd=str(path.parent),
                env=env,
                capture_output=True,
                text=True,
                timeout=6,
                check=False,
            )
        except Exception as exc:
            return False, str(exc)
        if cp.returncode == 0 and "SELFTEST:PASS" in cp.stdout:
            return True, "PASS"
        return False, (cp.stdout + "\n" + cp.stderr).strip()[:500]

    @staticmethod
    def repair(spec: CodeSpec, text: str, errors: list[str]) -> str:
        out = text
        # Deterministic, bounded repairs only. No guessed semantic rewrites.
        if spec.language == "python" and not out.endswith("\n"):
            out += "\n"
        if spec.language == "html":
            if "<!doctype html>" not in out.lower():
                out = "<!doctype html>\n" + out
            if "</html>" not in out.lower() and "<html" in out.lower():
                out += "\n</html>\n"
        if spec.language in {"json", "markdown"} and not out.endswith("\n"):
            out += "\n"
        return out

    @staticmethod
    def _python_calculator() -> str:
        return r'''#!/usr/bin/env python3
from __future__ import annotations
import ast
import operator
import sys

OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        a, b = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(b) > 12:
            raise ValueError("exponent too large")
        return OPS[type(node.op)](a, b)
    raise ValueError("unsupported expression")

def calculate(expr: str):
    expr = expr.replace("×", "*").replace("÷", "/").replace("^", "**")
    return _eval(ast.parse(expr, mode="eval"))

def self_test() -> None:
    cases = {"2+3": 5, "10-4": 6, "6*7": 42, "8/2": 4.0, "2^3": 8}
    for expr, expected in cases.items():
        actual = calculate(expr)
        assert actual == expected, (expr, actual, expected)
    print("SELFTEST:PASS")

def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        self_test(); return
    expr = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else input("式: ").strip()
    try:
        print(calculate(expr))
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2)

if __name__ == "__main__":
    main()
'''

    @staticmethod
    def _python_csv_stats() -> str:
        return r'''#!/usr/bin/env python3
from __future__ import annotations
import csv
import statistics
import sys


def summarize(values):
    nums = [float(x) for x in values]
    if not nums:
        raise ValueError("numeric values are empty")
    return {
        "count": len(nums),
        "mean": statistics.fmean(nums),
        "median": statistics.median(nums),
        "min": min(nums),
        "max": max(nums),
    }


def read_numeric_csv(path: str):
    values = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            for cell in row:
                try:
                    values.append(float(cell.strip()))
                except (ValueError, TypeError):
                    pass
    return values


def self_test() -> None:
    out = summarize([1, 2, 3, 4, 5])
    assert out == {"count": 5, "mean": 3.0, "median": 3.0, "min": 1.0, "max": 5.0}
    print("SELFTEST:PASS")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        self_test(); return
    if len(sys.argv) != 2:
        print("usage: python3 fap_csv_stats.py data.csv")
        raise SystemExit(2)
    result = summarize(read_numeric_csv(sys.argv[1]))
    for key, value in result.items():
        print(f"{key}: {value}")

if __name__ == "__main__":
    main()
'''

    @staticmethod
    def _html_notepad() -> str:
        return r'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>FAP Notepad</title><style>:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#07110f;color:#effff6;font-family:system-ui,sans-serif;min-height:100vh}.app{max-width:760px;margin:auto;padding:20px}textarea{width:100%;min-height:62vh;background:#0d1d19;color:#effff6;border:1px solid #31564a;border-radius:14px;padding:14px;font:16px/1.6 system-ui;resize:vertical}button{padding:11px 16px;border-radius:12px;border:1px solid #31564a;background:#10251f;color:#effff6;font-weight:800}.bar{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap}.status{opacity:.75;font-size:13px}</style></head>
<body><main class="app"><div class="bar"><h1>FAP Notepad</h1><div><button id="clear">CLEAR</button></div></div><textarea id="note" placeholder="ここにメモ"></textarea><p id="status" class="status">ローカル保存</p></main><script>
const KEY='fap_notepad_v1';const note=document.getElementById('note'),status=document.getElementById('status');note.value=localStorage.getItem(KEY)||'';let timer;note.addEventListener('input',()=>{clearTimeout(timer);status.textContent='編集中…';timer=setTimeout(()=>{localStorage.setItem(KEY,note.value);status.textContent='保存しました';},180)});document.getElementById('clear').addEventListener('click',()=>{note.value='';localStorage.removeItem(KEY);status.textContent='clearしました';note.focus()});
</script></body></html>
'''

    @staticmethod
    def _html_counter() -> str:
        return r'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>FAP Counter</title><style>:root{color-scheme:dark}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#07110f;color:#effff6;font-family:system-ui,sans-serif}.app{text-align:center}.num{font-size:72px;font-weight:900;margin:22px}.buttons{display:flex;gap:10px;justify-content:center}button{min-width:90px;padding:14px;border:1px solid #31564a;border-radius:14px;background:#10251f;color:#effff6;font-size:20px;font-weight:800}</style></head><body><main class="app"><h1>FAP Counter</h1><div class="num" id="count">0</div><div class="buttons"><button id="minus">−</button><button id="plus">＋</button><button id="reset">RESET</button></div></main><script>
let count=0;const view=document.getElementById('count');function render(){view.textContent=count}function increment(){count++;render()}function decrement(){count--;render()}function reset(){count=0;render()}document.getElementById('plus').addEventListener('click',increment);document.getElementById('minus').addEventListener('click',decrement);document.getElementById('reset').addEventListener('click',reset);render();
</script></body></html>
'''
