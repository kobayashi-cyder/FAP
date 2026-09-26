from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import operator
import re
from pathlib import Path
from typing import Any, Mapping

from fap_benchmark_reasoning import StructuredMCQParser
from fap_factual_qa import FactualQAOrgan
from fap_generic_derivation import GenericDerivationEngine
from fap_generic_rule_reasoner import GenericRuleReasoner
from fap_1x_grounded_retrieval import GroundedRetrievalReasoner


@dataclass(frozen=True)
class VerificationReport:
    status: str
    verifier: str
    score: float
    checks: tuple[str, ...]
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_NUM = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
_EXPR = re.compile(
    r"(?<![A-Za-z0-9_.])"
    r"(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\s*[+\-*/×÷]\s*"
    r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
    r"(?![A-Za-z0-9_.])"
)
_ANSWER = re.compile(r"(?i)Answer\s*:\s*\$?([A-D])\$?")


class IndependentCandidateVerifier:
    """Verifier separated from candidate generation.

    Deterministic arithmetic and supported physics formulae are recomputed here
    without calling the generator solver. Other lanes are corroborated by a
    fresh reasoning instance and structural evidence checks.
    """

    C = 299_792_458.0
    H = 6.62607015e-34
    KE = 8.9875517923e9
    R = 8.31446261815324
    WIEN_B = 2.897771955e-3
    SIGMA = 5.670374419e-8

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.parser = StructuredMCQParser()

    @staticmethod
    def _answer_letter(payload: Mapping[str, Any]) -> str:
        match = _ANSWER.search(str(payload.get("reply") or payload.get("text") or ""))
        return match.group(1).upper() if match else ""

    @staticmethod
    def _option_number(value: str) -> float | None:
        match = _NUM.search(str(value).replace(",", ""))
        if match is None:
            return None
        number = float(match.group(0))
        low = str(value).lower()
        if re.search(r"(?:nm|nanometer)", low):
            number *= 1e-9
        elif re.search(r"(?:μm|um|micrometer)", low):
            number *= 1e-6
        elif "%" in low or "percent" in low:
            # keep percentage in percent units; solver payload may also use %
            pass
        return number

    @staticmethod
    def _close(a: float, b: float, rel: float = 0.04) -> bool:
        return math.isclose(float(a), float(b), rel_tol=rel, abs_tol=max(1e-12, abs(float(b)) * rel))

    def _verify_arithmetic(
        self,
        query: str,
        payload: Mapping[str, Any],
    ) -> VerificationReport:
        task = self.parser.parse(query)
        if task is None:
            return VerificationReport("indeterminate", "arithmetic_recompute", 0.0, (), "not an MCQ")
        exprs = _EXPR.findall(task.question)
        if len(exprs) != 1:
            return VerificationReport("indeterminate", "arithmetic_recompute", 0.0, (), "no unique arithmetic expression")
        expr = exprs[0].replace("×", "*").replace("÷", "/")
        match = re.fullmatch(
            r"\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*([+\-*/])\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*",
            expr,
        )
        if match is None:
            return VerificationReport("indeterminate", "arithmetic_recompute", 0.0, (), "expression parser declined")
        a = float(match.group(1))
        b = float(match.group(3))
        ops = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv}
        if match.group(2) == "/" and b == 0:
            return VerificationReport("failed", "arithmetic_recompute", 1.0, ("division_by_zero",), "invalid arithmetic task")
        expected = float(ops[match.group(2)](a, b))
        letter = self._answer_letter(payload)
        option = task.choices.get(letter, "")
        option_value = self._option_number(option)
        ok = option_value is not None and self._close(option_value, expected, rel=1e-12)
        return VerificationReport(
            "passed" if ok else "failed",
            "arithmetic_recompute",
            1.0 if ok else 0.0,
            (f"expected={expected:g}", f"letter={letter}", f"option={option}"),
            "" if ok else "selected option does not equal independently recomputed value",
        )

    def _physics_expected(
        self,
        solver: str,
        details: Mapping[str, Any],
        unit: str,
    ) -> float | None:
        d = details
        try:
            if solver == "newton_second_law":
                return float(d["mass_kg"]) * float(d["acceleration_m_s2"])
            if solver == "linear_momentum":
                return float(d["mass_kg"]) * float(d["velocity_m_s"])
            if solver == "gravitational_potential_energy":
                return float(d["mass_kg"]) * float(d["g_m_s2"]) * float(d["height_m"])
            if solver == "centripetal_acceleration":
                return float(d["velocity_m_s"]) ** 2 / float(d["radius_m"])
            if solver == "wave_speed":
                return float(d["frequency_hz"]) * float(d["wavelength_m"])
            if solver == "light_frequency_from_wavelength":
                return self.C / float(d["wavelength_m"])
            if solver == "de_broglie_wavelength":
                return self.H / float(d["momentum_kg_m_s"])
            if solver == "coulomb_force":
                return self.KE * abs(float(d["q1_C"]) * float(d["q2_C"])) / float(d["r_m"]) ** 2
            if solver == "ideal_gas_pressure":
                return float(d["n_mol"]) * self.R * float(d["T_K"]) / float(d["V_m3"])
            if solver == "wien_peak_wavelength":
                return self.WIEN_B / float(d["T_K"])
            if solver == "stefan_boltzmann_flux":
                return self.SIGMA * float(d["T_K"]) ** 4
            if solver == "radioactive_half_life":
                fraction = 0.5 ** (float(d["elapsed"]) / float(d["half_life"]))
                return fraction * 100.0 if unit == "%" else fraction
            if solver == "ohms_law_voltage":
                return float(d["current_A"]) * float(d["resistance_ohm"])
            if solver == "electric_power":
                return float(d["voltage_V"]) * float(d["current_A"])
        except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
            return None
        return None

    def _verify_physics(
        self,
        query: str,
        payload: Mapping[str, Any],
    ) -> VerificationReport:
        task = self.parser.parse(query)
        block = payload.get("physics_deterministic")
        if task is None or not isinstance(block, Mapping):
            return VerificationReport("indeterminate", "physics_formula_recompute", 0.0, (), "missing structured physics evidence")
        solver = str(block.get("solver") or "")
        details = block.get("details")
        if not isinstance(details, Mapping):
            return VerificationReport("indeterminate", "physics_formula_recompute", 0.0, (), "missing solver details")
        expected = self._physics_expected(solver, details, str(block.get("unit") or ""))
        if expected is None or not math.isfinite(expected):
            return VerificationReport("indeterminate", "physics_formula_recompute", 0.0, (), f"unsupported solver={solver}")
        generator_value = float(block.get("value"))
        letter = self._answer_letter(payload)
        option_value = self._option_number(task.choices.get(letter, ""))
        generator_ok = self._close(generator_value, expected, rel=0.01)
        option_ok = option_value is not None and self._close(option_value, expected, rel=0.09)
        ok = generator_ok and option_ok
        return VerificationReport(
            "passed" if ok else "failed",
            "physics_formula_recompute",
            1.0 if ok else 0.0,
            (
                f"solver={solver}",
                f"expected={expected:.12g}",
                f"generator={generator_value:.12g}",
                f"letter={letter}",
            ),
            "" if ok else "independent formula recomputation disagrees with candidate",
        )

    def _verify_fact(self, query: str, payload: Mapping[str, Any]) -> VerificationReport:
        organ = FactualQAOrgan()
        rerun = organ.run(query)
        ok = bool(
            rerun
            and rerun.get("fact_id")
            and rerun.get("fact_id") == payload.get("fact_id")
            and str(rerun.get("reply") or "") == str(payload.get("reply") or "")
        )
        return VerificationReport(
            "passed" if ok else "failed",
            "fresh_fact_catalog_match",
            0.92 if ok else 0.0,
            (f"fact_id={payload.get('fact_id')}",),
            "" if ok else "fresh local fact lookup did not reproduce the candidate",
        )

    def _verify_rule(
        self,
        query: str,
        history: list[Mapping[str, Any]],
        payload: Mapping[str, Any],
    ) -> VerificationReport:
        rerun = GenericRuleReasoner(self.root).run(query, history)
        ok = bool(
            rerun
            and rerun.get("rule_verified")
            and rerun.get("subject_id") == payload.get("subject_id")
            and rerun.get("relation_id") == payload.get("relation_id")
            and self._close(float(rerun.get("value")), float(payload.get("value")), rel=1e-12)
            and tuple(rerun.get("evidence_ids") or ()) == tuple(payload.get("evidence_ids") or ())
        )
        return VerificationReport(
            "passed" if ok else "failed",
            "fresh_rule_replay",
            0.86 if ok else 0.0,
            tuple(str(x) for x in (payload.get("evidence_ids") or ())),
            "" if ok else "fresh rule replay did not reproduce value/evidence",
        )

    def _verify_derivation(
        self,
        query: str,
        history: list[Mapping[str, Any]],
        payload: Mapping[str, Any],
    ) -> VerificationReport:
        rerun = GenericDerivationEngine(self.root).run(query, history)
        ok = bool(
            rerun
            and rerun.get("derivation_verified")
            and rerun.get("derivation_id") == payload.get("derivation_id")
            and tuple(rerun.get("derivation_coefficients") or ()) == tuple(payload.get("derivation_coefficients") or ())
            and "independent-countercheck" in tuple(rerun.get("route_tags") or ())
        )
        return VerificationReport(
            "passed" if ok else "failed",
            "fresh_symbolic_replay",
            0.90 if ok else 0.0,
            tuple(str(x) for x in (payload.get("evidence_ids") or ())),
            "" if ok else "fresh symbolic replay/countercheck did not reproduce candidate",
        )

    def _verify_grounded_retrieval(
        self,
        query: str,
        history: list[Mapping[str, Any]],
        payload: Mapping[str, Any],
    ) -> VerificationReport:
        rerun = GroundedRetrievalReasoner(self.root).run(query, history)
        ok = bool(
            rerun
            and rerun.get("ok")
            and not rerun.get("needs_live_retrieval")
            and tuple(rerun.get("evidence_ids") or ()) == tuple(payload.get("evidence_ids") or ())
            and tuple(rerun.get("evidence_sources") or ()) == tuple(payload.get("evidence_sources") or ())
            and str(rerun.get("reply") or "") == str(payload.get("reply") or "")
        )
        return VerificationReport(
            "passed" if ok else "failed",
            "fresh_grounded_retrieval_replay",
            0.78 if ok else 0.0,
            tuple(str(x) for x in (payload.get("evidence_ids") or ())),
            "" if ok else "fresh retrieval did not reproduce the same evidence-backed extract",
        )

    def verify(
        self,
        source: str,
        query: str,
        history: list[Mapping[str, Any]],
        payload: Mapping[str, Any],
    ) -> VerificationReport:
        if source == "verified_arithmetic":
            return self._verify_arithmetic(query, payload)
        if source == "deterministic_physics":
            return self._verify_physics(query, payload)
        if source == "local_fact":
            return self._verify_fact(query, payload)
        if source == "rule_verified":
            return self._verify_rule(query, history, payload)
        if source == "derivation_verified":
            return self._verify_derivation(query, history, payload)
        if source == "grounded_retrieval":
            return self._verify_grounded_retrieval(query, history, payload)
        if source == "option_conditioned_science":
            return VerificationReport(
                "indeterminate",
                "evidence_margin_only",
                0.55,
                ("scientific_lane_has_evidence_but_no_independent_truth_oracle",),
                "supported, not independently verified",
            )
        if source == "hypothesis_provisional":
            return VerificationReport(
                "indeterminate",
                "falsifiability_check",
                0.35,
                ("hypothesis_remains_provisional",),
                "hypothesis generation is not fact verification",
            )
        return VerificationReport("indeterminate", "none", 0.0, (), "no verifier registered")
