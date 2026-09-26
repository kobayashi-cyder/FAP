# FAP V87.18 — Critic Cascade

V87.18 reduces evaluation transitions without weakening acceptance criteria.

Before:
`candidate -> critic A -> critic B -> critic C -> ...`

Now:
`candidate -> cheap critic -> if clearly bad, stop and repair`
`candidate -> cheap critic passes -> expensive critic(s) -> final minimum score`

Rules:
- fatal evidence stops immediately and fails closed;
- an early score below its configured continue floor skips later expensive critics;
- a candidate that survives early stages must still run the full configured stack;
- the final completed score remains the minimum of all evaluated required stages;
- therefore fast rejection becomes cheaper while acceptance remains fully verified.

This composes directly with V87.17:
`best lane first -> observed artifact -> critic cascade -> accept / repair / expand`

The combination attacks two transition costs at once:
1. unnecessary generator/observer lanes;
2. unnecessary expensive critics on obviously bad candidates.

No claim of universal superiority over GPT-5.6 Sol is made without an identical-prompt benchmark.
