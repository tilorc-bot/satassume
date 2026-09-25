# Agent report: phase 3, fuzz extension (track B follow-up)

- **Date:** 2026-09-25
- **Branch:** `ri/fuzz-ext` (from `eb106a6`), worktree `.claude/worktrees/ri-fuzz-ext`. Merged `origin/refine-identities` (A4, `b01b7a9`) at `adf44a2`; report commit on top.
- **Files:** `tools/refine_fuzz.py`, `tools/refine_differential.py`, `tools/refine_gates.sh`, `tests/refine_identities/test_fuzz_ext.py` (new), two needs tests. No engine file touched.
- **Status:** done. One real refine bug and one refine crash filed as needs tests. Three SymPy `ask` bugs reach refine through the combined backend. One checker artefact fixed.

## 1. What the fuzzers now generate

**Design choice: a separate case stream.**
- The new generation is a family of its own, `--ext`, seeded with the string `"ext-SEED-CASE"`.
- The default scalar stream (`refine_differential.generate`, `OUTER`, `COMBOS`, `PREDS`) and the matrix stream are byte-for-byte unchanged.
- `test_default_scalar_and_matrix_streams_unchanged` pins a digest of seeds 2, 3, 7 (every 7th case to 1,500) and of matrix seed 2.
- So the gates' existing sections (differential seeds 2, 3, 7 at 1,500 cases, satassume seed 2) still compare 1:1 with any older baseline.
- The new family and the matrices run as new gate sections.

**`refine_fuzz.py --ext` / `refine_differential.py --ext`:**
- **Predicates:** `finite`, `infinite`, `extended_real`, `extended_positive`/`negative`/`nonnegative`/`nonpositive`/`nonzero`, alone and in combinations (`infinite & extended_positive`, `finite & extended_real`, ...), next to the old ones (`EXT_PREDS`, `EXT_COMBOS`).
- **Relations:**
  - 0, 1 or 2 per case (two-sided bounds). The bounds include `oo` and `-oo`: `Q.ge(x, oo)`, `Q.lt(x, oo)`, `Q.le(x, -oo)`, `Q.gt(x, 1)`, `Q.eq`/`Q.ne`, and between symbols.
  - Half the time a symbol in a relation has no other fact. This is the B1–B7 shape, `Q.gt(x, 1)` alone.
- **New heads:**
  - `Piecewise` with Lt/Le/Gt/Ge/Eq/Ne conditions (bounds at ±oo, affine sides such as `3*k + 1`, And/Or), wrapped around an inner expression or around any old head (`Piecewise_outer`);
  - `KroneckerDelta` of affine arguments;
  - `acot`, and the pairs `acot(cot)`, `acoth(coth)`, `asech(sech)`, `acsch(csch)`.
  - 40% of the cases use a new head; the rest use the old heads under the new facts.
- **Sample points:**
  - A symbol takes `oo`, `-oo`, `zoo`, `oo*I`, `-oo*I` when its predicates allow them and it has a fact or occurs in a relation. A relation makes it extended real, so only ±oo pass there.
  - A symbol with no fact at all is sampled finite, as in the default family.
  - Edge points: 0, ±1, ±I, the branch-cut pre-images of the default differential, the relation's finite bounds, and the infinities.
  - Relations at infinite values are decided with SymPy's `Gt`/`Ge`/`Lt`/`Le`/`Eq`/`Ne`; at finite ones, numerically.
  - Equations (`Q.eq`) are made to hold on purpose, so they get checked.
  - Finite samples are 40-digit Floats (see artefact A1 below).
- **Values** (`ext_value`):
  - a finite complex; `("inf", direction)` for a signed or directed infinity; `zoo`; `nan` (nan or an AccumBounds: no value); or unevaluable.
  - `KroneckerDelta(oo, oo)`, which SymPy leaves unevaluated, is decided by `Eq`, so B3 is checkable.
  - A Piecewise is evaluated branch by branch. SymPy's Piecewise collapse recursed forever on `Ne(2, z**2)` with a complex Float `z` and hung a worker.
