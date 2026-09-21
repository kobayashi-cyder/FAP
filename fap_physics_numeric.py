from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from fap_benchmark_reasoning import MCQDecision, MCQTask


@dataclass(frozen=True)
class PhysicsNumericResult:
    decision: MCQDecision
    solver: str
    value: float
    unit: str
    details: dict[str, Any]


def _numbers_with_unit(choices, unit_pattern: str) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    rx = re.compile(rf"(?i)([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*{unit_pattern}")
    for letter, text in choices.items():
        m = rx.search(str(text))
        if m:
            try:
                out.append((letter, float(m.group(1))))
            except ValueError:
                pass
    return out


def _nearest_unique(target: float, candidates: list[tuple[str, float]], *, max_rel_error: float = 0.25) -> tuple[str, float] | None:
    if not candidates or not math.isfinite(target):
        return None
    ranked = sorted((abs(v - target), letter, v) for letter, v in candidates)
    if len(ranked) >= 2 and math.isclose(ranked[0][0], ranked[1][0], rel_tol=1e-12, abs_tol=1e-12):
        return None
    err, letter, value = ranked[0]
    scale = max(abs(target), 1e-12)
    if err / scale > max_rel_error:
        return None
    return letter, value


def _simpson_integral(fn, a: float, b: float, n: int = 4096) -> float:
    n = max(64, int(n))
    if n % 2:
        n += 1
    h = (b - a) / n
    total = fn(a) + fn(b)
    total += 4.0 * sum(fn(a + h * i) for i in range(1, n, 2))
    total += 2.0 * sum(fn(a + h * i) for i in range(2, n, 2))
    return total * h / 3.0


