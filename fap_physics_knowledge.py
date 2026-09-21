from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from fap_benchmark_reasoning import MCQDecision, MCQTask
from fap_scientific_reasoning import OptionConditionedScientificReasoner


_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_+\-]*")
_NEGATIVE = re.compile(r"(?i)(\bnot\b|\bfalse\b|\bincorrect\b|\bexcept\b|\bleast correct\b|誤り|正しくない|除く)")
_STOP = {
    "the","a","an","of","to","and","or","in","on","for","with","is","are","be","as","by",
    "which","what","this","that","from","at","it","its","than","when","under","into","about",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(str(text or "")) if len(w) > 1 and w.lower() not in _STOP}


def _as_patterns(value) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    return tuple(value or ())


def _shared_count(a: str, b: str) -> int:
    return len(_tokens(a) & _tokens(b))


def _overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    common = len(ta & tb)
    if common == 0:
        return 0.0
    precision = common / len(tb)
    recall = common / len(ta)
    return 2.0 * precision * recall / max(1e-9, precision + recall)


@dataclass(frozen=True)
class PhysicsKnowledgeEntry:
    knowledge_id: str
    area: str
    concepts: tuple[str, ...]
    aliases: tuple[str, ...]
    claims: tuple[str, ...]
    misconceptions: tuple[str, ...] = ()
    formulas: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    support_patterns: tuple[str, ...] = ()
    contradiction_patterns: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetrievedPhysics:
    entry: PhysicsKnowledgeEntry
    retrieval_score: float


@dataclass(frozen=True)
class PhysicsOptionEvidence:
    letter: str
    score: float
    evidence: tuple[str, ...]
    contradictions: tuple[str, ...]
    retrieved_ids: tuple[str, ...]


