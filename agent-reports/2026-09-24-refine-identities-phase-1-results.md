# Agent report: refine handlers as identities and rule tables — phase 1 results

- **Date:** 2026-09-24
- **Status:** phase 1 complete on `refine-identities` at the commit that adds
  this report. All nine families of `handlers_v3` are reimplemented as tables
  in `satrefine/handlers_identities/`, checked adversarially and trimmed.
- **Read this if:** you want the outcome of the identities approach, you are
  deciding whether to build on it, or you are starting phase 2
  (`archive/2026-09-24-refine-identities-phase-2-plan.md`; its results: `2026-09-25-refine-identities-phase-2-results.md`).
- **Stale after:** the staged derivation work, the piecewise experiment
  (`ri/piecewise`) being merged, or a fix to the satassume defect in section 5.
- **TL;DR:** the table package matches `handlers_v3` on 1,073 of the 1,086
  battery cases where v3 rewrites, gives no wrong answer and no crash on any
  of the 1,736 cases, and fires on 16 cases v3 refuses (one of them the
  known infinity case in section 4). Per family
  it is 3.3 times less code than v3 (483 lines against 1,595), in 203 rows,
  with the largest cuts where identities apply (inverse functions 4.5x,
  hyperbolic 4.4x, complex parts 3.8x). But the shared engine is 1,132
  lines, so the two systems are the same total size today; the payoff of the
  engine is in the next function, not in these nine. The adversarial passes
  found three defects below the tables, one of them in satassume on `main`:
  a single `ask` can corrupt the assumptions of every plain symbol in the
  process.

## 1. What was built

- **Engine** (`_engine.py`, `_dispatch.py`, `_specialize.py`, `_simple.py`,
  `_tables.py`, `_wraps.py`): structural matching with linear special forms
  (one factor against the rest, coefficient of a unit, predicate parts,
  head wildcards, matrix patterns), `provable()` deciding `And`/`Or` per
  connective, two table kinds (identity rows that fire only when the branch
  bookkeeping collapses and a measure decreases; plain conditional rows
  with an optional `unless`), sign and endpoint case splits, interval
  reasoning for `floor` from stated bounds, a loop guard, a dispatcher that
  re-refines auto-evaluated nodes, and a generator that specializes identity
  rows under assumption profiles, verifies every rule numerically at edge
  points, and writes `generated/<family>.py`.
- **Tables** for all nine families; see section 2.
- **Measurement:** the acceptance battery (1,736 cases recorded from the v3
  suite, proven faithful to v3), `tools/refine_identity_scoreboard.py`,
  `tools/refine_differential.py` (two packages on the same random inputs,
  edge points always checked), `tools/refine_ablate.py` (row removal against
  three gates), and a fix to `tools/refine_fuzz.py`, which had silently
  skipped every case with a relation assumption.

## 2. Results

### Battery, all 1,736 cases (default generated mode)

| Family | Same as v3 | Other correct form | Miss | Unchanged as required | Extra | Wrong | Crash |
| --- | --- | --- | --- | --- | --- | --- | --- |
| trig | 216 | 0 | 0 | 36 | 0 | 0 | 0 |
| hyperbolic | 196 | 30 | 0 | 142 | 0 | 0 | 0 |
| complex_parts | 150 | 8 | 4 | 79 | 1 | 0 | 0 |
| inverse | 124 | 2 | 0 | 164 | 12 | 0 | 0 |
| power_exp_log | 98 | 3 | 3 | 66 | 3 | 0 | 0 |
| integer_funcs | 67 | 0 | 0 | 31 | 0 | 0 | 0 |
| minmax_deltas | 65 | 0 | 0 | 23 | 0 | 0 | 0 |
| combinatorial | 64 | 0 | 3 | 40 | 0 | 0 | 0 |
| matrices | 50 | 0 | 3 | 53 | 0 | 0 | 0 |
| **Total** | **1,030** | **43** | **13** | **634** | **16** | **0** | **0** |

The 13 misses: 3 combinatorial cases where v3's own answer is wrong at
infinity; 3 matrix cases of symbolic index order, which v3 decides by how
the indices print and no hypothesis can express; 7 power and complex-part
cases documented in the module docstrings (an `ask` gap on odd parity, and
rules whose zero base cannot be checked). The extras are exact except one
known case (section 4). 189 cases are numerically unchecked (matrix
symbols, or no satisfying sample).

### Size

| Family | v3 lines (code) | Table lines (code) | Code ratio | Rows |
| --- | --- | --- | --- | --- |
| inverse | 610 (221) | 127 (49) | 4.5x | 11 facts, 2 rules |
| hyperbolic | 225 (128) | 68 (29) | 4.4x | 12 rules |
| complex_parts | 567 (342) | 175 (91) | 3.8x | 3 facts, 3 exp forms, 41 rules |
| trig | 221 (118) | 75 (35) | 3.4x | 13 rules |
| power_exp_log | 345 (184) | 163 (59) | 3.1x | 4 facts, 3 exp forms, 18 rules |
| minmax_deltas | 305 (139) | 128 (45) | 3.1x | 13 rules |
| integer_funcs | 252 (146) | 153 (49) | 3.0x | 17 rules |
| combinatorial | 236 (129) | 144 (51) | 2.5x | 16 rules |
| matrices | 356 (188) | 197 (75) | 2.5x | 30 rules |
| **Families** | **3,117 (1,595)** | **1,230 (483)** | **3.3x** | **203** |
| Shared code | `_common.py` 70 (30) | engine 1,709 (1,132) | | |

"Code" excludes blank lines, comments and docstrings; the table modules
carry a comment per row stating its theorem, so their total lines shrink
less than their code. 60 rules are generated from identity rows for
complex_parts, power_exp_log and inverse.

