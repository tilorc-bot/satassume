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