K: tuple[PhysicsKnowledgeEntry, ...] = (
    PhysicsKnowledgeEntry(
        "qm_born_rule","quantum",
        ("wavefunction","probability","measurement"),("born rule","probability amplitude","psi"),
        ("Measurement probabilities are given by the squared magnitude of the relevant probability amplitude.",
         "For a position wavefunction, |psi(x)|^2 is a probability density."),
        ("The wavefunction itself is directly an ordinary classical probability density.",),
        ("P = |amplitude|^2",),("normalized quantum state",),
        (r"(modulus|magnitude).{0,20}squared.{0,60}probability",r"\|?psi\|?.{0,30}squared.{0,60}probability"),
        (r"wavefunction.{0,50}classical probability without squar",)
    ),
    PhysicsKnowledgeEntry(
        "qm_unitary_evolution","quantum",
        ("quantum state","time evolution","schrodinger"),("unitary evolution","schrodinger equation","closed quantum system"),
        ("An isolated closed quantum system evolves unitarily according to the Schrodinger equation.",
         "Unitary evolution preserves total probability."),
        ("A closed quantum system necessarily loses normalization during ordinary time evolution.",),
        ("i hbar d|psi>/dt = H|psi>",),("closed isolated system",),
        (r"(closed|isolated).{0,60}quantum.{0,80}(unitary|schrodinger)",r"unitary.{0,80}preserv.{0,40}(norm|probability)"),
        (r"(closed|isolated).{0,60}quantum.{0,80}(always nonunitary|lose.*normalization)",)
    ),
    PhysicsKnowledgeEntry(
        "qm_uncertainty","quantum",
        ("uncertainty","position","momentum"),("heisenberg uncertainty","conjugate observables"),
        ("Position and momentum cannot both have arbitrarily small uncertainty in the same quantum state.",
         "The uncertainty relation concerns intrinsic state spreads, not merely poor instruments."),
        ("Heisenberg uncertainty is only a statement about defective measuring devices.",),
        ("Delta x Delta p >= hbar/2",),("noncommuting conjugate observables",),
        (r"(position.{0,60}momentum|momentum.{0,60}position).{0,80}(uncertainty|cannot.*simult)",),
        (r"uncertainty.{0,80}(instrument error only|measurement defect only)",)
    ),
    PhysicsKnowledgeEntry(
        "qm_commutator","quantum",
        ("commutator","observable","compatible"),("noncommuting observables","commuting operators"),
        ("Commuting observables can possess simultaneous eigenstates and are compatible.",
         "Noncommuting observables generally obey an uncertainty relation."),
        ("All pairs of quantum observables commute.",),
        ("[A,B] = AB - BA",),(),
        (r"commut.{0,50}(compatible|simultaneous eigen)",r"noncommut.{0,60}uncertainty"),
        (r"all.{0,30}observables.{0,30}commute",)
    ),
    PhysicsKnowledgeEntry(
        "qm_superposition","quantum",
        ("superposition","state","linear combination"),("quantum superposition","linear state"),
        ("A linear combination of allowed quantum states is also a possible state before measurement.",
         "Interference can arise from coherent superposition amplitudes."),
        ("A quantum superposition is always equivalent to a classical probabilistic mixture.",),
        (),("coherent isolated quantum description",),
        (r"superposition.{0,80}(linear combination|interference|coherent)",),
        (r"superposition.{0,80}always.{0,40}classical mixture",)
    ),
    PhysicsKnowledgeEntry(
        "qm_entanglement","quantum",
        ("entanglement","correlation","local"),("entangled state","bell correlation","no signalling"),
        ("Entangled systems can display correlations not reproducible by local hidden-variable models.",
         "Entanglement alone cannot be used for faster-than-light signalling."),
        ("Entanglement permits controllable superluminal communication by itself.",),
        (),(),
        (r"entangl.{0,100}(bell|nonlocal correlation|no.?signall)",),
        (r"entangl.{0,100}(faster.than.light signalling|superluminal communication)",)
    ),
    PhysicsKnowledgeEntry(
        "qm_tunneling","quantum",
        ("tunneling","barrier","wavefunction"),("quantum tunneling","classically forbidden"),
        ("A quantum particle can have nonzero transmission probability through a finite barrier even when its energy is below the barrier height.",),
        ("Quantum tunneling requires the particle energy to exceed the barrier height.",),
        (),("finite barrier and nonzero wavefunction penetration",),
        (r"tunnel.{0,100}(below|less than).{0,40}barrier",),
        (r"tunnel.{0,80}(requires|only if).{0,50}(above|greater than).{0,30}barrier",)
    ),
    PhysicsKnowledgeEntry(
        "qm_harmonic_oscillator","quantum",
        ("harmonic oscillator","energy level","zero point"),("quantum oscillator","zero-point energy"),
        ("The quantum harmonic oscillator has equally spaced energy levels E_n = hbar omega (n + 1/2).",
         "Its ground state has nonzero zero-point energy."),
        ("The quantum harmonic oscillator ground state has exactly zero energy.",),
        ("E_n = hbar omega (n + 1/2)",),(),
        (r"harmonic oscillator.{0,100}(equally spaced|zero.?point|n\s*\+\s*1/2)",),
        (r"harmonic oscillator.{0,80}ground.{0,50}zero energy",)
    ),
    PhysicsKnowledgeEntry(
        "de_broglie","quantum",
        ("wavelength","momentum","matter wave"),("de broglie wavelength","matter wave"),
        ("A particle with momentum p has de Broglie wavelength lambda = h/p.",),
        ("De Broglie wavelength increases in direct proportion to momentum.",),
        ("lambda = h/p",),(),
        (r"de broglie.{0,80}(h\s*/\s*p|inverse.{0,20}momentum)",),
        (r"de broglie.{0,80}directly proportional.{0,30}momentum",)
    ),
    PhysicsKnowledgeEntry(
        "photoelectric_effect","quantum",
        ("photoelectric","photon","work function"),("photoelectric effect","threshold frequency"),
        ("In the photoelectric effect, photon energy h nu must exceed the work function for emission.",
         "Increasing light intensity increases the number of photons but does not raise individual photon energy at fixed frequency."),
        ("Below threshold frequency, arbitrarily high intensity guarantees photoelectron emission in the ideal one-photon picture.",),
        ("K_max = h nu - phi",),(),
        (r"photoelectric.{0,100}(threshold|work function|h.?nu)",),
        (r"photoelectric.{0,100}below threshold.{0,80}intensity.{0,40}(always|guarantee)",)
    ),
    PhysicsKnowledgeEntry(
        "electron_fermion","particle",
        ("electron","fermion","spin"),("lepton","spin one half"),
        ("The electron is a spin-1/2 fermion and a lepton.",),
        ("The electron is a spin-1 boson.",),
        (),(),
        (r"electron.{0,50}(fermion|spin.?1/2|lepton)",),
        (r"electron.{0,50}(boson|spin.?1(?!/2)\b)",)
    ),
    PhysicsKnowledgeEntry(
        "photon_boson","particle",
        ("photon","boson","massless"),("gauge boson","electromagnetic quantum"),
        ("The photon is the massless spin-1 gauge boson of electromagnetism.",),
        ("The photon is a spin-1/2 fermion with electric charge.",),
        (),(),
        (r"photon.{0,70}(massless|spin.?1(?!/2)\b|boson|gauge)",),
        (r"photon.{0,70}(fermion|spin.?1/2|electric charge)",)
    ),
    PhysicsKnowledgeEntry(
        "pauli_exclusion","particle",
        ("pauli","fermion","state"),("pauli exclusion","identical fermions"),
        ("Identical fermions cannot occupy the same complete one-particle quantum state.",),
        ("Pauli exclusion applies to identical bosons in the same way.",),
        (),("identical fermions",),
        (r"pauli.{0,100}(fermion|identical fermion|same quantum state)",),
        (r"pauli.{0,100}boson",)
    ),
    PhysicsKnowledgeEntry(
        "bose_statistics","particle",
        ("boson","bose","occupation"),("bose-einstein","integer spin"),
        ("Identical bosons can occupy the same one-particle quantum state.",),
        ("Bosons obey the Pauli exclusion principle.",),
        (),(),
        (r"boson.{0,100}(same quantum state|bose.einstein|integer spin)",),
        (r"boson.{0,80}pauli exclusion",)
    ),
    PhysicsKnowledgeEntry(
        "neutrino","particle",
        ("neutrino","weak interaction","charge"),("neutral lepton","neutrino oscillation"),
        ("Neutrinos are electrically neutral leptons that participate in the weak interaction.",
         "Neutrino flavor oscillations imply nonzero neutrino mass differences."),
        ("Neutrinos carry electric charge equal to the electron charge magnitude.",),
        (),(),
        (r"neutrino.{0,80}(neutral|weak|oscillation|mass difference)",),
        (r"neutrino.{0,60}(electric charge|charged like electron)",)
    ),
    PhysicsKnowledgeEntry(
        "quark_color","particle",
        ("quark","color","strong interaction"),("color charge","qcd"),
        ("Quarks carry color charge and participate in the strong interaction.",
         "Isolated free quarks are not observed because of confinement."),
        ("Quarks are color-neutral elementary leptons.",),
        (),(),
        (r"quark.{0,80}(color|strong|confinement)",),
        (r"quark.{0,80}(lepton|color neutral elementary)",)
    ),
    PhysicsKnowledgeEntry(
        "gluon","particle",
        ("gluon","strong interaction","color"),("qcd gauge boson","color charge"),
        ("Gluons are spin-1 gauge bosons of the strong interaction and themselves carry color.",),
        ("Gluons are electrically charged leptons.",),
        (),(),
        (r"gluon.{0,80}(strong|gauge boson|color)",),
        (r"gluon.{0,80}(lepton|electric charge)",)
    ),
    PhysicsKnowledgeEntry(
        "conservation_charge","particle",
        ("electric charge","conservation","reaction"),("charge conservation",),
        ("Total electric charge is conserved in ordinary particle interactions.",),
        ("Electric charge can disappear without compensating charge in an isolated reaction.",),
        (),(),
        (r"(electric )?charge.{0,80}conserv",),
        (r"(electric )?charge.{0,80}(not conserved|disappear without)",)
    ),
    PhysicsKnowledgeEntry(
        "newton_second","mechanics",
        ("force","acceleration","mass"),("newton second law","net force"),
        ("For constant mass in Newtonian mechanics, net force equals mass times acceleration.",),
        ("An object with zero net force must have zero velocity.",),
        ("F_net = m a",),("inertial frame; constant mass",),
        (r"(net force|newton).{0,80}(m.?a|mass.{0,30}acceleration)",),
        (r"zero net force.{0,80}zero velocity",)
    ),
    PhysicsKnowledgeEntry(
        "momentum_conservation","mechanics",
        ("momentum","isolated system","external force"),("linear momentum conservation",),
        ("Total linear momentum is conserved when the net external force on a system is zero.",),
        ("Momentum conservation requires each object's momentum to stay individually constant during an internal collision.",),
        ("dP/dt = F_external",),("closed system with zero net external force",),
        (r"momentum.{0,80}(conserved|constant).{0,80}(external force|isolated)",),
        (r"collision.{0,80}each object.{0,60}momentum.{0,40}unchanged",)
    ),
    PhysicsKnowledgeEntry(
        "energy_conservation","mechanics",
        ("energy","conservation","work"),("mechanical energy","conservative force"),
        ("Total energy of an isolated system is conserved.",
         "Mechanical energy is conserved when only conservative forces do work."),
        ("Mechanical energy is always conserved even with dissipative friction while ignoring thermal energy.",),
        (),("isolated total system; conservative mechanical subsystem",),
        (r"(total )?energy.{0,80}isolated.{0,50}conserv|conservative force.{0,80}mechanical energy"),
        (r"mechanical energy.{0,80}always conserved.{0,50}friction",)
    ),
    PhysicsKnowledgeEntry(
        "angular_momentum","mechanics",
        ("angular momentum","torque","rotation"),("angular momentum conservation","external torque"),
        ("Total angular momentum is conserved when the net external torque is zero.",),
        ("Angular momentum can change in an isolated system with zero external torque.",),
        ("dL/dt = tau_external",),(),
        (r"angular momentum.{0,80}conserv.{0,80}(zero|no).{0,30}external torque",),
        (r"zero external torque.{0,80}angular momentum.{0,40}(changes|not conserved)",)
    ),
    PhysicsKnowledgeEntry(
        "work_energy","mechanics",
        ("work","kinetic energy","force"),("work-energy theorem",),
        ("Net work done on a particle equals its change in kinetic energy.",),
        ("Net work is always equal to the change in potential energy.",),
        ("W_net = Delta K",),(),
        (r"net work.{0,80}(change|delta).{0,30}kinetic energy",),
        (r"net work.{0,80}always.{0,40}(change|delta).{0,30}potential energy",)
    ),
    PhysicsKnowledgeEntry(
        "simple_harmonic_motion","mechanics",
        ("harmonic","restoring force","oscillation"),("simple harmonic motion","hooke"),
        ("Simple harmonic motion has a restoring force proportional and opposite to displacement.",),
        ("In ideal simple harmonic motion, restoring force points away from equilibrium.",),
        ("F = -kx",),("linear restoring regime",),
        (r"(simple )?harmonic.{0,80}(restoring|proportional).{0,50}displacement",),
        (r"harmonic.{0,80}force.{0,50}away from equilibrium",)
    ),
    PhysicsKnowledgeEntry(
        "coulomb_law","electromagnetism",
        ("coulomb","electric force","charge"),("inverse square electric force","electrostatic"),
        ("The electrostatic force between point charges is proportional to q1 q2 and inversely proportional to the square of separation.",),
        ("Electrostatic force between point charges falls as one over distance rather than distance squared.",),
        ("F = k q1 q2 / r^2",),("point charges or spherically symmetric charge distributions",),
        (r"(coulomb|electrostatic).{0,100}(inverse square|1.?/.?r\^?2)",),
        (r"(coulomb|electrostatic).{0,80}(1.?/.?r\b|inverse distance\b)",)
    ),
    PhysicsKnowledgeEntry(
        "gauss_law","electromagnetism",
        ("gauss","electric flux","enclosed charge"),("gauss law","electric flux"),
        ("The electric flux through a closed surface equals enclosed charge divided by epsilon_0.",),
        ("Gauss law says flux through a closed surface is determined only by charges outside the surface.",),
        ("closed integral E dot dA = Q_enclosed / epsilon_0",),("closed surface",),
        (r"(gauss|electric flux).{0,100}enclosed charge",),
        (r"gauss.{0,80}(outside charge only|only external charge)",)
    ),
    PhysicsKnowledgeEntry(
        "faraday_law","electromagnetism",
        ("faraday","magnetic flux","emf"),("electromagnetic induction","induced emf"),
        ("A changing magnetic flux through a circuit induces an emf opposing the flux change according to Lenz's law.",),
        ("A constant magnetic flux necessarily induces a nonzero emf in a stationary loop.",),
        ("emf = - d Phi_B / dt",),(),
        (r"(faraday|induc).{0,100}(changing|change).{0,40}magnetic flux.{0,60}(emf|voltage)",),
        (r"constant magnetic flux.{0,80}(nonzero|induces).{0,30}emf",)
    ),
    PhysicsKnowledgeEntry(
        "lorentz_force","electromagnetism",
        ("lorentz","magnetic force","velocity"),("charged particle","cross product"),
        ("The Lorentz force is q(E + v cross B). A purely magnetic force is perpendicular to velocity and does no work.",),
        ("A stationary charge in a purely magnetic field experiences magnetic force qB.",),
        ("F = q(E + v x B)",),(),
        (r"lorentz.{0,100}q.{0,20}(e|electric).{0,50}(v|velocity).{0,30}(cross|x).{0,20}b",
         r"magnetic force.{0,100}(perpendicular|does no work)"),
        (r"stationary charge.{0,80}purely magnetic.{0,50}(force|accelerat)",)
    ),
    PhysicsKnowledgeEntry(
        "maxwell_wave","electromagnetism",
        ("maxwell","electromagnetic wave","light"),("electromagnetic radiation","speed of light"),
        ("Maxwell's equations admit electromagnetic waves whose vacuum speed is c = 1/sqrt(mu_0 epsilon_0).",
         "Light is an electromagnetic wave."),
        ("Electromagnetic waves in vacuum require a material medium.",),
        ("c = 1/sqrt(mu_0 epsilon_0)",),("vacuum",),
        (r"(maxwell|electromagnetic).{0,100}(wave|light).{0,80}(vacuum|speed)",),
        (r"electromagnetic wave.{0,80}require.{0,40}material medium",)
    ),
    PhysicsKnowledgeEntry(
        "electrostatic_potential","electromagnetism",
        ("electric potential","electric field","voltage"),("potential gradient","electrostatic"),
        ("The electrostatic electric field is minus the gradient of electric potential.",),
        ("Electric potential is a vector pointing in the electric field direction.",),
        ("E = - grad V",),("electrostatic field",),
        (r"electric field.{0,80}(minus|negative).{0,30}gradient.{0,30}potential",),
        (r"electric potential.{0,60}vector",)
    ),
    PhysicsKnowledgeEntry(
        "first_law_thermo","thermodynamics",
        ("first law","internal energy","heat","work"),("energy conservation thermodynamics",),
        ("The first law relates change in internal energy to heat added and work, with sign convention specified consistently.",),
        ("The first law permits creation of energy in a cyclic process.",),
        ("Delta U = Q - W_by_system",),(),
        (r"first law.{0,100}(internal energy|heat|work|energy conserv)",),
        (r"first law.{0,80}(create|creation).{0,40}energy",)
    ),
    PhysicsKnowledgeEntry(
        "second_law_entropy","thermodynamics",
        ("second law","entropy","isolated"),("entropy increase","irreversible"),
        ("The entropy of an isolated system does not decrease in spontaneous macroscopic processes.",),
        ("The second law requires the entropy of every subsystem to increase in every process.",),
        ("Delta S_isolated >= 0",),("isolated total system",),
        (r"(second law|isolated).{0,100}entropy.{0,70}(increase|non.?decreas)",),
        (r"second law.{0,100}every subsystem.{0,40}entropy.{0,30}increase",)
    ),
    PhysicsKnowledgeEntry(
        "carnot_efficiency","thermodynamics",
        ("carnot","heat engine","efficiency"),("reversible engine","reservoir temperature"),
        ("A reversible Carnot engine between temperatures Th and Tc has maximum efficiency 1 - Tc/Th.",),
        ("A heat engine operating between two reservoirs can exceed Carnot efficiency without other changes.",),
        ("eta_C = 1 - Tc/Th",),("absolute temperatures; reversible cycle",),
        (r"carnot.{0,100}(maximum efficiency|1\s*-\s*t.?c\s*/\s*t.?h)",),
        (r"(exceed|greater than).{0,50}carnot.{0,40}efficiency",)
    ),
    PhysicsKnowledgeEntry(
        "boltzmann_factor","statistical",
        ("boltzmann","probability","energy","temperature"),("canonical ensemble","thermal probability"),
        ("In a canonical ensemble, relative probability of a state of energy E contains the factor exp(-E/kT).",),
        ("Higher-energy canonical states are favored by exp(+E/kT) at positive temperature.",),
        ("p proportional exp(-E/kT)",),("thermal equilibrium; canonical ensemble",),
        (r"(boltzmann|canonical).{0,100}exp.{0,20}-\s*e.{0,20}k.?t",),
        (r"(boltzmann|canonical).{0,80}exp.{0,20}\+\s*e.{0,20}k.?t",)
    ),
    PhysicsKnowledgeEntry(
        "ideal_gas","thermodynamics",
        ("ideal gas","pressure","volume","temperature"),("ideal gas law","equation of state"),
        ("An ideal gas satisfies PV = nRT.",),
        ("For a fixed amount of ideal gas, PV is independent of temperature.",),
        ("PV = nRT",),("ideal gas approximation",),
        (r"ideal gas.{0,80}p.?v.{0,30}n.?r.?t",),
        (r"ideal gas.{0,100}p.?v.{0,40}independent of temperature",)
    ),
    PhysicsKnowledgeEntry(
        "equipartition","statistical",
        ("equipartition","quadratic degree","temperature"),("classical thermal energy","degree of freedom"),
        ("In the classical equipartition regime, each independent quadratic degree of freedom contributes (1/2)kT to mean energy.",),
        ("Equipartition remains exact for all quantum degrees of freedom at arbitrarily low temperature.",),
        ("<E_quadratic> = kT/2",),("classical regime where relevant modes are thermally accessible",),
        (r"equipartition.{0,100}(1/2|half).{0,20}k.?t",),
        (r"equipartition.{0,100}(all quantum|arbitrarily low temperature).{0,40}exact",)
    ),
    PhysicsKnowledgeEntry(
        "lorentz_invariance_c","relativity",
        ("relativity","speed of light","inertial frame"),("special relativity","invariant speed"),
        ("All inertial observers measure the same vacuum speed of light c.",),
        ("An observer moving toward a light source measures c plus the observer speed in vacuum.",),
        (),("inertial frames in special relativity",),
        (r"(inertial|relativity).{0,100}(same|invariant).{0,50}speed of light",),
        (r"light.{0,80}(c\s*\+|c plus).{0,50}(observer|source).{0,20}speed",)
    ),
    PhysicsKnowledgeEntry(
        "time_dilation","relativity",
        ("time dilation","proper time","moving clock"),("special relativity clock","lorentz factor"),
        ("A clock moving relative to an inertial observer accumulates less proper time between the same pair of comparison events.",),
        ("Special relativistic time dilation makes a moving clock run faster than the observer's coordinate clock in the standard comparison.",),
        ("Delta t = gamma Delta tau",),(),
        (r"time dilation.{0,100}(moving clock|proper time|gamma)",),
        (r"time dilation.{0,80}moving clock.{0,40}faster",)
    ),
    PhysicsKnowledgeEntry(
        "length_contraction","relativity",
        ("length contraction","proper length","moving object"),("lorentz contraction",),
        ("The length of an object measured parallel to its relative motion is shorter than its proper length.",),
        ("Relativistic length contraction increases the measured parallel length above the proper length.",),
        ("L = L0/gamma",),("length parallel to relative velocity",),
        (r"length contraction.{0,100}(shorter|proper length|1.?/.?gamma)",),
        (r"length contraction.{0,80}(longer|increase).{0,40}proper length",)
    ),
    PhysicsKnowledgeEntry(
        "energy_momentum_relation","relativity",
        ("energy","momentum","mass","relativity"),("four-momentum","rest energy"),
        ("Relativistic energy and momentum obey E^2 = p^2 c^2 + m^2 c^4.",),
        ("For a massive particle at rest, total energy is zero.",),
        ("E^2 = p^2 c^2 + m^2 c^4","E0 = mc^2"),(),
        (r"e\^?2.{0,30}p\^?2.{0,20}c\^?2.{0,30}m\^?2.{0,20}c\^?4|rest energy.{0,40}m.?c\^?2"),
        (r"massive particle.{0,60}at rest.{0,30}(zero total energy|energy zero)",)
    ),
    PhysicsKnowledgeEntry(
        "radioactive_decay","nuclear",
        ("radioactive decay","half-life","exponential"),("decay constant","nuclear decay"),
        ("For a fixed decay constant, the expected number of undecayed nuclei decreases exponentially with time.",
         "Half-life is ln 2 divided by the decay constant."),
        ("Radioactive decay of a large ensemble is generally linear in time until all nuclei vanish.",),
        ("N(t)=N0 exp(-lambda t)","t_1/2 = ln2/lambda"),(),
        (r"(radioactive|decay).{0,100}(exponential|half.life|ln.?2)",),
        (r"radioactive decay.{0,80}linear in time",)
    ),
    PhysicsKnowledgeEntry(
        "binding_energy","nuclear",
        ("binding energy","mass defect","nucleus"),("nuclear binding","mass-energy"),
        ("Nuclear binding energy corresponds to the mass defect through E = Delta m c^2.",),
        ("A bound nucleus has greater mass than the separated free nucleons by the binding-energy mass equivalent.",),
        ("E_bind = Delta m c^2",),(),
        (r"(binding energy|mass defect).{0,100}(delta.?m|m.?c\^?2|mass defect)",),
        (r"bound nucleus.{0,100}greater mass.{0,40}separated nucleons",)
    ),
    PhysicsKnowledgeEntry(
        "alpha_beta_gamma","nuclear",
        ("alpha","beta","gamma","decay"),("nuclear radiation","helium nucleus","electron emission"),
        ("Alpha radiation consists of helium-4 nuclei; beta-minus decay emits an electron and antineutrino; gamma radiation is electromagnetic.",),
        ("Gamma radiation consists of massive helium nuclei.",),
        (),(),
        (r"alpha.{0,80}(helium|he.?4)|gamma.{0,80}(photon|electromagnetic)|beta.minus.{0,80}(electron|antineutrino)"),
        (r"gamma.{0,60}helium",)
    ),
    PhysicsKnowledgeEntry(
        "snell_law","optics",
        ("snell","refraction","index"),("refractive index","angle"),
        ("Snell's law is n1 sin(theta1) = n2 sin(theta2).",),
        ("Refraction requires equal angles in all media regardless of refractive index.",),
        ("n1 sin theta1 = n2 sin theta2",),(),
        (r"snell.{0,80}n.?1.{0,20}sin.{0,30}n.?2.{0,20}sin",),
        (r"refraction.{0,100}equal angles.{0,40}regardless.{0,30}index",)
    ),
    PhysicsKnowledgeEntry(
        "reflection_law","optics",
        ("reflection","incident angle","reflected angle"),("law of reflection",),
        ("For specular reflection, the angle of incidence equals the angle of reflection, measured from the normal.",),
        ("The reflection angle is measured from the surface and must equal the incidence angle measured from the normal.",),
        (),(),
        (r"reflection.{0,100}(incidence|incident).{0,60}(equal|same).{0,40}(reflection|reflected)",),
        (r"reflection angle.{0,80}measured from surface.{0,80}incidence.{0,30}normal",)
    ),
    PhysicsKnowledgeEntry(
        "interference","optics",
        ("interference","phase","wave"),("constructive interference","destructive interference"),
        ("Coherent waves add by superposition; relative phase determines constructive or destructive interference.",),
        ("Wave interference requires the waves to destroy energy conservation.",),
        (),("coherence for stable fringe pattern",),
        (r"interference.{0,100}(phase|constructive|destructive|superposition)",),
        (r"interference.{0,80}(destroy|violate).{0,40}energy conservation",)
    ),
    PhysicsKnowledgeEntry(
        "diffraction","optics",
        ("diffraction","wavelength","aperture"),("single slit","wave spreading"),
        ("Diffraction becomes prominent when aperture or obstacle dimensions are comparable to the wavelength.",),
        ("Diffraction is a purely particle effect that vanishes for waves.",),
        (),(),
        (r"diffraction.{0,100}(wavelength|aperture|slit|wave)",),
        (r"diffraction.{0,80}purely particle",)
    ),
    PhysicsKnowledgeEntry(
        "fermi_dirac","condensed",
        ("fermi-dirac","fermion","occupation"),("fermi energy","pauli"),
        ("Fermions in thermal equilibrium follow Fermi-Dirac statistics and obey Pauli exclusion.",),
        ("Fermi-Dirac statistics permit unlimited identical fermions in one single-particle state.",),
        (),(),
        (r"fermi.?dirac.{0,80}(fermion|pauli|occupation)",),
        (r"fermi.?dirac.{0,100}unlimited.{0,50}same state",)
    ),
    PhysicsKnowledgeEntry(
        "bose_einstein","condensed",
        ("bose-einstein","boson","condensate"),("bose statistics","BEC"),
        ("Bosons follow Bose-Einstein statistics; many bosons can macroscopically occupy one state in a condensate.",),
        ("Bose-Einstein statistics impose Pauli exclusion on identical bosons.",),
        (),(),
        (r"bose.?einstein.{0,100}(boson|condens|same state)",),
        (r"bose.?einstein.{0,80}pauli exclusion",)
    ),
    PhysicsKnowledgeEntry(
        "band_structure","condensed",
        ("band gap","conductor","insulator","semiconductor"),("energy band","valence band","conduction band"),
        ("Band gaps help distinguish conductors, semiconductors, and insulators; semiconductors have a finite but relatively modest gap.",),
        ("A perfect metal at ordinary band-theory level requires a large completely filled band gap at the Fermi energy.",),
        (),("band theory of crystalline solids",),
        (r"(band gap|semiconductor).{0,100}(conductor|insulator|valence|conduction)",),
        (r"metal.{0,80}large.{0,30}filled band gap.{0,30}fermi",)
    ),
    PhysicsKnowledgeEntry(
        "superconductivity_meissner","condensed",
        ("superconductivity","meissner","resistance"),("superconductor","magnetic flux expulsion"),
        ("An ideal superconductor has zero dc electrical resistance and exhibits the Meissner effect below its critical conditions.",),
        ("A superconductor is defined only by very low but nonzero resistance and has no magnetic response.",),
        (),("below critical temperature/field/current",),
        (r"superconduct.{0,100}(zero resistance|meissner|flux expulsion)",),
        (r"superconduct.{0,100}(nonzero resistance only|no magnetic response)",)
    ),
    PhysicsKnowledgeEntry(
        "phonon","condensed",
        ("phonon","lattice","vibration"),("quasiparticle","crystal vibration"),
        ("A phonon is a quantized collective vibrational excitation of a lattice.",),
        ("A phonon is an elementary lepton in the Standard Model.",),
        (),(),
        (r"phonon.{0,100}(lattice|vibration|quasiparticle|collective)",),
        (r"phonon.{0,80}(lepton|standard model elementary)",)
    ),
)