**Counting shared code, both systems are about 1,600 code lines.** The
engine is general: a new function costs rows, not procedure. That makes the
approach pay off with the next families added, not with these nine.

### Where the identity approach worked and where it did not

- **Worked best:** inverse functions (11 facts with wraps replace 610
  lines), complex parts (the base layer of `re`, `im`, `arg`, `Abs`
  became 26 counted rows instead of procedure), and `log` (two facts plus
  two exponential forms).
- **Did not reach:** trig and hyperbolic ended as plain conditional rows
  (13 and 12), not derived from exponential forms as planned. Still 3.4x
  and 4.4x less code than v3.
- **Plain-rules families:** already near minimal as rules. Ablation removed
  only 7 rows (integer_funcs 23 to 17, matrices 31 to 30); combinatorial
  and minmax_deltas need every row. Further reduction needs definitions,
  not deletion (section 6).
- **Still procedural:** interval reasoning for `floor` and `ceiling`, and
  `Piecewise` refinement. Both are generic, not facts about one function.

## 3. Soundness evidence

- Battery: 0 wrong, 0 crash across 1,736 cases.
- Differential fuzz against v3, seeds 2, 3 and 7 with 1,500 cases each, in
  generated and live mode: one result numerically different from v3
  (seed 3), which the checker believes is the `Abs`-of-imaginary defect in
  section 5 but did not match individually; unsound results unique to this
  side are the two `Abs`-of-imaginary cases, and the rest are shared with v3.
- Two adversarial passes (plain families, then branch-cut families) found
  and fixed 3 row defects: `Mod(a, b) = b/2` for odd `2*a/b` fired for
  non-real divisors; three combinatorial rows admitted infinite arguments
  through `~Q.integer` (v3 has the same bug); four inverse-hyperbolic facts
  were false on the lines where the forward function lands on the inverse's
  branch cut.
- **Gap:** the fuzzer generates no matrix expressions, and the battery's
  numeric check skips matrix symbols, so matrices have no numeric
  soundness check beyond their own tests.

## 4. Known accepted limitations

- Rules hold on the extended reals except at infinity in a small class:
  `log(1/x) -> -log(x)` under `Q.extended_positive(x)` is wrong at `oo`
  (`log(1/oo)` is `zoo`), and the checker found the same class in
  `log(exp(x))`, `arg(exp(x))`, `(1/x)**y` and `exp(y*log(x))` at infinite
  points. The branch-cut author chose coverage of the nonzero and complex
  cases over refusing whenever infinity is possible; documented in the
  modules.
- Live identity evaluation is slow where case splits run (seconds per
  expression); the generated tables are the fast path, with the live rows
  behind them.

## 5. Defects found outside this package

| Where | Defect | Status |
| --- | --- | --- |
| **satassume (`main`)** | One `ask` corrupts the assumptions of every plain symbol in the process. SymPy caches `(0**n).is_finite` as True (wrong: `0**-1` is `zoo`); satassume reads cached facts as unconditional, declares `Q.negative(n) & Q.nonnegative(x)` inconsistent, and writes a derived fact into the fact base shared by all assumption-free symbols. Afterwards `Symbol('fresh').is_negative` is False. Reproduced on `main` at 07e0bd5. | needs test `tests/refine_identities/needs/test_checker_ask_poisons_plain_symbols.py`; not fixed |
| SymPy `ask` | `Q.zero(b**2)` is True for imaginary `b`; `Q.zero(Abs(x))` is True for imaginary `x` | the second reaches results through the combined backend; needs test filed |
| SymPy old assumptions | `(0**n).is_finite` is True for a plain `n` | root of the satassume defect |
| SymPy `refine` | children of an auto-evaluated rebuild are never refined | fixed in this package's dispatcher only |
| SymPy `refine_Pow` | wrong answers (`sqrt(x**2)` for imaginary `x`; `sqrt(x**3)` for real `x`; `0**n` for odd `n`; `(x**3)**(1/3)` to `Abs(x)`) and a crash on `(-1)**(n + 1/2)` | replaced by this package's rows |
| SymPy `refine` | cube root of a cube becomes `Abs` under a relation assumption | found by the fixed fuzzer |
| this engine | `atan2` of a power of a nonpositive base exhausts the 500-firing cap (a crash, no wrong answer) | needs test filed |

**The satassume defect affects every long-running tool.** The scoreboard,
fuzzer and differential run many cases per process on the default combined
backend; after the first corrupting case, later results can be wrong. The
checker confirmed each of its findings in a fresh process. Until the defect
is fixed, treat any single anomaly in a long run as suspect and re-run it
alone.

## 6. Recommendations for phase 2

1. **Fix the satassume defect first.** It is on `main` and affects anything
   that calls `ask` twice in one process.
2. **Staged derivation** (now part of `archive/2026-09-24-refine-identities-phase-2-plan.md`):
   derive the base layer and families in dependency order to a fixpoint,
   with derivation records. Trig and hyperbolic through exponential forms
   are the obvious targets.
3. **Definitions for the plain families.** The piecewise experiment on
   `ri/piecewise` replaced 10 of minmax_deltas' 13 rules with 5 `Piecewise`
   definitions at identical coverage, but needed a 35-line relation-condition
   decider that belongs in the engine. Move the decider into the engine,
   then merge, then apply the same idea to integer_funcs (`ceiling`,
   `frac`, `Mod`, `Rem` via `floor`). The experiment's verdict on
   combinatorial via `gamma` is doubtful.
4. **Prover gaps worth closing in `ask`:** integrality of `(1 - n)/2` for odd
   `n` (costs power rules their clean form), and `re` and `im` of `floor(y)`
   being integers for finite `y` (would remove 4 integer_funcs rows).
5. **Matrix fuzzing**, to close the soundness gap in section 3.
