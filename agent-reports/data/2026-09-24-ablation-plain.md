# Row ablation of the four plain-rules families (2026-09-24)

Measured with `tools/refine_ablate.py <family>` on branch `ri/trim` after
merging `origin/refine-identities` at `29dfcf1` (the checker's fixes to
`integer_funcs` and `combinatorial` and the branch-cut engine included).
SymPy at `/home/tilo/orion/sympy`. No family module was changed in a
commit. Every merge below was measured by editing the module in the
worktree, running `refine_ablate.py <family> --compare-to <baseline>`, and
reverting.

Gates (a change passes only if none moves):

1. battery: the family's cases of `battery_v3.py`, classified as
   `refine_identity_scoreboard.py` does; no "same"/"other" case may become
   anything else, no "quiet" case may fire, no "wrong" or "crash";
2. tests: `test_<family>.py` and `test_engine_<family>.py`; every passing
   test still passes, except `test_table_size*` (asserts the row count);
3. soundness: the inputs of `refine_differential.py --seed 2 --cases 400`
   that contain one of the family's heads, checked with its edge points; no
   new unsound result, crash or timeout.

"Needed" means removing the row alone breaks gate 1 or 2; the number of
battery cases and tests that row alone keeps is given.

## matrices (31 rows)

Baseline: battery same 50, miss 3, quiet 53; tests 148 passed, 1 xfailed.
Gate 3 has no inputs: the fuzz grammar generates no matrix expressions, and
the battery's numeric check skips matrix symbols, so no gate checks matrix
rows numerically.

Test counts from the first run at `2fb1ff7` (tests run for every row);
the run at `29dfcf1` gives the same verdict for every row.

| row | kept by (battery cases / tests) |
|---|---|
| 0 `Z.T -> 0` | 1 / 1 |
| 1 `A.T -> A` symmetric | 4 / 4 |
| 2 `(A*M*A).T` | 1 / 1 |
| 3 `(N.T*M*N).T` | 1 / 1 |
| 4 `(A*B).T` diagonal | 1 / 1 |
| 5 `A**-1 -> A.T` orthogonal | 0 / 2 |
| 6 `A.T**-1 -> A` | 2 / 2 |
| 7 `A**-1 -> Adjoint(A)` unitary | 1 / 1 |
| 8 `(A*B)**-1` unitary | 1 / 1 |
| 9 `det -> 0` | 2 / 2 |
| 10 `det -> 1` unit triangular | 1 / 1 |
| 11 `Trace -> 0` | 1 / 1 |
| 12 `Z + R -> 0` both zero | 0 / 1 |
| 13 `Z + R -> R` | 2 / 2 |
| 14 `A - A -> 0` | 0 / 1 |
| 15 Hadamard zero | 2 / 2 |
| 16 `c*Z` zero scalar | 1 / 1 |
| 17 `Z*W` zero left | 1 / 1 |
| 18 `V*Z` zero right | 1 / 1 |
| 19 `A.T*A -> I` | 3 / 4 |
| 20 `A*A.T -> I` | 3 / 3 |
| 21 `Adjoint(A)*A -> I` real unitary | 1 / 1 |
| **22 `A*Adjoint(A) -> I` real unitary** | **0 / 0: droppable, gate 3 clean** |
| 23 `Adjoint(A)*A -> I` unless orthogonal | 2 / 2 |
| 24 `A*Adjoint(A) -> I` unless orthogonal | 1 / 1 |
| 25 `A**-1*A -> I` | 0 / 1 |
| 26 `A*A**-1 -> I` | 0 / 1 |
| 27 `A*A -> A**2` | 0 / 2 |
| 28 `Z[i, j] -> 0` | 2 / 2 |
| 29 diagonal off-diagonal element | 2 / 5 |
| 30 symmetric element swap | 5 / 1 |