K = K + (
    PhysicsKnowledgeEntry(
        "photon_energy_wavelength","quantum",
        ("photon","energy","frequency","wavelength"),("planck relation","photon wavelength"),
        ("Photon energy is E = h nu = hc/lambda, so shorter wavelength means higher photon energy.",),
        ("At fixed propagation medium, longer wavelength means higher photon energy.",),
        ("E = h nu","E = hc/lambda"),(),
        (r"photon.{0,100}(h.?nu|h.?c.?/.?lambda|shorter wavelength.{0,40}higher energy)",),
        (r"photon.{0,100}longer wavelength.{0,40}higher energy",)
    ),
    PhysicsKnowledgeEntry(
        "quantum_angular_momentum","quantum",
        ("angular momentum","quantum number","projection"),("j quantum number","magnetic quantum number"),
        ("For angular momentum quantum number j, J^2 has eigenvalue hbar^2 j(j+1), and a component has eigenvalues m hbar with m from -j to j.",),
        ("The magnitude of quantum angular momentum is generally j hbar exactly for every j.",),
        ("J^2 = hbar^2 j(j+1)","Jz = m hbar"),(),
        (r"angular momentum.{0,120}(j.?\(j.?\+.?1\)|m.?hbar|m.{0,40}-?j)",),
        (r"angular momentum.{0,100}magnitude.{0,30}j.?hbar exactly",)
    ),
    PhysicsKnowledgeEntry(
        "angular_momentum_addition","quantum",
        ("angular momentum","addition","coupling"),("spin coupling","total j","clebsch gordan"),
        ("Adding angular momenta j1 and j2 gives total j values from |j1-j2| through j1+j2 in integer steps.",),
        ("Two spin-1/2 particles can only form total spin 1/2.",),
        ("j = |j1-j2|,...,j1+j2",),(),
        (r"(angular momentum|spin).{0,100}(coupl|addition|total).{0,100}(j1|j2|integer steps|singlet|triplet)",),
        (r"two spin.?1/2.{0,80}only.{0,30}total spin.?1/2",)
    ),
    PhysicsKnowledgeEntry(
        "spin_half_projection","quantum",
        ("spin","spin-1/2","projection"),("spin half","m_s"),
        ("A spin-1/2 particle has spin projection quantum numbers +1/2 and -1/2 along a chosen axis.",),
        ("A spin-1/2 particle has three spin projections -1, 0, +1.",),
        ("m_s = +/- 1/2",),(),
        (r"spin.?1/2.{0,100}(\+.?1/2|-.?1/2|two projections)",),
        (r"spin.?1/2.{0,100}(-?1.{0,20}0.{0,20}\+?1|three projections)",)
    ),
    PhysicsKnowledgeEntry(
        "hydrogen_levels","quantum",
        ("hydrogen","energy level","principal quantum number"),("bohr energy","hydrogen spectrum"),
        ("Ignoring fine structure, hydrogen bound-state energies scale as -13.6 eV/n^2.",),
        ("Hydrogen bound-state energy grows linearly and positively with principal quantum number n.",),
        ("E_n = -13.6 eV/n^2",),("nonrelativistic hydrogenic atom with Z=1",),
        (r"hydrogen.{0,100}(-?13\.6|1.?/.?n\^?2|energy level)",),
        (r"hydrogen.{0,100}energy.{0,50}linear.{0,30}principal quantum",)
    ),
    PhysicsKnowledgeEntry(
        "spectral_transition","quantum",
        ("spectrum","transition","photon","energy level"),("spectral line","transition energy"),
        ("A transition between stationary energy levels emits or absorbs a photon with energy equal to the level-energy difference.",),
        ("The photon energy in a transition is unrelated to the difference between the initial and final energy levels.",),
        ("Delta E = h nu = hc/lambda",),(),
        (r"(transition|spectrum).{0,100}(delta.?e|energy difference).{0,80}(photon|frequency|wavelength)",),
        (r"transition.{0,100}photon energy.{0,50}unrelated.{0,50}energy level",)
    ),
    PhysicsKnowledgeEntry(
        "selection_rule_dipole","quantum",
        ("selection rule","electric dipole","angular momentum"),("dipole transition","delta l"),
        ("For ordinary electric-dipole atomic transitions, the orbital angular momentum rule is Delta l = +/-1, with corresponding magnetic selection rules.",),
        ("An electric-dipole atomic transition generically requires Delta l = 0 only.",),
        ("Delta l = +/-1",),("electric dipole approximation",),
        (r"(electric dipole|selection rule).{0,100}(delta.?l|\+.?/?-.?1)",),
        (r"electric dipole.{0,100}delta.?l.{0,30}=.?0 only",)
    ),
    PhysicsKnowledgeEntry(
        "zeeman_effect","quantum",
        ("zeeman","magnetic field","energy level"),("magnetic splitting","spectral line"),
        ("The Zeeman effect is the splitting or shifting of atomic energy levels in an external magnetic field.",),
        ("The Zeeman effect is caused by a static electric field rather than a magnetic field.",),
        (),(),
        (r"zeeman.{0,80}(magnetic field|splitting|energy level)",),
        (r"zeeman.{0,80}electric field",)
    ),
    PhysicsKnowledgeEntry(
        "stark_effect","quantum",
        ("stark","electric field","energy level"),("electric splitting","spectral line"),
        ("The Stark effect is the shifting or splitting of energy levels due to an external electric field.",),
        ("The Stark effect is specifically magnetic-field splitting.",),
        (),(),
        (r"stark.{0,80}(electric field|splitting|energy level)",),
        (r"stark.{0,80}magnetic field",)
    ),
    PhysicsKnowledgeEntry(
        "relativistic_gamma","relativity",
        ("gamma factor","velocity","relativity"),("lorentz factor","relativistic velocity"),
        ("The Lorentz factor is gamma = 1/sqrt(1-v^2/c^2), and increases as speed approaches c.",),
        ("The Lorentz factor decreases below one for ordinary subluminal speeds.",),
        ("gamma = 1/sqrt(1-v^2/c^2)",),("0 <= v < c",),
        (r"(lorentz factor|gamma).{0,100}(1.?/.?sqrt|approach.{0,20}c|greater than 1)",),
        (r"(lorentz factor|gamma).{0,80}(below one|less than 1).{0,40}subluminal",)
    ),
    PhysicsKnowledgeEntry(
        "relativistic_kinetic_energy","relativity",
        ("kinetic energy","gamma","relativity"),("relativistic kinetic energy",),
        ("Relativistic kinetic energy is K = (gamma-1)mc^2.",),
        ("Relativistic kinetic energy is always exactly (1/2)mv^2 at any speed.",),
        ("K = (gamma-1)mc^2",),(),
        (r"relativistic.{0,80}kinetic energy.{0,80}(gamma.?-.?1|mc\^?2)",),
        (r"relativistic.{0,80}kinetic energy.{0,80}always.{0,40}1/2.?m.?v\^?2",)
    ),
    PhysicsKnowledgeEntry(
        "center_of_mass_energy","particle",
        ("center of mass","collision","energy"),("center-of-momentum","invariant mass","s"),
        ("For collisions, the invariant center-of-mass energy is characterized by s = (total four-momentum)^2; available production energy depends on center-of-mass energy, not just lab energy.",),
        ("In a fixed-target collision, all projectile lab energy is generally available as new-particle rest mass.",),
        ("s = P_total^2",),(),
        (r"(center.of.mass|invariant).{0,100}(energy|four.momentum|s\b)",),
        (r"fixed.target.{0,100}all.{0,30}lab energy.{0,60}(rest mass|production)",)
    ),
    PhysicsKnowledgeEntry(
        "decay_q_value","nuclear",
        ("decay","q value","mass"),("Q-value","mass difference"),
        ("The Q-value of a decay or reaction is the decrease in total rest-mass energy between initial and final states; positive Q permits energy release.",),
        ("A negative Q-value means an isolated spontaneous decay has extra energy available without another source.",),
        ("Q = (M_initial - M_final)c^2",),(),
        (r"(q.?value|decay).{0,100}(mass difference|m_initial|energy release)",),
        (r"negative q.?value.{0,80}(spontaneous|extra energy available)",)
    ),
    PhysicsKnowledgeEntry(
        "compton_scattering","quantum",
        ("compton","photon","wavelength","electron"),("compton shift","scattering"),
        ("In Compton scattering from a free electron, the photon wavelength shift is proportional to 1-cos(theta).",),
        ("Compton scattering leaves photon wavelength unchanged for every nonzero scattering angle.",),
        ("Delta lambda = h/(m_e c) (1-cos theta)",),(),
        (r"compton.{0,100}(wavelength|1.?-.?cos|electron)",),
        (r"compton.{0,100}wavelength.{0,40}unchanged.{0,40}every",)
    ),
    PhysicsKnowledgeEntry(
        "blackbody_planck","astrophysics",
        ("blackbody","temperature","spectrum"),("planck spectrum","thermal radiation"),
        ("A blackbody spectrum is set by temperature; hotter blackbodies peak at shorter wavelength and radiate more total power per area.",),
        ("A hotter blackbody peaks at a longer wavelength than a cooler one.",),
        ("lambda_max T = constant","F = sigma T^4"),(),
        (r"blackbody.{0,100}(temperature|shorter wavelength|planck|sigma.?t\^?4)",),
        (r"hotter blackbody.{0,80}longer wavelength",)
    ),
    PhysicsKnowledgeEntry(
        "inverse_square_flux","astrophysics",
        ("luminosity","flux","distance"),("inverse square law","stellar flux"),
        ("For isotropic emission without absorption, observed flux is luminosity divided by 4 pi distance squared.",),
        ("Observed flux from an isotropic source falls only as one over distance.",),
        ("F = L/(4 pi d^2)",),(),
        (r"(flux|luminosity).{0,100}(distance squared|inverse square|4.?pi.?d\^?2)",),
        (r"flux.{0,80}(1.?/.?d\b|inverse distance\b)",)
    ),
    PhysicsKnowledgeEntry(
        "hubble_law","astrophysics",
        ("hubble","redshift","distance","universe"),("cosmic expansion","recession velocity"),
        ("At sufficiently low cosmological redshift, recession velocity is approximately H0 times distance.",),
        ("Hubble expansion implies gravitationally bound objects such as atoms expand in direct proportion to H0.",),
        ("v = H0 d",),("low-redshift large-scale cosmology",),
        (r"hubble.{0,100}(velocity|redshift|distance|h0)",),
        (r"hubble.{0,100}(atoms|bound objects).{0,50}expand",)
    ),
    PhysicsKnowledgeEntry(
        "cosmological_redshift","astrophysics",
        ("redshift","scale factor","universe"),("cosmological redshift","expansion"),
        ("Cosmological redshift satisfies 1+z = a_now/a_emit in an expanding FLRW universe.",),
        ("Cosmological redshift requires photons to lose energy by ordinary friction with space.",),
        ("1+z = a0/a_emit",),(),
        (r"cosmological redshift.{0,100}(scale factor|1.?\+.?z|expansion)",),
        (r"cosmological redshift.{0,100}(friction|tired light)",)
    ),
    PhysicsKnowledgeEntry(
        "schwarzschild_radius","astrophysics",
        ("black hole","schwarzschild","mass"),("event horizon","schwarzschild radius"),
        ("For a nonrotating uncharged black hole, the Schwarzschild radius is 2GM/c^2.",),
        ("The Schwarzschild radius decreases as black-hole mass increases.",),
        ("r_s = 2GM/c^2",),("nonrotating uncharged black hole",),
        (r"(schwarzschild|black hole).{0,100}(2.?g.?m.?/.?c\^?2|radius.{0,40}mass)",),
        (r"schwarzschild radius.{0,80}decrease.{0,40}mass increase",)
    ),
    PhysicsKnowledgeEntry(
        "gravitational_redshift","relativity",
        ("gravitational redshift","gravity","frequency"),("general relativity","clock rate"),
        ("Light climbing out of a gravitational potential well is redshifted relative to a distant observer; clocks deeper in a gravitational potential run slower in the standard static comparison.",),
        ("A deeper gravitational potential makes a stationary clock run faster than a distant one.",),
        (),("static gravitational field comparison",),
        (r"gravitational.{0,100}(redshift|clock).{0,100}(slower|potential)",),
        (r"deeper gravitational potential.{0,80}clock.{0,40}faster",)
    ),
    PhysicsKnowledgeEntry(
        "stellar_hydrostatic","astrophysics",
        ("star","hydrostatic equilibrium","gravity","pressure"),("stellar structure","pressure support"),
        ("A stable star approximately balances inward gravity with outward pressure gradients in hydrostatic equilibrium.",),
        ("Hydrostatic equilibrium in a star means both gravity and pressure gradient vanish separately.",),
        (),(),
        (r"star.{0,100}(hydrostatic|pressure).{0,80}(gravity|balance)",),
        (r"hydrostatic.{0,80}star.{0,80}(gravity|pressure gradient).{0,30}vanish separately",)
    ),
    PhysicsKnowledgeEntry(
        "stellar_fusion","astrophysics",
        ("star","fusion","hydrogen","helium"),("stellar energy","nuclear fusion"),
        ("Main-sequence stars are powered primarily by nuclear fusion converting hydrogen into helium, releasing binding energy.",),
        ("Main-sequence stellar luminosity is powered primarily by chemical combustion.",),
        (),("main-sequence stars",),
        (r"(main.sequence|star).{0,100}(fusion|hydrogen|helium|nuclear)",),
        (r"main.sequence.{0,100}(chemical combustion|burning coal)",)
    ),
    PhysicsKnowledgeEntry(
        "virial_theorem","mechanics",
        ("virial","bound system","kinetic","potential"),("virial theorem","gravitational system"),
        ("For a stable bound system with an inverse-square gravitational potential, the time-averaged relation is 2<K> = -<U>.",),
        ("A virialized self-gravitating system has zero kinetic energy.",),
        ("2<K> = -<U>",),("stable time-averaged self-gravitating system",),
        (r"virial.{0,100}(2.?k|potential|bound|gravit)",),
        (r"virial.{0,100}zero kinetic energy",)
    ),
)


