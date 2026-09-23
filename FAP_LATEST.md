# FAP V87.80 — Multi-Turn Consistency Fuzz Hardening

V87.80 extends the V87.79 conversation-quality work from single-turn semantic
stability into multi-turn discourse consistency. The runtime remains FAP
standalone; FCA is optional. The repository-coding safety sync derived from FCA
PR #19 is already present in the underlying main baseline, while this release
focuses on conversation continuity.

The randomized multi-turn corpus now checks:
- the newest grounded user topic wins over older topics;
- a newer explicit but unknown subject blocks resurrection of an older known
  topic;
- declaratively configured acknowledgements are transparent and may preserve
  the preceding grounded topic;
- explicit correction structures such as A-not-B prioritize the asserted B side;
- that corrected topic persists into a subsequent subjectless follow-up;
- the same correction focus is used by reflective and inquiry subject parsing.

The corpus exposed two general conversation defects:
1. after a newer unknown subject, a subjectless follow-up could skip backward and
   resurrect an older known topic;
2. in an explicit correction, the rejected side could win semantic matching
   simply because its alias was longer.

The fixes are structural rather than topic-specific:
- recent user turns form discourse boundaries; substantive unknown turns stop
  backward topic search instead of being ignored;
- transparent discourse markers are loaded from declarative knowledge data;
- a shared grammar-level correction boundary focuses semantic matching on the
  asserted replacement clause;
- reflective conversation and inquiry anchoring share that correction focus.

No generated concept, example topic or exact fuzz utterance is added as a
topic-routing exception. Qwen is not used.

# FAP V87.79 — Conversation Quality Fuzz Hardening

V87.79 moves conversation testing from crash resistance to semantic quality.
The quality corpus is generated from the existing concept registry and applies
generic transformations and conversation structures rather than storing
question-specific answers.

The automated properties now check:
- semantic topic stability across width, case, whitespace and separator variants;
- explicit current subjects cannot be replaced by a prior conversation topic;
- genuinely subjectless clarification may resolve from recent context;
- the user's stated topic outranks related concepts mentioned by FAP itself;
- a new explicit topic outranks unrelated history;
- grounded replies stay non-empty, bounded, free of internal exception markers,
  and below a repeated-sentence threshold.

The failing corpus exposed three general quality defects before the final fix:
1. an explicit unknown subject plus clarification wording could borrow the prior
   known topic;
2. follow-up resolution could select a related noun from FAP's previous answer
   instead of the subject stated by the user (for example, a related concept
   mentioned inside an explanation);
3. Unicode/punctuation separators such as full-width slash could destabilize
   semantic matching.

The fixes are structural rather than utterance-specific:
- context inheritance is permitted only when generic request/reference framing
  leaves no substantive current-turn subject;
- recent user turns are searched before assistant turns when resolving a
  subjectless follow-up;
- NFKC/case normalization plus generic separator removal stabilizes concept
  matching;
- context-only clarification is left to the lightweight reflective resolver
  instead of triggering the mass inquiry engine.

No generated utterance or individual concept is added as a routing exception.

# FAP V87.78 — Randomized Conversation Fuzz Hardening

V87.78 hardens ordinary FAP conversation boundaries with a deterministic,
seeded random corpus rather than adding utterance-specific fixes.

The generator derives semantic material from the repository's declarative
knowledge files, then mixes it with randomized Unicode, punctuation, empty and
long input, malformed history containers, invalid or non-finite pressure hints,
and non-finite metadata. The oracle checks generic invariants: routing must not
raise, context stays bounded, dispatch stays well-formed, and exposed structures
remain strict-JSON serializable.

The pre-hardening run exposed **853 errors across 1,024 generated cases**.
After shared-boundary normalization, the expanded suite passes:
- 4 deterministic seeds × 1,024 lower-layer cases on Python 3.11 and 3.12;
- 96 randomized end-to-end chat turns through the actual V87.78 gateway;
- 48 additional randomized multi-turn continuity checks;
- existing Interaction Fabric, Session Continuity, semantic conversation and
  semantic action regressions.

