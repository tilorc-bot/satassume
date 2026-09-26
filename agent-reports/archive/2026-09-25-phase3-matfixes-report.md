# Phase 3: matrix fixes (ri/matfixes)

Branch `ri/matfixes` from f7e85d7 (refine-identities head). origin/refine-identities had no new commits at the merge. Code commits 5027d87, 25c8656; gated at **25c8656**.

## Cases

| case | cause | fix | status |
|---|---|---|---|
| B11 `HadamardProduct(X, X)` ValueError | `_engine._match` built the rest of `Z + R` / `HadamardProduct(Z, R)` as `[g for g in args if g is not t]`, which drops every copy of a repeated atom; `HadamardProduct()` raises. | Matcher removes the bound argument **by position**. Same change in the other "one and the rest" forms that had the same identity filter: `c*Z` over `MatMul` (`MatMul(c, c, X)` lost both `c`), `Max(a, b)` of any arity, two-symbol `Add`/`Mul` (`Add(x, x, evaluate=False)` gave rest `0`). `Max`/`Min` fold duplicates on construction and `MatAdd`/evaluated `Add` combine them, so only Hadamard and unevaluated `Add`/`Mul`/`MatMul` reached the bug. The partition and `n*unit + r` forms filter by value and treat equal terms equally: unchanged. | fixed; `tests/refine_identities/test_matrices_hadamard_duplicate.py` (+ a matcher test for the four forms) |
| `MatAdd(X)` TypeError | Same code: a one-term `MatAdd` has an empty rest, `MatAdd()` is `GenericZeroMatrix`, whose `.shape` raises in `_bind_matrix`. | `Z + R` needs a non-empty rest (skip). New row `MatAdd(Z) -> ZeroMatrix(m, q)` if `Q.zero(Z)`. No unwrap row `MatAdd(Z) -> Z`: tests/refine expects `MatAdd(X)` kept when nothing is known (as `handlers` does). | fixed; `test_matrices_matadd_single_term.py` |
| `MatMul(X.T, 2, X)` / `MatMul(X, 2, Y)` | A run of adjacent matrix factors may not contain a scalar, and nothing puts scalars in front. | Canonical row `c*Z -> c*Z` (MATMUL, last); the `c*Z` match now rebuilds its right side with `doit(deep=False)`, so it fires exactly when the product is not canonical (`rule_handler` requires `out != expr`). `X.T*2*X -> 2*X.T*X -> 2*I` under orthogonal. | fixed; `test_matrices_matmul_scalar_factor.py` |
| `X[i, j]` index order under symmetric/diagonal | The swap row oriented by `Q.gt(i, j)`, which `ask` cannot decide for symbolic indices. SymPy's order is structural: keep `A[i, j]` when `(i - j).could_extract_minus_sign()`. | New `matrices._SwappedOrder(i, j)`, a `BooleanFunction` that evaluates on construction (i.e. when the row's binding is substituted) and stays unevaluated for the row's own index variables (`_Index` symbols). True only when `i - j` has no minus sign **and** `j - i` has one, so no swap back and forth. It never reaches `ask`, so no backend sees it. Numeric indices orient as before. | swaps fixed; `test_matrices_matrixelement_index_order.py` |
| `A[i, j] -> 0` under `Q.diagonal(A) & Q.ne(i, j)` | Deliberate refusal: SymPy keeps negative indices (`A[-1, 0]` stays `MatrixElement(A, -1, 0)` and means the last row once `A` is explicit), so `i != j` does not make the element off-diagonal (`i=-1, j=2`, 3x3). | None. Needs a decision that symbolic indices are nonnegative, not an engine change. | left: `needs/test_default_matrixelement_ne_wrapping.py` (renamed from `test_default_matrixelement_index_order.py`), strict xfail `test_refine_matrix_element.py::test_diagonal_element_with_independent_symbols_ne` points at it |

Files: `satrefine/handlers_identities/_engine.py` (matcher only, 4 hunks: positions instead of identity; REBUILD on the `c*Z` form), `satrefine/handlers_identities/matrices.py` (30 -> 32 rows, `_SwappedOrder`, docstring). Matrices have no generated table, so nothing to regenerate.

Tests: `tests/refine_identities/test_matrices.py`: 9 new positive cases (swaps, scalar to front, one-term sum, Hadamard duplicate), negatives adjusted (`X[i, j]` under diagonal now swaps; `X[j, i]`, `X[i, 2*i]`, `X[0, i]` kept; `MatAdd(X)` kept), the strict xfail `test_symmetric_element_symbolic_order` now a plain test, table size 32. tests/refine: 7 default_xfail markers removed (verifier_matrix x3, matrix_matadd x2, test_refine `test_matrixelement_symbolic_swap`, SymPy suite `test_matrixelement`); `test_diagonal_element_with_independent_symbols_swap_and_ne` split into a passing swap test and the xfail ne test.

## Gates

`.claude/gates/matfixes-25c8656{,.log}` against `a67-merged-f7e85d7`, PYTHONHASHSEED=0, JOBS=10 SLOTS=11 SUITE_WORKERS=4, 819 s.

| section | baseline | matfixes |
|---|---|---|
| suite | 66 failed, 2516 passed, 30 xfailed | 50 failed, 2556 passed, 29 xfailed; all 50 in needs/, none mine except the kept `ne_wrapping` (1) |
| scoreboard generated / live | matrices same 50, miss 3; total same 1032, miss 13 | matrices same 53, miss 0; total same 1035, miss 10; wrong 0, crash 0 in both modes; family rows 75 -> 88 lines (matrices) |
| matrix differential gen / live, seed 2 | identities fired 419, crash 3, unsound 0; only-v3-fires 56 | fired 430, **crash 0**, unsound 0; only-v3-fires 45; both-fire-different 104 (96 equal, 0 different, 8 undecided) |
| differential seeds 2, 3, 7 gen/live; satassume seed 2 | | identical (timing lines only) |
| ext differential gen / live | identities timeout 3 | timeout 5, unchanged 685 -> 683 (load-dependent timeouts, see the fuzz-ext report); unsound, crash unchanged |
| termination / full fixpoint | 8 passed / 3 passed 1 skipped | same |

tests/refine (own run, -n 4): before (f7e85d7) 419 passed, 46 skipped, 36 xfailed; after 427 passed, 46 skipped, 29 xfailed.
tests/refine_v3: 1 failed, 1004 passed both before and after (`test_complex_parts.py::test_arg_of_exp_needs_the_principal_range`, pre-existing).

## Open

- `A[i, j]` under diagonal and `Q.ne(i, j)`: needs a decision on symbolic negative indices (above).
- `HadamardProduct(X)` (one term) under `Q.zero(X)` stays unchanged (no crash); no row, not requested.