- **Classified, not reported:** every skipped or excused point is counted (section 5 of the "how work gets lost" report).
  - A point where the input has no value is counted as `input undefined`; one where a side cannot be evaluated, as `unevaluable`.
  - A mismatch that SymPy's conventions explain is counted per label and not reported:
    - `zoo vs signed infinity (1/0 = zoo)` and `(log(0) = zoo)`. Only when an exact 1/0 or log(0) produced the zoo: zoo from a function's own pole, like `acsch(0)`, is still reported. B6 would otherwise be excused.
    - `log of a non-positive infinity` (`log(-oo) = oo`).
    - `atan2 of two infinities`.
  - Every other mismatch is a counterexample, with a kind: `finite point`, `infinite point`, or `undefined output` (the input has a value, the output is nan).
- **Differential output:** per package, the unsound count by kind, the number of cases checked at an infinite point, point counts (checked at an infinity / input undefined / unevaluable), and cases with a convention-excused point per label.

**Other tool changes:**
- `refine_differential`:
  - `_load` knows `ExprCondPair` and `AccumulationBounds`; a result it cannot rebuild is an "undecided" verdict instead of a crash of the parent. That crash lost the first 35-minute batch.
  - `--keep DIR` keeps the workers' JSON.
  - In `--ext` mode, the worker's timeout is never swallowed by the checker (`refine_fuzz.NO_SWALLOW`).
  - The "input finite at the point" count treats zoo/oo inputs as non-finite.
- **`refine_gates.sh`:** new sections, both modes:
  - `differential ext $m seed 2, 1000 cases` (`--ext --timeout 20`; `EXT_CASES`);
  - `differential matrices $m seed 2, 1500 cases` (`--matrices`; `MAT_CASES`).
  - A baseline without these sections prints "no baseline" for them (the per-section compare already does this).

