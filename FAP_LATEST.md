# FAP latest development snapshot

Current mainline: **V87.54 — Targeted Research Cycles**.

V87.54 takes the rolling research frontier one step further. High-value
unresolved clusters are converted into explicit research cycles and then
re-challenged against targeted recent literature before FAP suggests the next
test.

Each cycle contains:
- one priority research question;
- multiple competing provisional hypotheses;
- an explicit falsifier for each hypothesis;
- the next observation/experiment that would best discriminate the alternatives;
- a value-of-information score used to prioritize scarce reasoning/search effort;
- a targeted Crossref literature re-search (up to 20 top topics × 60 papers in
  the scheduled workflow) that checks whether the relevant appraisal dimension
  is actually discussed in a broader one-year evidence window;
- a phase such as `evidence-needed`, `literature-signal-found`,
  `evidence-still-ambiguous`, or `evidence-sparse`.

The rolling workflow publishes a sanitized
`knowledge/research_cycle_latest.json` snapshot together with the research
frontier. Literature hits are only screening signals: they do not automatically
confirm a hypothesis and are never promoted to verified fact solely because
many papers mention the same issue.

When the snapshot is present, prompts such as:

```text
大気について次の検証を進めて
この未解決問題の研究サイクルを回して
```

route to:

```text
research-cycle → literature-rechallenge → falsification-next
```

V87.53 research frontier, V87.52 hypothesis reasoning, V87.51 literature
appraisal, V87.50 dated recent science, V87.49 scientific modeling and V87.48
epistemic learning remain underneath V87.54.

V87.53 turns the large unresolved-literature pool into a rolling research
agenda instead of leaving it as a flat list of unanswered appraisal questions.

The broad literature workflow now:
- screens recent journal articles;
- keeps short abstract-derived open-question / limitation / claim hints in the
  workflow artifact without committing full abstracts;
- clusters papers into recurring research-topic families;
- aggregates unresolved appraisal dimensions such as validation, causality,
  robustness, generalization, scale and uncertainty;
- ranks clusters by paper volume, critical unresolved dimensions,
  explicit open-question hints, post-publication updates and Crossref citation
  counts;
- generates priority research questions for each cluster;
- attaches **provisional** hypothesis → falsifier → next-test loops;
- publishes a sanitized top-frontier snapshot to
  `knowledge/research_frontier_latest.json` when the workflow can push it.

Important epistemic boundary: absence of a method or limitation from an abstract
is not proof that the underlying science is unresolved. Frontier entries are
research priorities produced by automated screening, not verified facts.

When a snapshot is present, chat prompts such as:

```text
この分野の未解決問題は？
大気について次に調べるべき研究課題は？
```

route to:

```text
research-frontier → gap-prioritize
```

and return the highest-priority questions together with provisional
hypothesis/falsification/next-observation loops.

V87.52 hypothesis reasoning, V87.51 literature appraisal, V87.50 dated recent
science, V87.49 scientific modeling and V87.48 epistemic learning remain
underneath V87.53.

V87.52 adds a generic abductive-reasoning layer above the existing scientific
models, inquiry engine and epistemic ledger.

For prompts asking for hypotheses, possible causes, alternative explanations,
or falsification plans, FAP now:

- retrieves relevant local evidence and a structured scientific model when one
  exists;
- generates multiple **competing** hypotheses rather than one preferred story;
- derives an observable prediction for each hypothesis;
- derives an explicit falsifier / failure condition for each hypothesis;
- identifies the next observation or experiment that would discriminate among
  alternatives;
- scores hypotheses by evidence support, novelty, falsifiability and parsimony;
- stores hypotheses in a separate provisional ledger under
  `runtime/hypotheses/ledger.json`;
- never promotes a generated hypothesis to verified fact merely because it was
  generated repeatedly.

The hypothesis engine is topic-generic. Scientific domains grow through the
existing knowledge/model data rather than through new per-topic chat branches.

Example route:

```text
YOU: 大気の運動について競合仮説と反証条件を出して
route: hypothesis-generate → falsification-plan
```

V87.51 literature appraisal, V87.50 dated recent science, V87.49 scientific
modeling and V87.48 epistemic learning remain underneath V87.52.

