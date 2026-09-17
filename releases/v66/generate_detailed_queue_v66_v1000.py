#!/usr/bin/env python3
"""Generate the explicit one-version/one-experiment queue for FAP V66..V1000.

The source-of-truth is intentionally compact and deterministic. Each topic consumes
five consecutive versions: Contract, Prototype, Break-it test, Benchmark, Gate.
The generator refuses gaps, duplicates, or a total other than 935 versions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


STAGES = [
    ("Contract", "Define the minimal interface, inputs, outputs, invariants, baseline fixture, and resource budget."),
    ("Prototype", "Implement the smallest working path behind a feature flag; avoid unrelated refactors."),
    ("Break-it test", "Add adversarial, malformed, stale, partial, conflicting, or fault-injected cases that must fail safely."),
    ("Benchmark", "Measure task success/regression plus RAM, p50/p95 latency, storage growth, reproducibility, and energy/thermal cost where available."),
    ("Gate", "Encode KEEP/MODIFY/KILL and promotion/rollback thresholds in machine-readable evidence; rehearse rollback from a failed candidate."),
]


@dataclass(frozen=True)
class Phase:
    start: int
    end: int
    title: str
    goal: str
    topics: tuple[str, ...]


PHASES = [
    Phase(66, 100, "Evidence-first foundation", "Make every later self-improvement independently reproducible and rollback-safe.", (
        "EvidenceManifest v1",
        "Artifact digest + provenance chain",
        "Deterministic observation/action replay",
        "Failure-injection harness",
        "CI matrix + clean-checkout verification",
        "Android E2E smoke path",
        "Rollback rehearsal + recovery-time objective",
    )),
    Phase(101, 150, "Memory architecture", "Build bounded provenance-aware memory that improves retrieval without uncontrolled growth.", (
        "Event/episodic memory",
        "Failure Memory normalization",
        "Semantic memory + provenance",
        "Contradiction tracking",
        "Retrieval scoring",
        "Dedupe + near-duplicate merge",
        "Retention/decay policy",
        "Counterexample preservation",
        "Memory compaction snapshot",
        "Memory utility benchmark",
    )),
    Phase(151, 200, "Perception and state estimation", "Estimate Android UI state robustly from noisy and partial observations.", (
        "Accessibility-tree parser",
        "Screenshot region segmentation",
        "OCR/accessibility fusion",
        "Temporal differencing",
        "UI-state graph",
        "Confidence map + unknown-state detector",
        "Visual anomaly detection",
        "Region-of-interest scheduler",
        "Theme/scale/font robustness",
        "Perception benchmark corpus",
    )),
    Phase(201, 250, "Planning core", "Produce bounded auditable plans that can repair themselves under uncertainty.", (
        "Declarative action schema",
        "Precondition/effect model",
        "Bounded best-first planner",
        "Cost/time budget planner",
        "Risk-aware planner",
        "Plan repair after action failure",
        "Alternative-plan cache",
        "Goal decomposition/HTN layer",
        "Uncertainty-aware branch planning",
        "Plan trace visualizer + benchmark",
    )),
    Phase(251, 300, "Android embodied execution", "Run long-lived Android tasks and recover from focus, app, timing, and display failures.", (
        "ADB/accessibility action arbitration",
        "Idempotent action keys",
        "Package/window mismatch recovery",
        "Focus recovery controller",
        "Task watchdog + false-positive control",
        "Browser/Play Store escape recovery",
        "Multi-window/display state isolation",
        "Device capability profile",
        "Action postcondition verifier",
        "24-hour Android soak harness",
    )),
    Phase(301, 350, "Skill system", "Make reusable skills composable, permission-bounded, versioned, and evidence-scored.", (
        "Typed skill manifest",
        "Skill input/output contracts",
        "Skill precondition/effect contracts",
        "Permission envelope",
        "Versioned skill registry",
        "Skill dependency graph",
        "Skill composition engine",
        "Evidence-based skill quality score",
        "Skill deprecation/garbage collection",
        "Skill portability benchmark",
    )),
    Phase(351, 400, "Sparse / fly-inspired computation", "Test whether sparse high-dimensional routing and memory beat dense baselines on constrained hardware.", (
        "Sparse random projection baseline",
        "KC-like high-dimensional expansion",
        "Winner-take-most inhibition",
        "Sparse novelty detector",
        "Locality-sensitive sparse codes",
        "Sparse associative recall",
        "Event-driven sparse updates",
        "Learned sparse readout",
        "Sparsity/adversarial robustness sweep",
        "Sparse-vs-dense frontier benchmark",
    )),
    Phase(401, 450, "Distillation and compression", "Shrink useful behavior and knowledge while explicitly measuring competence loss.", (
        "Teacher-trace capture schema",
        "Teacher-trace quality filters",
        "Rule/tree behavior distillation",
        "Finite-state-controller distillation",
        "Tiny adapter/student distillation",
        "Quantization sweep",
        "Dictionary/codon-like knowledge coding",
        "Irreversible trace compression",
        "Reversible knowledge-pack compression",
        "Competence-bytes-latency frontier",
    )),
    Phase(451, 500, "Self-evaluation", "Detect likely failures before execution and calibrate confidence against observed outcomes.", (
        "Independent critic interface",
        "Invariant-based verifier",
        "Confidence calibration",
        "Abstain/retry policy",
        "Metamorphic testing",
        "Counterexample generator",
        "Adversarial task mutation",
        "Duplicate-plan disagreement test",
        "Hidden holdout evaluator",
        "Self-evaluation calibration benchmark",
    )),
    Phase(501, 550, "Trusted sandbox and synthesis", "Test generated components without trusting their code or self-reported evidence.", (
        "Capability-spec-first handoff",
        "Fixed-argv sandbox transport",
        "No-shell execution boundary",
        "Filesystem capability allowlist",
        "Network-deny/default policy",
        "CPU/RAM/time/output quotas",
        "Generated patch size/file limits",
        "Artifact signing + provenance",
        "Auto-repair candidate tournament",
        "Sandbox escape/fault-injection suite",
    )),
    Phase(551, 600, "Multimodal fusion", "Fuse complementary signals only where fusion improves measured state estimation.", (
        "Text + accessibility fusion",
        "Pixel patch + UI-tree fusion",
        "Temporal event fusion",
        "Audio/event channel adapter",
        "Cross-modal alignment",
        "Conflicting-channel arbitration",
        "Missing-channel degradation",
        "Modality confidence calibration",
        "Adaptive modality scheduler",
        "Fusion-vs-single-channel benchmark",
    )),
    Phase(601, 650, "Continual learning", "Learn new routines while protecting old competence and keeping mutable state rollbackable.", (
        "Frozen-core/mutable-edge split",
        "Online adapter bank",
        "Replay buffer policy",
        "Drift detector",
        "Plasticity budget",
        "Consolidation window",
        "Learned-state checkpoint/rollback",
        "Catastrophic-forgetting holdout",
        "Skill-vs-weight learning router",
        "Continual-learning long-run benchmark",
    )),
    Phase(651, 700, "Multi-agent / committee architecture", "Use specialized roles only where reliability gains justify coordination overhead.", (
        "Planner/executor role split",
        "Independent verifier role",
        "Memory curator role",
        "Compressor role",
        "Disagreement protocol",
        "Evidence arbitration",
        "Role state isolation",
        "Correlated-error detector",
        "Conditional committee activation",
        "Committee gain-vs-cost benchmark",
    )),
    Phase(701, 750, "Distributed and device-aware runtime", "Adapt one task graph across weak phones and stronger hosts under explicit resource budgets.", (
        "CPU/GPU/NPU capability probe",
        "Per-kernel device routing",
        "Local/remote split planner",
        "Bandwidth-aware execution",
        "Memory-mapped index tier",
        "Bounded cache hierarchy",
        "Checkpoint migration",
        "Low-RAM runtime mode",
        "Battery/thermal budget controller",
        "Cross-device performance frontier",
    )),
    Phase(751, 800, "Formalized safety and invariants", "Move critical controllers from convention-based safety to machine-checkable properties.", (
        "Typed side-effect model",
        "Forbidden-transition invariants",
        "Property-based controller tests",
        "Small-state model checking",
        "Permission proof object",
        "Fail-closed transition rules",
        "Schema/data rollback invariant",
        "Concurrency/race invariant tests",
        "Invariant drift detector",
        "Safety-proof coverage benchmark",
    )),
    Phase(801, 850, "Knowledge substrate", "Keep knowledge compact, updateable, contradiction-aware, and provenance-linked.", (
        "Structured concept graph",
        "Executable knowledge fragments",
        "Compressed inverted index",
        "Causal/relation links",
        "Contradiction sets",
        "Source confidence model",
        "Knowledge aging/refresh",
        "Content-addressed knowledge packs",
        "Knowledge dedupe/merge",
        "Knowledge retrieval + update benchmark",
    )),
    Phase(851, 900, "Cognitive architecture integration", "Integrate perception, memory, planning, skills, and evaluation into one measured loop.", (
        "Bounded working memory",
        "Attention/routing controller",
        "Global task-state model",
        "Perception-memory-planner loop",
        "Goal arbitration",
        "Curiosity under cost/risk budget",
        "Idle sleep/consolidation cycle",
        "Meta-controller algorithm selection",
        "Closed-loop fault recovery",
        "Integrated architecture soak benchmark",
    )),
    Phase(901, 950, "Generalization and transfer", "Measure transfer on unseen apps and environments rather than only replaying known tasks.", (
        "Cross-app primitive abstraction",
        "Few-shot skill adaptation",
        "Zero-shot skill routing",
        "Subplan/macro discovery",
        "Analogy retrieval",
        "Synthetic curriculum generator",
        "Unseen-theme/timing transfer",
        "Entire-app hidden holdout",
        "Transfer failure clustering",
        "Generalization efficiency benchmark",
    )),
    Phase(951, 1000, "Hardening and long-horizon autonomy", "Reach weeks-scale operation with bounded resources, auditable upgrades, and disaster recovery.", (
        "Multi-day soak runner",
        "Process-kill/restart recovery",
        "Disk-full/partial-write recovery",
        "Corrupt-index recovery",
        "Upgrade/backward-compatibility contract",
        "Stable public API/ABI boundary",
        "Resource-cap enforcement",
        "Reproducibility pack + clean bootstrap",
        "Governance/capability-limit manifest",
        "V1000 end-to-end audit + disaster drill",
    )),
]


def build_rows() -> list[tuple[int, str, str, str, str]]:
    rows: list[tuple[int, str, str, str, str]] = []
    for phase in PHASES:
        expected = phase.end - phase.start + 1
        if len(phase.topics) * len(STAGES) != expected:
            raise ValueError(
                f"{phase.start}-{phase.end}: {len(phase.topics)} topics x {len(STAGES)} stages != {expected} versions"
            )
        version = phase.start
        for topic in phase.topics:
            for stage, experiment in STAGES:
                rows.append((version, phase.title, topic, stage, experiment))
                version += 1

    versions = [r[0] for r in rows]
    expected_versions = list(range(66, 1001))
    if versions != expected_versions:
        missing = sorted(set(expected_versions) - set(versions))
        dupes = sorted(v for v in set(versions) if versions.count(v) > 1)
        raise AssertionError(f"queue coverage invalid; missing={missing}, duplicates={dupes}")
    if len(rows) != 935:
        raise AssertionError(f"expected 935 experiments, got {len(rows)}")
    return rows


def render_markdown() -> str:
    rows = build_rows()
    out = [
        "# FAP Explicit Experiment Queue — V66 to V1000",
        "",
        "Generated deterministically by `generate_detailed_queue_v66_v1000.py`.",
        "",
        "Each version owns exactly one falsifiable experiment. Each topic uses five releases in order: Contract -> Prototype -> Break-it test -> Benchmark -> Gate. A failed idea is allowed and should end as `KILL` rather than being promoted by version-number pressure.",
        "",
        "Global evidence requirement: source SHA, artifact digest, reproducible test result, resource metrics, known limitations, rollback target, and explicit KEEP/MODIFY/KILL. Candidate self-report alone is not evidence.",
        "",
        "| Version | Phase | Experiment | Required exit |",
        "|---|---|---|---|",
    ]
    for version, phase, topic, stage, experiment in rows:
        out.append(
            f"| V{version} | {phase} | **{topic} — {stage}**: {experiment} | EvidenceManifest + reproducible result + explicit KEEP/MODIFY/KILL; Gate stages must also prove rollback. |"
        )
    out.extend([
        "",
        "## Coverage check",
        "",
        "- First version: V66",
        "- Last version: V1000",
        "- Experiment count: 935",
        "- Missing versions: 0",
        "- Duplicate versions: 0",
        "",
    ])
    return "\n".join(out)


def main() -> None:
    target = Path(__file__).with_name("DETAILED_QUEUE_V66_V1000.md")
    text = render_markdown()
    target.write_text(text, encoding="utf-8")
    print(f"wrote {target} with {len(build_rows())} experiments")


if __name__ == "__main__":
    main()
