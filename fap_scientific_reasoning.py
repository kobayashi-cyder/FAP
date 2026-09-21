from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from fap_benchmark_reasoning import MCQDecision, MCQTask, StructuredMCQReasoner


_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_+\-]*")
_NEGATIVE_QUESTION = re.compile(
    r"(?i)(\bnot\b|\bfalse\b|\bincorrect\b|\bexcept\b|\bleast (?:likely|accurate|correct)\b|"
    r"誤って|誤り|正しくない|当てはまらない|除く)"
)
_ABSOLUTE = re.compile(r"(?i)\b(always|never|only|completely|impossible|must|all|none)\b")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _tokens(text: str) -> set[str]:
    return {x.lower() for x in _WORD.findall(str(text or "")) if len(x) > 1}


@dataclass(frozen=True)
class ScienceRule:
    rule_id: str
    domain: str
    anchors: tuple[str, ...]
    true_patterns: tuple[str, ...]
    false_patterns: tuple[str, ...]
    weight: float = 1.0


@dataclass(frozen=True)
class OptionAssessment:
    letter: str
    option: str
    truth_score: float
    evidence: tuple[str, ...]
    contradictions: tuple[str, ...]
    active_rules: int


# The rules below are general, high-confidence textbook relations. They are not
# derived from GPQA answer keys and contain no benchmark-specific question text.
RULES: tuple[ScienceRule, ...] = (
    # Quantum / particle physics
    ScienceRule("electron_fermion", "physics", ("electron", "fermion", "lepton"),
                (r"electron.{0,40}fermion|fermion.{0,40}electron|electron.{0,40}spin.?1/2|spin.?1/2.{0,40}electron",),
                (r"electron.{0,40}boson|boson.{0,40}electron|electron.{0,40}integer spin",), 1.4),
    ScienceRule("photon_boson", "physics", ("photon", "boson", "gauge"),
                (r"photon.{0,40}boson|boson.{0,40}photon|photon.{0,40}spin.?1",),
                (r"photon.{0,40}fermion|fermion.{0,40}photon|photon.{0,40}spin.?1/2",), 1.3),
    ScienceRule("pauli_fermions", "physics", ("pauli", "fermion", "exclusion"),
                (r"pauli.{0,60}fermion|fermion.{0,60}pauli|identical fermion.{0,80}same quantum state",),
                (r"pauli.{0,60}boson|boson.{0,60}pauli exclusion",), 1.2),
    ScienceRule("bosons_share_state", "physics", ("boson", "bose", "condensate"),
                (r"boson.{0,70}(same|single) quantum state|bose.{0,60}condens",),
                (r"boson.{0,70}pauli exclusion",), 1.0),
    ScienceRule("uncertainty", "physics", ("uncertainty", "position", "momentum", "heisenberg"),
                (r"(position.{0,80}momentum|momentum.{0,80}position).{0,80}(uncertain|uncertainty|cannot.*simult)",
                 r"heisenberg.{0,80}position.{0,80}momentum"),
                (r"position.{0,80}momentum.{0,80}(exact|arbitrary precision|simultaneously known)",), 1.3),
    ScienceRule("wavefunction_probability", "physics", ("wavefunction", "probability", "born"),
                (r"(wavefunction|amplitude).{0,80}(probability|born)|probability.{0,80}(wavefunction|amplitude)",
                 r"modulus.?squared.{0,50}probability"),
                (r"wavefunction.{0,80}(classical trajectory|direct observable probability without squar)",), 1.0),
    ScienceRule("unitary_closed_quantum", "physics", ("unitary", "schrodinger", "closed system", "quantum state"),
                (r"(closed quantum|quantum state).{0,100}(unitary|schrodinger)|unitary.{0,100}(closed quantum|state)",
                 r"schrodinger.{0,80}(evol|time)"),
                (r"closed quantum.{0,100}(nonunitary always|random classical trajectory)",), 1.0),
    ScienceRule("light_speed", "physics", ("light", "photon", "vacuum", "relativity"),
                (r"(light|photon).{0,80}vacuum.{0,80}(c|speed of light)|vacuum.{0,80}(light|photon).{0,80}constant",
                 r"massless.{0,60}(light speed|speed of light)"),
                (r"(light|photon).{0,80}vacuum.{0,80}(depends on source speed|faster than c)",), 1.0),
    ScienceRule("mass_energy", "physics", ("mass", "energy", "relativity"),
                (r"e\s*=\s*mc\^?2|mass.{0,50}energy equival",),
                (r"mass.{0,50}energy.{0,50}unrelated",), 1.0),
    ScienceRule("entropy_isolated", "physics", ("entropy", "isolated", "second law"),
                (r"(isolated|closed).{0,80}entropy.{0,80}(increase|non.?decreas)|second law.{0,80}entropy",
                 r"entropy.{0,80}(isolated|closed).{0,80}(increase|non.?decreas)"),
                (r"isolated.{0,80}entropy.{0,80}always decrease",), 1.2),
    ScienceRule("heat_hot_to_cold", "physics", ("heat", "temperature", "thermal"),
                (r"heat.{0,80}(hot|higher temperature).{0,80}(cold|lower temperature)",
                 r"(hot|higher temperature).{0,80}(cold|lower temperature).{0,80}heat"),
                (r"spontaneous heat.{0,80}(cold|lower).{0,80}(hot|higher)",), 0.9),
    ScienceRule("charge_conservation", "physics", ("charge", "conservation", "electric"),
                (r"electric charge.{0,80}conserv|conserv.{0,80}electric charge",),
                (r"electric charge.{0,80}(created from nothing|not conserved)",), 1.0),
    ScienceRule("gauss_flux", "physics", ("gauss", "flux", "electric field"),
                (r"electric flux.{0,80}enclosed charge|gauss.{0,80}enclosed charge",),
                (r"gauss.{0,80}surface area only",), 0.9),
    ScienceRule("lorentz_force", "physics", ("lorentz", "magnetic", "charge", "velocity"),
                (r"magnetic.{0,80}(velocity|moving charge).{0,80}(perpendicular|cross product|qv)",
                 r"lorentz.{0,80}q.{0,30}(e|v)"),
                (r"stationary charge.{0,80}magnetic force alone",), 0.9),

    # Chemistry / physical chemistry
    ScienceRule("acid_proton_donor", "chemistry", ("acid", "bronsted", "proton"),
                (r"(bronsted|brønsted).{0,60}acid.{0,60}proton donor|acid.{0,60}proton donor",),
                (r"(bronsted|brønsted).{0,60}acid.{0,60}proton acceptor",), 1.1),
    ScienceRule("base_proton_acceptor", "chemistry", ("base", "bronsted", "proton"),
                (r"(bronsted|brønsted).{0,60}base.{0,60}proton acceptor|base.{0,60}proton acceptor",),
                (r"(bronsted|brønsted).{0,60}base.{0,60}proton donor",), 1.1),
    ScienceRule("oxidation_electron_loss", "chemistry", ("oxidation", "electron", "reduction"),
                (r"oxidation.{0,50}(loss|lose).{0,30}electron|electron.{0,40}loss.{0,40}oxidation",),
                (r"oxidation.{0,50}(gain|gains).{0,30}electron",), 1.2),
    ScienceRule("reduction_electron_gain", "chemistry", ("reduction", "electron", "oxidation"),
                (r"reduction.{0,50}(gain|gains).{0,30}electron|electron.{0,40}gain.{0,40}reduction",),
                (r"reduction.{0,50}(loss|lose).{0,30}electron",), 1.2),
    ScienceRule("catalyst_activation_energy", "chemistry", ("catalyst", "activation energy", "equilibrium"),
                (r"catalyst.{0,80}(lower|reduce).{0,50}activation energy",),
                (r"catalyst.{0,80}(change|shift).{0,50}equilibrium constant|catalyst.{0,80}increase.*activation energy",), 1.2),
    ScienceRule("equilibrium_catalyst", "chemistry", ("catalyst", "equilibrium", "rate"),
                (r"catalyst.{0,80}(forward|reverse).{0,80}(rate|faster)|catalyst.{0,100}equilibrium.{0,50}(not change|unchanged)",
                 r"equilibrium constant.{0,80}(not change|unchanged).{0,80}catalyst"),
                (r"catalyst.{0,80}(changes|shifts).{0,50}equilibrium constant",), 1.0),
    ScienceRule("gibbs_spontaneous", "chemistry", ("gibbs", "free energy", "spontaneous"),
                (r"(gibbs|free energy).{0,80}(negative|<\s*0).{0,80}spontaneous|spontaneous.{0,80}(negative|<\s*0).{0,50}(gibbs|free energy)",),
                (r"(gibbs|free energy).{0,80}(positive|>\s*0).{0,80}spontaneous under constant",), 1.1),
    ScienceRule("ph_log", "chemistry", ("ph", "hydrogen ion", "acid"),
                (r"ph.{0,50}negative log.{0,50}(hydrogen|h\+)|ph.{0,40}-\s*log",),
                (r"ph.{0,50}positive log.{0,50}(hydrogen|h\+)",), 1.0),
    ScienceRule("sn2_inversion", "chemistry", ("sn2", "substitution", "stereochemistry"),
                (r"sn2.{0,80}(backside|inversion|walden)",),
                (r"sn2.{0,80}(carbocation|racemization|two step)",), 1.2),
    ScienceRule("sn1_carbocation", "chemistry", ("sn1", "substitution", "carbocation"),
                (r"sn1.{0,80}(carbocation|unimolecular|racemi)",),
                (r"sn1.{0,80}(concerted backside|single step backside)",), 1.1),
    ScienceRule("ideal_gas", "chemistry", ("ideal gas", "pressure", "volume", "temperature"),
                (r"p\s*v\s*=\s*n\s*r\s*t|ideal gas.{0,80}pv.{0,30}nrt",),
                (r"ideal gas.{0,80}pv.{0,30}constant independent of temperature for fixed n",), 1.0),
    ScienceRule("le_chatelier", "chemistry", ("le chatelier", "equilibrium", "stress"),
                (r"le chatelier.{0,100}(oppose|counteract|shift).{0,80}(change|stress)",),
                (r"le chatelier.{0,100}equilibrium never shifts",), 0.9),

    # Biology / molecular biology / genetics
    ScienceRule("dna_to_rna", "biology", ("dna", "rna", "transcription"),
                (r"dna.{0,80}(transcri|template).{0,80}rna|transcription.{0,80}dna.{0,80}rna",),
                (r"transcription.{0,80}rna.{0,80}dna as product",), 1.2),
    ScienceRule("rna_to_protein", "biology", ("rna", "protein", "translation", "ribosome"),
                (r"(mrna|rna).{0,80}translation.{0,80}protein|translation.{0,80}(mrna|rna).{0,80}protein|ribosome.{0,80}(translate|protein)",),
                (r"translation.{0,80}dna replication",), 1.2),
    ScienceRule("dna_replication_semiconservative", "biology", ("dna", "replication", "semiconservative"),
                (r"dna replication.{0,100}semi.?conservative|semi.?conservative.{0,100}dna replication",),
                (r"dna replication.{0,100}fully conservative only",), 1.1),
    ScienceRule("polymerase_direction", "biology", ("polymerase", "dna", "5", "3"),
                (r"dna polymerase.{0,100}5.?to.?3|5.?to.?3.{0,100}dna polymerase",),
                (r"dna polymerase.{0,100}3.?to.?5 synthesis",), 1.0),
    ScienceRule("codon_three", "biology", ("codon", "amino acid", "nucleotide"),
                (r"codon.{0,60}(three|3).{0,40}nucleotide|(three|3).{0,40}nucleotide.{0,60}codon",),
                (r"codon.{0,60}(two|2|four|4).{0,40}nucleotide",), 1.0),
    ScienceRule("mitosis_ploidy", "biology", ("mitosis", "daughter", "chromosome"),
                (r"mitosis.{0,100}(genetically similar|same chromosome|same ploidy)",),
                (r"mitosis.{0,100}halve.{0,40}(chromosome|ploidy)",), 0.9),
    ScienceRule("meiosis_reduction", "biology", ("meiosis", "haploid", "gamete", "ploidy"),
                (r"meiosis.{0,100}(haploid|half.{0,30}chromosome|gamete)",),
                (r"meiosis.{0,100}identical diploid daughter",), 1.0),
    ScienceRule("natural_selection_population", "biology", ("natural selection", "evolution", "population", "allele"),
                (r"natural selection.{0,120}(population|allele frequenc|differential reproductive)",),
                (r"individual.{0,80}evolve during lifetime by natural selection",), 1.0),
    ScienceRule("mutation_source_variation", "biology", ("mutation", "variation", "genetic"),
                (r"mutation.{0,80}(genetic variation|new allele)|genetic variation.{0,80}mutation",),
                (r"mutation.{0,80}always beneficial",), 0.9),
    ScienceRule("enzyme_catalyst", "biology", ("enzyme", "activation energy", "catalyst"),
                (r"enzyme.{0,80}(catalyst|lower.*activation energy)",),
                (r"enzyme.{0,80}(consumed permanently|raise.*activation energy)",), 1.0),
    ScienceRule("membrane_bilayer", "biology", ("membrane", "phospholipid", "bilayer"),
                (r"(cell|plasma) membrane.{0,100}phospholipid.{0,50}bilayer|phospholipid.{0,50}bilayer.{0,100}(cell|plasma) membrane",),
                (r"(cell|plasma) membrane.{0,100}single rigid protein sheet",), 0.9),
    ScienceRule("atp_energy", "biology", ("atp", "energy", "cell"),
                (r"atp.{0,80}(energy|phosphate transfer)|cell.{0,80}atp.{0,80}energy",),
                (r"atp.{0,80}genetic information storage primary",), 0.8),
    ScienceRule("antibody_bcell", "biology", ("antibody", "b cell", "plasma cell"),
                (r"(b cell|plasma cell).{0,80}antibod|antibod.{0,80}(b cell|plasma cell)",),
                (r"red blood cell.{0,80}produce antibody",), 0.9),
    ScienceRule("tcell_cellular", "biology", ("t cell", "cell-mediated", "immune"),
                (r"t cell.{0,80}(cell.?mediated|cytotoxic|helper)",),
                (r"t cell.{0,80}secrete immunoglobulin as primary function",), 0.8),
    ScienceRule("oxygen_mitochondria", "biology", ("mitochond", "oxygen", "respiration", "electron transport"),
                (r"oxygen.{0,100}(final electron acceptor|electron transport)|mitochond.{0,100}(respiration|atp)",),
                (r"oxygen.{0,100}primary electron donor in respiration",), 1.0),
    ScienceRule("photosynthesis_chloroplast", "biology", ("photosynthesis", "chloroplast", "light"),
                (r"photosynthesis.{0,100}(chloroplast|light energy)|chloroplast.{0,100}photosynthesis",),
                (r"photosynthesis.{0,100}mitochondria only",), 0.9),

    # Math / probability / CS foundations
    ScienceRule("probability_range", "mathematics", ("probability", "probabilities"),
                (r"probabilit.{0,80}(between 0 and 1|0\s*(?:to|and)\s*1|nonnegative)",),
                (r"probabilit.{0,80}(less than 0|greater than 1).{0,30}valid",), 0.9),
    ScienceRule("conditional_probability", "mathematics", ("conditional probability", "bayes", "p(a|b)"),
                (r"p\s*\(?.{0,20}\|.{0,20}\)?.{0,40}=.{0,80}/.{0,80}p\s*\(",),
                (), 0.6),
    ScienceRule("derivative_slope", "mathematics", ("derivative", "slope", "rate of change"),
                (r"derivative.{0,80}(slope|rate of change)|slope.{0,80}derivative",),
                (r"derivative.{0,80}area under curve",), 0.9),
    ScienceRule("integral_area", "mathematics", ("integral", "area", "antiderivative"),
                (r"integral.{0,80}(area|antiderivative)|area under.{0,80}integral",),
                (r"integral.{0,80}slope at a point",), 0.9),
    ScienceRule("big_o_upper", "computer_science", ("big o", "complexity", "asymptotic"),
                (r"big.?o.{0,80}(upper bound|asymptotic)",),
                (r"big.?o.{0,80}exact running time for every input",), 0.8),
    ScienceRule("binary_search_log", "computer_science", ("binary search", "sorted", "log"),
                (r"binary search.{0,100}(sorted|logarithmic|o\(log)",),
                (r"binary search.{0,100}unsorted.{0,40}o\(log",), 0.9),
)