V87.51 adds a broad recent-literature screening pipeline on top of the dated
science snapshot. It can page through recent Crossref journal-article metadata,
generate a fixed epistemic appraisal grid for each paper, resolve only what the
metadata/abstract actually supports, and preserve unresolved questions instead
of inventing answers.

The appraisal grid checks research question, design, sample, intervention or
input conditions, outcomes, methods, controls, uncertainty, effect size,
statistics, assumptions, confounding, bias, missing data, robustness,
validation, reproducibility, mechanism, causality, generalization, limitations,
contradictions, extreme conditions, scale dependence, prospective prediction,
data provenance, ethics/funding, correction or retraction signals, novelty,
practical significance, future tests and remaining open questions.

The rolling GitHub workflow
`.github/workflows/broad-literature-critical-appraisal.yml` performs an
initial seven-day broad screening (up to 50,000 journal articles) and then a
daily rolling screen (up to 50,000 per run). Results are stored as workflow
artifacts; the compact output does not copy full abstracts into the public
repository.

Important boundary: this is automated **critical appraisal**, not formal
independent expert peer review. A Crossref `journal-article` record also does
not by itself prove that a particular article completed peer review. Full-text
methodological review remains impossible when only bibliographic metadata or an
abstract is available.

V87.50 dated recent science, V87.49 scientific modeling and V87.48 epistemic
learning remain underneath V87.51.

V87.50 adds a dated, source-provenanced recent-science evidence layer on top of
the structured scientific models. The snapshot is current to **2026-09-22** and
is stored as data in `knowledge/latest_science_2026.jsonl`, not as
topic-specific routing logic.

For atmospheric science, the current evidence pack includes:
- ECMWF IFS Cycle 50r1 (12 May 2026): fully coupled atmosphere-ocean-sea-ice
  data assimilation and improved convective-precipitation representation;
- ECMWF AIFS Single v2 / AIFS ENS v2 (12 May 2026): operational data-driven
  deterministic and ensemble forecasting alongside the physics-based IFS;
- operational ensemble uncertainty handling and documented ML limitations,
  including smoothing of small-scale fields and tropical-cyclone intensity
  underprediction;
- WMO State of the Global Climate 2025 (23 March 2026): the latest global
  observational context, including record Earth energy imbalance.

Scientific-model answers can attach the most relevant recent evidence together
with its date, institution, source title and source URL. The chat API exposes the
same provenance under `scientific_model.recent_science`. The endpoint
`/api/v1/science-snapshot` lists the installed science snapshot.

This is a static verified snapshot, not an automatic live literature feed. New
science is added by appending dated evidence records rather than changing chat
routing code.

V87.49 structured scientific modeling and V87.48 epistemic learning remain
underneath V87.50.

V87.49 adds a generic structured scientific-model layer on top of V87.48.
Scientific coverage is now data-driven: a model record can provide variables,
drivers, governing equations, mechanisms, scale dependence, assumptions,
observables and prediction limits without adding a topic-specific branch to the
chat router.

The first models cover atmospheric dynamics and generic fluid dynamics. For
atmospheric motion the model can connect pressure-gradient acceleration,
Coriolis deflection, gravity, surface friction, buoyancy, thermodynamics and
mass conservation, and can expose equations such as momentum balance,
hydrostatic balance, the ideal-gas relation and continuity.

Example route:

```text
YOU: 大気の動き方を式も含めて解説して
route: scientific-model → equations
```

New scientific domains can be added to
`knowledge/scientific_models_ja.jsonl` rather than by growing hard-coded chat
logic.

V87.48 epistemic learning remains underneath V87.49.

V87.48 changes the inquiry loop from "ask many questions" into a more selective
learning system:

- every generated question receives an epistemic value score; falsification,
  uncertainty, failure modes, evidence and validation are prioritized over
  repetitive definitions;
- verified answers are persisted locally with their original evidence IDs;
- repeated compatible answers reinforce an existing conclusion instead of
  duplicating it;
- conflicting conclusions are quarantined in a contradiction ledger instead of
  silently overwriting prior knowledge;
