from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Callable

from fap_benchmark_reasoning import MCQDecision, MCQTask


_NUM = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


@dataclass(frozen=True)
class PhysicsSolverResult:
    decision: MCQDecision
    solver: str
    value: float
    unit: str
    details: dict[str, Any]


def _extract(patterns: tuple[str, ...], text: str) -> float | None:
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if not m:
            continue
        try:
            return float(m.group(1))
        except (ValueError, TypeError):
            pass
    return None


def _choices_with_unit(choices, unit_pattern: str, scale: float = 1.0) -> list[tuple[str, float]]:
    rx = re.compile(rf"(?i)({_NUM})\s*{unit_pattern}")
    out: list[tuple[str, float]] = []
    for letter, text in choices.items():
        m = rx.search(str(text))
        if m:
            try:
                out.append((letter, float(m.group(1)) * scale))
            except ValueError:
                pass
    return out


def _plain_numeric_choices(choices) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    rx = re.compile(rf"^\s*({_NUM})\s*$")
    for letter, text in choices.items():
        m = rx.match(str(text))
        if m:
            out.append((letter, float(m.group(1))))
    return out


def _nearest(target: float, candidates: list[tuple[str, float]], rel: float = 0.06) -> tuple[str, float] | None:
    if not math.isfinite(target) or not candidates:
        return None
    ranked = sorted((abs(v-target), letter, v) for letter, v in candidates)
    if len(ranked) > 1 and math.isclose(ranked[0][0], ranked[1][0], rel_tol=1e-12, abs_tol=1e-12):
        return None
    err, letter, value = ranked[0]
    if err / max(abs(target), 1e-15) > rel:
        return None
    return letter, value


def _result(letter: str, solver: str, value: float, unit: str, rationale: str, details: dict[str, Any], confidence: float = 0.99) -> PhysicsSolverResult:
    return PhysicsSolverResult(
        MCQDecision(letter, "physics_deterministic_solver", confidence, rationale),
        solver,
        value,
        unit,
        details,
    )


