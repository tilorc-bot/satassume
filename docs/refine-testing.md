# Testing satrefine

How satrefine's refine (`satrefine/identities/`, the default package
`handlers_identities`) is verified, what the checks found, and the numbers
they give now. How the engine works and why is in [refine.md](refine.md); the
backends and the tool command lines are in the
[README](../README.md#satrefine-the-refine-layer-as-a-yardstick); satassume's
own gates (the corpus replay, `tools/gate2.py`) are in [testing.md](testing.md).

Every check runs with `PYTHONHASHSEED=0`: a hash-seed dependence once moved a
battery case from run to run. It is fixed (`core/test_engine_hash_seed.py`),
but baselines are only comparable under the same seed.

## Test trees

| Tree | What | Package |
|---|---|---|
| `tests/refine/` | the refine layer's original handler tests, the verifier tests (`test_refine_verifier_*.py`) and SymPy's own `test_refine.py` (`test_sympy_refine_suite.py` rebinds its `refine`) | the default; `SATREFINE_HANDLERS` selects another |
| `tests/refine_identities/` | the package's own tests, laid out like it: `core/`, `rules/`, `compat/`, `build/`, `tools/`; plus `regressions.py`, the battery, the termination tests, `test_import_direction.py` and `needs/` | `handlers_identities` (its conftest sets it) |
| `tests/refine_v3/` | the v3 reference's suite, frozen with the reference | `handlers_v3` (its conftest sets it) |

- **`regressions.py`**: one row per `refine` input that once went wrong,
  `Case(expr, assumptions, expected, bug, reason, backends)`, grouped by bug id
  (`#10 B1`, `default: ...`, `checker: ...`). `test_regressions.py` runs every
  row (160 at `075d1f8`) in both identity modes and under the row's backends.
- **The battery** (`battery_v3.py`): 1,736 cases (1,086 that v3 rewrites, 650
  it leaves unchanged), recorded from the outermost `refine` calls of
  `tests/refine_v3` (`satrefine/tools/refine_battery_capture.py`, then
  `refine_battery_generate.py`). `test_battery.py` proves it faithful to v3
  (only with `SATREFINE_HANDLERS=handlers_v3`, so the default run skips those
  1,736 tests) and checks every firing case numerically; known oracle limits
  are strict xfails (`_known_oracle_limit`).
- **Termination** (`test_engine_termination.py`): the engine against
  adversarial `ask` oracles (always None, always True, random, `P` and `~P` both
  True) on battery and differential cases; each call must return within 20 s.
  `SATREFINE_TERMINATION_FUZZ=N` runs the large version (N=150 about 10
  minutes; N=1500: 45,304 calls, 0 failures, 25 minutes at `9b73ddb`).
- **Marker `full`**: the fixpoints of `power_exp_log`, `complex_parts` and
  `integer_funcs` and one slow battery case run only with
  `SATREFINE_FULL_TESTS=1`; the default run keeps `inverse` as a smoke test.
  `SATREFINE_STRICT_LOOPS=1` (set by the conftest, the scoreboard and the
  differential) turns a tripped termination guard into a failure.
- **`default_xfail(needs_file, reason)`** in `tests/refine`: a strict xfail
  for an expectation the default package does not meet, naming the `needs/` test.

### `needs/`: open requests

`tests/refine_identities/needs/` holds tests that state a wanted result the
code does not give; CI leaves them out, the gates' suite reports them as its
only failures. Everything else filed there was fixed and moved. Two cases are
left open on purpose, because each needs a decision, not a fix (see
[refine.md](refine.md#semantic-decisions)):

| Needs test | Wanted | Why refused | Strict xfail in `tests/refine` |
|---|---|---|---|
| `test_default_pow_of_pow.py` | `(x**y)**z -> Abs(x)**(y*z)` for real `x`, even `y` | nothing is known of `z`: at `x = 0, y = -2, z = oo` SymPy gives `zoo**oo = 0` but `0**(-oo) = zoo`; fires for real `z` since #46; a finite non-real `z` stays refused (`zoo**(1 + I)` stays unevaluated, `0**(-2 - 2*I)` is `nan`) | `test_refine_pow.py::test_nested_power_even_inner` |
| `test_default_matrixelement_ne_wrapping.py` | `A[i, j] -> 0` under `Q.diagonal(A) & Q.ne(i, j)` | SymPy keeps negative indices, which wrap once `A` is explicit (`i = -1, j = 2` in a 3x3); fires when both indices have one sign | `test_refine_matrix_element.py::test_diagonal_element_with_independent_symbols_ne` |

`needs/test_sympy_ask_bugs.py` is different: three strict xfails on SymPy's own
`ask` (`Q.eq(i, j)` True at `i = -oo`, `j <= 0`; `Q.unitary` from
`Q.orthogonal`; "inconsistent" raised for consistent assumptions). They pass
when SymPy is fixed, and the xfail must then go.

## CI

`.github/workflows/test.yml` runs one pytest per tree, as the gates do:

```bash
pip install pytest pytest-xdist hypothesis mpmath z3-solver "sympy @ git+https://github.com/tilorc-bot/sympy@6379c4da69"
PYTHONHASHSEED=0 python -m pytest -q -n auto tests --ignore=tests/refine --ignore=tests/refine_identities --ignore=tests/refine_v3
PYTHONHASHSEED=0 python -m pytest -q -n auto tests/refine_identities --ignore=tests/refine_identities/needs
PYTHONHASHSEED=0 python -m pytest -q -n auto tests/refine
PYTHONHASHSEED=0 python -m pytest -q -n auto tests/refine_v3
```

- **One process per tree.** Each refine conftest selects its handler package
  with `setdefault` before `satrefine` is imported, so in one session the first
  choice wins and the other suite runs against the wrong package (106 of 297
  regression tests failed that way). The trees also share module basenames.
  `--import-mode=importlib` is no way out: tests import sibling helpers
  (`_rows`, `battery_v3`, `regressions`) and 167 fail.
- **The SymPy fork.** Refine needs `tilorc-bot/sympy` at `6379c4da69` ("Add
  refine handler for conjugate" on a base older than `ddbb536`); with PyPI's
  SymPy 1.14, 25 refine tests fail. The gates take it from `SYMPY_PATH`
  (default `/home/tilo/orion/sympy`, at that commit on this machine).

At `075d1f8`: `tests/refine_identities` 2,903 passed, 1,920 skipped, 32
xfailed; `tests/refine` 449 passed, 6 xfailed; `tests/refine_v3` 1,004 passed,
1 xfailed (v3's `arg(exp(I*t))` rule does not fire under the combined and
satassume backends; not traced, v3 is frozen).

## The gates

`satrefine/tools/refine_gates.sh OUTDIR [BASEDIR]` runs every check below in
parallel (`JOBS`, default 6; at most `SLOTS`, default 8, gate jobs
machine-wide) and writes one log per task and `OUTDIR/summary.txt`. With
`BASEDIR`, an earlier `OUTDIR`, it prints the summary lines that changed, per
section ("no baseline" for a section added since). Re-running into an existing
`OUTDIR` re-runs only the tasks that did not finish, so a run cut short can be
completed. Start it detached and poll in short chunks (see
[agents.md](agents.md)): `nohup satrefine/tools/refine_gates.sh OUT BASE > OUT.log 2>&1 &`.

| Section | What | Wall time at `ce0a261` |
|---|---|---|
| suite | `pytest -n 3 tests/refine_identities` (with `needs/`) | 51 s |
| scoreboard generated, live | `scoreboard battery` in each `SATREFINE_IDENTITIES` mode | about 80 s each |
| differential, seeds 2, 3, 7, both modes | `refine_differential --seed S --cases 1500`, combined backend | 48 to 83 s each |
| differential satassume | seed 2 with `SATREFINE_BACKEND=satassume`, both modes | 49 to 67 s |
| differential ext, matrices | `--ext --timeout 20` (1,000 cases), `--matrices` (1,500), seed 2, both modes | 200 to 215 s, 110 to 130 s |
| tests/refine, full, termination | `pytest -n 2 tests/refine`; the `full` tests; `test_engine_termination.py` | 42 s, 50 s, 7 s |

A whole run takes 7 to 15 minutes (860 s at `JOBS=3`, 400 s at `JOBS=6`);
section times move with load and are not timings. `tests/refine_v3`,
satassume's own tests, `refine_fuzz`, the oracle and the ablation are not in
the gates.

**"Identical to the baseline"** means every changed line is a time
(`time=...s`, `in N s`), except that the ext section's 20 s per-case timeout
depends on load, so its timeout and fired counts can move by a few (compare its
unsound and crash lines), and the suite fails only in `needs/`. Any other change
is explained case by case: `scoreboard battery --show` lists every case that is
not a clean pass, and `refine_differential --keep DIR` keeps per-case JSON so
two trees can be diffed (as #60 did for eight changed cases); a new difference
from v3 is fixed or accepted in `lib/accepted.py` with a reason. Work meant to
change nothing (speed, refactors) met a stronger standard: identical per-case
output (the battery's result strings and the differential's records, both
modes, satassume and combined backends) and byte-identical regenerated tables.

### Scoreboard

`python -m satrefine.tools.scoreboard battery` (old name
`refine_identity_scoreboard`) prints rows and code lines per family
(`lib/sizes.py`), then classifies every battery case (`lib/battery.py`): same
as v3, other form (`simplify` of the difference is 0), miss, quiet (unchanged as
v3 expects), extra (fired where v3 does not), numerically wrong, crash. A
difference from v3 is *accepted* when `lib/accepted.py` lists it with the same
result and a reason, *open* otherwise; an accepted entry that no longer occurs
is printed as stale. Cases with matrix symbols or no satisfying sample count as
unchecked, never as passed. `scoreboard suite` (old name `refine_scoreboard`)
runs `tests/refine` under the `sympy`, `satassume` and `combined` backends and
sorts tests into satassume gaps (in scope or not), satassume wins,
combination-only wins and refine gaps.

### Differential against v3

`python -m satrefine.tools.refine_differential --seed S --cases N` runs two
packages (default v3 against identities), each in its own subprocess, on the
same random inputs. Per package it reports fired, unchanged, inconsistent,
crash, timeout, checked, unchecked and unsound; then which side alone fires,
and whether different results are numerically equal, different or undecided.
Each input family has its own random stream, pinned by digests in
`tests/refine_identities/tools/test_fuzz_ext.py`, so adding a family leaves
the others' cases unchanged:

- **default** (`lib/grammar.generate`): an outer head over an inner expression,
  each symbol with a predicate set from `assumptions.COMBOS`, sometimes a relation;
- **`--ext`**: `finite`, `infinite` and `extended_*` facts, up to two relations
  with bounds at `+-oo` (half the time the symbol's only fact, the B1-B7
  shape), `Piecewise`, `KroneckerDelta` of affine arguments, and `acot(cot)`,
  `acoth(coth)`, `asech(sech)`, `acsch(csch)`;
- **`--matrices`** (`lib/matrices.py`): matrix symbols under 32 predicate
  combinations (complex orthogonal included), valued at explicit exact 0x0 to
  3x3 matrices checked against a numeric definition of each predicate, and
  evaluated operation by operation, so no SymPy rule decides a value.

`refine_fuzz SEED CASES [--ext|--matrices]` checks one package on the same
inputs, runs SymPy's `refine` beside it so inherited bugs are told apart, and
prints per-head fire counts (for matrices, per-row coverage).

### Oracle, ablation, table verification

- **`refine_oracle`** compares refine with what SymPy's old assumption system
  and simplifiers make of hand-written shapes (mode A; matrices at explicit
  2x2 instances) and of the asserts in SymPy's test modules (mode B), checked at
  exact points. A slow measurement, not a gate.
- **`refine_ablate FAMILY`** removes each row in turn and keeps a removal only
  if the family's battery cases keep their class, its tests keep passing, and
  the differential's inputs with its heads (seed 2, 400 cases) gain no unsound
  result, crash or timeout; `--compare-to` measures hand-made merges. On the
  plain families (at `29dfcf1`, 2.5 to 23 minutes per family): `combinatorial`
  and `minmax_deltas` needed every row; `integer_funcs` went from 23 to 17;
  `matrices` merged its left and right zero-factor rows into one `Z*W` row
  with `Q.zero(Z) | Q.zero(W)` (no battery case, test or fuzz input moved),
  and its one droppable row was untested, not redundant, so it got a test.
- **Generated tables**: `refine_specialize` generates each rule and installs
  it only after `satrefine/build/verify.py` checks it at a sample point of its
  hypothesis and at every edge point that satisfies it (`0, 1, -1, I, -I`, plus
  `build/specs.EDGE_POINTS`: `+-2` for integer_funcs, `+-oo` for inverse). This
  check found SymPy's `Q.zero(b**2)` True for imaginary `b`.

## Numeric checking

All checkers compare the rewrite with its input at points satisfying the
assumptions; a mismatch is evidence, not proof. `lib/numeric.py` evaluates at
20 digits and compares with a relative tolerance of 1e-7; a point where both
sides fail to evaluate is skipped. Points (`lib/points.py`) are random draws
plus edge points, always tried: `0, 1, -1, I, -I` and the branch-cut points of
`log`, non-integer powers, `asin`, `acos`, `atan`, `acoth`, `asech`, `acsch`,
as symbol values and as the value that puts a linear argument on the cut.
Relations are decided at each point. The ext checker (`ext_value`) tells finite
values, signed or directed infinities, `zoo`, `nan` (also `AccumBounds`) and
unevaluable apart, decides `KroneckerDelta` by `Eq` and `Piecewise` branch by
branch, and counts without reporting the mismatches a SymPy convention explains
(`zoo` from an exact `1/0` or `log(0)` against a signed infinity, `log` of a
non-positive infinity, `atan2` of two infinities).

Every checker prints what it could not check next to what passed: "0 unsound"
means nothing without "N unchecked". About 13% of the differential's fired
cases and 194 battery cases are unchecked, mostly assumption sets no sample
satisfies, inputs undefined at every point, and matrix symbols in the battery.

**Known false alarm.** The ext section reports `acoth(coth(x**x)) -> x**x`
under `Q.extended_nonnegative(x)` (seed 2, case 621) as unsound at `x = 3`,
27.0327 against 27. The rewrite is exact: `coth(27)` is `1 + 7e-24`, and
`N(acoth(coth(27)), 20)` returns 27.0327 because evalf loses the digits `acoth`
needs next to 1 (at 40 digits: 26.99999999999999999999972). Random samples are
40-digit Floats for this reason (`atanh(tanh(x**3))`); an exact integer edge
point slips through.

**The other unsound counts at `075d1f8` are artefacts**, and v3 reports the
same cases: `-im(x)/(re(x)**2 + im(x)**2) -> 0` at 0 (seeds 2 and 3, three
cases: the input is `nan`, a removable singularity), `acoth(conjugate(x)) ->
acoth(x)` at `x = -1` (seed 3: both sides are `-oo`, which `agree` compares as
unequal), and `binomial(m**3, z - 1) -> 0` at a pole (seed 7). The matrix
section's 3 are not artefacts: they appeared when #22 made the unitary rows
plain identities, and rest on SymPy's wrong `ask(Q.unitary(X), Q.orthogonal(X))`
(one checked: seed 2, case 1439, `X**(-1) + X*Adjoint(X)` under
`Q.orthogonal(X)` gives `I + X.T`; see [refine.md](refine.md#the-ask-backend-compatbackendpy)).

**Checker faults found and fixed**, each making a tool pass on work it had not
done: relations decided with `.doit()`, so every case with one (353 of 1,485)
was checked at no point; `refine_fuzz` forcing the combined backend, so no
"satassume-only" differential before `9b73ddb` was one; matrix values through
`doit`; `oo` and `zoo` folded into one value.

## Fuzzing: what is in use

Of the staged fuzzing proposal made for the three handler packages, this was
built: edge and branch-cut points always checked (one list, not a table per
family); infinities and `zoo` as values with SymPy's conventions classified;
inconsistent assumptions counted, not skipped; matrices at explicit instances
with row coverage; the differential as the first filter; SymPy's `refine` on
the same inputs; pinned per-case streams; and `tools/ask_fuzz.py`, which checks
the answers the combined backend takes from SymPy at satisfying points. Not
built: a Hypothesis port with shrinking and an example database, generation
from each rule's precondition, assumptions drawn from the satassume solver,
metamorphic checks, and an audit of every `True` answer per case.

## Bugs the checks found

Why each fix is right is in [refine.md](refine.md); the regression groups are
in `tests/refine_identities/regressions.py` unless a file is named.

| Class | What went wrong | Fix | Regression |
|---|---|---|---|
| B9, termination | an empty stated interval (`Q.negative(k) & Q.gt(k, pi/2)`) proved every sign; two `log` rows alternated, each one level deeper, until `RecursionError` | an empty interval proves nothing; nesting, re-entry and work limits (`core/guard.py`) | `test_engine_termination.py`; "default: inconsistent assumptions" |
| B1-B7, bounds read as finite | `Q.gt(x, 1)` proved `Q.real(x)` and the finite signs, though `x = oo` satisfies it: `Piecewise` with `x < oo`, `Eq(x, 2*x)`, `KroneckerDelta`, `sign(exp(-x))`, `log(x**n)`, `acsch(csch(x))`, `RisingFactorial` | a bound proves `extended_real` and the extended signs; the finite ones need infinity excluded on that side | "#10 B1" to "#10 B7", "#10 B1-B7"; `core/test_engine_bounds_infinity.py` |
| extended reals | the B1-B7 fix lost 14 rewrites that hold at `+-oo` | rows stated over the extended reals where the identity holds there | "B1-B7 extended" |
| B8 | `acot`/`acoth` of a rewritten `-z` changed value at `z = 0` (SymPy's evaluation) | rebuilt unevaluated unless the argument is nonzero | "#10 B8" |
| B10 | `acsch(csch(Abs(z)))` fired at infinite `z` (`im(Abs(w))` is 0) | `Q.finite` on that disjunct | "#10 B10" |
| B12 | `Mod`/`Rem(p, q) -> p` where the relation allows `q = +-oo` | `Q.finite(q)` in the rows | "#10 B12" |
| B11, matcher | a repeated argument was removed by identity, dropping every copy (`HadamardProduct(X, X)` raised) | removed by position | "matfixes: Hadamard of a repeated atom" |
| matrix crashes | a one-term `MatAdd`; stated bounds substituting a scalar into a `MatrixElement` | a row; no scalar substitution | "default: one-term MatAdd", "diff: MatrixElement bounds" |
| default switch | 33 `tests/refine` expectations the old package met and this one did not (sign forms at odd `pi/2`, `(-1)**((-1)**x/2 + c)`, `sqrt(1/x)`, floor/ceiling of infinities and of sums of floors, `arg(0)`, `Rem(0, q)`, `Max`/`Min`/`factorial` at `+-oo`, `x + n*I*pi` shifts, matrix index order, scalars in a `MatMul`); 31 fixed, 2 left open (above); 10 old expectations were wrong (`det(X) -> 1` for orthogonal `X`) | rows; trig and hyperbolic try each binding against a row group (`by_binding`) | the "default: ..." groups |
| firing cap | the 500-firing cap counted all firings of a call, so a 501-term sum raised; `atan2` of a power exhausted it | cap per rewrite chain | "checker: firing cap", "checker: atan2 firing cap" |
| infinities | `Eq(x, y)` undecided for two equal infinities; `Max(n**k, log(x))` raised when a child refined to `nan` | a same-infinity proof; the head refuses | "checker: Eq of equal infinities", "engine: head refuses a refined child" |
| hash seed | `log(1/x)` under `Q.zero(x)` depended on `PYTHONHASHSEED` (a split explored an inconsistent sign case) | no sign case when neither is consistent | `core/test_engine_hash_seed.py`, "engine: zero base" |
| SymPy `Q.nonzero` | `Abs(x)`, `x**2`, `x*y` of imaginary factors called zero, reaching refine through the combined backend (`c**2*X*Y**2 -> 0`) | guard in `compat/backend.py` | `compat/test_backend_nonzero_guard.py` |
| SymPy `Q.extended_real` | `sqrt(z)` extended real for negative `z` (`sqrt(z)*conjugate(sqrt(z)) -> z`) | guard in `compat/backend.py` | none dedicated |
| satassume shared facts | one `ask` wrote a derived fact into the fact base every plain symbol shares | fixed on `main`: the engine never touches SymPy's `_assumptions` | `compat/test_earlier_calls_do_not_leak.py` |

## Numbers at `075d1f8`

From the gate run on `ce0a261` (the same tree), generated mode. Battery:

| Family | same | other | miss | quiet | extra | wrong | crash | open |
|---|---|---|---|---|---|---|---|---|
| combinatorial | 64 | 0 | 3 | 39 | 1 | 0 | 0 | 0 |
| complex_parts | 154 | 8 | 0 | 77 | 3 | 0 | 0 | 0 |
| hyperbolic | 196 | 30 | 0 | 126 | 16 | 0 | 0 | 0 |
| integer_funcs | 57 | 0 | 10 | 30 | 1 | 0 | 0 | 0 |
| inverse | 124 | 2 | 0 | 153 | 23 | 0 | 0 | 0 |
| matrices | 53 | 0 | 0 | 51 | 2 | 0 | 0 | 2 |
| minmax_deltas | 65 | 0 | 0 | 21 | 2 | 0 | 0 | 1 |
| power_exp_log | 103 | 1 | 0 | 66 | 3 | 0 | 0 | 0 |
| trig | 216 | 0 | 0 | 36 | 0 | 0 | 0 | 0 |
| **total** | **1,032** | **41** | **13** | **599** | **51** | **0** | **0** | **3** |

Live mode differs in one case (same 1,033, other 40). 194 cases are
numerically unchecked. Every other form and miss is accepted (the 10
`integer_funcs` misses are `Mod`/`Rem` under a bare relation, where v3 is wrong
at `q = +-oo`), and 48 of 51 extras. The 3 open extras: `KroneckerDelta(i, j)`
for two `-oo` indices gives 1 (the definition, #22), and `Adjoint(X)*X` and
`(X*Y)**(-1)` under `Q.orthogonal(X)`, wrong for a complex orthogonal `X` (SymPy's
`Q.unitary` answer) but not counted as wrong: the battery cannot sample matrices.

Differential, identities (v3 in parentheses):

| Section | fired | unsound | crash | only v3 / only identities fires | numerically different |
|---|---|---|---|---|---|
| seed 2 | 459 (436) | 2 (2) | 0 (0) | 2 / 25 | 0 |
| seed 3 | 462 (438) | 2 (3) | 0 (0) | 0 / 24 | 1 (v3 wrong: B8) |
| seed 7 | 417 (401) | 1 (1) | 0 (0) | 4 / 20 | 0 |
| satassume, seed 2 | 459 (436) | 2 (2) | 0 (0) | 2 / 25 | 0 |
| ext, seed 2 | 270 (163) | 1 (3) | 0 (3) | 10 / 109 | 1 |
| matrices, seed 2 | 439 (474) | 3 (0) | 0 (0) | 44 / 9 | 1 |

v3 lets `ask`'s "inconsistent" `ValueError` through on 56 / 59 / 71 default
inputs; identities returns the input. The ext section checked 153 identities
cases at an infinite point.

## Speed

Timings are of refine alone over the battery, satassume backend, generated
mode, one process pinned to a fast core (0, 1, 10 or 11 on this 12-core host;
2 to 5 are slow), interleaved with the reference tree (`git archive`), best of
two or more. A change under 3% was not kept.

| Step | Change | Battery refine | Other | Reference, candidate |
|---|---|---|---|---|
| routing (#7) | the combined backend asks SymPy only where satassume has no model | 135 s to 36 s (one process, unpinned) | | `cab778f` |
| start of phase 3 | | 14.8 s | fixpoint `power_exp_log` 64.7 s | `f83f195` |
| A0 | satrefine's own `Pow`/`exp._eval_refine` through the backend and the per-call memo; patterns analysed once when compiled | 14.38 to 10.23 s (-29%) | differential worker -9% | `9819814`, `d54ca58` |
| A4/A5 | case splits: one real-part dummy per symbol, stop at the first failing case, skip splits no assumption links to the node | 9.69 to 8.38 s (-13.5%) | fixpoint `power_exp_log` 55.6 to 25.7 s (-54%); full fixpoint 133-141 to 64-66 s; differential -6% | `eb106a6`, `2cb920d` |
| A6/A7 | bounded memos of pure functions (`n*unit` ratio, `subst`, `count_ops`, `_distributed`); long checks behind `full`, a session-shared fixture | 8.55-8.83 to 6.93-7.12 s (-19%) | fixpoint `power_exp_log` 24.5 to 19.3-20.0 s (-20%); differential -9%; suite (`-n 4`) 112-114 to 44-53 s | `b01b7a9`, `04fddc4`/`e116c54` |

Measured and dropped: a head test before matching (0.8%, `c071543`); a node
cache keyed on the engine flags a result read (A5: 0% battery, -2.5%
differential, +3% fixpoint; code and argument in `e3218da`); a `_stated` memo
(0 to 1.6%); a split memo across calls (0: the repeats are between fixpoint
rounds); `endpoint_split` off in the fixpoint (2.2%, but it needs a switch).

Not re-timed since A6; #60 brought `main`'s #45 (faster, same answers) and #48
(+13% on queries with constants). Under the satassume backend alone the battery
loses the matrix family (52 misses against 3 at `eb106a6`: satassume has no
matrix predicates). The relation losses measured then were `pi/2` bounds,
which satassume reads since #48; Float and `AccumBounds` bounds still fall back
to SymPy (#64).

## Test data outside the repository

Two files the performance gates use exist only in `/home/tilo/provable/data/`
on this machine (#62 asks to commit them or a script that regenerates them):

- `stream.pkl` (sha256 `94db857d9d5d...`): the `ask` query stream of the
  battery, 16,232 `(proposition, assumptions, answer)` triples, written by
  `python -m satrefine.tools.refine_record` and replayed against any satassume
  checkout by `refine_replay`, which fails if an answer differs;
- `gate2-frozen.jsonl` (sha256 `d53ed3db2f3a...`): the frozen answers for
  `tools/gate2.py --frozen` (see [testing.md](testing.md)).