- high-value unresolved questions persist as the next-session frontier;
- later sessions can recall previously verified conclusions without treating the
  stored conclusion as new independent evidence;
- 2048-question burst mode remains available, but only the strongest verified
  conclusions are promoted to long-term epistemic memory.

The persistent ledger is stored under `runtime/epistemic/ledger.json`. The
chat API exposes question value, attempts, recall state, learning counts and
ledger statistics. This keeps knowledge growth data-driven and avoids adding
topic-specific routing branches.

V87.47 mass inquiry remains underneath V87.48.

V87.47 raises the generic inquiry volume substantially:

- default target: 256 self-questions
- burst target: 2048 self-questions for phrases such as `とにかく増やして`,
  `最大限`, `限界まで`, or `可能な限り`
- resolution retry budget: up to 8 rounds
- explicit numeric requests remain supported up to 2048 questions

The engine still uses the same generic dimensions and answer-to-question
expansion. It does not add topic-specific routing branches just to reach the
higher counts.

V87.46 and V87.45 remain underneath V87.47.

V87.46 increases self-question generation from the earlier five-question audit
to a high-volume generic inquiry loop.

Default behavior:

```text
retrieve local evidence
→ generate 96 epistemic questions
→ answer what the evidence supports
→ use resolved answers to discover related concepts
→ generate follow-up questions from those answers
→ retry unresolved questions for up to 5 rounds
→ keep unsupported questions explicitly unresolved
```

An explicit request such as `128問` raises the target, up to 256 questions.
`FAP_INQUIRY_TARGET`, `FAP_INQUIRY_ROUNDS`, and
`FAP_INQUIRY_DISPLAY` can tune the defaults without changing code.

The question dimensions are generic (mechanism, conditions, uncertainty,
evidence, counterfactuals, validation, scale, failure modes, etc.). New subject
matter is added under `knowledge/*.jsonl`; it does not require new
topic-specific routing branches.

The chat API exposes every generated question together with resolution state,
evidence IDs, generation depth, total generated/resolved/unresolved counts and
resolution rate. The browser only prints a bounded subset so a 96-256 question
audit does not make the UI unusable.

V87.45 generic retrieval/inquiry and V87.44 context follow-up remain underneath
V87.46.

V87.44 fixes a failure where a known topic was explained correctly but a natural
clarification such as:

```text
YOU: 大気の運動について
FAP: ...気圧傾度力、コリオリ効果...
YOU: どういうことなのかわかりますか？
```

lost the topic and fell back to the generic unresolved answer.

The reflective organ now recognizes natural clarification / understanding
phrases, resolves the most recent known topic from conversation history, and
re-explains it in plain language. The diagnostic route marks this as:

```text
reflective-chat → clarify → context-followup
```

V87.43 reflective reasoning remains underneath V87.44.

V87.43 moves ordinary conversation beyond exact constants and fixed capability
answers. A new local reflective organ resolves known topics, chooses an
explanation mode (overview / why / how / deep / compare), uses recent chat to
resolve short follow-ups, and keeps every answer tied to explicit local concept
evidence.

Example:

```text
YOU: 大気の運動に関しては？
FAP: 大気の運動は、空間的な気圧・密度・温度の差から生じる力と、
     地球の自転、重力、地表摩擦の組み合わせで決まります。...
```

The first knowledge set covers atmospheric motion, pressure-gradient force,
Coriolis effect, convection, waves, energy, entropy, natural selection, gene
expression, acid/base chemistry and algorithmic complexity. It also supports
two-concept comparisons and topic follow-ups. It also has a premise-reasoning
lane for open-ended prompts such as hypotheses, "どう思う？", "もし〜なら",
or conceptual frames: it separates premise, consequence, alternative
explanation, counterexample and possible test without inventing missing external
facts. Unknown factual topics still fall through to the conservative unresolved
path instead of being fabricated.

The lightweight status endpoint now reports the descendant version correctly,
so V87.42/V87.43 no longer appear as V87.41 in the browser header.

V87.42 science-capability self-knowledge and V87.41 low-latency behavior remain
underneath V87.43.

V87.42 fixes a conversational self-knowledge failure where questions such as:

```text
科学的な質問に答えられますか？
```

