# Refine as identities and rule tables: phase 2 results

- **Date:** 2026-09-25
- **Branch:** `refine-identities` at cab778f (GitHub `tilorc-bot/satassume`).
  The package is `satrefine/handlers_identities/`.
- **Read this if:** you want to know what phase 2 did to the table-driven
  refine handlers, what it measured, and what is still open. You do not
  need the step reports. They are in `agent-reports/archive/` if you want
  the detail.
- **Read first:** `2026-09-24-refine-identities-phase-1-results.md` for
  what the package is and how the battery and differential work.
- **TL;DR:**
  - Phase 2 ran five steps: the satassume fix and a new baseline, the
    relation decider and Piecewise definitions, definitions for the plain
    families, staged derivation, and prover gaps plus matrix fuzzing.
    Two changes were added along the way: a `0**e = zoo` row and backend
    routing (issue #7).
  - **Soundness held.** The battery has 0 wrong and 0 crash in both modes.
    Across the six differential runs the identities side has 0 crashes
    (2 at the start) and 0 numerically different results, and its
    unsound counts are unchanged at 2, 3 and 1. v3 gives the same
    rewrite in every one of those cases. Five are artefacts of the check,
    at points where the input has no value. One is a one-point
    difference at `z = 0` caused by SymPy's own `acoth` (section 4.3).
  - **Coverage:** unchanged per family, except that generated mode gains
    2 "same as v3" cases in power_exp_log.
  - **Stated rows:** 192 to 166 (-26). **Derived rules:** 60 to 75.
    **Family code:** 483 to 478 lines. **Engine:** 1,131 to 1,434
    lines (+303).
  - **Speed:** refine over the battery takes 36 s, down from 135 s
    before the routing change. The full gate run takes 376 s. At the
    phase-2 start the suite alone took 1,819 s. The fixpoint that
    regenerates every table takes 303 s.
  - **Rejected:** trig and hyperbolic through definitions (stage 4), and
    combinatorial through `gamma`. Gröbner bases were out of scope.

## 1. What phase 2 set out to do, and what happened

The phase-2 plan (`archive/2026-09-24-refine-identities-phase-2-plan.md`)
had one measure: fewer hand-stated rows and less function-specific Python,
at unchanged coverage and soundness. Every change had to pass the same
gates before it landed:

- battery same plus other form must not drop, per family;
- unchanged-as-required must stay unchanged;
- wrong and crash must stay 0;
- differential seeds 2, 3 and 7 at 1,500 cases must show no new unsound
  or numerically different result;
- the tests must pass.

| Step | Plan | Outcome |
| --- | --- | --- |
| 1.1 | Fix satassume corrupting shared symbol facts | Done (PR #2, on `main`) |
| 1.2, 1.3 | Merge `main`, re-baseline | Done; 4 inverse cases moved to "extra" (section 1.1) |
| 1.4 | Guard against SymPy's Abs-of-imaginary answer; fix the atan2 firing-cap crash | Done (guard in matfuzz; crash fix in step 2) |
| 2 | Relation decider in the engine; minmax_deltas as Piecewise definitions | Done: 13 rows to 8 |
| 3.1 | integer_funcs by definitions | Done: 17 rows to 9; only `frac` pays |
| 3.2 | combinatorial through `gamma` | Measured and rejected; unchanged |
| 3.3 | matrices | Left as is, as planned |
| 4 | Staged derivation, stages 0 to 5 | Manifest, fixpoint and derivation records done; complex_parts 45 to 32 stated rows; range table moved to rows. Stage 4 (trig, hyperbolic) rejected |
| 5 | Prover gaps; matrix fuzzing | Done (PR #3 on `main`; `--matrices` in both fuzz tools) |
| added | `0**e = zoo` row; checker pass; backend routing (#7) | Done |

### 1.1 Step 1: the satassume fix and the baseline

**The defect.** SymPy caches `(0**n).is_finite` as True for a plain `n`.
satassume read a node's cached SymPy facts as unconditional, derived a
contradiction from them, and wrote a derived fact into the fact base that
every symbol created without assumptions shares. After one such `ask`,
`Symbol('fresh').is_negative` was False. So any tool that ran many cases
in one process could report wrong results.

**The fix** (PR #2, merged into `main`). The engine no longer reads or
writes SymPy's `_assumptions`. SymPy objects enter only through their
declared assumptions and the facts of constants. Derived context-free
facts go into an engine-owned cache. The benchmark showed no measurable
cost. The SymPy side (`Pow._eval_is_algebraic` ignores the exponent) is
written up as an upstream issue candidate in
`archive/2026-09-24-satfix-report.md`. It was not filed.

**The baseline** (`archive/2026-09-25-phase-2-baseline.md`). Merging `main`
brought satassume's LRA and EUF relation theories. The merge made one
change to the battery. 4 inverse cases, `acoth(coth(x))` and
`acsch(csch(x))` under `Q.gt(x, 0)` or `Q.ge(x, 1)`, moved from
"unchanged as required" to "extra". They give `x`. That is correct under
the package's convention that a stated bound implies a real argument
(section 4.2). The baseline accepted the move, so the reference became
630 unchanged as required instead of 634. It became 629 after the
prover-gap fix (section 1.5).

**The baseline also found** that results depended on the hash seed. The
engine's candidate order followed hash order, and one battery case,
`log(1/x)` under `Q.zero(x)`, came out differently under different seeds.
Every gate since then runs with `PYTHONHASHSEED=0`, and step 2 made the
case seed-independent.

**The combined-backend guard** (plan 1.4). SymPy calls `Abs(x)` and `x**2`
zero for imaginary `x`, because its `Q.nonzero` means "real and nonzero".
While the combined backend asks SymPy, its `Q.nonzero` handlers for `Abs`,
`Pow` and `Mul` are wrapped. They keep every True and None, and replace a
False with a checked answer. This removed 3 unsound results, 1
numerically different result and 1 crash from the differential, and it
changed no battery case.

### 1.2 Step 2: relation decider, Piecewise, firing cap

- **Decider.** The engine now decides `Piecewise` conditions and relation
  atoms itself (section 3.1).
- **minmax_deltas.** `Min`, `Max`, `KroneckerDelta` and `Heaviside` are now
  5 Piecewise definitions, and the 3 DiracDelta rules stay. That is 13
  rows down to 8, and 45 code lines down to 30. This replaced the
  unmerged `ri/piecewise` experiment.
- **atan2 firing-cap crashes.** They are gone. A per-call result cache
  now does repeated work once.
- **Min/Max speed.** Min/Max-heavy refusals are 4.4 times faster
  (25.8 s to 5.9 s over 23 battery refusals, pinned CPU). The engine now
  asks SymPy's slow `Q.eq` only when the assumptions state a relation.
- **Battery.** One case moved from "other form" to "miss":
  `log(1/x) | Q.zero(x)`. Its `zoo` had come from a case split under
  inconsistent assumptions. The `0**e = zoo` row (f686dcc) restored it
  soundly.

### 1.3 Step 3: definitions for the plain families

- **integer_funcs: 17 rows to 9** (2 identity rows, 7 rules), plus 11
  derived rules.
  - `frac(x) = x - floor(x)` pays. Beyond v3, it gives `frac(x) = x - k`
    on `[k, k + 1)`.
  - One shift row `F(n + x) = F(x) + F(n)` covers every head, with `n` a
    Gaussian integer. It is shared by `floor`, `ceiling` and `frac`.
  - One half-integer row covers both `Mod` and `Rem`.
  - The satassume prover gap from step 5 (the parts of `floor(y)` are
    integers) made 2 more rows unnecessary.
- **Definitions measured and not used:**
  - `ceiling(x) = -floor(-x)`: the generic head already covers it.
  - `Mod(a, b) = a - b*floor(a/b)`: 7 tests fail, and it derives none of
    the rows it would replace.
  - `Rem` by truncation: same obstacles.
- **combinatorial through `gamma`: rejected, measured.** Each of
  factorial, binomial, RisingFactorial and FallingFactorial kept every
  row: 0 rows replaced, and 4 to 9 tests failed without them. There are
  three reasons:
  - the rows' hypotheses are equalities (`n == k`), which the identity
    engine does not substitute;
  - every zero or pole row lies where the gamma ratio is not the
    definition;
  - v3's target forms need the `gamma -> factorial` rows anyway.

  `combinatorial.py` is unchanged.
- **matrices:** unchanged, as the plan said. Matrix fuzzing (step 5)
  found no wrong row.

### 1.4 Step 4: staged derivation

- **The cheap test first.** complex_parts had 27 base rows for `re`, `im`,
  `arg` and `Abs`:
  - 9 never fired, because SymPy rewrites their left side when the node is
    built;
  - 6 now derive from 2 definitions through `sign` (section 3.2);
  - 2 follow from `ask`;
  - 10 stay stated. They are what `Q.real`, `Q.imaginary` and the sign
    facts mean, plus linearity.

  complex_parts went from 45 stated rows to 32. Definitions through
  `conjugate` reproduced all 27 rows, but were rejected: they are unsound
  at infinity, and they lose facts about whole products, because SymPy
  distributes `conjugate(x*y)` on construction.
- **Manifest, fixpoint, records.** These are built (section 3.3). On the
  old tables the fixpoint reproduced all four generated tables exactly.
- **Range rows.** The `_simple.py` range table is now range rows owned by
  the families (section 3.6).
- **Stage 4, trig and hyperbolic through definitions: rejected.**
  - The prototype made `tan`, `cot`, `sec` and `csc` definitions over the
    `sin`/`cos` shift rows. It saved about 6 rows: 12 shift rows became 4
    definitions, plus 2 new rows for base -1. It needed a new top-down
    engine fold of about 20 lines.
  - The cost was 6 to 14 trig battery cases moving from "same" to
    "other form": 208/8 with the rows, 194/22 with the definitions, and
    202/14 with the 2 extra rows. The worse forms look like
    `(-1)**(1/2 - k/2)` and `sec(x)/(-1)**(k/2)`.
  - Hyperbolic through trig would fire where v3 expects unchanged. The
    trig rows fire for any even or odd `n`, while v3's hyperbolic rows
    need `m mod 4`. The gate forbids that.
  - The coordinator rejected stage 4. Trig and hyperbolic keep their
    stated rows.
- **Stage 5 (inverse)** is in the manifest and regenerated by the
  fixpoint. Its rows did not change.

The plan was uncertain about the row count, and the result confirms it.
Derivation proper removed few rows: 6 of complex_parts' 27. Deleting dead
and redundant rows removed more. Most of the value is in auditability:
every derived rule carries its derivation, and one fixpoint check replaces
per-family staleness checks.

### 1.5 Step 5: prover gaps and matrix fuzzing

- **Prover gaps** (PR #3, on `main`, general template rules):
  - `ask` now shows that `(n - 1)/2` is an integer for odd `n`. This
    covers sums with coefficients of denominator 2.
  - `ask` also shows that `re(floor(y))` and `im(floor(y))` are integers
    for finite `y`.
  - The corpus replay shows 0 wrong and 10 new correct answers, with no
    slowdown.
  - On the refine side, `log(x**n)` for negative `x` and odd `n` now gets
    v3's form `n*log(-x) + I*pi`.
  - `exp(I*pi*n/2)` now folds for odd `n`. v3's test expects it
    unchanged, so the case moved from "unchanged as required" to "extra".
    The result is correct, since `I**n = I*(-1)**((n - 1)/2)`.
- **Matrix fuzzing.** `refine_fuzz.py --matrices` and
  `refine_differential.py --matrices` generate matrix expressions. They
  evaluate them on explicit exact sample matrices that satisfy each
  assigned predicate.
  - Over 5,849 matrix cases in 3 seeds, all 30 matrix rows fired and were
    checked numerically. None was wrong.
  - The one wrong matrix result came from SymPy's `ask` (`c**2*X -> 0`
    for imaginary `c`). The guard in section 1.1 fixes it.
  - Both fuzz tools now print how many fired cases they could not check.

### 1.6 Added during the phase

- **`0**e = zoo`**: one power_exp_log row (section 3.7).
- **Checker 2**, an adversarial pass over steps 2 and 3 and the `0**e`
  row. It tried about 350 hand-written cases, about 600 raw `ask`
  probes, two scratch-fuzzer seeds
  (1,100 cases) and differential seeds 11 and 13. It found 0 wrong
  results. It filed two needs tests, and step 4 fixed both:
  - a firing-cap crash on wide inputs, fixed by the cap per chain
    (section 3.4);
  - `Eq(oo, oo)` staying undecided, fixed by a same-infinity proof form
    for `eq`, which needed `unless` on identity rows (section 3.5).
- **Backend routing** (issue #7): section 3.8.

All needs tests filed during the phase are fixed.
`tests/refine_identities/needs/` is empty and has been removed.

## 2. Before and after

"Before" is the shared gate baseline `base-8f0e147`, the state when the
phase-2 gates began. It already contains steps 1 and 5 and the matrix
fuzzing, merged earlier. "After" is `routing-78e6325`, whose code is
identical to the head cab778f. Both summaries are under
`/home/tilo/fable-rewrite/.claude/gates/<name>/summary.txt`. All numbers
use `PYTHONHASHSEED=0`.

### 2.1 Battery scoreboard (1,736 cases)

Columns: same as v3 / other correct form / miss / unchanged as required /
extra (fired where v3 expects unchanged) / wrong / crash.

| Family | generated, before | generated, after | live, before | live, after |
| --- | --- | --- | --- | --- |
| combinatorial | 64/0/3/40/0/0/0 | same | 64/0/3/40/0/0/0 | same |
| complex_parts | 150/8/4/79/1/0/0 | same | 151/7/4/79/1/0/0 | same |
| hyperbolic | 196/30/0/142/0/0/0 | same | 196/30/0/142/0/0/0 | same |
| integer_funcs | 67/0/0/31/0/0/0 | same | 67/0/0/31/0/0/0 | same |
| inverse | 124/2/0/160/16/0/0 | same | 124/2/0/160/16/0/0 | same |
| matrices | 50/0/3/53/0/0/0 | same | 50/0/3/53/0/0/0 | same |
| minmax_deltas | 65/0/0/23/0/0/0 | same | 65/0/0/23/0/0/0 | same |
| power_exp_log | 98/3/3/65/4/0/0 | **100/1/3/65/4/0/0** | 100/1/3/65/4/0/0 | same |
| trig | 216/0/0/36/0/0/0 | same | 216/0/0/36/0/0/0 | same |
| **total** | 1,030/43/13/629/21/0/0 | **1,032/41/13/629/21/0/0** | 1,033/40/13/629/21/0/0 | same |

- The generated-mode gain is `log` of an odd power of a negative base. It
  now gets v3's `n*log(-x) + I*pi` in generated mode too. The prover gap
  fix gave the clean form. The fixpoint's shared table order then put the
  bare `log(x)` row after the power rows.
- In both runs, 193 cases are numerically unchecked: matrix symbols, no
  satisfying sample, or the sampler raised.
- Against phase 1 (2fd72b8, generated 1,030/43/13/634/16/0/0), 5 cases
  moved from "unchanged as required" to "extra" before the base run. They
  are the 4 inverse cases from section 1.1 and `exp(I*pi*n/2)` from
  section 1.5. All 5 are correct.

### 2.2 Differential against v3 (1,500 cases per seed)

Identities side (b):

| Mode, seed | fired | unsound | numerically different | crash | timeout |
| --- | --- | --- | --- | --- | --- |
| generated 2 | 482 -> 484 | 2 -> 2 | 0 -> 0 | 0 -> 0 | 2 -> 0 |
| generated 3 | 484 -> 486 | 3 -> 3 | 0 -> 0 | 0 -> 0 | 2 -> 0 |
| generated 7 | 456 -> 456 | 1 -> 1 | 0 -> 0 | 0 -> 0 | 0 -> 0 |
| live 2 | 480 -> 483 | 2 -> 2 | 0 -> 0 | 0 -> 0 | 1 -> 0 |
| live 3 | 483 -> 486 | 3 -> 3 | 0 -> 0 | **1 -> 0** | 0 -> 0 |
| live 7 | 455 -> 456 | 1 -> 1 | 0 -> 0 | **1 -> 0** | 1 -> 0 |

- The two crashes at the start were the atan2 firing cap.
- On the v3 side (a), unsound stays 2, 3, 1 and crash stays 0. Its 3
  timeouts at the start (1 in generated seed 2, 2 in live seed 2) are
  gone.
- Timeouts reflect machine load as much as code. The before-run shared
  the machine with other gate runs.
- "Only v3 fires" fell from 4, 3, 5 (generated) and 5, 4, 6 (live) to 2, 3,
  3 and 3, 3, 3.

### 2.3 Test suite (`tests/refine_identities`)

| | passed | failed | skipped | xfailed | time |
| --- | --- | --- | --- | --- | --- |
| before | 2,306 | 6 (all needs tests) | 1,917 | 30 | 1,819 s |
| after | 2,382 | 0 | 1,917 | 30 | 374 s |

### 2.4 Rows and code

"Stated" is the scoreboard's `stage0` column: every hand-stated table
counted once, in the family that owns it, including splits and ranges.
The base summary does not print this column or the line counts. I counted
them on an export of 8f0e147 with the current
`tools/refine_identity_scoreboard.py --lines`. Two adjustments make the
base number comparable with the head:

- the tool at the head counts complex_parts' imported `EXP_FORMS` a second
  time (3 rows), so I subtracted 3;
- I added the 5 entries of the old `_simple.BOUNDS` range table, which
  are range rows now.

This method reproduces the stages report's 180 at f686dcc.

| Family | stated, before | stated, after | derived, before | derived, after | code lines, before | code lines, after |
| --- | --- | --- | --- | --- | --- | --- |
| combinatorial | 16 | 16 | 0 | 0 | 51 | 51 |
| complex_parts | 45 | 32 | 36 | 40 | 91 | 88 |
| hyperbolic | 12 | 12 | 0 | 0 | 29 | 29 |
| integer_funcs | 17 | 9 | 0 | 11 | 49 | 52 |
| inverse | 13 | 17 (4 of them range rows) | 7 | 7 | 49 | 57 |
| matrices | 30 | 30 | 0 | 0 | 75 | 75 |
| minmax_deltas | 13 | 8 | 0 | 0 | 45 | 31 |
| power_exp_log | 27 | 28 | 17 | 17 | 59 | 60 |
| trig | 14 | 14 | 0 | 0 | 35 | 35 |
| engine range table | 5 | 0 | | | | |
| **total** | **192** | **166** | **60** | **75** | **483** | **478** |

| Engine module | before | after |
| --- | --- | --- |
| `_dispatch` | 125 | 211 |
| `_engine` | 546 | 623 |
| `_simple` | 207 | 206 |
| `_specialize` | 198 | 214 |
| `_stages` | | 125 |
| `_tables`, `_wraps` | 41, 14 | 41, 14 |
| **total** | **1,131** | **1,434** |

Engine plus families: 1,614 before, 1,912 after. The engine grew by:

- about 50 lines for the decider;
- about 45 for the result cache and iterative chains;
- 125 for the stage manifest, fixpoint and derivation records;
- some for the range rows, `unless` on identity rows and the per-chain
  cap.

The lines in the engine that name a specific function fell from about 27
to about 14 (a count by hand in the stages report).

### 2.5 Speed

These numbers come from different runs, and they are labelled by source.
No summary measures refine time over the battery, so those rows come from
the step reports.

| | before | after | source |
| --- | --- | --- | --- |
| refine over the 1,736 battery cases, one process | 135 s, of which 112 s in the SymPy fallback (`union` backend, the old `combined`) | 36 s, of which about 13 s in SymPy | routing report |
| the same at 8f0e147, instrumented | 219 s, of which 179 s in the SymPy fallback | | issue #7 |
| full gate run | 1,191 s at stages-3865d76, `JOBS=9` | 376 s at routing-78e6325, `JOBS=9` | gate summaries |
| gate suite | 1,819 s at base-8f0e147 (`JOBS=6`) | 374 s | gate summaries |
| differential, identities worker per run | 678 to 1,265 s at base-8f0e147 | 86 to 136 s | gate summaries |
| fixpoint (`refine_specialize.py --write`, all tables) | 1,461 s first run; 1,117 s at 3865d76 | 303 s | stages and routing reports |
| Min/Max-heavy refusals (23 cases, pinned) | 25.8 s | 5.9 s | engine step 2 report |

- The base-8f0e147 gate run has no usable total. It stopped on a script
  error and was resumed, and its "847 s" header covers only the resumed
  part.
- Before the fixpoint existed, one generation round over the four
  generated families took about 15 minutes (218 + 315 + 27 + 318 s).
- The routing report's side-by-side suite runs (292 s and 294 s) show that
  the suite itself did not get faster. Most of the gate suite's drop comes
  from less competing load in the gate run.

## 3. What changed in the design

### 3.1 Relation decider

`_engine.decide(cond, a)` decides `Piecewise` conditions and relation
atoms (`Q.ge`/`gt`/`le`/`lt`/`eq`/`ne` and relationals like `x >= y`)
through an order vocabulary:

- A relation holds by a sign form or an infinite-endpoint form. For
  example, `Q.ge(a, b)` holds when `a` is nonnegative and `b` is
  nonpositive.
- Failing that, it holds by a relation form (`Q.le`, `Q.lt`, `Q.zero(u - v)`,
  ...), but only when no argument is known infinite. This is the `-oo`
  guard: SymPy's `ask` wrongly proves `Q.eq(i, j)` for `i = -oo`.
- It is refuted when its negation holds.
- `Q.eq`/`Q.ne` are asked of the backend only when the assumptions state
  a relation, because SymPy's `Q.eq` costs about 0.6 s per query.

Tables write plain `Q.ge(a, b)` conditions, with no special node. The
dispatcher hands a `Piecewise`'s arguments to the engine, so every table
and every user input gets the decider. Rule hypotheses keep their meaning;
they do not go through the order vocabulary.

### 3.2 Piecewise definitions

A definition is an identity row whose right side is a `Piecewise`:

```
(Max(a, b), Piecewise((a, Q.ge(a, b)), (b, Q.lt(a, b)), (nan, True)), true)
```

The row fires when the decider picks a branch. A candidate that still
contains an undecided `Piecewise` the input did not have is declined
without a case split. A table can switch case splits off (`splits=False`)
and can opt out of generation (`SPECIALIZE = False`).

complex_parts uses the same idea without a `Piecewise`:

```
(Abs(z), z/sign(z),       ~Q.zero(z) & Q.finite(z))
(arg(z), -I*log(sign(z)), ~Q.zero(z))
```

With the stated `sign` rows, these derive `Abs` and `arg` of positive,
negative and imaginary arguments.

### 3.3 Stages, fixpoint and derivation records

- **The manifest.** `_stages.STAGES` lists the stages:
  - stage 1: integer_funcs and complex_parts;
  - stage 2: power_exp_log;
  - stage 4: trig and hyperbolic, which have no generated tables;
  - stage 5: inverse.
- **The fixpoint.** `tools/refine_specialize.py --write` runs the families
  in stage order. Each family is specialized against the tables generated
  so far, and its verified rules are installed before the next family
  runs. A round regenerates a family only if a table it looked up has
  changed. The loop stops when a round changes nothing, and it fails
  after 5 rounds, naming the families still changing. Today it converges
  in 2 rounds.
- **The check.** `test_generated.py` checks the fixpoint property for each
  family.
- **Derivation records.** Every generated rule carries a comment with the
  round, the source identity row and profile, the rows that fired
  (`complex_parts.RULES[6]`, or `family.generated[i]` for another
  family's table) and the `ask` queries answered True. Two uses:
  - tracing a rule that fails verification back to its cause;
  - knowing what to rederive when a stated row changes.

### 3.4 Firing cap per chain

Phase 1 capped firings per top-level `refine` call at 500. A wide input
with many independent rewrites hit that cap and crashed, for example
`Add(*[Abs(x + k) for k in range(1, 502)])` under `Q.positive(x)`. v3
handles that input.

- `MAX_FIRINGS = 500` now bounds one rewrite chain: a node rewritten, the
  result rewritten again, and so on.
- A backstop of 100 times that bounds the whole call.
- Case splits get their own counter.

So the cap detects loops, not the width of the input.

### 3.5 `unless` on identity rows

Rule rows already had an optional `unless`: a condition that blocks the
row when it is provable. Identity rows can now take one too, as a fourth
element. The KroneckerDelta definition needs it:

```
(G(i, j), Piecewise((1, Q.eq(i, j)), (0, Q.ne(i, j)), (nan, True)), true,
 Q.infinite(i) & Q.infinite(j))      # unless: KroneckerDelta(oo, oo) is undefined
```

This let `eq` gain a same-infinity proof form (`Eq(oo, oo)` is True)
without making `KroneckerDelta(oo, oo)` evaluate to 1. Code that unpacks
family rows as `lhs, rhs, dom` must now slice `row[:3]`.

### 3.6 Range rows

The engine's floor/ceiling interval reasoning needs the range of bounded
functions. That knowledge used to be a dict in `_simple.py`
(`BOUNDS`, 5 entries plus a special case for `arg`). It is now rows
`(head(y), interval, condition)`, stated by the owning family and
registered with `register_ranges`:

```
(atan(y), Interval.open(-pi/2, pi/2), Q.real(y))     # inverse.RANGES
```

complex_parts states 2 rows for `arg`: open at `pi` off the negative axis,
and `(-pi, pi]` otherwise. inverse states 4 rows, for `atan`, `acot`,
`asin` and `acos`. `_simple._range` reads the first row whose condition is
provable.

### 3.7 The `0**e` row

```
(b**e, zoo, Q.zero(b) & Q.negative(e))    # power_exp_log: 1/x at x = 0
```

It fires only for a zero base and a negative (real, finite) exponent. It
does not fire for extended-negative, `-oo`, nonpositive or imaginary
exponents. The checker verified it downstream through `log`, `Abs`, `sin`,
`exp` and sums and products of poles. It restores `log(1/x)` under
`Q.zero(x)` soundly. Before, that case's `zoo` had come from reasoning
under inconsistent assumptions.

### 3.8 Backend routing

The default `combined` backend used to ask SymPy whenever satassume said
None. SymPy answered about 10% of those queries and took 82% of refine's
time (issue #7). Now satassume's answer stands, and `backend.route` sends
a query to SymPy only for these reasons:

| reason | when |
| --- | --- |
| `matrix`, `custom`, `other`, `relation` | satassume cannot translate the query (matrix predicates or arguments, unregistered custom predicates, malformed relations) |
| `no-theory` | a relation bound no theory interprets: `pi/2`, a float, `oo`, `AccumBounds` |
| `inconsistent` | satassume finds the assumptions inconsistent; SymPy decides whether to raise |
| `error` | satassume raises; the result is None, not a crash |

- The `Q.nonzero` guard applies to every SymPy call.
- The old behaviour is kept as backend `union`.
- The battery is identical under the new routing.
- The differential loses 1 to 3 rewrites per run. Most of them rested on
  SymPy answers that do not hold, for example `Q.lt(n, 1/sqrt(k))` True
  where one side is imaginary. The rest are satassume gaps, listed in
  section 4.1.

## 4. Open items

### 4.1 satassume side of issue #7

The refine side is done (cab778f). The coordinator's latest comment on
tilorc-bot/satassume#7 lists what is left for satassume, in order of
value:

1. A relation that no theory interprets (`pi/2`, float, `oo`,
   `AccumBounds` bounds) should become an opaque atom, instead of dropping
   the whole query. This is the only relation-related fallback to SymPy
   left, and on the battery it is the only case where satassume alone
   loses a rewrite: `sqrt(asin(sin(x))**2)` under
   `Q.nonnegative(x) & Q.le(x, pi/2)`.
2. `Q.integer(1/(m + 1))` under `Q.zero(m)`, for example by substituting
   the zero symbol.
3. `Q.eq`/`Q.ne` between a real and an imaginary term, through
   `Q.zero(x - z)`. This would also close the refine-side miss
   `KroneckerDelta(x, z)` for positive `x` and imaginary `z`, which v3
   handles.
4. Do not match SymPy's `Q.lt` on non-real terms, or its `Q.real(1/sqrt(x))`
   under `Q.nonnegative(x)`. Both are wrong.

The cross-call cache and the session reuse for case splits (the issue's
item 5) matter less now.

### 4.2 Does a stated bound imply a real argument? (user decision, pending)

v3 and this engine read `Q.gt(x, 1)` as implying that `x` is real. For
example, `refine(im(x), Q.gt(x, 0))` gives `0`. SymPy's `ask` does not
make that inference, and neither does satassume:
`ask(Q.positive(x), Q.gt(x, 1))` is None for a plain `x`, which is correct
by SymPy's definitions.

- **Current state:** the engine keeps v3's convention.
- **Visible effects:**
  - the 4 inverse "extra" cases (`acoth(coth(x))` and `acsch(csch(x))` to
    `x`, section 1.1);
  - the checker's note that `Q.lt(x, 0)` excludes `x = -oo` in
    `atan2`'s rows.
- **To switch to SymPy's reading:** add row conditions (for the inverse
  cases, in `inverse.py`), then re-run the gates. The results that rest
  on the convention would then stay unchanged, as v3's tests expect for
  those 4 cases.

The user has not decided yet.

### 4.3 The remaining unsound differential cases

The identities side has 2, 3 and 1 unsound results at seeds 2, 3 and 7.
The counts are the same in both modes and at every gate in the phase, and
v3 gives the same rewrite in every case. I re-ran the three seeds at the
head (generated mode) with the cases listed:

| Seed | Case (identities and v3 give the same rewrite) | Point | Input | Rewrite | Verdict |
| --- | --- | --- | --- | --- | --- |
| 2 | `-im(x)/(re(x)**2 + im(x)**2) -> 0` under `Q.real(x)` | x = 0 | nan (0/0) | 0 | input undefined: removable singularity |
| 2 | the same under `Q.nonnegative(z)` | z = 0 | nan | 0 | same |
| 3 | the same under `Q.even(y)` | y = 0 | nan | 0 | same |
| 3 | `acoth(conjugate(x)) -> acoth(x)` under `Q.negative(x)` | x = -1 | -oo | -oo | equal values; the check counts `-inf == -inf` as a mismatch |
| 3 | `acoth(sqrt(z**2)) -> -acoth(z)` under `Q.nonpositive(z)` | z = 0 | `I*pi/2` | `-I*pi/2` | a real one-point difference, below the tables (see below) |
| 7 | `binomial(m**3, z - 1) -> 0` under `Q.odd(z) & Q.negative(z) & ...` | m = -2, z = -5 | oo (pole) | 0 | input undefined: pole |

Five of the six are artefacts of the check. At the counterexample point
the input has no value (`nan` or a pole), or both sides are `-oo` and the
comparison counts that as a mismatch. The summary's "input finite at the
point" count (0, 2, 0) includes the `-oo` case and the `acoth` case below.

The sixth is a real difference at a single point. The refine step
`sqrt(z**2) -> -z` is correct for nonpositive `z`. SymPy then builds
`acoth(-z)` as `-acoth(z)`, and on SymPy's own convention that does not
hold at `z = 0`, where `acoth(0)` is `I*pi/2`. At `z = -1/2` and
`z = -1/10` the two sides agree. v3 gives the same rewrite, and this case
has been in every baseline since phase 1. Fixing it means SymPy's `acoth`
not extracting the sign at 0, which is outside this package.

The checker's report (`archive/2026-09-25-checker2-report.md`) calls the
unsound results it saw "spurious": every one was shared with v3, and was
either `-inf == -inf` counted as a mismatch or a `nan` input. But the
checker ran differential seeds 11 and 13 and `refine_fuzz` seed 5, not the
gate seeds. For the gate seeds, the "comparison artefact" description
fits five of the six. It does not fit the `acoth(sqrt(z**2))` case.

### 4.4 Not done, from the step reports

- **Stage 4** (trig and hyperbolic through definitions): rejected,
  section 1.4.
- **combinatorial:** unchanged, section 1.3.
- **Gröbner bases:** out of scope, per the user.
- **integer_funcs:**
  - `Mod(a, b) -> b/2` for odd `2*a/b` no longer fires when the signs of
    both `a` and `b` are unknown. The engine does not nest case splits.
    The battery and v3's tests do not have this case.
  - `floor(x) + frac(x)` is not rewritten to `x`. That would need a rule
    over sums (an `Add` handler).
  - The ablation was not re-run after the Gaussian-integer merge removed
    2 more rules.
- **Misses v3 also has** (checker 2): transitivity of relations
  (`Min(x, y, z)` under `x <= y <= z` gives `Min(x, z)`), and
  `Max(x, y, z)` with an infinite `z` but no realness fact on `x` and `y`.
  Also:
  - `KroneckerDelta(i, j, (1, 3))` checks only `i` against the range;
  - `frac(x)` on `[n, n+1)` for a symbolic `n`;
  - `Heaviside(x, 1)` under `Q.extended_nonnegative(x)`;
  - `atan2(y, x)` for `x = +oo`;
  - a `Piecewise` branch is not refined from its own relational
    condition;
  - `x**(-y)` under `Q.zero(x) & Q.negative(y)`.
- **Matrices:**
  - 5 coverage gaps against v3, all misses and not wrong answers:
    - `c*X -> 0` for a zero `X`;
    - `X*Y.T*Y -> 0`;
    - `HadamardProduct(0, -X)`;
    - `(X*Y)**-1` and `(-X)**-1` for orthogonal factors.
  - The battery's numeric check still skips matrix symbols. The fuzzer's
    sample matrices (`refine_fuzz.mat_points`) could be reused there.
- **Numerically unchecked cases:** 13% of the differential's fired cases
  (52 to 68 per run), and 193 battery cases. Most have assumption sets no
  sample satisfies, or inputs undefined at every point.
- **Upstream SymPy candidates, not filed:**
  - `(0**n).is_finite` is True for a plain `n`;
  - the `Q.nonzero` handler class, now guarded here;
  - four single-point `ask` errors at 0 or at a pole, listed in the
    matfuzz report.
- **Prover gaps:** denominators above 2 (`(n - 1)/4`) need residue
  predicates that satassume's vocabulary lacks.
- **Speed:** generation did not get faster from installing earlier
  stages' tables, because the live fallback runs whenever a table
  declines. Routing is what made the fixpoint fast (303 s).
- **Plan open question:** whether `handlers_identities` should become the
  default `SATREFINE_HANDLERS`. It has not been decided; `handlers` is
  still the default.
- **Cleanup (plan step 6):** delete the merged `ri/*` branches and their
  worktrees. That is for the coordinator. `ri/piecewise` is superseded by
  `ri/engine2`.

## 5. Running the agents

The process lessons from phase 1 are in
`2026-09-24-read-before-running-agents-how-work-gets-lost.md`. Phase 2
followed them: one worktree per agent, commits before long runs, requests
as failing needs tests, and liveness judged from branches. What phase 2
added:

- **Hash seed.** Results depended on `PYTHONHASHSEED`, which made
  before/after comparisons noisy until every run pinned it to 0.
- **One gate script and a shared baseline.** `tools/refine_gates.sh` runs
  every gate in parallel, compares against a baseline the coordinator
  produced once, and prints only a summary and the changed lines. Agents
  stopped re-running old code for comparison. The baseline run itself
  failed halfway on a script error and was resumed, so its wall time is
  not usable.
- **Cost.** Idle waits longer than about 5 minutes expire the prompt cache,
  and each one rewrites the agent's whole context. Measured: 92% of cache
  writes were such rewrites. Agents now keep every tool call under about
  4 minutes and wait for detached runs in short foreground chunks.
- **Context size.** The stages agent was handed off mid-step because of
  context size. The handoff note it wrote (now folded into the stages
  report) was enough for a fresh agent to finish the fixpoint rerun, the
  gates and the metrics without repeating work.
- **Load.** Timeouts in the differential tracked machine load, not code.
  Compare crash and unsound counts across runs, not timeouts.

## 6. Where things are

- Step reports: `agent-reports/archive/`, 2026-09-24 and 2026-09-25:
  - the plan: `2026-09-24-refine-identities-phase-2-plan.md`;
  - the baseline: `2026-09-25-phase-2-baseline.md`;
  - the step reports:
    - `2026-09-24-satfix-report.md`
    - `2026-09-25-matfuzz-report.md`
    - `2026-09-25-prover-gaps-report.md`
    - `2026-09-25-engine-step2-report.md`
    - `2026-09-24-defs-step3-report.md`
    - `2026-09-25-checker2-report.md`
    - `2026-09-25-stages-report.md`
    - `2026-09-25-routing-report.md`
- Gate runs: `/home/tilo/fable-rewrite/.claude/gates/`:
  - `base-8f0e147`
  - `engine2-1610aeb`
  - `int-f686dcc`
  - `stages-b44342b`
  - `stages-3865d76`
  - `routing-78e6325`
- Issue: tilorc-bot/satassume#7 (open, satassume side).