class ExpandedPhysicsSolver:
    """Generic equation solvers with strict semantic and unit guards.

    These solvers contain equations/constants only. They do not contain benchmark
    prompts, answer keys, or option-specific heuristics.
    """

    G = 6.67430e-11
    H = 6.62607015e-34
    C = 299792458.0
    KB = 1.380649e-23
    R = 8.31446261815324
    EPS0 = 8.8541878128e-12
    KE = 1.0 / (4.0 * math.pi * EPS0)
    SIGMA = 5.670374419e-8
    WIEN = 2.897771955e-3
    G_STD = 9.80665

    def _newton_second(self, task: MCQTask) -> PhysicsSolverResult | None:
        q = task.question
        low = q.lower()
        if not (("net force" in low or "force" in low) and "mass" in low and "acceleration" in low):
            return None
        m = _extract((rf"(?:mass|m)\s*(?:is|=|:)\s*({_NUM})\s*kg\b",), q)
        a = _extract((rf"(?:acceleration|a)\s*(?:is|=|:)\s*({_NUM})\s*m\s*/\s*s(?:\^?2|²)\b",), q)
        if m is None or a is None or m <= 0:
            return None
        value = m * a
        near = _nearest(value, _choices_with_unit(task.choices, r"(?:n|newtons?)\b"), 0.04)
        if not near:
            return None
        letter, matched = near
        return _result(letter, "newton_second_law", value, "N", f"F=ma={value:.8g} N", {"mass_kg":m,"acceleration_m_s2":a,"matched":matched})

    def _momentum(self, task: MCQTask) -> PhysicsSolverResult | None:
        q = task.question
        low = q.lower()
        if "momentum" not in low or "mass" not in low or not ("speed" in low or "velocity" in low):
            return None
        m = _extract((rf"(?:mass|m)\s*(?:is|=|:)\s*({_NUM})\s*kg\b",), q)
        v = _extract((rf"(?:speed|velocity|v)\s*(?:is|=|:)\s*({_NUM})\s*m\s*/\s*s\b",), q)
        if m is None or v is None or m <= 0:
            return None
        value = m*v
        cands = _choices_with_unit(task.choices, r"(?:kg\s*[·*]?\s*m\s*/\s*s|kg\s*m\s*s\^-?1)\b")
        near = _nearest(value, cands, 0.04)
        if not near:
            return None
        letter, matched = near
        return _result(letter,"linear_momentum",value,"kg m/s",f"p=mv={value:.8g} kg m/s",{"mass_kg":m,"velocity_m_s":v,"matched":matched})

    def _potential_energy(self, task: MCQTask) -> PhysicsSolverResult | None:
        q = task.question
        low = q.lower()
        if not ("gravitational potential energy" in low or ("potential energy" in low and "height" in low)):
            return None
        m = _extract((rf"(?:mass|m)\s*(?:is|=|:)\s*({_NUM})\s*kg\b",), q)
        h = _extract((rf"(?:height|h)\s*(?:is|=|:)\s*({_NUM})\s*m\b",), q)
        g = _extract((rf"(?:g|gravitational acceleration)\s*(?:is|=|:)\s*({_NUM})\s*m\s*/\s*s(?:\^?2|²)\b",), q)
        if m is None or h is None or m <= 0 or h < 0:
            return None
        g = self.G_STD if g is None else g
        value = m*g*h
        near = _nearest(value, _choices_with_unit(task.choices, r"(?:j|joules?)\b"), 0.06)
        if not near:
            return None
        letter, matched = near
        return _result(letter,"gravitational_potential_energy",value,"J",f"U=mgh={value:.8g} J",{"mass_kg":m,"height_m":h,"g_m_s2":g,"matched":matched})

    def _centripetal_acceleration(self, task: MCQTask) -> PhysicsSolverResult | None:
        q = task.question
        low = q.lower()
        if "centripetal acceleration" not in low:
            return None
        v = _extract((rf"(?:speed|velocity|v)\s*(?:is|=|:)\s*({_NUM})\s*m\s*/\s*s\b",), q)
        r = _extract((rf"(?:radius|r)\s*(?:is|=|:)\s*({_NUM})\s*m\b",), q)
        if v is None or r is None or r <= 0:
            return None
        value = v*v/r
        near = _nearest(value, _choices_with_unit(task.choices, r"m\s*/\s*s(?:\^?2|²)\b"), 0.05)
        if not near:
            return None
        letter, matched = near
        return _result(letter,"centripetal_acceleration",value,"m/s^2",f"a_c=v^2/r={value:.8g} m/s^2",{"velocity_m_s":v,"radius_m":r,"matched":matched})

    def _wave_speed(self, task: MCQTask) -> PhysicsSolverResult | None:
        q = task.question
        low = q.lower()
        if not ("wave" in low and "frequency" in low and "wavelength" in low):
            return None
        f = _extract((rf"(?:frequency|f)\s*(?:is|=|:)\s*({_NUM})\s*(?:hz|hertz)\b",), q)
        lam = _extract((rf"(?:wavelength|lambda|λ)\s*(?:is|=|:)\s*({_NUM})\s*m\b",), q)
        if f is None or lam is None or f <= 0 or lam <= 0:
            return None
        value = f*lam
        near = _nearest(value, _choices_with_unit(task.choices, r"m\s*/\s*s\b"), 0.05)
        if not near:
            return None
        letter, matched = near
        return _result(letter,"wave_speed",value,"m/s",f"v=f lambda={value:.8g} m/s",{"frequency_hz":f,"wavelength_m":lam,"matched":matched})

    def _frequency_from_wavelength(self, task: MCQTask) -> PhysicsSolverResult | None:
        q = task.question
        low = q.lower()
        if not ("electromagnetic" in low or "light" in low or "photon" in low):
            return None
        if "wavelength" not in low or "frequency" not in low:
            return None
        m_nm = re.search(rf"(?i)(?:wavelength|lambda|λ)[^\d]{{0,30}}({_NUM})\s*nm\b", q)
        m_m = re.search(rf"(?i)(?:wavelength|lambda|λ)[^\d]{{0,30}}({_NUM})\s*m\b", q)
        if m_nm:
            lam = float(m_nm.group(1))*1e-9
        elif m_m:
            lam = float(m_m.group(1))
        else:
            return None
        if lam <= 0:
            return None
        value = self.C/lam
        cands = _choices_with_unit(task.choices, r"(?:hz|hertz)\b")
        near = _nearest(value,cands,0.06)
        if not near:
            return None
        letter, matched = near
        return _result(letter,"light_frequency_from_wavelength",value,"Hz",f"f=c/lambda={value:.8g} Hz",{"wavelength_m":lam,"matched":matched})

    def _de_broglie(self, task: MCQTask) -> PhysicsSolverResult | None:
        q = task.question
        low = q.lower()
        if not ("de broglie" in low and "momentum" in low and "wavelength" in low):
            return None
        p = _extract((rf"(?:momentum|p)\s*(?:is|=|:)\s*({_NUM})\s*kg\s*[·*]?\s*m\s*/\s*s\b",), q)
        if p is None or p <= 0:
            return None
        lam = self.H/p
        candidates = []
        candidates.extend(_choices_with_unit(task.choices,r"m\b"))
        candidates.extend(_choices_with_unit(task.choices,r"nm\b",1e-9))
        # duplicate parsing of "nm" by m-pattern is avoided by only accepting close candidate
        near = _nearest(lam,candidates,0.06)
        if not near:
            return None
        letter, matched = near
        return _result(letter,"de_broglie_wavelength",lam,"m",f"lambda=h/p={lam:.8g} m",{"momentum_kg_m_s":p,"matched_m":matched})

    def _coulomb_force(self, task: MCQTask) -> PhysicsSolverResult | None:
        q=task.question
        low=q.lower()
        if not ("coulomb" in low or "electrostatic force" in low):
            return None
        q1=_extract((rf"(?:q1|charge 1|first charge)\s*(?:is|=|:)\s*({_NUM})\s*c\b",),q)
        q2=_extract((rf"(?:q2|charge 2|second charge)\s*(?:is|=|:)\s*({_NUM})\s*c\b",),q)
        r=_extract((rf"(?:distance|separation|r)\s*(?:is|=|:)\s*({_NUM})\s*m\b",),q)
        if q1 is None or q2 is None or r is None or r<=0:
            return None
        value=self.KE*abs(q1*q2)/(r*r)
        near=_nearest(value,_choices_with_unit(task.choices,r"(?:n|newtons?)\b"),0.08)
        if not near:
            return None
        letter,matched=near
        return _result(letter,"coulomb_force",value,"N",f"F=k|q1q2|/r^2={value:.8g} N",{"q1_C":q1,"q2_C":q2,"r_m":r,"matched":matched})

    def _ideal_gas_pressure(self, task: MCQTask) -> PhysicsSolverResult | None:
        q=task.question
        low=q.lower()
        if not ("ideal gas" in low and "pressure" in low):
            return None
        n=_extract((rf"(?:moles|n)\s*(?:is|=|:)\s*({_NUM})\s*(?:mol|moles?)\b",),q)
        T=_extract((rf"(?:temperature|t)\s*(?:is|=|:)\s*({_NUM})\s*k\b",),q)
        V=_extract((rf"(?:volume|v)\s*(?:is|=|:)\s*({_NUM})\s*m(?:\^?3|³)\b",),q)
        if n is None or T is None or V is None or n<=0 or T<=0 or V<=0:
            return None
        value=n*self.R*T/V
        near=_nearest(value,_choices_with_unit(task.choices,r"(?:pa|pascals?)\b"),0.08)
        if not near:
            return None
        letter,matched=near
        return _result(letter,"ideal_gas_pressure",value,"Pa",f"P=nRT/V={value:.8g} Pa",{"n_mol":n,"T_K":T,"V_m3":V,"matched":matched})

    def _wien_peak(self, task: MCQTask) -> PhysicsSolverResult | None:
        q=task.question
        low=q.lower()
        if not ("blackbody" in low and ("peak wavelength" in low or "wien" in low)):
            return None
        T=_extract((rf"(?:temperature|t)\s*(?:is|=|:)\s*({_NUM})\s*k\b",),q)
        if T is None or T<=0:
            return None
        lam=self.WIEN/T
        cands=[]
        cands.extend(_choices_with_unit(task.choices,r"(?:m|meter|meters)\b"))
        cands.extend(_choices_with_unit(task.choices,r"(?:um|μm|micrometers?)\b",1e-6))
        cands.extend(_choices_with_unit(task.choices,r"(?:nm|nanometers?)\b",1e-9))
        near=_nearest(lam,cands,0.08)
        if not near:
            return None
        letter,matched=near
        return _result(letter,"wien_peak_wavelength",lam,"m",f"lambda_max=b/T={lam:.8g} m",{"T_K":T,"matched_m":matched})

    def _stefan_boltzmann_flux(self, task: MCQTask) -> PhysicsSolverResult | None:
        q=task.question
        low=q.lower()
        if not (("stefan" in low or "blackbody" in low) and ("radiative flux" in low or "power per unit area" in low or "emitted flux" in low)):
            return None
        T=_extract((rf"(?:temperature|t)\s*(?:is|=|:)\s*({_NUM})\s*k\b",),q)
        if T is None or T<=0:
            return None
        value=self.SIGMA*T**4
        near=_nearest(value,_choices_with_unit(task.choices,r"w\s*/\s*m(?:\^?2|²)\b"),0.08)
        if not near:
            return None
        letter,matched=near
        return _result(letter,"stefan_boltzmann_flux",value,"W/m^2",f"F=sigma T^4={value:.8g} W/m^2",{"T_K":T,"matched":matched})

    def _half_life_remaining(self, task: MCQTask) -> PhysicsSolverResult | None:
        q=task.question
        low=q.lower()
        if "half-life" not in low and "half life" not in low:
            return None
        if not ("remain" in low or "undecayed" in low or "fraction" in low or "percentage" in low):
            return None
        half=_extract((rf"(?:half[- ]life)\s*(?:is|=|:)\s*({_NUM})\s*(?:s|seconds?|min|minutes?|h|hours?|days?|years?)\b",),q)
        elapsed=_extract((rf"(?:after|elapsed time|time)\s*(?:is|=|:)?\s*({_NUM})\s*(?:s|seconds?|min|minutes?|h|hours?|days?|years?)\b",),q)
        if half is None or elapsed is None or half<=0 or elapsed<0:
            return None
        n=elapsed/half
        frac=0.5**n
        pct=100*frac
        cands_pct=_choices_with_unit(task.choices,r"%")
        near=_nearest(pct,cands_pct,0.04)
        unit="%"
        value=pct
        if not near:
            near=_nearest(frac,_plain_numeric_choices(task.choices),0.04)
            unit="fraction"
            value=frac
        if not near:
            return None
        letter,matched=near
        return _result(letter,"radioactive_half_life",value,unit,f"remaining=(1/2)^(t/t_half)={frac:.8g}",{"half_life":half,"elapsed":elapsed,"n_half_lives":n,"matched":matched})

    def _ohms_law(self, task: MCQTask) -> PhysicsSolverResult | None:
        q=task.question
        low=q.lower()
        if not ("ohm" in low or ("voltage" in low and "current" in low and "resistance" in low)):
            return None
        I=_extract((rf"(?:current|i)\s*(?:is|=|:)\s*({_NUM})\s*a\b",),q)
        R=_extract((rf"(?:resistance|r)\s*(?:is|=|:)\s*({_NUM})\s*(?:ohm|ohms|Ω)\b",),q)
        if I is None or R is None or I<0 or R<0:
            return None
        value=I*R
        near=_nearest(value,_choices_with_unit(task.choices,r"(?:v|volts?)\b"),0.04)
        if not near:
            return None
        letter,matched=near
        return _result(letter,"ohms_law_voltage",value,"V",f"V=IR={value:.8g} V",{"current_A":I,"resistance_ohm":R,"matched":matched})

    def _electric_power(self, task: MCQTask) -> PhysicsSolverResult | None:
        q=task.question
        low=q.lower()
        if not ("electric power" in low or ("power" in low and "voltage" in low and "current" in low)):
            return None
        V=_extract((rf"(?:voltage|potential difference|v)\s*(?:is|=|:)\s*({_NUM})\s*v\b",),q)
        I=_extract((rf"(?:current|i)\s*(?:is|=|:)\s*({_NUM})\s*a\b",),q)
        if V is None or I is None:
            return None
        value=V*I
        near=_nearest(value,_choices_with_unit(task.choices,r"(?:w|watts?)\b"),0.04)
        if not near:
            return None
        letter,matched=near
        return _result(letter,"electric_power",value,"W",f"P=VI={value:.8g} W",{"voltage_V":V,"current_A":I,"matched":matched})

    def solve(self, task: MCQTask) -> PhysicsSolverResult | None:
        solvers: tuple[Callable[[MCQTask], PhysicsSolverResult | None], ...] = (
            self._newton_second,
            self._momentum,
            self._potential_energy,
            self._centripetal_acceleration,
            self._wave_speed,
            self._frequency_from_wavelength,
            self._de_broglie,
            self._coulomb_force,
            self._ideal_gas_pressure,
            self._wien_peak,
            self._stefan_boltzmann_flux,
            self._half_life_remaining,
            self._ohms_law,
            self._electric_power,
        )
        for solver in solvers:
            out=solver(task)
            if out is not None:
                return out
        return None

    def run(self, task: MCQTask) -> dict[str, Any] | None:
        out=self.solve(task)
        if out is None:
            return None
        d=out.decision
        return {
            "ok":True,
            "reply":d.rationale+"\nAnswer: $"+d.letter,
            "confidence":d.confidence,
            "decision_source":d.source,
            "domain":task.domain,
            "forced_choice":False,
            "needs_teacher":False,
            "physics_deterministic":{
                "used":True,
                "solver":out.solver,
                "value":out.value,
                "unit":out.unit,
                "details":out.details,
            },
        }
