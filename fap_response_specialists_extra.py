from __future__ import annotations

import ast
import math
import re
from typing import Any, Mapping


_LINEAR_EQ_CUE = re.compile(r"(方程式|解いて|solve|equation|x\s*=)", re.I)
_LINEAR_EQ = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"([+-]?(?:\d+(?:\.\d+)?)?)\s*\*?\s*x"
    r"\s*([+-])\s*(\d+(?:\.\d+)?)\s*=\s*"
    r"([+-]?\d+(?:\.\d+)?)"
    r"(?![A-Za-z0-9_])",
    re.I,
)
_PHYSICS_CUE = re.compile(
    r"(force|mass|acceleration|momentum|velocity|speed|potential energy|kinetic energy|"
    r"voltage|current|resistance|power|frequency|wavelength|"
    r"力|質量|加速度|運動量|速度|位置エネルギー|運動エネルギー|電圧|電流|抵抗|電力|周波数|波長)",
    re.I,
)
_CODE_BLOCK = re.compile(r"`{3}(?:python|py)?\s*\n(.*?)`{3}", re.I | re.S)
_ASSIGN_NUMERIC = re.compile(
    r"(?im)^\s*([A-Za-z_][A-Za-z0-9_ -]{0,40})\s*[:=]\s*"
    r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*"
    r"([A-Za-z/%^0-9·²³_-]{0,12})\s*$"
)


class LinearEquationSpecialist:
    """Solve a narrow, explicitly recognized one-variable linear equation."""

    def run(self, text: str) -> dict[str, Any] | None:
        value = str(text or "")
        if not _LINEAR_EQ_CUE.search(value):
            return None
        m = _LINEAR_EQ.search(value.replace("−", "-").replace("＋", "+"))
        if not m:
            return None
        a_raw, sign, b_raw, c_raw = m.groups()
        a = -1.0 if a_raw == "-" else (1.0 if a_raw in {"", "+"} else float(a_raw))
        b_abs = float(b_raw)
        b = b_abs if sign == "+" else -b_abs
        c = float(c_raw)
        if abs(a) < 1e-15:
            return None
        x = (c - b) / a
        if not math.isfinite(x):
            return None
        shown = int(x) if float(x).is_integer() else round(x, 12)
        return {
            "ok": True,
            "reply": f"{a:g}x {sign} {b_abs:g} = {c:g} なので、x = {shown} です。",
            "confidence": 0.995,
            "verified": True,
            "grounded": True,
            "local": True,
            "linear_equation_verified": True,
            "decision_source": "verified_linear_equation",
        }


class PhysicsNumericSpecialist:
    """Strict free-response numerical physics solver for common SI formulas."""

    _NUM = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"

    @classmethod
    def _grab(cls, text: str, names: tuple[str, ...], unit: str) -> float | None:
        name = "|".join(re.escape(x) for x in names)
        m = re.search(rf"(?i)(?:{name})\s*(?:is|=|:|は)?\s*({cls._NUM})\s*{unit}", text)
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None

    def run(self, text: str) -> dict[str, Any] | None:
        q = str(text or "")
        low = q.lower()
        if not _PHYSICS_CUE.search(q):
            return None

        if ("force" in low or "力" in q) and ("mass" in low or "質量" in q) and ("acceleration" in low or "加速度" in q):
            mass = self._grab(q, ("mass", "質量", "m"), r"kg\b")
            acc = self._grab(q, ("acceleration", "加速度", "a"), r"m\s*/\s*s(?:\^?2|²)\b")
            if mass is not None and acc is not None and mass >= 0:
                return self._result("F=ma", mass * acc, "N", {"mass_kg": mass, "acceleration_m_s2": acc})

        if ("momentum" in low or "運動量" in q) and ("mass" in low or "質量" in q):
            mass = self._grab(q, ("mass", "質量", "m"), r"kg\b")
            vel = self._grab(q, ("velocity", "speed", "速度", "v"), r"m\s*/\s*s\b")
            if mass is not None and vel is not None and mass >= 0:
                return self._result("p=mv", mass * vel, "kg·m/s", {"mass_kg": mass, "velocity_m_s": vel})

        if "kinetic energy" in low or "運動エネルギー" in q:
            mass = self._grab(q, ("mass", "質量", "m"), r"kg\b")
            vel = self._grab(q, ("velocity", "speed", "速度", "v"), r"m\s*/\s*s\b")
            if mass is not None and vel is not None and mass >= 0:
                return self._result("K=1/2·m·v²", 0.5 * mass * vel * vel, "J", {"mass_kg": mass, "velocity_m_s": vel})

        if ("potential energy" in low or "位置エネルギー" in q) and ("height" in low or "高さ" in q):
            mass = self._grab(q, ("mass", "質量", "m"), r"kg\b")
            height = self._grab(q, ("height", "高さ", "h"), r"m\b")
            g = self._grab(q, ("gravity", "gravitational acceleration", "重力加速度", "g"), r"m\s*/\s*s(?:\^?2|²)\b")
            if mass is not None and height is not None and mass >= 0 and height >= 0:
                g = 9.80665 if g is None else g
                return self._result("U=mgh", mass * g * height, "J", {"mass_kg": mass, "height_m": height, "g_m_s2": g})

        if ("voltage" in low or "電圧" in q) and ("current" in low or "電流" in q) and ("resistance" in low or "抵抗" in q):
            current = self._grab(q, ("current", "電流", "i"), r"A\b")
            resistance = self._grab(q, ("resistance", "抵抗", "r"), r"(?:ohm|ohms|Ω)\b")
            if current is not None and resistance is not None and current >= 0 and resistance >= 0:
                return self._result("V=IR", current * resistance, "V", {"current_A": current, "resistance_ohm": resistance})

        if ("power" in low or "電力" in q) and ("voltage" in low or "電圧" in q) and ("current" in low or "電流" in q):
            voltage = self._grab(q, ("voltage", "電圧", "v"), r"V\b")
            current = self._grab(q, ("current", "電流", "i"), r"A\b")
            if voltage is not None and current is not None:
                return self._result("P=VI", voltage * current, "W", {"voltage_V": voltage, "current_A": current})

        if ("frequency" in low or "周波数" in q) and ("wavelength" in low or "波長" in q):
            freq = self._grab(q, ("frequency", "周波数", "f"), r"(?:Hz|hertz)\b")
            wave = self._grab(q, ("wavelength", "波長", "lambda", "λ"), r"m\b")
            if freq is not None and wave is not None and freq >= 0 and wave >= 0:
                return self._result("v=fλ", freq * wave, "m/s", {"frequency_hz": freq, "wavelength_m": wave})
        return None

    @staticmethod
    def _result(formula: str, value: float, unit: str, details: Mapping[str, float]) -> dict[str, Any]:
        if not math.isfinite(value):
            return {}
        return {
            "ok": True,
            "reply": f"{formula} より {value:.10g} {unit} です。",
            "confidence": 0.995,
            "verified": True,
            "grounded": True,
            "local": True,
            "physics_numeric_verified": True,
            "formula": formula,
            "value": value,
            "unit": unit,
            "details": dict(details),
            "decision_source": "verified_physics_numeric",
        }