Single droppable: row 22. Largest removable set: {22} (31 -> 30).
Row 22 is droppable only because nothing tests it: it mirrors row 21
(`X*Adjoint(X)` for a real orthogonal `X`, where row 24's guard refuses),
and removing it loses that rewrite. It points to a missing test, not a
redundant row.

## integer_funcs (23 rows)

Baseline: battery same 67, quiet 31; tests 131 passed; gate 3: 38 inputs
touch the family, 4 fire, none unsound.

| row | kept by (battery cases / tests) |
|---|---|
| 0 `F(x) -> x` (floor, ceiling) | 6 / 4 |
| 1 `floor(n + x)` | 4 / 2 |
| 2 `floor(floor(y) + x)` | 2 / 1 |
| 3 `floor(ceiling(y) + x)` | 0 / 1 |
| **4 `floor(x) -> 0`, 0 <= x < 1** | **0 / 0: droppable, gate 3 clean** |
| 5 `ceiling(n + x)` | 2 / 1 |
| 6 `ceiling(floor(y) + x)` | 0 / 1 |
| 7 `ceiling(ceiling(y) + x)` | 0 / 1 |
| **8 `ceiling(x) -> 0`, -1 < x <= 0** | **0 / 0: droppable, gate 3 clean** |
| 9 `frac(x) -> 0` | 2 / 1 |
| 10 `frac(n + x)` | 2 / 1 |
| 11 `frac(floor(y) + x)` | 0 / 1 |
| 12 `frac(ceiling(y) + x)` | 2 / 1 |
| 13 `frac(x) -> x` | 2 / 1 |
| 14 `Mod -> 0` multiple | 8 / 5 |
| 15 `Mod -> b/2` | 2 / 3 |
| 16 `Mod(c + x, b)` | 4 / 2 |
| 17 `Mod -> a` in the period | 4 / 2 |
| 18 `Mod -> Rem` same signs | 2 / 2 |
| 19 `Rem -> 0` multiple | 7 / 3 |
| 20 `Rem -> b/2` | 2 / 2 |
| 21 `Rem -> -b/2` | 2 / 2 |
| 22 `Rem -> a` | 8 / 6 |

(The test counts come from the first run at `2fb1ff7`, which ran the tests
for every row; the run at `29dfcf1` stops at the battery when it already
keeps the row. The verdicts are the same in both runs except rows 4 and 8.)

Single droppable: rows 4, 8. Largest removable set: {4, 8} (23 -> 21),
gate 3 clean. At `2fb1ff7` both were needed; since the branch-cut merge
the dispatcher's fallback for `floor`/`ceiling`, `_simple.floor_of_bounded`
(interval arithmetic over the stated bounds and sign facts), gives the
same `0` for every case they served, both spellings of `x < 1` included.
Row 17 (`Mod -> a`) is not covered by chaining through row 18 (`Mod ->
Rem`) and row 22: `ask` does not derive `Q.positive(b)` from `0 <= a < b`.

## combinatorial (16 rows)

Baseline: battery same 64, miss 3 (the three `~Q.integer`-only cases the
checker made need `Q.finite`), quiet 40; tests 112 passed; gate 3: 19
inputs, 6 fire, none unsound.

| row | battery cases it alone keeps |
|---|---|
| 0 `G(x, k) -> 1`, k = 0 (binomial, rf, ff) | 9 |
| 1 `G(x, k) -> x`, k = 1 | 3 |
| 2 `factorial -> 1` at 0, 1 | 5 |
| 3 `factorial -> zoo` | 2 |
| 4 `gamma -> factorial(x - 1)` | 3 |
| 5 `gamma -> zoo` | 5 |
| 6 `binomial(n, n) -> 1` | 3 |
| 7 `binomial(n, n - 1) -> n` | 1 |
| 8 `binomial -> 0` | 9 |
| 9 `binomial -> zoo` | 1 |
| 10 `rf(1, k) -> k!` | 2 |
| 11 `rf -> 0` | 4 |
| 12 `rf -> gamma ratio` | 4 |
| 13 `ff(k, k) -> k!` | 2 |
| 14 `ff -> 0` | 2 |
| 15 `ff -> factorial ratio` | 5 |

Every row is needed by battery cases of its own (the first run, at
`2fb1ff7`, also found each row needed by 1 to 4 of its own tests). No
single row is droppable; largest removable set: none (16 rows).
Row 10 is not covered by row 12 (`rf(x, k)` with `x = 1`): `ask` does not
derive `Q.positive(x)` from `Q.eq(x, 1)`. Row 13 is not covered by row 15:
its cases (`ff(x, k)` under `Q.integer(k) & Q.eq(x, k)`) do not make `x`
provably nonnegative.

## minmax_deltas (13 rows)

Baseline: battery same 65, quiet 23; tests 120 passed; gate 3: 46 inputs,
20 fire, none unsound.

| row | battery cases it alone keeps |
|---|---|
| 0 `Max(a, b) -> a` by signs | 10 |
| 1 `Max(a, b) -> a` by relation, unless infinite | 5 |
| 2 `Min(a, b) -> a` by signs | 9 |
| 3 `Min(a, b) -> a` by relation, unless infinite | 5 |
| 4 `DiracDelta(x) -> 0` | 5 |
| 5 `DiracDelta(x, r) -> 0` | 1 |
| 6 `DiracDelta(c*x)` scaling | 7 |
| 7 `KroneckerDelta(i, j) -> 0` | 6 |
| 8 `KroneckerDelta(i, j, r) -> 0` | 1 |
| 9 `KroneckerDelta(i, j) -> 1` | 4 |
| 10 `Heaviside -> 1` | 3 |
| 11 `Heaviside -> 0` | 2 |
| 12 `Heaviside -> H0` | 4 |

Every row is needed by battery cases of its own (and, in the first run, by
1 to 7 of its own tests). No single row is droppable; largest removable set:
none (13 rows). Rows 4/5 and 7/8 are the same rule at two arities: the
matcher has no variadic head pattern, so each arity is its own row.

## Merges (measured, then reverted)

Each proposal was written into the module in the worktree, measured with
`refine_ablate.py <family> --compare-to` against the family's baseline at
`29dfcf1` (all three gates), and reverted. "PASS" means no battery case,
test or fuzz input moved; the only failing test is `test_table_size*`,
which asserts the old count. The battery gave identical outputs for every
case (no "changed output" lines).

| family | proposal | rows | result |
|---|---|---|---|
| integer_funcs | **A**: `floor`/`ceiling` integer-shift rows as one shared generic-head list `SHIFT = [(F(n + x), n + F(x), Q.integer(n)), (F(floor(y) + x), floor(y) + F(x), Q.finite(y)), (F(ceiling(y) + x), ceiling(y) + F(x), Q.finite(y))]`, used as `ROUNDING + SHIFT + [F4]` by both tables | 6 -> 3 | with B: PASS |
| integer_funcs | **B**: `Mod -> 0` and `Rem -> 0` (same hypothesis `Q.nonzero(b) & Q.integer(a/b)`) as one generic two-argument row `(G(a, b), 0, ...)` at the head of both tables | 2 -> 1 | with A: PASS (23 -> 19) |
| integer_funcs | **A + B + drop rows 4, 8**: `FLOOR = CEILING = ROUNDING + SHIFT` (F4 left to the `floor_of_bounded` fallback) | | PASS (23 -> 17) |
| matrices | **C**: `(Z*W, 0, Q.zero(Z))` and `(V*Z, 0, Q.zero(Z))` as one row `(Z*W, ZeroMatrix(m, s), Q.zero(Z) \| Q.zero(W))` | 2 -> 1 | PASS (31 -> 30); gate 3 has no matrix inputs |
| matrices | **C + drop row 22** | | PASS (31 -> 29); see the caveat on row 22: add a test for `X*Adjoint(X)` under `Q.orthogonal(X) & Q.real_elements(X)` rather than drop it |

Not merged, and why (no measurement, the reason is structural):

* `combinatorial`: no two rows share a right side and a head class that a
  generic head could serve with one hypothesis (`rf(1, k)` and `ff(k, k)`
  both give `k!`, but under hypotheses that differ by head); the pole rows
  of `factorial` (n < 0) and `gamma` (x <= 0) differ at 0.
* `minmax_deltas`: `Max`/`Min` sign and relation rows cannot share one row:
  the relation row's `unless` (known infinite) would block the sign row's
  infinite-endpoint cases, and `~Q.infinite` as a hypothesis is not provable
  for a plain symbol. Rows 4/5 and 7/8 differ only in arity.
* `matrices`: the mirrored pairs (19/20, 23/24, 25/26) need a matcher that
  knows `(A*B).T = B.T*A.T`; the unitary rows 21/23 cannot share one row
  (`unless Q.orthogonal(A) & ~Q.real_elements(A)` is undecided for a complex
  orthogonal `A` and would let the unsound case through).

## Rows that exist only for a prover gap

`integer_funcs` rows 2, 3, 6, 7, 11, 12 (`floor`/`ceiling`/`frac` of
`floor(y) + x` and `ceiling(y) + x` under `Q.finite(y)`). `ask` proves
`Q.integer(floor(y))` for real `y` (so the plain shift rows 1, 5, 10 cover
real `y` already), but for a merely finite `y`, `floor(y)` is a Gaussian
integer and SymPy has no predicate for it: `ask(Q.integer(re(floor(y))),
Q.finite(y))` and the same for `im` are `None`. With a Gaussian-integer fact
(or `Q.integer(re(n)) & Q.integer(im(n))` provable for floor/ceiling of a
finite argument) the shift rows' hypotheses could read `Q.integer(n) |
gaussian_integer(n)` and the six rows would go: 17 -> 13 on top of the
merges above (not measurable without the prover change). Of the six, rows
3, 6, 7 and 11 are kept only by the family's own one-case-per-row tests; no
battery case exercises them.

## Summary

| family | rows | single droppable | largest removable set | with measured merges |
|---|---|---|---|---|
| integer_funcs | 23 | 4, 8 | {4, 8}: 21 | 17 |
| combinatorial | 16 | none | none: 16 | 16 |
| minmax_deltas | 13 | none | none: 13 | 13 |
| matrices | 31 | 22 (untested, not redundant) | {22}: 30 | 30 (29 with row 22) |

Run time per family (single-row pass, gates 1 and 2 plus gate 3 on
candidates, one worker at a time on a shared machine): matrices 2.5 min,
integer_funcs 4 min, combinatorial 20 min, minmax_deltas 23 min.
