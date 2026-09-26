# Agent report: phase 3, scalar fixes (track B follow-up)

- **Date:** 2026-09-25 to 2026-09-26
- **Branch:** `ri/fixes` (from `f7e85d7`), worktree `.claude/worktrees/ri-fixes`. `origin/refine-identities` had no new commits when the gates started; the coordinator merged ri/matfixes (`3bf5543`) during the gate run and re-gates the combination.
- **Status:** done. 11 of the 12 scalar needs files pass and moved out of `needs/`. One case is left as a needs test: `(x**y)**z -> Abs(x)**(y*z)` for real `x`, even `y` (section 2.3). Inconsistent assumptions: B9's behaviour is kept and documented (section 2.9). The fuzz coverage line is fixed.
- **Files:** `trig.py`, `hyperbolic.py`, `power_exp_log.py`, `complex_parts.py`, `integer_funcs.py`, `combinatorial.py`, `minmax_deltas.py`, `inverse.py`, `_engine.py` (`rule_handler` only), the generated tables (only their derivation comments changed), `tools/refine_fuzz.py` (one line), and tests. `matrices.py` and the matrix code in `_match` were not touched.

## 1. Summary per case

| case (needs file) | cause | fix | status |
|---|---|---|---|
| odd_half_pi_sign_form (8) | three separate causes, see 2.1 | row forms, `by_binding`, a `Mul` row for powers of -1, shifted-parity rows | fixed |
| neg_one_power_exponent (5) | no row for SymPy's `(-1)**((-1)**x/2 + c)` case | 1 `Pow` rule | fixed |
| pow_of_pow: `sqrt(1/x)` | the positive-base rule needed `a > 0` | 1 `Pow` rule: `b > 0`, `a` real | fixed |
| pow_of_pow: `(x**y)**z` | guard `a > 0 or b != 0` | none; would be wrong at `x = 0`, `y < 0`, `z = oo` in SymPy's arithmetic | **left open** |
| floor_ceiling (5) | the infinite row needed `extended_real`; `ask` cannot show that `ceiling(x)` is an integer | row relaxed to `Q.infinite`; new rounded-term shift row | fixed |
| arg_of_zero (1) | `arg` had no zero row | `arg` uses the shared zero row | fixed |
| infinite_arguments (9) | no `factorial(oo)` row; the order vocabulary needs `y` extended real | 1 factorial row, 4 Max/Min rows | fixed |
| hyperbolic_i_pi_shift (4) | the hypotheses required the residue mod 4 (v3's scope) | hypotheses `Q.even(m)` / `Q.odd(m)`, symbolic sign | fixed |
| rem_zero_dividend (1) | no row | `Mod`/`Rem(0, b) = 0` row | fixed |
| inconsistent_assumptions (2) | B9 returns the input | **kept**; the test now documents it | decided, 2.9 |
| B10 fuzzext_acsch_infinite (14) | `im(Abs(w)) = 0` made the off-cut-lines disjunct hold at infinite `w` | `Q.finite` on that disjunct | fixed |
| `refine_fuzz.py` matrix coverage | compared the env var with `handlers_identities` | compares `satrefine.HANDLERS_PACKAGE` | fixed |

## 2. Cases

### 2.1 Sign form at odd multiples of pi/2 (highest priority)

SymPy expects `cos(x + n*pi/2) -> (-1)**((n + 1)/2)*sin(x)` for odd `n`. Identities gave `-(-1)**(n/2 + 3/2)*sin(x)`. There were three separate causes.

1. **Row form.** The `cos` and `sec` odd rows had `-(-1)**((n - 1)/2)`. The rational-constant rule reduces `-1/2` to `3/2`, and the leading minus stays. The rows now read `(-1)**((n + 1)/2)*sin(r)` and `(-1)**((n + 1)/2)*csc(r)`. The value is the same. `sin` and `csc` already gave SymPy's `(-1)**((n + 3)/2)`.
2. **Row order.** `sec(x + (2*n + 1)*pi/2)` under `Q.integer(n)` gave `-(-1)**n*csc(x)`. The rule handler tries every binding of one row before it tries the next row. So the even row fired first on the single term `2*n`, and `sec(x + pi/2)` then auto-evaluated to `-csc(x)`. The odd row never got to see the whole coefficient `2*n + 1`.
   - **Engine change** (`_engine.rule_handler`, local): a new keyword `by_binding=False`. With it, consecutive rows with the same left side form a group, and each binding is tried against every row of the group. The first binding that any row fires on wins.
   - `trig` and `hyperbolic` use it, so the whole coefficient is tried under both parities first.
   - The groups are rebuilt from `rows` on each call, because `tools/refine_ablate.py` edits that list in place.
   - Tables without the keyword run exactly as before.
3. **Products of powers of -1.** Several shifts gave `(-1)**n*(-1)**(m/2 + 1/2)`, and SymPy does not combine these. New `Mul` rule in `complex_parts`: `(-1)**a*(-1)**e -> (-1)**(a + e)`, with hypothesis `true`. It is exact because `(-1)**a = exp(I*pi*a)` for every complex `a`.

Then `test_trig`'s v3 rows `cos(x + k*pi/2)` under `Q.odd(k) & Q.even((k - 1)/2)` lost their collapse to `-sin(x)`:
- the exponent is now `k/2 + 1/2`;
- `ask` does not derive a parity of `k/2 + 1/2` from one of `k/2 - 1/2`.

Two `Pow` rules fix this: `(-1)**x -> -1` under `Q.even(x - 1)` and `-> 1` under `Q.odd(x - 1)`.

### 2.2 `(-1)**((-1)**x/2 + c)`

This is SymPy's continuation case (`test_pow1`, `test_pow2`). For integer `x`, `(-1)**x/2` is `+-1/2`, and `(-1)**(a - 1) = -(-1)**a`. So `(-1)**((-1)**x/2 + r) = (-1)**(x + r + 1/2)`.

- The new rule has hypothesis `Q.integer(x) & Q.integer(r + 1/2)`.
- The identity holds for every `r`. The hypothesis limits the rule to SymPy's case, so a plain `(-1)**((-1)**x/2)` is not turned into `(-1)**(x + 1/2)`.
- The existing mod-2 rule then reduces the constant.

### 2.3 Powers of powers

- **`sqrt(1/x)`, `x > 0`: fixed.** New rule `((b**a)**e, b**(a*e), Q.positive(b) & Q.real(a))`. It holds because `a*log(b)` is real. The old rule needed `a > 0`.
- **`(x**y)**z` for real `x`, even `y`: left as `needs/test_default_pow_of_pow.py`, with the strict xfail `test_refine_pow.py::test_nested_power_even_inner`.**
  - The existing row `(b**a)**e -> Abs(b)**(a*e)` needs `Q.positive(a) | ~Q.zero(b)`, and the test states neither.
  - Without the guard the row is wrong at `x = 0`, `y < 0`, `z = oo`: SymPy evaluates the input `zoo**oo` to `0` and the output `0**(-oo)` to `zoo`. A grid check found this.
  - It is also unevaluable at complex `z`: `zoo**(1 + I)` stays unevaluated, while `0**(-2 - 2*I)` is `nan`.
  - To fire here, the rule needs `x != 0`, `y > 0` or a finite `z` from the assumptions, or a SymPy where `zoo**oo` is not `0`.
  - This is not an engine limitation, so no large change would help. SymPy's own `refine_Pow` does not do this rewrite either (only for a `Rational` outer exponent).

### 2.4 floor / ceiling (SymPy's test_floor_ceiling)

- **`floor(x) -> x` for infinite `x`.** Row F1/F2 required `Q.infinite(x) & Q.extended_real(x)`. It now requires `Q.infinite(x)`. SymPy gives `floor(zoo) = zoo`, `floor(oo*I) = oo*I` and `ceiling(-oo*I) = -oo*I`.
- **`ceiling(ceiling(x) + y + floor(z))` with no assumptions.** `ask` cannot show `ceiling(x)` to be an integer. For complex `x` it is a Gaussian integer, and for infinite `x` it is `x`.
  - New row `(F(g + x), F(x) + g, true)`, where `g = part('g', ...)` binds the terms that are an integer times a `floor` or `ceiling`. Only `floor` and `ceiling` get it; `frac` does not (`frac(oo)` is `AccumBounds`).
  - At finite points it is exact.
  - At an infinite rounded term the left side is an infinity that absorbs the rest. Only at `g = +-oo*I` do the two sides differ, and only in the finite real part attached to the directed infinity: `floor(1/2 + oo*I)` stays `1/2 + oo*I`, while the right side is `oo*I + floor(1/2)` = `oo*I`. As points of the extended plane they are the same. SymPy's own test expects this rewrite with no assumptions.
  - `test_integer_funcs` had `floor(x + floor(y)), True` as a v3 refusal. It is now a positive row.

### 2.5 `arg(0)`

`arg` had its own rule table without the shared zero row ("arg(0) is nan"). SymPy's `arg(0)` is `nan`, which is exactly what the input is at 0, so `arg` now uses the shared `_rules` with the zero row.

### 2.6 Infinite arguments

- **`factorial`:** new row `(factorial(n), oo, Q.positive_infinite(n))`.
- **`Max` / `Min`:** four rules, chained before the definitions: `Max(a, b) -> a` for `a = +oo` and `-> b` for `a = -oo`, and the mirror for `Min`. The pair pattern keeps any other arguments.
  - The Piecewise definition decides `Q.ge(x, y)` from an infinite `x` only when `y` is extended real, which a plain `y` is not.
  - SymPy's `Max` is defined only at extended real arguments (`Max(oo, I)` raises), so the rows are exact wherever the input has a value.
  - `test_minmax_deltas` refused `Max(x, y)` under `Q.positive_infinite(x)` ("y may not be real"). It is now a positive row.
  - Where both arguments are the same infinity, the result is the other symbol, which has the same value. Three tests accepted `oo`/`x` there and now also accept `y`.

### 2.7 Hyperbolic `x + n*I*pi`

v3 fires only when the residue of the coefficient mod 4 is known. SymPy and the old `handlers` give `(-1)**n*sinh(x)` for integer `n`.

- The hypotheses are now `Q.even(m)` and `Q.odd(m)`, and the sign stays symbolic, as in the trig table. This follows the "exact rows with a symbolic sign" noted in the module docstring, which is updated.
- Odd `m` now also fires: `sinh(x + k*pi*I/2) -> I*(-1)**(k/2 + 3/2)*cosh(x)`.
- `test_hyperbolic` marks both as `extra`.

### 2.8 `Rem(0, q)`

New row `(G(a, b), 0, Q.zero(a))` in `MULTIPLE`, shared by `Mod` and `Rem`. At `b = 0`, `+-oo` and `zoo` the input is undefined or `nan`.

### 2.9 Inconsistent assumptions: kept B9's behaviour

The needs test asked for `ValueError`. What SymPy does:
- SymPy's `refine` lets `ask`'s `ValueError` through, but only when a handler asks a question that exposes the contradiction: `refine(x + 1, Q.positive(x) & Q.negative(x))` returns `x + 1`, while `refine(sin(x), ...)` raises.
- SymPy's `test_refine.py` has no case with inconsistent assumptions; its `ValueError` is tested only for `ask`.

So there is no SymPy test expectation to match, and I kept B9. The reasons:
- whether an error occurs would depend on which questions the engine happens to ask, and the satassume backend detects other contradictions than SymPy's;
- every result is correct under inconsistent assumptions;
- nested calls still see the error, so a case split still drops an inconsistent branch.

Changes:
- The needs test became `tests/refine_identities/test_default_inconsistent_assumptions.py`. It checks that the input is returned under all three backends, for the two cases and `gamma(n)` under `Q.infinite(n) & Q.integer(n)`, and its docstring gives the reasons.
- `tests/refine`'s `test_inconsistent_assumptions_raise_pre_existing_engine_error` is now pinned to `handlers`. It was a strict xfail.

### 2.10 B10: `acsch(csch(Abs(z)))` at infinite `z`

The domain was `~Q.zero(z) & (Q.real(z) | ~Q.integer(im(z)/pi + 1/2))`. For `z = Abs(w)`, SymPy builds `im(Abs(w)) = 0`, so the second disjunct held for an infinite `w`. There `acsch(csch(oo)) = acsch(0) = zoo`, but the output was `oo`.

- The domain is now `~Q.zero(z) & (Q.real(z) | Q.finite(z) & _OFF_CUT_LINES)`. `Q.real` stays a disjunct of its own because the bounds decide it (`Q.gt(x, 1) & Q.lt(x, 3)` proves `Q.real` but not `Q.finite`); `test_engine_bounds_infinity` caught the first version, which put `Q.finite` on the whole row.
- The other three rows on `_OFF_CUT_LINES` (`asinh`, `atanh`, `acoth`) hold at `+-oo`.
- All 14 cases of the test pass, both modes and both backends.

### 2.11 `tools/refine_fuzz.py`

Matrix-row coverage now checks `satrefine.HANDLERS_PACKAGE == "handlers_identities"`, so a run on the default package counts coverage.

## 3. Verification

- **Grid check of every new row** (a scratch script: every point of `{0, +-1, +-2, +-3, 1/2, -3/2, 5/2, +-I, 1 + I, 2*I, 7/3, oo, -oo, zoo, +-oo*I}` per symbol where the hypothesis holds; left and right side compared, points where the input is `nan` skipped).
  - No mismatch except the ones described in 2.3 and 2.4.
  - Points checked: sign rows 80 each; `(-1)` merge 372; continuation 21; positive-base power 1,320; hyperbolic rows 56 to 72 each; Max/Min 19 each.
  - One `AccumBounds` comparison artefact for `csch` at `m = 0`, where both sides are identical.
- **Generated tables:** regenerated twice with the full fixpoint (`tools/refine_specialize.py --write`, 80–89 s). No generated rule changed; only the derivation comments did (for example, `asks` now lists `Q.integer(-1)`). Committed.
- **Suites (PYTHONHASHSEED=0, each directory in its own process):**

| suite | before (default report / f7e85d7) | after |
|---|---|---|
| tests/refine (default = handlers_identities) | 419 passed, 36 xfailed, 46 skipped | 444 passed, 11 xfailed, 47 skipped, 0 failed |
| tests/refine, `SATREFINE_HANDLERS=handlers` | 492 passed, 9 xfailed | 493 passed, 9 xfailed |
| tests/refine_v3 | 1004 passed, 1 failed | 1004 passed, 1 failed (the same pre-existing `test_arg_of_exp_needs_the_principal_range`) |
| tests/refine_identities | needs: 44 default + 10 hadamard failing | 2591 passed, 30 xfailed, 1920 skipped, 18 failed: only needs tests (matadd 2, matmul 2, matrixelement 3, hadamard 10: the matrix agent's; pow_of_pow 1: mine) |

The 11 xfails left in tests/refine are the matrix cases (matrixelement, matadd, matmul) and `test_nested_power_even_inner`.

## 4. Gates

The gates ran on `16841b8` against `a67-merged-f7e85d7`: output in `.claude/gates/fixes-16841b8{,.log}`, `JOBS=10 SLOTS=11 SUITE_WORKERS=4`, 771 s. Every section exited 0 except the suite, which fails only on needs tests.

| gate | baseline (f7e85d7) | ri/fixes |
|---|---|---|
| suite (tests/refine_identities) | failures: the 44 default needs cases and 10 hadamard | 2591 passed, 30 xfailed, 1920 skipped, 18 failed. All 18 are needs tests: matadd 2, matmul 2, matrixelement 3, hadamard 10 (the matrix agent's), pow_of_pow 1 (mine, section 2.3) |
| scoreboard generated | same 1032, other 41, miss 13, quiet 639, extra 11, wrong 0, crash 0 | same 1032, other 41, miss 13, quiet 620, extra 30, **wrong 0, crash 0** |
| scoreboard live | same 1033, other 40, quiet 639, extra 11 | same 1033, other 40, quiet 620, extra 30, **wrong 0, crash 0** |
| differential seeds 2, 3, 7 (generated and live), satassume seed 2 (both) | | identities fires 2 more per run; unsound, crash and "different" counts unchanged |
| differential ext seed 2 (both modes) | unsound 0, crash 0 | **unsound 0, crash 0**; fired +1, timeouts 4 → 3 (generated), unevaluable points 87 → 100 |
| differential matrices seed 2 (both) | | identical |
| full fixpoint, termination | 3 passed, 1 skipped; 8 passed | identical |

**Changes explained:**

- **Scoreboard: 19 more "extra" (fired where v3 expects unchanged), the same number fewer "quiet".** Each has a numeric check (wrong stays 0). Listed with `--show`:
  - 16 in hyperbolic: `sinh`/`cosh`/`sech`/`csch` of `x + k*pi*I` under `Q.integer(k)` and of `x + k*pi*I/2` under `Q.odd(k)`, in three v3 battery tests each (section 2.7);
  - 1 in complex_parts: `arg(x)` under `Q.zero(x)` gives `nan` (2.5);
  - 1 in integer_funcs: `floor(x + floor(y))` with no assumptions gives `floor(x) + floor(y)`. v3's battery calls it `test_floor_of_infinite_is_not_a_gaussian_integer`; the value agrees at an infinite `y` too (2.4);
  - 1 in minmax_deltas: `Max(x, y)` under `Q.positive_infinite(x)` gives `x` (2.6).
  - "numerically unchecked" 183 → 184.
- **Differential (default family):**
  - identities fires 2 more cases per run;
  - "only v3 fires" drops by 1 or 2 per run, and "both fire, same result" rises by as much, so identities now meets v3 on those cases;
  - "unsound", "crash" and "different" are unchanged.
  - The changed cases, found by refining every case of seeds 2, 3 and 7 with identities alone, at f7e85d7 (extracted with `git archive`) and at this branch, and diffing the results. Six cases change, and all are new firings:
    - seed 2, case 279: `Rem(pi*x*z, x)` under `Q.zero(x)` gives `0`. The input is `Rem(0, 0)`, which is undefined.
    - seed 2, case 625: `sqrt(k**n)` under `Q.ge(k, 1) & Q.nonpositive(n)` gives `k**(n/2)`.
    - seed 3, case 480: `sqrt(1/(m + 1))` gives `1/sqrt(m + 1)`. The assumptions are inconsistent (`Q.positive(m) & Q.lt(m, -pi/2)`).
    - seed 3, case 1362: `(1/(n + 1))**(3/2)` under `Q.nonnegative(n)` gives `(n + 1)**(-3/2)`.
    - seed 7, case 770: `sqrt(1/n)` gives `1/sqrt(n)`.
    - seed 7, case 1114: `(1/(x + 1))**(3/2)` gives `(x + 1)**(-3/2)`.
    
    All but the first come from the positive-base power rule (2.3), and v3 gives the same result for them.
- **Differential ext (`--ext --seed 2 --cases 1000 --show 40`, rerun on this branch to list the cases):**
  - One case newly fires: `Min(sqrt(m), m**3)` under `Q.extended_negative(m) & Q.infinite(m)` gives `m**3`. At `m = -oo` the argument `sqrt(-oo) = oo*I` is not real, so `Min` is undefined there and the points are unevaluable (+13).
  - The "different results" +1 is `Max(m, n, 1/x)` under `Q.infinite(n) & Q.extended_positive(n)`: identities gives `n`, v3 gives `Max(n, 1/x)`. They are equal at all 48 points.
  - The timeout 4 → 3 is one case that finishes now. Identities has 0 unsound results.


**Verdict:** pass.
- The scoreboards have wrong 0 and crash 0.
- No differential section has a new unsound result or crash.
- The suite fails only on needs tests (the matrix agent's, and `pow_of_pow`'s even-inner case).
- Every change is explained above.

## 5. Open items

- `needs/test_default_pow_of_pow.py::test_power_of_even_power_of_real` (section 2.3). It needs a SymPy decision on `zoo**oo`, or assumptions that exclude `x = 0` with `y < 0`, or a finite `z`.
- `by_binding` is used only by `trig` and `hyperbolic`. Other tables with repeated left sides (the `(-1)**(n + r)` parity rows) keep their row-major order.