Runtime changes remain generic:
- malformed or missing history is normalized before demand/context accounting;
- pressure hints are converted to finite bounded values at conversation
  boundaries while the lower-level estimator remains strict;
- session metadata rejects non-finite/oversized scalar values before JSON output;
- route-tag containers are normalized defensively;
- no generated utterance is copied into routing or response code.

# FAP V87.77 — Repository Context Precision

V87.77 tightens repository-scale coding while preserving the V87.66-V87.76
interfaces.

Repository reading now distinguishes symbol-focused source windows from a simple
file prefix. If a matching Python symbol is near the end of a large indexed
file, the reader streams to the bounded line window instead of returning an
irrelevant prefix. The configured per-file/total byte budgets still apply.

Planning now separates mutation targets from dependency context:

- explicit existing paths are the only mutation targets when paths are named;
- dependency-hop files remain inspect-only;
- delete requests require an explicit existing path;
- missing explicit modify targets fail closed;
- attempts to create an already-existing explicit path fail closed.

This keeps repository context broad enough for reasoning while narrowing actual
write authority.

# FAP V87.76 — Adaptive Session Continuity

V87.76 generalizes multi-turn continuity across the V87.75 semantic interaction
fabric without introducing a second message store.

FAP already has persistent session messages and long-term semantic memory.
V87.76 reuses those stores and adds two bounded runtime layers:

- `AdaptiveContextSelector` chooses the most recent valid conversation turns
  that fit the current exponential-linear context budget;
- `SessionRouteLedger` remembers only endpoint IDs/state/safe route tags so the
  next endpoint or handoff policy can see recent capability flow without
  duplicating message text.

The selector expands context for structurally heavier requests and larger
conversation histories, but remains bounded by 128 turns, 20k characters per
turn and 250k selected characters. Arbitrary message metadata is not copied into
the active context; only small intent/verdict/ability fields may pass.

Route continuity is in-memory and non-persistent by default. Existing persistent
session messages remain unchanged. FCA is optional.

# FAP V87.75 — Declarative Semantic Fabric Bindings

V87.75 removes the need to add Python route branches whenever a new chat-facing
capability is attached to FAP.

The existing semantic resource/action knowledge now resolves to a route ID, and
`SemanticFabricBridge` binds that route ID to any registered
`InteractionEndpoint`.

Built-in bindings now include:

- image generation and image capability;
- constrained standalone artifact code generation;
- read-only repository inspection.

Repository write coding remains opt-in. A host may mount
`RepositoryCodingInteraction` onto the declarative `repository_coding` route;
the existing worktree, verification and promotion gates remain mandatory.

Code/repository vocabulary is stored in `knowledge/semantic_actions_ja.jsonl`,
not as new routing branches. The existing V87.08 Code Generator now accepts a
bounded per-call repair budget so the V87.73 exponential-linear law can control
its repair depth without breaking legacy callers.

# FAP V87.74 — Bounded Cooperative Interaction Chain

V87.74 extends the V87.73 interaction fabric from single-endpoint selection to
explicit multi-endpoint cooperation.

A trusted host-supplied HandoffPolicy may connect generic capabilities such as:

```text
chat -> reasoning -> repository coding -> verification
```

No concrete chain is hardcoded. The policy returns the next typed
`InteractionRequest` plus an optional endpoint allowlist.

Safety remains bounded:

- the initial exponential-linear budget limits chain depth;
- the runtime hard-caps chains at 12 steps by default;
- endpoints cannot revisit themselves by default;
- every handoff request is checked against the original context budget;
- conversation history has a fixed maximum;
- policy exceptions expose only exception type, not arbitrary provider text;
- ordinary chat does not automatically enter a chain.

FAP remains standalone. FCA is optional.

# FAP V87.73 — Exponential-Linear Interaction Fabric

V87.73 generalizes chat and repository coding behind one provider-neutral
interaction fabric while keeping FAP fully standalone.