fell through to the generic unknown-answer path. The current FAP now reports
the scientific abilities it actually implements: direct local facts, structured
A-D scientific reasoning, and deterministic physics solvers, while keeping the
boundary that unknown free-form facts are not fabricated.

It also tightens verification: replies that explicitly say they cannot reach a
confirmed answer are now `PARTIAL`, not incorrectly `OK`.

V87.41 low-latency chat behavior remains underneath V87.42.

V87.41 removes the expensive recursive status tree from the hot chat path.
Normal chat responses now return only a lightweight version/state snapshot, and
the web UI uses a lightweight `/api/v1/status`. Full diagnostics remain
available explicitly at `/api/v1/status/full`.

It also treats latency reports such as:

```text
20秒程度応答にかかりました。
```

as conversation feedback instead of falling into the generic unknown-answer
response.

V87.40 direct factual routing is preserved underneath V87.41. For example:

```text
YOU: 真空中の光速度は？
FAP: 真空中の光速度 c は 299,792,458 m/s です。
```

The factual path remains fail-closed: only explicit local entries are answered
directly; unknown facts continue through the existing reasoning / optional-
teacher paths rather than inventing a value.

V87.39 remains the media/geometry foundation underneath V87.40/V87.41.

V87.39 extends the V87.38 native boundary upward from screen-space raster work
into geometry preparation, morphology and skeletal deformation.

New C99 operations:
- camera transform and perspective projection;
- smooth vertex-normal accumulation;
- 32x32 active-tile discovery;
- cat coat / face-pattern evaluation;
- linear blend skinning;
- sparse LBS updates based on changed skin matrices.

The current media execution path is:

```text
V82 SparseRouter
  -> lazy V87.34 / V87.35 / V87.36 organ
  -> V87.39 native geometry preparation
  -> V87.38 native raster/shading/FXAA/filmic
  -> Python PNG + artifact verification
```

Human LBS keeps a persistent mesh/skeleton in the current scene path. On a new
pose, V87.39 compares every bone skin matrix to the previous pose. A vertex is
recomputed only when at least one of its weighted bones changed; unaffected
vertices are copied from the previous result.

Cat coat generation keeps the V87.35 semantics (calico/hachiware/tabbies/
tortoiseshell) but evaluates face centroids and pattern equations in C.

Fallback:
- no V87.39 library -> V87.38 native raster / earlier Python geometry path;
- no V87.38 raster library -> V87.37 sparse Python renderer.

Windows manual build:

```text
BUILD_FAP_V87_39_NATIVE_GEOMETRY.cmd
```

Normal launch:

Windows:

```text
RUN_FAP_CHAT_LATEST.cmd
```

Debian / Linux / Android proot:

```bash
git pull --ff-only
chmod +x RUN_FAP_CHAT_LATEST.sh
./RUN_FAP_CHAT_LATEST.sh
```

The Linux launcher uses Python's standard library for readiness checks, keeps
older FAP instances intact, selects another local port when needed, writes the
background server PID/log under `runtime/`, and prints the exact local chat URL.
It attempts to build the portable V87.38/V87.39 C99 `.so` libraries when a C
compiler is available; if native compilation is unavailable, the preserved
Python fallback remains usable.

If Python 3 is missing on Debian:

```bash
sudo apt update
sudo apt install -y python3 build-essential
```

The Windows launcher attempts to build both V87.38 raster and V87.39 geometry
DLLs when absent.

Compatibility:
- V87.38 Native Raster remains;
- V87.37 Sparse End-to-End remains;
- V87.36 Scientific DNA remains;
- V87.35 Cat Morphology remains;
- V87.34 Scene Graph 2 remains;
- earlier reasoning/physics/chat-speed paths remain;
- Qwen is not used.


Measured CI benchmark (GitHub Ubuntu runner, Python 3.11):
- V87.38 native render median: 0.032831 s;
- V87.39 native-geometry render median: 0.028092 s;
- incremental render speedup: **1.169x**;
- Python LBS median: 0.002458 s;
- native sparse-LBS median: 0.001992 s;
- LBS speedup: **1.234x**.

These are runner-specific measurements and are not guarantees for every
Windows PC or workload.