def validate_knowledge_patterns() -> list[str]:
    errors: list[str] = []
    for entry in K:
        for kind, patterns in (
            ("support", _as_patterns(entry.support_patterns)),
            ("contradiction", _as_patterns(entry.contradiction_patterns)),
        ):
            for pattern in patterns:
                try:
                    re.compile(pattern, re.I)
                except re.error as exc:
                    errors.append(f"{entry.knowledge_id}:{kind}:{pattern!r}:{exc}")
    return errors


class PhysicsKnowledgeStore:
    MAX_RETRIEVAL = 12

    @staticmethod
    def stats() -> dict[str, Any]:
        areas: dict[str, int] = {}
        for e in K:
            areas[e.area] = areas.get(e.area, 0) + 1
        return {"entries": len(K), "areas": areas, "benchmark_answer_keys": 0}

    def retrieve(self, task: MCQTask, limit: int | None = None) -> list[RetrievedPhysics]:
        limit = min(self.MAX_RETRIEVAL, max(1, int(limit or self.MAX_RETRIEVAL)))
        q = _norm(task.question + " " + " ".join(task.choices.values()))
        qtokens = _tokens(q)
        ranked: list[RetrievedPhysics] = []
        for e in K:
            phrases = e.concepts + e.aliases
            exact = sum(1 for p in phrases if _norm(p) and _norm(p) in q)
            etokens = _tokens(" ".join(phrases + e.claims + e.formulas))
            overlap = len(qtokens & etokens) / max(1, len(etokens))
            if exact == 0 and overlap < 0.08:
                continue
            score = exact * 2.0 + overlap * 3.0
            ranked.append(RetrievedPhysics(e, round(score, 4)))
        ranked.sort(key=lambda x: (-x.retrieval_score, x.entry.knowledge_id))
        return ranked[:limit]

    @staticmethod
    def _evaluate_entry(entry: PhysicsKnowledgeEntry, question: str, option: str) -> tuple[float, list[str], list[str]]:
        combined = _norm(question + " " + option)
        option_n = _norm(option)
        evidence: list[str] = []
        contra: list[str] = []
        score = 0.0

        for pat in _as_patterns(entry.support_patterns):
            if re.search(pat, combined, re.I):
                score += 1.25
                evidence.append(entry.knowledge_id + ":pattern")
        for pat in _as_patterns(entry.contradiction_patterns):
            if re.search(pat, combined, re.I):
                score -= 1.35
                contra.append(entry.knowledge_id + ":pattern")

        combined_text = question + " " + option_n
        true_pairs = [
            (
                max(_overlap(option_n, claim), 0.90 * _overlap(combined_text, claim)),
                max(_shared_count(option_n, claim), _shared_count(combined_text, claim)),
            )
            for claim in entry.claims
        ]
        false_pairs = [
            (
                max(_overlap(option_n, claim), 0.90 * _overlap(combined_text, claim)),
                max(_shared_count(option_n, claim), _shared_count(combined_text, claim)),
            )
            for claim in entry.misconceptions
        ]
        true_sim, true_shared = max(true_pairs, default=(0.0, 0))
        false_sim, false_shared = max(false_pairs, default=(0.0, 0))

        # Semantic matching requires at least two meaningful shared tokens. The
        # lower threshold improves paraphrase coverage while the token-count gate
        # prevents one-word topic matches from becoming truth evidence.
        if true_sim >= 0.30 and true_shared >= 2:
            score += min(0.90, 1.35 * true_sim)
            evidence.append(entry.knowledge_id + ":claim")
        if false_sim >= 0.30 and false_shared >= 2:
            score -= min(0.95, 1.40 * false_sim)
            contra.append(entry.knowledge_id + ":misconception")

        return score, evidence, contra

    def evaluate_options(self, task: MCQTask) -> tuple[list[PhysicsOptionEvidence], list[RetrievedPhysics]]:
        retrieved = self.retrieve(task)
        rows: list[PhysicsOptionEvidence] = []
        for letter in "ABCD":
            score = 0.0
            evidence: list[str] = []
            contra: list[str] = []
            ids: list[str] = []
            for item in retrieved:
                delta, ev, co = self._evaluate_entry(item.entry, task.question, task.choices[letter])
                if delta or ev or co:
                    # Retrieval relevance scales evidence but cannot create evidence.
                    scale = min(1.0, 0.55 + item.retrieval_score / 6.0)
                    score += delta * scale
                    evidence.extend(ev)
                    contra.extend(co)
                    ids.append(item.entry.knowledge_id)
            rows.append(PhysicsOptionEvidence(
                letter=letter,
                score=round(score, 4),
                evidence=tuple(dict.fromkeys(evidence)),
                contradictions=tuple(dict.fromkeys(contra)),
                retrieved_ids=tuple(dict.fromkeys(ids)),
            ))
        return rows, retrieved


