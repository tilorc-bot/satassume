# Report: matrix fuzzing and the Abs-of-imaginary guard (phase 2, agent "matfuzz")

- **Date:** 2026-09-25
- **Branch:** `ri/matfuzz` (from `origin/refine-identities` at 2fd72b8), pushed.
- **Plan steps:** 5 (matrix fuzzing, last bullet) and 1.4, first half (guard the combined backend).
- **TL;DR:** The fuzzer now generates matrix expressions and checks them at explicit
  sample matrices. Across 5,849 matrix cases in 3 seeds it found no wrong row in
  `matrices.py`. The one wrong matrix result it found (`c**2*X*Y**2 -> 0` for imaginary
  `c`) came from SymPy's `ask`. The combined backend now guards the SymPy handlers behind
  that answer and behind the Abs-of-imaginary answer. On the scalar differential this
  removes 3 unsound results, 1 numerically different result and 1 crash, and adds
  nothing new. Both tools now print a count of fired-but-unchecked cases.

## 1. Matrix fuzzing

### What was added

`tools/refine_fuzz.py` (`python tools/refine_fuzz.py SEED CASES --matrices`) and
`tools/refine_differential.py --matrices`:

- **A separate case stream.** Matrix cases use `mat_generate(seed, case)`, seeded with
  `"matrix-{seed}-{case}"`. The scalar grammar and scalar streams are unchanged: the
  scalar differential generates the same cases as before.
- **Grammar.** Square `X`, `Y` (size 1, 2, 3 or symbolic `n`), rectangular `R`, `R2`
  (`k x l`) and `W` (`l x k`), a scalar `c` and indices `i`, `j`. Heads: `Transpose`,
  `Inverse`, `Determinant`, `Trace`, `MatAdd` (2 or 3 terms), `MatMul` (2 or 3 factors),
  scalar multiple, `HadamardProduct`, `MatrixElement`, `Adjoint`, `Trace` of a sum,
  `Determinant` of a product, `Inverse(X*Y)`, and rectangular forms (`N.T*M*N`, `R*W`,
  `Z*W` and others). Inner arguments include the forms the rows are stated for (`A*M*A`,
  `A.T*M*A`, `A*A`, `A - A.T`, `A**-1*A`, `Adjoint(A)*A`, ...). A quarter of the inner
  arguments are bare symbols.
- **Assumptions.** Each matrix symbol gets one of 32 combinations of the matrix
  predicates `matrices.py` and v3 use: zero, square, symmetric, diagonal, orthogonal,
  unitary, normal, invertible, singular, fullrank, upper/lower/unit triangular,
  triangular, positive definite, and real/integer/complex elements. The combinations
  include orthogonal without real elements (complex orthogonal) and unitary without
  orthogonal. Scalars, indices and sizes get sign and integer predicates, and there is
  an occasional relation between the indices.
- **Sample points.** Explicit exact matrices with rational or Gaussian-rational entries,
  from 14 constructions: generic, zero, identity, diagonal, `G + G.T`, rank 1, orthogonal
  (rotations and reflections from Pythagorean triples, complex orthogonal blocks such as
  `[[5/4, 3i/4], [-3i/4, 5/4]]`, block-diagonal and permuted), unitary, singular (a
  repeated or zero row), triangular, unit triangular, and positive definite
  (`G.T*G + I`). Rejection sampling keeps only matrices that pass a numeric definition of
  every assigned predicate (`MPREDS`). For example, "orthogonal" means `M.T*M = M*M.T = I`
  exactly, and "unitary" uses `M.H`. Symbolic sizes are sampled from 0 to 3. Indices are
  valid indices, including negative ones that wrap. The relation is checked at each
  point.
- **Value.** `_explicit` evaluates the expression operation by operation on the explicit
  matrices: `det` of 0x0 is 1, the inverse of a singular matrix is undefined, and indices
  wrap. No symbolic SymPy rule decides a value. This matters: SymPy calls
  `det(ZeroMatrix(0, 0))` 0 and turns `0*X` into `ZeroMatrix`. The first version of the
  checker used `doit` and flagged the correct rewrite `det(0*X*Y) -> det(ZeroMatrix(n, n))`
  as unsound at `n = 0`. A point where the input is undefined is skipped. A point where
  only the rewrite is undefined is a counterexample.