The shared capacity law is exponential-linear:

```text
scale(x) = exp(alpha*x)                                  x <= knee
         = exp(alpha*knee) * (1 + alpha*(x-knee))       x > knee
```

The linear branch is the tangent of the exponential at the knee, so value and
first derivative are continuous. Every budget still has a hard cap.

Generic request structure—not subject-specific vocabulary—produces a normalized
demand value from request size, token/diversity structure, line structure,
conversation depth and an explicit pressure hint. That demand expands bounded
routing breadth, context, source bytes, reasoning steps, output size and repair
depth.

The new `InteractionFabric` supports dynamically registered endpoints for chat,
coding or future capabilities. V87.73 mounts the existing V87.64 chat stack as a
low-priority fallback, so FAP still works normally with no external connector.

Repository coding can be mounted through `RepositoryCodingInteraction`. The
same exponential-linear budget controls repository context breadth and bounded
repair depth, while the existing V87.66-V87.72 worktree/verification boundaries
remain unchanged. FCA is optional and is not imported or required.

# FAP V87.64 — Multi-Concept Raster + Honest Quality Gate

V87.64 fixes two problems exposed by the Pixel test:

- multi-subject requests are now composed generically from every matched visual
  concept instead of silently rendering only the first concept;
- the built-in raster fallback is no longer certified as finished general image
  generation merely because it produced a valid PNG.

The local raster path now distinguishes structural success from visual quality.
A normal creative-image request can still return a schematic draft artifact, but
the verifier marks it PARTIAL unless the user explicitly asked for a schematic,
diagram, icon, or similarly simple output.

Visual subjects remain declarative data under `knowledge/visual_concepts_ja.jsonl`.
The renderer contains no subject-specific dog/bird/cat branch.

# FAP V87.63 — Self-Contained Local Raster Image Generation

V87.63 adds a built-in image fallback that works without AUTOMATIC1111, a
network service, Pillow, or other third-party Python packages.

The path is:

```text
semantic image-create intent
→ declarative visual concept lookup
→ generic scene graph
→ pure-stdlib raster renderer
→ PNG structure verification
→ artifact display
```

Visual subject knowledge lives in `knowledge/visual_concepts_ja.jsonl`. The
renderer itself knows only generic primitives such as ellipses, rectangles,
polygons and lines; it has no dog/cat/tree-specific code branch. New lightweight
visual concepts can therefore be added as data.

This backend is intentionally classified as lightweight illustration, not a
photorealistic diffusion model. If an external compatible image model is
available, the existing multi-candidate/inspection path can still use it;
otherwise FAP falls back to its own local raster generator.

V87.63 also exposes semantic-action routes such as image generation as the
displayed ability instead of leaving the UI at `ability: chat`.

# FAP V87.62 — Semantic Action Routing + Canonical Latest Port

V87.62 fixes two generic failure classes observed on Pixel:

1. Resource/action paraphrases such as image + create are now composed from
   declarative semantic-action data instead of relying on one exact verb form.
2. The "latest" Linux launcher now replaces an older repository-local FAP
   gateway occupying the canonical 127.0.0.1:11439 endpoint, rather than
   silently starting the new version on another port while the browser remains
   connected to the stale server.

The semantic action path is:

```text
resource concept
→ action concept
→ declarative route
→ capability organ
→ verifier
```

No subject-specific image branch is used; subjects such as animals or scenery
do not participate in route selection.

# FAP V87.61 — Generic Multi-Turn Recommendation

V87.61 adds a generic recommendation layer that handles open-ended requests and
follow-up constraints without adding question-specific branches.

The recommendation pipeline is:

```text
recommendation action
→ domain/context resolution
→ recent user-turn constraint composition
→ data-driven candidate ranking
→ recommendation verification
```

Concrete vocabulary and candidates live in `knowledge/recommendation_framework_ja.jsonl`.
The Python engine contains no branch for a particular lunch question or allergy
sentence. A constraint-only follow-up is accepted only when recent conversation
history contains a matching recommendation request, so unrelated statements are
not hijacked.