DOMAIN_TERMS: Mapping[str, tuple[str, ...]] = {
    "physics": ("quantum", "photon", "electron", "energy", "momentum", "field", "force", "relativity", "entropy", "wave"),
    "chemistry": ("acid", "base", "reaction", "molecule", "bond", "catalyst", "oxidation", "reduction", "solvent", "equilibrium"),
    "biology": ("cell", "gene", "dna", "rna", "protein", "enzyme", "organism", "evolution", "membrane", "immune"),
    "mathematics": ("theorem", "equation", "integral", "derivative", "probability", "matrix", "integer", "polynomial"),
    "computer_science": ("algorithm", "compiler", "database", "runtime", "complexity", "program", "binary search"),
}


class OptionConditionedScientificReasoner:
    """Evaluate A-D as separate hypotheses, then select only with sufficient evidence.

    This stage is deliberately conservative. If the evidence margin is too small,
    the caller falls back to the V87.25 unresolved path instead of pretending a
    heuristic guess is verified scientific reasoning.
    """

    MIN_EVIDENCE = 0.85
    MIN_MARGIN = 0.50

    def __init__(self, fallback: StructuredMCQReasoner):
        self.fallback = fallback

    @staticmethod
    def _rule_active(rule: ScienceRule, task: MCQTask, option: str) -> bool:
        hay = _norm(task.question + " " + option)
        return any(_norm(anchor) in hay for anchor in rule.anchors)

    @staticmethod
    def _score_rule(rule: ScienceRule, task: MCQTask, option: str) -> tuple[float, list[str], list[str]]:
        combined = _norm(task.question + " " + option)
        support = [p for p in rule.true_patterns if re.search(p, combined, re.I)]
        oppose = [p for p in rule.false_patterns if re.search(p, combined, re.I)]
        score = rule.weight * (len(support) - len(oppose))
        evidence = [rule.rule_id + ":support"] * len(support)
        contradictions = [rule.rule_id + ":contradiction"] * len(oppose)
        return score, evidence, contradictions

    @staticmethod
    def _domain_mismatch(task: MCQTask, option: str) -> float:
        if task.domain not in DOMAIN_TERMS:
            return 0.0
        low = _norm(option)
        own = sum(term in low for term in DOMAIN_TERMS[task.domain])
        others = 0
        for domain, terms in DOMAIN_TERMS.items():
            if domain == task.domain:
                continue
            others += sum(term in low for term in terms)
        # A mild penalty only for an option that is strongly in another domain
        # while containing no vocabulary from the inferred question domain.
        if own == 0 and others >= 2:
            return -0.30
        return 0.0

    def assess(self, task: MCQTask) -> list[OptionAssessment]:
        out: list[OptionAssessment] = []
        question_tokens = _tokens(task.question)
        for letter in "ABCD":
            option = task.choices[letter]
            score = 0.0
            evidence: list[str] = []
            contradictions: list[str] = []
            active = 0
            for rule in RULES:
                if rule.domain not in {task.domain, "general"} and task.domain != "general":
                    continue
                if not self._rule_active(rule, task, option):
                    continue
                active += 1
                delta, ev, contra = self._score_rule(rule, task, option)
                score += delta
                evidence.extend(ev)
                contradictions.extend(contra)

            mismatch = self._domain_mismatch(task, option)
            if mismatch:
                score += mismatch
                contradictions.append("domain:mismatch")

            # Unsupported absolutes receive only a very small penalty; they are
            # common distractors but can also be scientifically valid.
            if _ABSOLUTE.search(option) and not evidence:
                score -= 0.12
                contradictions.append("logic:absolute-unverified")

            # Content relevance is not treated as truth, but a completely
            # off-topic option gets a tiny plausibility penalty.
            opt_tokens = _tokens(option)
            overlap = len(question_tokens & opt_tokens)
            if question_tokens and overlap == 0 and len(opt_tokens) >= 4:
                score -= 0.05

            out.append(
                OptionAssessment(
                    letter=letter,
                    option=option,
                    truth_score=round(score, 4),
                    evidence=tuple(evidence),
                    contradictions=tuple(contradictions),
                    active_rules=active,
                )
            )
        return out

    def decide(
        self,
        task: MCQTask,
        history: list[Mapping[str, Any]] | None = None,
        *,
        teacher_allowed: bool = False,
    ) -> tuple[MCQDecision, list[OptionAssessment]]:
        assessments = self.assess(task)
        negative = bool(_NEGATIVE_QUESTION.search(task.question))

        ordered = sorted(
            assessments,
            key=lambda x: (x.truth_score, x.letter),
            reverse=not negative,
        )
        best = ordered[0]
        runner = ordered[1]
        utility_best = -best.truth_score if negative else best.truth_score
        utility_runner = -runner.truth_score if negative else runner.truth_score
        margin = utility_best - utility_runner

        strongest = max(abs(x.truth_score) for x in assessments)
        evidence_count = len(best.evidence) + len(best.contradictions)

        if strongest >= self.MIN_EVIDENCE and margin >= self.MIN_MARGIN and evidence_count:
            rationale = (
                f"option-conditioned scientific evidence; polarity={'negative' if negative else 'positive'}; "
                f"score={best.truth_score:.3f}; margin={margin:.3f}; "
                f"evidence={','.join(best.evidence[:4]) or '-'}; "
                f"contradictions={','.join(best.contradictions[:4]) or '-'}"
            )
            return MCQDecision(
                best.letter,
                "option_conditioned_science",
                min(0.86, 0.58 + min(0.28, margin / 4.0)),
                rationale,
            ), assessments

        fallback = self.fallback.decide(
            task,
            history,
            teacher_allowed=teacher_allowed,
        )
        return fallback, assessments

    def run(
        self,
        task: MCQTask,
        history: list[Mapping[str, Any]] | None = None,
        *,
        teacher_allowed: bool = False,
    ) -> dict[str, Any]:
        decision, assessments = self.decide(
            task,
            history,
            teacher_allowed=teacher_allowed,
        )
        lines = []
        if decision.source in {"verified_arithmetic", "option_conditioned_science"} and decision.rationale:
            lines.append(decision.rationale)
        lines.append("Answer: $" + decision.letter)
        return {
            "ok": True,
            "reply": "\n".join(lines),
            "confidence": decision.confidence,
            "decision_source": decision.source,
            "domain": task.domain,
            "forced_choice": decision.source == "unresolved_content_tiebreak",
            "needs_teacher": decision.source == "unresolved_content_tiebreak",
            "option_assessments": [
                {
                    "letter": x.letter,
                    "truth_score": x.truth_score,
                    "evidence": list(x.evidence),
                    "contradictions": list(x.contradictions),
                    "active_rules": x.active_rules,
                }
                for x in assessments
            ],
        }


def science_rule_stats() -> dict[str, Any]:
    domains: dict[str, int] = {}
    for rule in RULES:
        domains[rule.domain] = domains.get(rule.domain, 0) + 1
    return {
        "rules": len(RULES),
        "domains": domains,
        "benchmark_answer_keys": 0,
    }