**Tests** (`tests/refine_identities/test_fuzz_ext.py`, 52 tests, 5 s):
- all of B1–B7 (issue #10) are found at ±oo from generic facts, without pointing the checker at the point;
- rewrites that are right at ±oo pass and count infinite points;
- each convention label is counted, not reported;
- undefined inputs are skipped and counted;
- every `EXT_COMBOS` sample satisfies its predicates;
- the infinity classification and relations at infinity;
- the ext stream is deterministic and generates every new head;
- the default streams' digests;
- the 40-digit sample case.

## 2. Extended run

Seeds 21–24, 2,000 cases each, `handlers_v3` against `handlers_identities`, for each of: combined/satassume backend × generated/live mode (16 runs, 8 at a time).
- Logs and worker JSON: `.claude/gates/fuzz-ext-runs-542eb04/` (`agg.py` there makes the totals).
- Code: `542eb04` (before the 40-digit fix).
- Of the 8,000 generated cases, 6,776 were compared. The rest were dropped by the generator: no satisfying point found, or an expression without symbols.

Identities (b side), totals over the 4 seeds:

| | combined gen | combined live | satassume gen | satassume live |
|---|---|---|---|---|
| fired | 1,106 | 1,098 | 961 | 955 |
| checked (≥ 1 point) | 1,031 | 1,023 | 899 | 893 |
| **unchecked** (fired, no point checked) | 68 | 68 | 57 | 57 |
| cases checked at an infinite point | 407 | 400 | 334 | 329 |
| points checked at an infinity | 6,664 | 6,640 | 5,667 | 5,644 |
| points skipped, input undefined | 1,221 | 1,221 | 1,033 | 1,033 |
| points skipped, unevaluable | 1,285 | 1,285 | 1,177 | 1,177 |
| cases with a convention-excused point | 0 | 0 | 0 | 0 |
| unsound: finite point / infinite point / undefined output | 1 / 5 / 1 | 1 / 5 / 1 | 1 / 4 / 0 | 1 / 4 / 0 |
| crash / timeout (60 s) | 0 / 23 | 0 / 19 | 0 / 0 | 0 / 0 |

- **Unchecked:** all are either refine results equal to SymPy's own value where the input has no value, or values the checker cannot evaluate (`Rem`, `Min` with a symbolic side, a Piecewise condition on a non-real sample).
  - Examples of the first kind: `sin(k)` → `AccumBounds(-1, 1)` under `Q.infinite(k) & Q.extended_real(k)`; `acsch(csch(AccumBounds(-1, 1)))`.
  - v3 gives the same results for those.
- **v3 (a side), same runs:** 11 unsound per combined mode (8 at an infinite point, 2 at a finite point, 1 undefined output), 7 per satassume mode.
  - They are of the B1–B3 class: `KroneckerDelta(y + I*z, 3*y + 1) -> 0` at `y = oo`; Piecewise `Ne(m, 2*m)` / `x >= x + 1` / `Ne(x, oo)` decided as for finite values; `Ne(n, -oo)` dropped as False at a finite `n`.
  - v3 also has 1 convention-excused case per run ("log of a non-positive infinity") and 4 crashes per combined mode.
  - The extended family finds this bug class without being pointed at it.

## 3. Triage (identities)

| # | Finding | Runs | Verdict |
|---|---|---|---|
| 1 | `acsch(csch(Abs(z))) -> Abs(z)` under `Q.infinite(z)`, `Q.extended_negative(z) & Q.infinite(z)`, `Q.extended_negative(y) & Q.eq(y, -oo)`, `Q.gt(n, 0)`. At ±oo the input is `acsch(0) = zoo`, the output `oo`. | 4 cases × 4 runs; both backends, both modes | **Real refine bug.** The row `acsch(csch(z))` has domain `~Q.zero(z) & (Q.real(z) \| ~Q.integer(im(z)/pi + 1/2))`. For `z = Abs(w)`, SymPy builds `im(Abs(w)) = 0`, so the second disjunct holds for any `w`, infinite included. B6 through the row domain instead of `_from_bounds`. The satassume answers are right (`Q.real(Abs(z))` is False under `Q.infinite(z)`). Needs test filed. |
| 2 | `Piecewise((exp(n), k >= k + 1), (pi*x, Eq(k, 1) \| Ne(k, 0)), (pi*m, True)) -> pi*x` under `Q.extended_negative(k) & ... & Q.gt(n, pi/2)`; at `k = -oo` SymPy gives `Ge(-oo, -oo + 1) = True`, so the input is `exp(n)`. | combined only, seed 22 | **SymPy `ask` bug, inherited through the combined backend.** `sympy.ask(Q.ge(k, k + 1), Q.infinite(k) & Q.extended_negative(k))` is False, from `k - (k + 1) = -1`. satassume leaves it unchanged. Minimal: `refine(Piecewise((0, k >= k + 1), (1, True)), Q.extended_negative(k) & Q.gt(n, pi/2))` → `1` (combined). The unrelated relation fact is needed for the combined backend to consult SymPy here. v3 and `sympy.refine` give `1` even without it. |
| 3 | `acos(cos(1/sqrt(x))) -> acos(AccumBounds(-1, 1))` under `Q.extended_real(x) & Q.infinite(x) & Q.gt(x, -pi/2)`; the input is `acos(cos(0)) = 0`. | combined only, seed 22 | **SymPy `ask` bug, inherited through the combined backend.** `sympy.ask(Q.infinite(1/sqrt(x)), Q.infinite(x))` is True and `Q.zero` is False (`1/sqrt(oo) = 0`). `sympy.refine(cos(1/sqrt(x)), ...)` gives `AccumBounds(-1, 1)` as well; satassume leaves it unchanged; v3 has the same result. |
| 4 | `atanh(tanh(x**3)) -> x**3` at `x = -2.36`: 7-digit mismatch. | all 16 runs (v3 too) | **Checker artefact, fixed:** a 15-digit Float sample makes `tanh(-13.19) = -1 + 7e-12` lose the digits `atanh` needs. Samples are now 40-digit Floats (the same binary value). |
| 5 | Timeouts at 60 s: KroneckerDelta of affine arguments 27, Min3 4, Piecewise_outer 4, Max 3, Piecewise 2, factorial 2. | combined only | **Performance, not correctness.** KroneckerDelta at ±oo is already known to be slow (p3-bugs: `KroneckerDelta(x, 2*x)` under `Q.ge(x, oo)` takes 33 s); satassume has none. |
| 6 | Matrix differential: `refine(HadamardProduct(X, X), f)` raises `ValueError: HadamardProduct needs at least one argument` for any fact `f` on `X`. | `--matrices --seed 2`, both modes | **Real refine crash.** `_engine._match` builds the rest of a `HadamardProduct(Z, R)` pattern with `[g for g in target.args if g is not t]`, which removes both copies of a repeated atom. `MatAdd` folds duplicates, so only Hadamard gets there. Needs test filed. |

Other SymPy `ask` answers seen while triaging, which refine does not reach under satassume: `sympy.ask(Q.real(Abs(z)), Q.infinite(z))`, `Q.zero(Abs(z))` and `Q.finite(Abs(z))` are all True.

## 4. Needs tests filed (for issue #10)

- **`tests/refine_identities/needs/test_fuzzext_acsch_infinite.py`:** 12 fail, 2 pass. The 2 passing ones guard that the finite case keeps firing.
  - Reproduction: `refine(acsch(csch(Abs(z))), Q.infinite(z))` → `Abs(z)` (expected unchanged); also `Q.gt(n, 0)` on `Abs(n)`.
  - Both modes, both backends.
  - Fix idea: `Q.finite(z)` on the acsch row, or in `_OFF_CUT_LINES`.
- **`tests/refine_identities/needs/test_fuzzext_hadamard_duplicate.py`:** 10 fail.
  - Reproduction: `refine(HadamardProduct(X, X), Q.diagonal(X))` with `X = MatrixSymbol('X', 2, 2)` raises `ValueError`.
  - Fix idea: remove the matched copy by position in `_engine._match`.

## 5. Gates

`.claude/gates/fuzz-ext-adf44a2` (the code of `adf44a2`: this branch merged with `origin/refine-identities` at `b01b7a9`), against the baseline `.claude/gates/speed-a45-de12f0a`. `PYTHONHASHSEED=0`, `JOBS=9 SLOTS=11 SUITE_WORKERS=4`, 989 s.

**Existing sections:** identical to the baseline except the timing lines (`time=...s`, termination `8 passed in 53 s`).
- Scoreboards: identical in both modes.
- Differential seeds 2, 3, 7 in both modes and satassume seed 2 in both modes: identical counts.
- Termination: 8 passed.
- No engine change, as expected.

**Suite:** 2,518 passed, 22 failed, 1,917 skipped, 30 xfailed.
- The 22 failures are exactly the new needs tests: 12 acsch, 10 Hadamard.
- The baseline had 2,464 passed; the 54 new passing tests are `test_fuzz_ext.py` and the 2 acsch guards.

**New sections** (no baseline; recorded here):

| Section | Package | Fired | Checked / unchecked | Unsound | Crash / timeout | Cases checked at ±oo | Convention-excused cases |
|---|---|---|---|---|---|---|---|
| ext gen, seed 2, 1,000 cases (835 compared) | v3 | 136 | 121 / 12 | 3 (1 finite, 2 at ±oo) | 3 / 2 | 54 | 0 |
| | identities | 147 | 133 / 14 | 0 | 0 / 6 | 60 | 0 |
| ext live, same cases | v3 | 136 | 121 / 12 | 3 | 3 / 2 | 54 | 0 |
| | identities | 146 | 132 / 14 | 0 | 0 / 8 | 59 | 0 |
| matrices gen, seed 2, 1,500 cases (1,457 compared) | v3 | 474 | 444 / 30 | 0 | 0 / 0 | – | – |
| | identities | 419 | 393 / 26 | 0 | 3 / 0 | – | – |
| matrices live | identities | 419 | 393 / 26 | 0 | 3 / 0 | – | – |

- **Both-fire-different verdicts:** ext 11 / 12, all numerically equal. Matrices 109: 100 numerically equal, 9 undecided, 0 different.
- **Identities matrix crashes:** the 3 crashes are the `HadamardProduct(X, X)` crash (needs test).
- **Timeouts:**
  - The ext section runs with a 20 s timeout. Its identities timeouts (6 generated, 8 live: KroneckerDelta at ±oo, Min/Max) depend on the machine load, so its timeout and fired counts can move by a few between gate runs.
  - Compare its unsound and crash lines. The default sections have no timeouts.
- **Cost:**
  - The ext section is the longest gate task: 750–800 s at load about 13, against 190–310 s for a default differential section.
  - `EXT_CASES=500` halves it. I left 1,000 so the section sees about 60 cases checked at an infinite point per run.

## 6. Open items

- The combined backend passes on SymPy's wrong answers at infinity (findings 2, 3). This can be reported to SymPy (`ask(Q.ge(k, k + 1))` for an infinite `k`; `ask(Q.infinite(1/sqrt(x)))`; `ask(Q.real(Abs(z)))` for an infinite `z`), or the combined backend can prefer satassume on these. I did not file anything.
- A symbol with no fact at all is sampled finite in the ext family. Allowing ±oo/zoo there would test refine's reading of "no fact" as "possibly infinite", but would bring many zoo conventions. Not done.
- The ext gate section costs about as much as one default differential section. KroneckerDelta timeouts dominate under the combined backend.