class PythonStaticAnalysisSpecialist:
    """Parse Python source and report syntax/policy facts without executing it."""

    FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__"}
    FORBIDDEN_IMPORTS = {"subprocess", "socket", "ctypes", "multiprocessing"}

    def run(self, text: str) -> dict[str, Any] | None:
        raw = str(text or "")
        block = _CODE_BLOCK.search(raw)
        source = block.group(1) if block else ""
        if not source and "python" in raw.lower() and "\n" in raw and re.search(r"\b(def|class|import|from)\b", raw):
            source = raw
        if not source.strip():
            return None
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return {
                "ok": True,
                "reply": f"Python静的解析: 構文エラー line={exc.lineno}: {exc.msg}",
                "confidence": 0.995,
                "verified": True,
                "grounded": True,
                "local": True,
                "python_static_analysis": True,
                "syntax_ok": False,
                "issues": [f"syntax:{exc.msg}:line={exc.lineno}"],
            }

        issues: list[str] = []
        functions = 0
        classes = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions += 1
            elif isinstance(node, ast.ClassDef):
                classes += 1
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in self.FORBIDDEN_IMPORTS:
                        issues.append(f"forbidden_import:{root}")
            elif isinstance(node, ast.ImportFrom):
                root = str(node.module or "").split(".")[0]
                if root in self.FORBIDDEN_IMPORTS:
                    issues.append(f"forbidden_import:{root}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in self.FORBIDDEN_CALLS:
                issues.append(f"forbidden_call:{node.func.id}")

        status = "問題なし" if not issues else "要確認: " + ", ".join(sorted(set(issues)))
        return {
            "ok": True,
            "reply": f"Python静的解析: syntax=OK / functions={functions} / classes={classes} / {status}",
            "confidence": 0.995,
            "verified": True,
            "grounded": True,
            "local": True,
            "python_static_analysis": True,
            "syntax_ok": True,
            "issues": sorted(set(issues)),
            "functions": functions,
            "classes": classes,
        }


class NumericContradictionSpecialist:
    """Detect same-key numeric contradictions in the request/history."""

    def run(self, text: str, history: list[Mapping[str, Any]] | None = None) -> dict[str, Any] | None:
        corpus: list[str] = []
        for row in list(history or [])[-8:]:
            role = str(row.get("role") or "")
            if role in {"user", "assistant"}:
                corpus.append(str(row.get("text") or ""))
        corpus.append(str(text or ""))
        seen: dict[tuple[str, str], float] = {}
        conflicts: list[tuple[str, str, float, float]] = []
        for chunk in corpus:
            for key, raw, unit in _ASSIGN_NUMERIC.findall(chunk):
                norm_key = re.sub(r"\s+", " ", key.strip().casefold())
                norm_unit = unit.strip().casefold()
                value = float(raw)
                slot = (norm_key, norm_unit)
                if slot in seen and not math.isclose(seen[slot], value, rel_tol=1e-12, abs_tol=1e-12):
                    conflicts.append((norm_key, norm_unit, seen[slot], value))
                else:
                    seen[slot] = value
        if not conflicts:
            return None
        rows = [
            f"{key}: {a:g} と {b:g}" + (f" {unit}" if unit else "")
            for key, unit, a, b in conflicts[:6]
        ]
        return {
            "ok": True,
            "reply": "数値矛盾を検出しました: " + " / ".join(rows),
            "confidence": 0.99,
            "verified": True,
            "grounded": True,
            "local": True,
            "numeric_contradiction_verified": True,
            "conflicts": rows,
        }