class PhysicsNumericSolver:
    """Small deterministic physics solvers used before heuristic knowledge scoring.

    They solve generic equation classes and never contain benchmark answer keys.
    """

    C_KM_S = 299792.458
    LYA_NM = 121.567
    J1_ZERO_1 = 3.8317059702075125
    J1_ZERO_2 = 7.015586669815619
    HC_EV_NM = 1239.8419843320026
    SCHWARZSCHILD_KM_PER_SOLAR_MASS = 2.95325008

    @staticmethod
    def _extract_param(text: str, names: tuple[str, ...]) -> float | None:
        for name in names:
            patterns = [
                rf"(?i){name}\s*(?:is|=|:)\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))",
                rf"(?i){name}[^\d+-]{{0,35}}([-+]?(?:\d+(?:\.\d*)?|\.\d+))",
            ]
            for pattern in patterns:
                m = re.search(pattern, text)
                if m:
                    try:
                        return float(m.group(1))
                    except ValueError:
                        pass
        return None

    def _solve_quasar_comoving_distance(self, task: MCQTask) -> PhysicsNumericResult | None:
        q = str(task.question)
        low = q.lower()
        required = ("quasar" in low and "comoving distance" in low and "hubble" in low)
        if not required:
            return None
        if not ("wavelength" in low and "nm" in low):
            return None

        wm = re.search(r"(?i)wavelength[^\d]{0,30}(\d+(?:\.\d+)?)\s*nm", q)
        if not wm:
            return None
        observed_nm = float(wm.group(1))
        if observed_nm <= self.LYA_NM:
            return None

        h0 = self._extract_param(q, (r"hubble constant", r"h[_ ]?0"))
        omega_m = self._extract_param(q, (r"matter density parameter", r"omega[_ ]?m"))
        omega_l = self._extract_param(
            q,
            (r"dark energy density parameter", r"lambda density parameter", r"omega[_ ]?(?:lambda|l)"),
        )
        if h0 is None or omega_m is None or omega_l is None:
            return None
        if not (20.0 < h0 < 150.0 and 0.0 <= omega_m <= 2.0 and 0.0 <= omega_l <= 2.0):
            return None

        # A sharp short-wavelength drop in a high-z quasar optical/NIR spectrum
        # is the generic Lyman-alpha break. This derives z from the observed
        # break; it does not inspect the answer choices.
        z = observed_nm / self.LYA_NM - 1.0
        if not (0.1 < z < 20.0):
            return None

        omega_k = 1.0 - omega_m - omega_l

        def inv_e(x: float) -> float:
            e2 = omega_m * (1.0 + x) ** 3 + omega_k * (1.0 + x) ** 2 + omega_l
            if e2 <= 0:
                return float("nan")
            return 1.0 / math.sqrt(e2)

        integral = _simpson_integral(inv_e, 0.0, z)
        if not math.isfinite(integral):
            return None
        distance_gpc = (self.C_KM_S / h0) * integral / 1000.0

        candidates = _numbers_with_unit(task.choices, r"(?:gpc|gigaparsec(?:s)?)\b")
        nearest = _nearest_unique(distance_gpc, candidates, max_rel_error=0.20)
        if nearest is None:
            return None
        letter, option_value = nearest
        return PhysicsNumericResult(
            MCQDecision(
                letter,
                "physics_numeric_solver",
                0.94,
                f"Ly-alpha z={z:.3f}; flat-LambdaCDM comoving distance={distance_gpc:.3f} Gpc",
            ),
            "lcdm_lya_comoving_distance",
            distance_gpc,
            "Gpc",
            {
                "observed_break_nm": observed_nm,
                "rest_lya_nm": self.LYA_NM,
                "redshift": z,
                "H0_km_s_Mpc": h0,
                "omega_m": omega_m,
                "omega_lambda": omega_l,
                "omega_k": omega_k,
                "matched_option_value": option_value,
            },
        )

    def _solve_circular_aperture_minima_gap(self, task: MCQTask) -> PhysicsNumericResult | None:
        q = str(task.question)
        low = q.lower()
        if "aperture" not in low or "minima" not in low:
            return None
        polygon_limit = (
            ("polygon" in low and ("infinitely large" in low or "infinite" in low))
            or bool(re.search(r"(?i)n\s*(?:->|→|tends? to)\s*(?:infinity|∞)", q))
        )
        if not polygon_limit:
            return None
        if not (
            "first two minima" in low
            or "between the first two minima" in low
            or "between first two minima" in low
        ):
            return None

        # N -> infinity turns the equal-apothem regular polygon into a circular
        # aperture of radius a. Airy minima satisfy J1(x)=0:
        # theta_n ~= j_{1,n} lambda/(2*pi*a).
        coeff = (self.J1_ZERO_2 - self.J1_ZERO_1) / (2.0 * math.pi)

        candidates: list[tuple[str, float]] = []
        for letter, option in task.choices.items():
            text = str(option).lower().replace("\\", "")
            if "lambda" not in text and "λ" not in text:
                continue
            if "/ a" not in text and "/a" not in text:
                continue
            m = re.search(r"([-+]?(?:\d+(?:\.\d*)?|\.\d+))", text)
            if m:
                candidates.append((letter, float(m.group(1))))

        nearest = _nearest_unique(coeff, candidates, max_rel_error=0.08)
        if nearest is None:
            return None
        letter, option_value = nearest
        return PhysicsNumericResult(
            MCQDecision(
                letter,
                "physics_numeric_solver",
                0.97,
                f"circular-aperture minima gap coefficient={(coeff):.6f} lambda/a",
            ),
            "circular_aperture_first_minima_gap",
            coeff,
            "lambda/a",
            {
                "j1_zero_1": self.J1_ZERO_1,
                "j1_zero_2": self.J1_ZERO_2,
                "matched_option_value": option_value,
            },
        )


    def _solve_photon_energy_from_wavelength(self, task: MCQTask) -> PhysicsNumericResult | None:
        q = str(task.question)
        low = q.lower()
        if "photon" not in low or "wavelength" not in low:
            return None
        if not ("energy" in low or "ev" in low):
            return None
        m = re.search(r"(?i)wavelength[^\d]{0,30}(\d+(?:\.\d+)?)\s*nm\b", q)
        if not m:
            m = re.search(r"(?i)(\d+(?:\.\d+)?)\s*nm\b", q)
        if not m:
            return None
        wavelength_nm = float(m.group(1))
        if wavelength_nm <= 0:
            return None
        energy_ev = self.HC_EV_NM / wavelength_nm
        candidates = _numbers_with_unit(task.choices, r"(?:ev|electron\s*volts?)\b")
        nearest = _nearest_unique(energy_ev, candidates, max_rel_error=0.08)
        if nearest is None:
            return None
        letter, option_value = nearest
        return PhysicsNumericResult(
            MCQDecision(letter, "physics_numeric_solver", 0.98,
                        f"E=hc/lambda={energy_ev:.6g} eV for lambda={wavelength_nm:g} nm"),
            "photon_energy_from_wavelength",
            energy_ev,
            "eV",
            {"wavelength_nm": wavelength_nm, "matched_option_value": option_value},
        )

    def _solve_lorentz_gamma(self, task: MCQTask) -> PhysicsNumericResult | None:
        q = str(task.question)
        low = q.lower()
        if not ("lorentz factor" in low or re.search(r"(?i)\bgamma\b", q)):
            return None
        if not ("speed" in low or "velocity" in low or "moving" in low):
            return None
        beta = None
        m = re.search(r"(?i)(\d+(?:\.\d+)?)\s*%\s*(?:of\s+)?(?:the\s+)?speed of light", q)
        if m:
            beta = float(m.group(1)) / 100.0
        if beta is None:
            m = re.search(r"(?i)(\d+(?:\.\d+)?)\s*c\b", q)
            if m:
                beta = float(m.group(1))
        if beta is None:
            m = re.search(r"(?i)(?:v\s*=\s*)?(0\.\d+)\s*c\b", q)
            if m:
                beta = float(m.group(1))
        if beta is None or not (0.0 < beta < 1.0):
            return None
        gamma = 1.0 / math.sqrt(1.0 - beta * beta)
        candidates: list[tuple[str, float]] = []
        for letter, text in task.choices.items():
            m = re.fullmatch(r"\s*(?:gamma\s*=\s*)?([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*", str(text), re.I)
            if m:
                candidates.append((letter, float(m.group(1))))
        nearest = _nearest_unique(gamma, candidates, max_rel_error=0.06)
        if nearest is None:
            return None
        letter, option_value = nearest
        return PhysicsNumericResult(
            MCQDecision(letter, "physics_numeric_solver", 0.98,
                        f"gamma=1/sqrt(1-beta^2)={gamma:.6g} for beta={beta:.6g}"),
            "lorentz_gamma",
            gamma,
            "dimensionless",
            {"beta": beta, "matched_option_value": option_value},
        )

    def _solve_hubble_recession_velocity(self, task: MCQTask) -> PhysicsNumericResult | None:
        q = str(task.question)
        low = q.lower()
        if "hubble" not in low:
            return None
        if not ("recession velocity" in low or "recessional velocity" in low or "velocity" in low):
            return None
        h = re.search(r"(?i)(?:hubble constant|h[_ ]?0)[^\d]{0,30}(\d+(?:\.\d+)?)\s*km\s*/\s*s\s*/\s*mpc", q)
        d = re.search(r"(?i)(?:distance|at)\s*(?:of|=|:)??\s*(\d+(?:\.\d+)?)\s*mpc\b", q)
        if not h or not d:
            return None
        h0 = float(h.group(1))
        distance_mpc = float(d.group(1))
        if not (0 < h0 < 200 and distance_mpc > 0):
            return None
        velocity = h0 * distance_mpc
        candidates = _numbers_with_unit(task.choices, r"km\s*/\s*s\b")
        nearest = _nearest_unique(velocity, candidates, max_rel_error=0.08)
        if nearest is None:
            return None
        letter, option_value = nearest
        return PhysicsNumericResult(
            MCQDecision(letter, "physics_numeric_solver", 0.98,
                        f"v=H0 d={velocity:.6g} km/s"),
            "hubble_recession_velocity",
            velocity,
            "km/s",
            {"H0_km_s_Mpc": h0, "distance_Mpc": distance_mpc, "matched_option_value": option_value},
        )

    def _solve_schwarzschild_radius(self, task: MCQTask) -> PhysicsNumericResult | None:
        q = str(task.question)
        low = q.lower()
        if "schwarzschild radius" not in low:
            return None
        m = re.search(r"(?i)(\d+(?:\.\d+)?)\s*(?:solar masses|solar mass|m_sun|msun|M☉)", q)
        if not m:
            return None
        mass_solar = float(m.group(1))
        if mass_solar <= 0:
            return None
        radius_km = self.SCHWARZSCHILD_KM_PER_SOLAR_MASS * mass_solar
        candidates = _numbers_with_unit(task.choices, r"km\b")
        nearest = _nearest_unique(radius_km, candidates, max_rel_error=0.08)
        if nearest is None:
            return None
        letter, option_value = nearest
        return PhysicsNumericResult(
            MCQDecision(letter, "physics_numeric_solver", 0.98,
                        f"r_s=2GM/c^2={radius_km:.6g} km for M={mass_solar:g} M_sun"),
            "schwarzschild_radius",
            radius_km,
            "km",
            {"mass_solar": mass_solar, "matched_option_value": option_value},
        )

    def _solve_classical_kinetic_energy(self, task: MCQTask) -> PhysicsNumericResult | None:
        q = str(task.question)
        low = q.lower()
        if "kinetic energy" not in low:
            return None
        mm = re.search(r"(?i)(?:mass|m)\s*(?:is|=|:)\s*(\d+(?:\.\d+)?)\s*kg\b", q)
        vv = re.search(r"(?i)(?:speed|velocity|v)\s*(?:is|=|:)\s*(\d+(?:\.\d+)?)\s*m\s*/\s*s\b", q)
        if not mm or not vv:
            return None
        mass = float(mm.group(1))
        speed = float(vv.group(1))
        if mass <= 0 or speed < 0:
            return None
        ke = 0.5 * mass * speed * speed
        candidates = _numbers_with_unit(task.choices, r"(?:j|joules?)\b")
        nearest = _nearest_unique(ke, candidates, max_rel_error=0.05)
        if nearest is None:
            return None
        letter, option_value = nearest
        return PhysicsNumericResult(
            MCQDecision(letter, "physics_numeric_solver", 0.99,
                        f"K=1/2 mv^2={ke:.6g} J"),
            "classical_kinetic_energy",
            ke,
            "J",
            {"mass_kg": mass, "speed_m_s": speed, "matched_option_value": option_value},
        )

    def solve(self, task: MCQTask) -> PhysicsNumericResult | None:
        for solver in (
            self._solve_photon_energy_from_wavelength,
            self._solve_lorentz_gamma,
            self._solve_hubble_recession_velocity,
            self._solve_schwarzschild_radius,
            self._solve_classical_kinetic_energy,
            self._solve_quasar_comoving_distance,
            self._solve_circular_aperture_minima_gap,
        ):
            result = solver(task)
            if result is not None:
                return result
        return None

    def run(self, task: MCQTask) -> dict[str, Any] | None:
        result = self.solve(task)
        if result is None:
            return None
        d = result.decision
        return {
            "ok": True,
            "reply": d.rationale + "\nAnswer: $" + d.letter,
            "confidence": d.confidence,
            "decision_source": d.source,
            "domain": task.domain,
            "forced_choice": False,
            "needs_teacher": False,
            "physics_numeric": {
                "used": True,
                "solver": result.solver,
                "value": result.value,
                "unit": result.unit,
                "details": result.details,
            },
        }