class PhysicsKnowledgeReasoner:
    MIN_ABS_SCORE = 0.55
    MIN_MARGIN = 0.24

    def __init__(self, fallback: OptionConditionedScientificReasoner):
        self.fallback = fallback
        self.store = PhysicsKnowledgeStore()

    def run(self, task: MCQTask, history=None, *, teacher_allowed: bool = False) -> dict[str, Any]:
        # Physics is intentionally the only domain augmented in V87.27.
        if task.domain != "physics":
            out = self.fallback.run(task, history, teacher_allowed=teacher_allowed)
            out["physics_knowledge"] = {"used": False, "reason": "non-physics-domain"}
            return out

        rows, retrieved = self.store.evaluate_options(task)
        negative = bool(_NEGATIVE.search(task.question))
        ordered = sorted(rows, key=lambda x: x.score, reverse=not negative)
        best, runner = ordered[0], ordered[1]
        ub = -best.score if negative else best.score
        ur = -runner.score if negative else runner.score
        margin = ub - ur
        has_evidence = bool(best.evidence or best.contradictions)

        if abs(best.score) >= self.MIN_ABS_SCORE and margin >= self.MIN_MARGIN and has_evidence:
            decision = MCQDecision(
                best.letter,
                "physics_knowledge_retrieval",
                min(0.90, 0.62 + min(0.25, margin / 4.0)),
                f"physics retrieval score={best.score:.3f}; margin={margin:.3f}",
            )
            result = {
                "ok": True,
                "reply": decision.rationale + "\nAnswer: $" + decision.letter,
                "confidence": decision.confidence,
                "decision_source": decision.source,
                "domain": task.domain,
                "forced_choice": False,
                "needs_teacher": False,
            }
        else:
            result = self.fallback.run(task, history, teacher_allowed=teacher_allowed)

        result["physics_knowledge"] = {
            "used": result.get("decision_source") == "physics_knowledge_retrieval",
            "retrieved": [
                {"knowledge_id": x.entry.knowledge_id, "area": x.entry.area, "score": x.retrieval_score}
                for x in retrieved
            ],
            "options": [
                {
                    "letter": x.letter,
                    "score": x.score,
                    "evidence": list(x.evidence),
                    "contradictions": list(x.contradictions),
                    "retrieved_ids": list(x.retrieved_ids),
                }
                for x in rows
            ],
        }
        return result