- **Row coverage.** Under `handlers_identities`, the fuzzer counts how often each of the
  30 rows fires. It credits the first row that alone gives the same rewrite.
- **Unchecked count.** Both tools now report, per package, `checked=` (fired and agreed
  at one point or more), `unchecked=` (fired, no point checkable) and `unsound=`, and they
  list the unchecked cases. This applies to the scalar mode too; the scalar results are
  unchanged, only the output has the new columns.

Tests: `tests/refine_identities/test_matrix_fuzz.py` has 105 tests. Every matrix
combination samples correctly at sizes 1 to 3. Complex orthogonal and unitary are told
apart. The 0x0 determinant is 1. A known wrong rule (`det X = 1` for orthogonal `X`) is
caught. A right one passes. An undefined input counts as unchecked. The index points
respect their predicates and the relation. Generation is deterministic. The coverage
counter names the firing row.

### Results

`refine_fuzz.py --matrices --handlers handlers_identities`, 2,000 cases per seed, final
version:

| seed | tried | fired | checked | unchecked | unsound | crash | rows fired |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1,959 | 548 | 508 | 40 | 0 | 30 | 28 of 30 |
| 2 | 1,946 | 550 | 512 | 38 | 0 | 22 | 28 of 30 |
| 3 | 1,944 | 549 | 513 | 36 | 0 | 20 | 30 of 30 |

Every one of the 30 rows fired in at least one seed and was checked numerically.

`refine_differential.py --matrices`, v3 against identities, 1,500 cases per seed, final
version:

| seed | v3 fired / checked / unchecked / unsound / crash | identities fired / checked / unchecked / unsound / crash | only v3 | only ids | both, different (numerically different) |
| --- | --- | --- | --- | --- | --- |
| 1 | 473 / 433 / 40 / 0 / 0 | 407 / 379 / 28 / 0 / 25 | 57 | 0 | 125 (0) |
| 2 | 474 / 444 / 30 / 0 / 0 | 411 / 386 / 25 / 0 / 17 | 55 | 1 | 110 (0) |
| 3 | 472 / 439 / 33 / 0 / 2 | 416 / 389 / 27 / 0 / 15 | 53 | 1 | 123 (0) |

- **Wrong rows in `matrices.py`: none found**, so `matrices.py` is unchanged. The only
  wrong matrix result was `refine(c**2*X*Y**2, Q.imaginary(c) & ...) -> 0` (matrix
  seed 1, case 142). Its cause is SymPy's `ask` (`Q.zero(c**2)` is True for imaginary
  `c`), and v3 gives the same result. Section 2 fixes it; the test is in
  `test_backend_nonzero_guard.py`.
- **Unchecked** cases are mostly inputs undefined at every point, such as the inverse of
  a singular matrix (`Trace(X**-1*X)` under `Q.singular(X)`, `(X - X.T)**-1`), and
  assumption sets that no sample satisfies (`Q.negative(j) & Q.eq(j, 0)`).
- **Crashes (identities only):** `TypeError: First argument of MatrixElement should be a
  matrix`, from the engine's `_simple.stated_bounds` -> `_affine`, which substitutes a
  scalar for a `MatrixSymbol` inside a `MatrixElement`. v3 does not crash on these
  inputs. This is the engine's code, so I filed a needs test:
  `tests/refine_identities/needs/test_matfuzz_matrixelement_bounds_crash.py` (2 tests,
  failing).
