# FAP latest development snapshot

Current mainline: **V87.43 — Reflective Local Conversation**.

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
two-concept comparisons and topic follow-ups. Unknown factual topics still fall
through to the conservative unresolved path instead of being fabricated.

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