The observed sequence “lunch recommendation → no allergies” is covered by an
end-to-end regression test, alongside preference-based reranking and
out-of-context rejection.

# FAP V87.60 — Current-Turn Relevance Isolation

V87.60 prevents unrelated new questions from borrowing the previous topic simply
because conversation history contains strong local knowledge matches.

The generic rule is now:

```text
current user turn establishes the subject
→ direct local relevance check
→ conversation context may refine that subject
→ context may not introduce a subject that had zero current-turn relevance
→ answer / fail closed
```

This is implemented in the generic inquiry/retrieval path rather than as a list
of blocked words, names, characters, or domains.

Persistent goal handling was tightened at the same layer. A polite one-shot
request is no longer automatically stored as a long-running goal, and failed
ordinary questions are replanned against an old goal only when the current turn
explicitly refers back to that goal.

This prevents two broad failure classes:
- an unknown or unrelated term being answered with material from the previous
  science/math topic;
- an unrelated new question being rewritten into an earlier creation or
  self-description task.

V87.59 semantic conversation routing and all earlier reasoning layers remain
underneath V87.60.

# FAP V87.59 — Semantic Conversation Generalization

V87.59 fixes ordinary-chat paraphrase failures without adding utterance-specific
branches. Semantic conversation intents are stored as data under
`knowledge/conversation_intents_ja.jsonl` and matched compositionally from
subject concepts and action concepts.

For self-description, the response is generated from the currently running
version and capability set instead of replaying the legacy V78 self-introduction.
Equivalent requests such as asking FAP to introduce itself, asking who it is, or
asking what it can do now share the same semantic route.

Greetings also use the semantic conversation route and no longer claim a
specific device such as Pixel from a canned legacy string.

The execution path is:

```text
semantic intent data
→ compositional subject/action match
→ current runtime inspection
→ capability grouping
→ dynamic response
→ verifier
```

V87.58 generic contextual rule reasoning, V87.57 generic symbolic derivation,
V87.56 image orchestration, and earlier fallback paths remain underneath
V87.59.

# FAP V87.58 — Generic Contextual Rule Reasoning

V87.58 removes the next class of exact-answer behavior from ordinary chat.
Short follow-up questions can now resolve their subject from recent
conversation context and answer by recursively chaining declarative rules.

The runtime code does **not** contain a branch for a particular theorem,
polygon, angle sum, or numeric answer. Instead it loads four generic data
types from `knowledge/*.jsonl`:

- semantic entities and aliases;
- semantic relations and aliases;
- reusable constants;
- rules with dependencies and safe arithmetic expressions.

The execution path is:

```text
relation resolve
→ subject resolve from current turn or conversation history
→ recursively satisfy rule dependencies
→ safe AST arithmetic evaluation
→ evidence trace
→ verifier
```

This specifically fixes the observed failure where a derivation about a right
triangle was followed by a short property question and the subject was lost.
The same inference engine and the same rule chain are exercised against more
than one entity in tests; there is no exact question-response lookup in the
Python implementation.

V87.57 generic symbolic derivation, V87.56 image orchestration, and all earlier
fallback paths remain underneath V87.58.

# FAP V87.57 — Generic Verified Derivation

V87.57 adds a generic local derivation lane above V87.56. It is not a
theorem-name router and does not contain a canned branch for the Pythagorean
theorem. Mathematical subject matter is stored as data under
`knowledge/*.jsonl`; the Python engine performs the same retrieval and
verification procedure for every supported derivation record.

The derivation flow is:

```text
generic derivation intent
→ retrieve local derivation record
→ parse equations with a restricted AST
→ normalize both sides to rational-coefficient polynomials
→ prove the target relation is in the algebraic span of the premises
→ independently countercheck that relation with several numeric substitutions
→ render the verified derivation
```