- **Only v3 fires (53 to 57 per seed):** v3's canonical `doit` form (`Trace(X**-1*X) ->
  Trace(I)` and similar), and a few coverage gaps with correct v3 results that no row
  expresses:
  - `c*X -> 0` for a zero matrix `X` and a scalar `c`;
  - `X*Y.T*Y -> 0` for zero `X`: the `Z*W` row binds atoms only, and `Y.T` is not one;
  - `HadamardProduct(0, -X) -> 0`;
  - `(X*Y)**-1 -> Y.T*X.T` for orthogonal `X`, `Y` (the unitary row refuses orthogonal
    factors);
  - `(-X)**-1` for orthogonal `X`.

  These are misses, not wrong answers. I did not add rows for them, because that would be
  a coverage change that goes through the battery gates.

## 2. The combined-backend guard (Abs of imaginary)

**Cause.** SymPy defines `Q.nonzero(e)` as "real and nonzero", so False means "zero or
not real". Its handlers for `Abs`, `Pow` and `Mul`
(`sympy/assumptions/handlers/order.py`) answer False whenever an argument is not a real
nonzero number, even when the expression itself is real and nonzero: `Abs(x)`, `x**2`
and `x*y` for imaginary `x`, `y`. `Q.zero(e)` is derived as
`fuzzy_and(not Q.nonzero(e), Q.real(e))`. So SymPy calls `Abs(x)` and `x**2` **zero** for
imaginary `x`, and everything built on those answers inherits the error:
`Q.positive(Abs(x))` is False, `Q.positive(exp(I*Abs(x)))` is True, and `c**2*X` is the
zero matrix.

**The guard** (`satrefine/backend.py`). While the combined backend asks SymPy, the three
dispatcher entries `Q.nonzero.handler.funcs[(Abs,)]`, `[(Pow,)]` and `[(Mul,)]` are
wrapped. They keep every True and every None. They replace a False with a checked
answer:

- **False** only if the expression is provably not real, or provably zero: a zero factor
  with all factors finite, a zero base with a positive exponent, or `Abs` of zero.
- **True** if the expression is real and every part is finite and provably nonzero. For
  `Pow` that means a nonzero finite base and a finite exponent. For `Abs` it means a
  finite nonzero argument.
- **None** otherwise.

This is sound under SymPy's own definition, and it covers the whole class (three
handlers), not just the one reported instance. The switch is a module flag set only
inside `_guarded_sympy_ask`. The `sympy` backend and direct `sympy.ask` calls are
unchanged, and a test checks this.

**Evidence** (`tests/refine_identities/test_backend_nonzero_guard.py`, 20 tests; it
replaces `needs/test_checker_abs_of_imaginary_is_zero.py`):

- The three original needs cases now pass: `refine(log(exp(I*Abs(x))), Q.imaginary(x))`
  is no longer 0, and `refine(arg(log(z)), Q.imaginary(z) & Q.ne(z, 0))` is no longer
  nan.
- The matrix case (`c**2*X*Y**2`) and the seed-3 fuzz form (`log(exp(I*sqrt(x**2)))`)
  also pass.
- 6 answers change: `Q.zero(Abs(x))`, `Q.zero(b**2)`, `Q.positive(Abs(x))` and
  `Q.nonzero(x*y)` under imaginary facts. The tests also check that plain SymPy still
  gives its original answer to each.
- 9 correct answers are kept, including `Q.nonzero(I*x)` False for positive `x` and
  `Q.zero(x*y)` True for zero `x`.

### Scalar differential, before and after (seeds 2, 3, 7, 1,500 cases, v3 against identities)

Before: 2fd72b8 in a clean copy. After: `ri/matfuzz` with the guard. Both packages run
on the combined backend, so v3 moves too.

| seed | | ids fired | ids unsound | ids crash | v3 fired | v3 unsound | only ids | both, different (numerically different) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | before | 481 | 2 | 0 | 454 | 2 | 30 | 11 (0) |
| 2 | after | 481 | 2 | 0 | 454 | 2 | 30 | 11 (0) |
| 3 | before | 480 | 4 | 1 | 455 | 3 | 28 | 17 (1) |
| 3 | after | 479 | 3 | 0 | 454 | 3 | 28 | 17 (0) |
| 7 | before | 445 | 3 | 0 | 426 | 2 | 23 | 19 (0) |
| 7 | after | 443 | 1 | 0 | 425 | 1 | 22 | 17 (0) |

Every change removes a wrong result or a crash:

- `log(exp(sqrt(x**2)))` under `Q.imaginary(x)`: was 0; now unchanged. This was the one
  numerically different result.
- `arg(log(z))`: was nan.
- `sign(n**2)` under `Q.imaginary(n)`: was 0 in both packages, because SymPy calls `n**2`
  zero.
- `Max(n**k, log(x))`: was a crash (`nan is not comparable`); its assumptions are
  inconsistent (`Q.imaginary(n) & Q.gt(n, 0)`).
- Two "undecided" pairs under inconsistent assumptions disappeared (seed 7).

The remaining unsound results are the known ones at poles (`im(1/x)` at 0,
`acoth(conjugate(x))` at -1), `acoth(sqrt(z**2))` at `z = 0`, and a binomial result at
a pole, all present before. **No new unsound or numerically different result.** The new
columns: identities `checked=418/427/377`, `unchecked=61/49/65` (seeds 2/3/7), which is
13% of fired cases with no checkable point. Most of them have unsatisfiable assumption
sets from the random relation (`Q.odd(m) & Q.negative(m) & Q.eq(m, 1)`) or inputs
undefined at every point (`cot(sqrt(m))`, `Q.zero(m)`).

### Other SymPy `ask` wrong answers the backend passes through

`tools/ask_fuzz.py` is a new tool. It asks a random unary predicate of random
expressions under random assumptions. For answers that satassume leaves open and SymPy
gives, it checks the answer at satisfying points, both raw and with the guard. Runs:
4,000 cases, plain and with `--relation` (which forces a relation, so satassume answers
less). There were 212 and 888 SymPy-only answers. The guard removed every nonzero-class
error; wrong answers that remain, both raw and guarded:

| answer | why wrong | effect seen |
| --- | --- | --- |
| `Q.zero(b**2)` True, `Q.zero(Abs(x))` True for imaginary `b`, `x` (and `Q.nonzero(x*y)` False) | nonzero handlers, above | **guarded now** |
| `Q.imaginary(I*y)` True for `Q.nonnegative(y)` or `Q.integer(n) & Q.lt(n, 1)` | `y = 0` gives 0, which SymPy does not call imaginary | none found in refine results (`re(I*n) -> 0` is still right) |
| `Q.integer(pi*x)` False for integer `x` | `x = 0` gives 0 | none found; a row with `~Q.integer(...)` could fire at 0 |
| `Q.finite(sign(1/sqrt(y)))` True for `Q.integer(y) & Q.ne(y, 1)` | `y = 0` gives `sign(zoo)` | none found |
| `Q.finite(Abs(log(k)))` True for `Q.zero(k)` | `log(0) = zoo` | none; refine gives the right `oo` |
| `Q.algebraic(exp(x))` True for algebraic imaginary `x` (from reading `handlers/sets.py`: `~Q.nonzero(x)` read as zero) | `exp(I)` is transcendental | combined already says False (satassume answers) |

The last four are single-point errors at 0 or at a pole. I did not guard them: the fix
would be per-handler, and I found no refine result they make wrong. They are listed here
as upstream candidates.

## 3. Tests and gates

- `tests/refine_identities` (full run, with the guard): 2,302 passed, 1,917 skipped,
  30 xfailed, 10 failed. The 10 failures:
  - 7 needs tests: the 3 poisoning tests, the 2 atan2 firing-cap tests and my 2 new
    MatrixElement tests;
  - 3 others: `test_generated_module_is_up_to_date[complex_parts]`,
    `test_specialize::test_expected_rules_are_generated` and
    `test_specialize::test_generated_rules_verify_or_are_flagged`. The first two fail
    identically on the untouched base 2fd72b8: generation now keys `exp(re(z))` rows where
    the table has `Abs(exp(z))`, and it produces an unexpected
    `log(p*r) -> log(-p) + log(-r)`. They are pre-existing and belong to the engine agent.
    The third I did not re-run on the base.
- `test_matrices.py` + `test_engine_matrices.py`: 150 passed, 1 xfailed.
- Battery and scoreboard: **not run** by me. The guard changes `ask` answers, so the
  scoreboard is the one gate left open. Only answers under imaginary (or otherwise
  non-real) facts change, and the differential moved only toward fewer wrong results.

## 4. Commits (on `ri/matfuzz`)

- cc34ac1: refine_fuzz, matrix expressions (`--matrices`)
- a3d8e45: refine_differential `--matrices`; unchecked counts
- f7a8e86: combined backend guard; needs test moved to `test_backend_nonzero_guard.py`
- 1bae672: needs test for the MatrixElement crash; `tools/ask_fuzz.py`
- b236d2e: tests for the matrix fuzz
- 75cf61e: `ask_fuzz --relation`
- c964fe7: explicit evaluation, row coverage, more bare-symbol arguments
- this report

## 5. Open

- Engine: the MatrixElement crash in `stated_bounds` (needs test filed).
- The scoreboard in both `SATREFINE_IDENTITIES` modes with the guard is not run.
- Matrix coverage gaps against v3 (section 1) are misses, not wrong answers; adding rows
  is a separate decision.
- The battery's numeric check still skips matrix symbols (`tools/refine_identity_scoreboard.py`,
  owned by engine). `refine_fuzz.mat_points` and `mat_compare` could be reused there.