The initial data pack includes area-rearrangement, equation-rearrangement and
multi-premise examples. For example, `三平方の定理を導出して` retrieves the
area construction from `knowledge/math_derivations_ja.jsonl`, expands the
area equality and verifies that its normalized relation is exactly equivalent
to `a^2 + b^2 = c^2`. Unsupported theorems are not fabricated: they fall
through to the existing conservative paths.

New derivations can be added as data records without adding theorem-specific
Python branches. V87.56 image orchestration and all earlier chat, science,
research, media and local fallback paths remain underneath V87.57.

# Historical V87.64 development snapshot

The following section records the V87.64-era baseline. The authoritative current mainline is declared at the top of this file and in `VERSION`.

V87.56 reconnects image generation to the current unified FAP chat and replaces
the old one-shot `txt2img` path with a generate → inspect → repair → select
loop.

The image path now:
- parses the request into an `ImageRequestSpec` containing subjects, count,
  requested style, framing, lighting, background, required terms and negative
  constraints;
- keeps the original natural-language request in the generation prompt so
  unknown concepts are not discarded by the parser;
- generates multiple candidates per round through an AUTOMATIC1111-compatible
  local API configured by `FAP_IMAGE_API`;
- optionally calls `/sdapi/v1/interrogate` with CLIP to inspect the actual
  generated pixels;
- scores requested subjects/style/composition cues against the visual caption;
- explicitly penalizes missing primary subjects such as a requested beagle;
- carries missing requirements into a repair prompt and regenerates;
- selects the best candidate across rounds;
- marks images as visually unverified when the interrogation endpoint is not
  available instead of pretending the semantic check succeeded.

Default control variables are `FAP_IMAGE_CANDIDATES=2`,
`FAP_IMAGE_ROUNDS=2`, `FAP_IMAGE_STEPS=28`,
`FAP_IMAGE_CFG=7.0`, and `FAP_IMAGE_PASS_SCORE=0.80`. Width and height
default to 768×768 and can be overridden with `FAP_IMAGE_WIDTH` and
`FAP_IMAGE_HEIGHT`.

Photorealistic output still depends on the local image checkpoint connected to
the AUTOMATIC1111-compatible API. The FAP-owned V87.29/V87.31 procedural and
scene renderers remain useful for structural rendering, but are not
misrepresented as photorealistic diffusion models.

V87.55 recursive research and the earlier scientific/epistemic layers remain
underneath V87.56.

V87.55 makes the targeted research cycle recursive instead of doing only one
literature pass. Each high-value unresolved topic can now run several refined
search rounds using the unresolved gap type itself to change the query.

Examples of generic refinement dimensions include:
- validation → external validation / independent validation / out-of-sample;
- causality → causal mechanism / intervention / longitudinal / natural experiment;
- robustness → sensitivity analysis / ablation / specification curve;
- uncertainty → uncertainty quantification / confidence / probabilistic evidence;
- scale → multiscale / spatial-temporal resolution / scale transition;
- replication → independent cohort / reproducibility / multi-site replication.

The cycle deduplicates papers by DOI/URL, records per-round new-yield,
tracks whether the relevant appraisal dimension is explicitly addressed, and
stops when either:
- refined searches are saturated (very little new literature), or
- the targeted methodological dimension is already well covered.

This produces explicit stop reasons such as `search-saturated`,
`dimension-well-addressed`, or `round-budget`. The research phase can become
`search-saturated-gap-persists`, `literature-dimension-addressed`,
`literature-signal-found`, `evidence-still-ambiguous`, or
`evidence-sparse`.

The important boundary remains unchanged: repeated literature mentions are not
automatic proof that a hypothesis is true. V87.55 refines where to search and
when to stop searching; it does not auto-promote provisional hypotheses into
verified facts.

V87.54 targeted research cycles, V87.53 research frontier, V87.52 hypothesis
reasoning, V87.51 literature appraisal, V87.50 dated recent science, V87.49
scientific modeling and V87.48 epistemic learning remain underneath V87.55.

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
