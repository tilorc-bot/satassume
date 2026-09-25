# Agent report: phase 3, track D, default switch (handlers_identities becomes the default refine)

- **Date:** 2026-09-25
- **Branch:** `ri/default` (base eb106a6; merged origin/refine-identities at cf34f5f).
- **Status:** done. `SATREFINE_HANDLERS` now defaults to `handlers_identities`. `tests/refine` passes under it with 0 failures: 36 strict xfails, each pointing at one of 12 new needs tests, and 46 skips (tests of `satrefine.handlers` internals). With `SATREFINE_HANDLERS=handlers` the same suite still passes, with 0 failures (it had 3 before). Gates: section 6.

## 1. What changed

| File | Change |
|---|---|
| `satrefine/__init__.py` | `DEFAULT_HANDLERS = "handlers_identities"` (was the literal `"handlers"`); `HANDLERS_PACKAGE` records the package the process loaded. `handlers`, `handlers_v2` and `handlers_v3` stay selectable. |
| `tools/refine_oracle.py` | `--handlers` defaults to the new default. |
| `tests/refine/conftest.py` | Three markers. `handlers(name)` skips a test unless that package is loaded. `default_xfail(needs, reason)` gives a strict xfail under `handlers_identities`. `original_wrong(reason)` gives a strict xfail under `handlers`. An autouse check fails any test that imports a `satrefine.handlers.*` module under another package (section 2). |
| `tests/refine/*.py` (27 files) | The triage in section 4. |
| `tests/refine_identities/needs/test_default_*.py` | 12 needs tests (section 5). |
| `README.md` | The default and the markers. |

What already selected handlers explicitly, and was left unchanged:
- The gates, the differential (`--a handlers_v3 --b handlers_identities`), the identity scoreboard (`--handlers`, default `handlers_identities`), `refine_ablate` and `refine_battery_capture` all name their packages.
- The conftests of `tests/refine_identities`, `tests/refine_v2` and `tests/refine_v3` `setdefault` their own package, so the switch does not touch those suites.

One place follows the env var alone, and I did not change it because ri/fuzz-ext owns the file. `tools/refine_fuzz.py:867` turns matrix-row coverage on only when `SATREFINE_HANDLERS` is literally `handlers_identities`, so a run that relies on the default gets no coverage. The fix is to compare against `satrefine.HANDLERS_PACKAGE`.

## 2. Why the "31" was not the real count, and the counting method

Importing a `satrefine.handlers.<module>` registers that module's handler into the shared `handlers_dict`, over whatever package is loaded. Under `handlers_identities`, three tests in `tests/refine` did this:
- `test_refine_trig_sin_cos.py` at module level;
- `test_refine_trighelper.py`, indirectly;
- `test_refine_harness.py::test_no_duplicate_handler_keys`, which imports all 33 modules.

After any of them ran, the rest of the process ran partly on the old handlers. So whole-directory counts under `handlers_identities` depended on test order:
- one process: 36 failures;
- `-n 2`: 77 failures;
- each file in its own process: 114 failures.

The 31 (34 − 3) from f83f195 was a whole-directory count, so it had this problem too. The counts below run **each file in its own process**. The new autouse check in `tests/refine/conftest.py` makes such an import a test error.

## 3. Counts (each test file in its own process, PYTHONHASHSEED=0, default backend)

| suite | package | before (eb106a6) | after (ri/default) |
|---|---|---|---|
| tests/refine | default | 467 passed, 3 failed, 4 xfailed (`handlers`) | 419 passed, 0 failed, 36 xfailed, 46 skipped (`handlers_identities`) |
| tests/refine | `SATREFINE_HANDLERS=handlers_identities` | 358 passed, **114 failed**, 2 xfailed | as the default row |
| tests/refine | `SATREFINE_HANDLERS=handlers` | as the default row | 492 passed, 0 failed, 9 xfailed |
| tests/refine_v2 | default (its conftest selects handlers_v2) | 160 passed, 1 failed | GATE_V2 |
| tests/refine_v3 | default (its conftest selects handlers_v3) | 1004 passed, 1 failed | GATE_V3 |

The suite has 501 tests after the change, 27 more than before, because multi-assert tests were split. A failing case in a multi-assert test was moved into its own test, so the other asserts keep running.

The pre-existing failures:
- The three in `tests/refine` under `handlers` were wrong expectations (category d, below): `Max`/`Min(x, y)` under `Q.positive(x) & Q.negative(y)` is decided, so the result is `x`/`y`, not unchanged. They pass now.
- The one each in `tests/refine_v2` (`test_relation_rules_do_not_fire_under_the_satassume_backend`) and `tests/refine_v3` (`test_arg_of_exp_needs_the_principal_range`) are unrelated to the default and unchanged.

## 4. Triage

The 114 failures, plus `trig_sin_cos::test_shifts`, which the module-level import had hidden. Categories:
- **a:** tests `handlers` internals: query order, a scripted or all-None `ask` patched into `satrefine._upstream`, module ownership. Pinned with `@pytest.mark.handlers("handlers")`.
- **b:** identities gives an equal or better result. The expectation accepts both results, and the rewrite is checked with `assert_refinement_valid` where it is new.
- **c:** identities is worse. The case gets a strict xfail with a needs test.
- **d:** the old expectation was wrong. It is corrected, with an `original_wrong` strict xfail under `handlers` where `handlers` gives the wrong value.

Totals: a 36, b 28, c 33, d 10, mixed 8 (a+d 1, b+d 3, d+b 2, b+c 2).

The "v3" and "identities" columns show the value of the first differing assert, computed with every assert turned into a soft check (`refine(...)` under each package in its own process). "(+k more)" counts further differing asserts in the same test. Where the columns are empty, the note column describes the case.

| # | test (tests/refine/test_refine_*) | input (first differing case) | v3 | identities | cat | action |
|---|---|---|---|---|---|---|
| 1 | `abs::test_abs_none_safety` | queries[0][0] == Q.zero(x) | `Q.zero(x)` | `Q.positive(x)` | a | pinned `handlers` |
| 2 | `arg::test_arg_documented_divergences` | refine(arg(x), Q.zero(x)) is nan | `arg(x)` | `arg(x)` | c | arg(0) line moved to test_arg_zero (xfail) -> arg_of_zero |
| 3 | `arg::test_arg_zero` | refine(arg(x), Q.zero(x)) is nan | `arg(x)` | `arg(x)` | c | xfail -> needs/test_default_arg_of_zero.py |
| 4 | `conjugate::test_conjugate_integer_power_negative` | refine(conjugate(x ** n), Q.integer(n)) == conjugate(x ** n) | `conjugate(x)**n` | `conjugate(x)**n` | b | accept both |
| 5 | `conjugate::test_conjugate_none_safety` | refine(z * conjugate(z)) == Abs(z) ** 2 (+1 more) | `Abs(z)**2` | `z*conjugate(z)` | a | pinned `handlers` |
| 6 | `conjugate::test_conjugate_real` | refine(conjugate(x), Q.zero(x)) == x | `0` | `0` | b | accept both |
| 7 | `factorial::test_negative_infinite_is_gamma_pole` | refine(factorial(n), Q.negative_infinite(n)) == gamma(S.NegativeInfinity) | `factorial(n)` | `factorial(n)` | b | accept both |
| 8 | `factorial::test_positive_infinite_is_infinity` | refine(factorial(n), Q.positive_infinite(n)) is S.Infinity | `factorial(n)` | `factorial(n)` | c | xfail -> needs/test_default_infinite_arguments.py |
| 9 | `gamma::test_ask_goes_through_upstream` | refine(gamma(n), proposition) is S.ComplexInfinity (+1 more) | `gamma(n)` | `gamma(n)` | a | pinned `handlers` |
| 10 | `gamma::test_non_poles_unchanged` | refine(gamma(n), Q.integer(n) & Q.positive(n)) == gamma(n) | `factorial(n - 1)` | `factorial(n - 1)` | b | accept both |
| 11 | `harness::test_reference_ask_detects_wrong_handler` | patches _upstream.handlers_dict['Abs'] |  |  | a | pinned `handlers` |
| 12 | `hyperbolic_forward::test_integer_shift_with_unknown_parity` | refine(sinh(x + n * I_PI), Q.integer(n)) == (-1) ** n * sinh(x) (+3 more) | `sinh(I*pi*n + x)` | `sinh(I*pi*n + x)` | c | xfail -> needs/test_default_hyperbolic_i_pi_shift.py |
| 13 | `hyperbolic_inverse::test_acosh_cosh_not_nonnegative` | refine(acosh(cosh(x)), Q.real(x)) == acosh(cosh(x)) (+1 more) | `Abs(x)` | `Abs(x)` | b | accept both, numeric check |
| 14 | `hyperbolic_inverse::test_asech_sech_not_nonnegative` | refine(asech(sech(x)), Q.real(x)) == asech(sech(x)) (+1 more) | `Abs(x)` | `Abs(x)` | b | accept both, numeric check |
| 15 | `hyperbolic_inverse::test_none_answers_leave_expression_unchanged` | refine(acosh(cosh(x)), Q.nonnegative(x)) == acosh(cosh(x)) (+1 more) | `acosh(cosh(x))` | `x` | a | pinned `handlers` |
| 16 | `inverse_trig::test_acos_cos_outside_branch` | refine(acos(cos(x)), below) == acos(cos(x)) | `-x` | `-x` | b | accept both, numeric check |
| 17 | `inverse_trig::test_asin_sin_outside_branch` | refine(asin(sin(x)), mirrored) == asin(sin(x)) | `pi - x` | `pi - x` | b | accept both, numeric check |
| 18 | `inverse_trig::test_none_answers_leave_expression_unchanged` | refine(asin(sin(x)), ASIN_RECTANGLE) == asin(sin(x)) (+1 more) | `x` | `x` | a | pinned `handlers` |
| 19 | `inverse_trig::test_only_matching_inner_function` | refine(asin(cos(x)), ASIN_RECTANGLE) == asin(cos(x)) (+1 more) | `asin(cos(x))` | `-Abs(x) + pi/2` | b | accept both, numeric check |
| 20 | `kronecker_delta::test_ask_goes_through_upstream` | [entry[0] for entry in log] == [Q.eq(i, j)] | `[Q.nonzero(i - j), Q.zero(i - j), Q.infinite(i), Q` | `[Q.infinite(i), Q.negative_infinite(i), Q.positive` | a | pinned `handlers` |
| 21 | `kronecker_delta::test_ne_direction_uses_direct_assumption` | [entry[0] for entry in log] == [Q.eq(i, j), Q.ne(i, j)] | `[Q.nonzero(i - j), Q.zero(i - j), Q.infinite(i), Q` | `[Q.infinite(i), Q.negative_infinite(i), Q.positive` | a | pinned `handlers` |
| 22 | `log::test_log_none_safety` | queries[0][0] == Q.real(x) | `Q.real(x)` | `Q.zero(x)` | a | pinned `handlers` |
| 23 | `log::test_log_numeric_oracle` | refined == log(x ** 2) | `2*log(Abs(x))` | `2*log(Abs(x))` | b | accept both |
| 24 | `log::test_log_power_rule_negative_and_guards` | refine(log(x ** 2), Q.real(x)) == log(x ** 2) (+1 more) | `2*log(Abs(x))` | `2*log(Abs(x))` | b | accept both, numeric check |
| 25 | `log::test_log_product_split_negative` | refine(log(x * y), Q.positive(x)) == log(x * y) (+2 more) | `log(x) + log(y)` | `log(x) + log(y)` | b | accept both, numeric check |
| 26 | `log::test_log_reference_ask` | log(x**2), Q.real(x) |  |  | b | accept both |
| 27 | `matrix_det::test_asks_base_matrix` | refine(det(X), Q.orthogonal(X)) == S.One (+1 more) | `Determinant(X)` | `Determinant(X)` | a+d | pinned `handlers` (asserts det = 1) |
| 28 | `matrix_det::test_local_refinement` | refine(det(X), Q.orthogonal(X)) == S.One | `Determinant(X)` | `Determinant(X)` | d | orthogonal case -> original_wrong test |
| 29 | `matrix_det::test_reference_ask_fidelity` | det(X), Q.orthogonal(X): sympy 1 |  |  | d | orthogonal case removed from SymPy parity (SymPy also gives 1) |
| 30 | `matrix_det::test_singular_ask_order` | [entry[0] for entry in log] == [Q.orthogonal(X), Q.singular(X)] | `[Q.singular(X)]` | `[Q.singular(X)]` | a | pinned `handlers` |
| 31 | `matrix_det::test_unit_triangular_ask_order` | [entry[0] for entry in log] == [Q.orthogonal(X), Q.singular(X), Q.unit_triangular(X)] | `[Q.singular(X), Q.zero(X), Q.unit_triangular(X)]` | `[Q.singular(X), Q.positive(2), Q.unit_triangular(X` | a | pinned `handlers` |
| 32 | `matrix_element::test_ask_order` | refine(X[0, 1], Q.diagonal(X)) == S.Zero (+3 more) | `0` | `X[0, 1]` | a | pinned `handlers` |
| 33 | `matrix_element::test_diagonal_element_with_independent_symbols` | refine(A[i, j], Q.diagonal(A)) == A[j, i] (+1 more) | `A[j, i]` | `A[i, j]` | c | 2 lines split out, xfail -> needs/test_default_matrixelement_index_order.py |
| 34 | `matrix_inverse::test_local_refinement` | refine(X.I, Q.unitary(X)) == X.conjugate() | `Adjoint(X)` | `Adjoint(X)` | d | unitary case -> original_wrong test |
| 35 | `matrix_inverse::test_reference_ask_fidelity` | X**-1, Q.unitary(X): sympy Adjoint(X.T) |  |  | d | unitary case removed from SymPy parity (SymPy also wrong) |
| 36 | `matrix_inverse::test_singular_inverse_raises` | X**-1, Q.singular(X): handlers raises ValueError, identities/v3/SymPy leave X**-1 |  |  | a | pinned `handlers` |
| 37 | `matrix_inverse::test_singular_inverse_raises_under_reference_ask` | same |  |  | a | pinned `handlers` |
| 38 | `matrix_matadd::test_none_answers_unchanged` | refine(MatAdd(X), Q.zero(X)) == MatAdd(X) | `X` | `TypeError: GenericZeroMatrix does not have a speci` | c | MatAdd(X) line split out, xfail -> needs/test_default_matadd_single_term.py |
| 39 | `matrix_matadd::test_single_term_sum` | refine(MatAdd(X), Q.zero(X)) == ZeroMatrix(2, 2) (+1 more) | `0` | `TypeError: GenericZeroMatrix does not have a speci` | c | xfail -> needs/test_default_matadd_single_term.py |
| 40 | `matrix_matmul::test_asks_factor` | refine(X.T * X, Q.orthogonal(X)) == MatMul(Identity(2)) | `I` | `I` | a | pinned `handlers` |
| 41 | `matrix_matmul::test_local_refinement` | refine(X.T * X, Q.orthogonal(X)) == MatMul(Identity(2)) (+2 more) | `I` | `I` | b+d | accept Identity(2); unitary case -> original_wrong test |
| 42 | `matrix_matmul::test_reference_ask_fidelity` | X.T*X, Q.orthogonal(X): Identity(2) vs MatMul(Identity(2)) |  |  | b+d | both cases removed from parity (structural; SymPy wrong for unitary) |
| 43 | `matrix_transpose::test_asks_base_matrix` | [entry[0] for entry in log] == [Q.symmetric(X)] | `[Q.zero(X), Q.symmetric(X)]` | `[Q.zero(X), Q.symmetric(X)]` | a | pinned `handlers` |
| 44 | `max::test_ask_goes_through_upstream` | refine(Max(x, y), Q.ge(x, y)) == x (+1 more) | `Max(x, y)` | `Max(x, y)` | a | pinned `handlers` |
| 45 | `max::test_infinite_arguments` | refine(Max(x, y), Q.positive_infinite(x)) == x (+4 more) | `Max(x, y)` | `Max(x, y)` | c | xfail -> needs/test_default_infinite_arguments.py |
| 46 | `max::test_multi_argument_without_single_maximum_unchanged` | refine(Max(x, y, z), Q.ge(x, y)) == Max(x, y, z) (+1 more) | `Max(x, z)` | `Max(x, z)` | b | accept both |
| 47 | `max::test_unmet_assumptions_unchanged` | refine(Max(x, y), Q.positive(x) & Q.negative(y)) == Max(x, y) (+1 more) | `x` | `x` | d+b | x > 0 > y gives x (failed before the switch too); Q.eq: accept both |
| 48 | `min::test_ask_goes_through_upstream` | [entry[0] for entry in log] == [Q.le(x, y)] | `[Q.extended_nonpositive(x), Q.infinite(y), Q.infin` | `[Q.extended_nonnegative(y), Q.extended_nonpositive` | a | pinned `handlers` |
| 49 | `min::test_infinite_arguments` | refine(Min(x, y), Q.negative_infinite(x)) == x (+4 more) | `Min(x, y)` | `Min(x, y)` | c | xfail -> needs/test_default_infinite_arguments.py |
| 50 | `min::test_multi_argument_without_single_minimum_unchanged` | refine(Min(x, y, z), Q.le(x, y)) == Min(x, y, z) (+1 more) | `Min(x, z)` | `Min(x, z)` | b | accept both |
| 51 | `min::test_unmet_assumptions_unchanged` | refine(Min(x, y), Q.positive(x) & Q.negative(y)) == Min(x, y) (+1 more) | `y` | `y` | d+b | x > 0 > y gives y (failed before the switch too); Q.eq: accept both |
| 52 | `mod::test_asks_the_quotient_first` | refine(Mod(p, 1), Q.integer(p)) is S.Zero (+1 more) | `Mod(p, 1)` | `Mod(p, 1)` | a | pinned `handlers` |
| 53 | `mod::test_integer_pair_uses_floor_definition` | refine(Mod(p, q), Q.integer(p) & Q.integer(q)) == expected | `Mod(p, q)` | `Mod(p, q)` | b | accept both (Mod kept, not expanded) |
| 54 | `mod::test_sign_variants_share_the_floor_definition` | refine(Mod(p, q), Q.integer(p) & Q.integer(q) & Q.nonnegative(p) & Q.positive(q)) == expec (+3 more) | `Rem(p, q)` | `Rem(p, q)` | b | accept both (Rem/Mod kept) |
| 55 | `mod::test_unmet_assumptions_unchanged` | refine(Mod(p, 2), Q.positive(p)) == Mod(p, 2) | `Rem(p, 2)` | `Rem(p, 2)` | b | accept both |
| 56 | `pow::test_nested_power_positive_base` | refine(sqrt(1 / x), Q.positive(x)) == 1 / sqrt(x) | `1/sqrt(x)` | `sqrt(1/x)` | c | line split out, xfail -> needs/test_default_pow_of_pow.py |
| 57 | `pow::test_nested_power_real_base_even_inner` | refine((x ** y) ** z, Q.real(x) & Q.even(y)) == Abs(x) ** (y * z) | `(x**y)**z` | `(x**y)**z` | c | line split out, xfail -> needs/test_default_pow_of_pow.py |
| 58 | `pow::test_pow_none_safety` | queries[0][0] == Q.real(x) | `Q.integer(z)` | `Q.integer(y)` | a | pinned `handlers` |
| 59 | `pow::test_pow_vendored_behavior_retained` | refine((-1) ** ((-1) ** x / 2 - S.Half), Q.integer(x)) == (-1) ** x | `(-1)**x` | `(-1)**((-1)**x/2 + 3/2)` | c | line split out, xfail -> needs/test_default_neg_one_power_exponent.py |
| 60 | `rem::test_ask_goes_through_upstream` | refine(Rem(p, q), Q.zero(p)) is S.Zero (+1 more) | `Rem(p, q)` | `Rem(p, q)` | a | pinned `handlers` |
| 61 | `rem::test_opposite_sign_uses_ceiling` | refine(Rem(p, q), Q.integer(p) & Q.integer(q) & Q.nonnegative(p) & Q.negative(q)) == expec (+3 more) | `Rem(p, q)` | `Rem(p, q)` | b | accept both (Rem kept) |
| 62 | `rem::test_same_sign_uses_floor` | refine(Rem(p, q), Q.integer(p) & Q.integer(q) & Q.nonnegative(p) & Q.positive(q)) == expec (+3 more) | `Rem(p, q)` | `Rem(p, q)` | b | accept both (Rem kept) |
| 63 | `rem::test_zero_dividend_is_zero` | refine(Rem(p, q), Q.zero(p)) is S.Zero | `Rem(p, q)` | `Rem(p, q)` | c | xfail -> needs/test_default_rem_zero_dividend.py |
| 64 | `sign::test_sign_none_safety` | refine(sign(x), Q.positive(x)) == sign(x) | `sign(x)` | `1` | a | pinned `handlers` |
| 65 | `test_refine::test_floor_ceiling` | refine(floor(x), Q.infinite(x)) == x (+4 more) | `floor(x)` | `floor(x)` | c | 5 lines split out, xfail -> needs/test_default_floor_ceiling.py |
| 66 | `test_refine::test_matrixelement` | refine(x[i, j], Q.symmetric(x)) == x[j, i] | `x[j, i]` | `x[i, j]` | c | line split out, xfail -> needs/test_default_matrixelement_index_order.py |
| 67 | `test_refine::test_pow1` | refine(sqrt(1 / x), Q.positive(x)) == 1 / sqrt(x) (+3 more) | `1/sqrt(x)` | `sqrt(1/x)` | c | lines split out, xfail -> needs/test_default_pow_of_pow.py, neg_one_power_exponent |
| 68 | `test_refine::test_pow2` | refine((-1) ** ((-1) ** x / 2 - 7 * S.Half), Q.integer(x)) == (-1) ** (x + 1) (+1 more) | `(-1)**(x + 1)` | `(-1)**((-1)**x/2 + 1/2)` | c | lines split out, xfail -> needs/test_default_neg_one_power_exponent.py |
| 69 | `test_refine::test_sin_cos` | refine(cos(x + n * pi / 2), Q.odd(n)) == (-1) ** ((n + 1) / 2) * sin(x) (+4 more) | `(-1)**(n/2 + 1/2)*sin(x)` | `-(-1)**(n/2 + 3/2)*sin(x)` | c | 5 lines split out, xfail -> needs/test_default_odd_half_pi_sign_form.py |
| 70 | `test_sympy_refine_suite::test_floor_ceiling` | floor(x), Q.infinite(x) |  |  | c | xfail -> needs/test_default_floor_ceiling.py (whole SymPy test) |
| 71 | `test_sympy_refine_suite::test_matrixelement` | x[i, j], Q.symmetric(x) |  |  | c | xfail -> needs/test_default_matrixelement_index_order.py (whole SymPy test) |
| 72 | `test_sympy_refine_suite::test_pow1` | sqrt(1/x), Q.positive(x) |  |  | c | xfail -> needs/test_default_pow_of_pow.py (whole SymPy test) |
| 73 | `test_sympy_refine_suite::test_pow2` | (-1)**((-1)**x/2 - 7/2), Q.integer(x) |  |  | c | xfail -> needs/test_default_neg_one_power_exponent.py (whole SymPy test) |
| 74 | `test_sympy_refine_suite::test_sin_cos` | cos(x + n*pi/2), Q.odd(n) |  |  | c | xfail -> needs/test_default_odd_half_pi_sign_form.py (whole SymPy test) |
| 75 | `trig_sec_csc::test_integration_structural_parity` | refine(sec(x + (2 * n + 1) * S.Pi / 2), Q.integer(n)) == (-1) ** (n + 1) * csc(x) (+1 more) | `(-1)**(n + 1)*csc(x)` | `-(-1)**n*csc(x)` | c | 2 lines split out, xfail -> needs/test_default_odd_half_pi_sign_form.py |
| 76 | `trig_sec_csc::test_sec_odd_half_pi_shift` | refine(sec(x + n * S.Pi / 2), Q.odd(n)) == (-1) ** ((n + 1) / 2) * csc(x) | `(-1)**(n/2 + 1/2)*csc(x)` | `-(-1)**(n/2 + 3/2)*csc(x)` | c | xfail -> needs/test_default_odd_half_pi_sign_form.py |
| 77 | `trig_sin_cos::test_shifts` | refine(cos(x + n * S.Pi / 2), Q.odd(n)) == (-1) ** ((n + 1) / 2) * sin(x) | `(-1)**(n/2 + 1/2)*sin(x)` | `-(-1)**(n/2 + 3/2)*sin(x)` | c | line split out, xfail -> needs/test_default_odd_half_pi_sign_form.py |
| 78 | `verifier_complex_int::test_abs_zero_and_sign_assumptions_divergences` | refine(arg(x), Q.zero(x)) is nan | `arg(x)` | `arg(x)` | c | arg(0) line moved to an xfail test -> arg_of_zero |
| 79 | `verifier_complex_int::test_boundary_zero_times_infinite_artifact` | refine(Abs(x * y), Q.zero(x) & Q.infinite(y)) is S.Zero | `0` | `x*Abs(y)` | b | accept both (identities has no nan -> 0 artifact) |
| 80 | `verifier_complex_int::test_handlers_ask_through_the_upstream_module` | log and log[0][0] == Q.zero(x) | `True` | `False` | a | pinned `handlers` |
| 81 | `verifier_complex_int::test_inconsistent_assumptions_raise_pre_existing_engine_error` | Abs(x), Q.positive(x) & Q.negative(x): v3 raises ValueError, identities Abs(x) |  |  | c | xfail -> needs/test_default_inconsistent_assumptions.py |
| 82 | `verifier_complex_int::test_log_branch_cut_oracle_adversarial` | refined == log(x ** 2) | `2*log(Abs(x))` | `2*log(Abs(x))` | b | accept both |
| 83 | `verifier_complex_int::test_min_max_no_rule_is_noop_without_relations` | refine(Min(x, y), Q.eq(x, y)) == Min(x, y) (+3 more) | `x` | `x` | b | accept both |
| 84 | `verifier_complex_int::test_minmax_oracle_adversarial` | refine(Min(x, y), Q.positive_infinite(x) & Q.positive_infinite(y)) is oo (+1 more) | `x` | `x` | b | accept both |
| 85 | `verifier_complex_int::test_mul_handler_pairs_only_matching_conjugates` | refine(x * conjugate(x)) == Abs(x) ** 2 | `Abs(x)**2` | `x*conjugate(x)` | a | all-None part split out and pinned |
| 86 | `verifier_complex_int::test_reference_ask_matches_upstream_on_broad_corpus` | Abs(x**2), True: sympy Abs(x**2), v3/identities Abs(x)**2 |  |  | b+c | 2 better cases accepted with numeric check; 16 SymPy-suite cases -> xfail test |
| 87 | `verifier_complex_int::test_reference_ask_quoted_rules` | got == expected (+12 more) | `2*log(Abs(x))` | `2*log(Abs(x))` | b+c | log/Mod/Rem accepted; arg(0), factorial(oo) -> 2 xfail tests |
| 88 | `verifier_complex_int::test_scope_runtime_handler_comes_from_expected_module` | handler.__module__ == f'satrefine.handlers.{module}' (+5 more) | `satrefine.handlers_v3.power_exp_log` | `satrefine.handlers_identities._tables` | a | pinned `handlers` |
| 89 | `verifier_complex_int::test_scope_vendored_handler_names_are_overridden_not_duplicated` | _upstream.handlers_dict['atan2'].__module__ == 'satrefine._upstream' (+1 more) | `satrefine.handlers_v3.inverse` | `satrefine.handlers_identities._engine` | a | pinned `handlers` |
| 90 | `verifier_complex_int::test_unmet_assumptions_leave_expression_unchanged` | refine(expr, assumptions) == expr (+22 more) | `2*log(Abs(x))` | `2*log(Abs(x))` | b+d | 12 decided cases accepted, numeric check test added |
| 91 | `verifier_matrix::test_determinant_ask_order` | [entry[0] for entry in log] == [Q.orthogonal(X), Q.singular(X), Q.unit_triangular(X)] | `[Q.singular(X), Q.zero(X), Q.unit_triangular(X)]` | `[Q.singular(X), Q.positive(2), Q.unit_triangular(X` | a | pinned `handlers` |
| 92 | `verifier_matrix::test_determinant_positive` | refine(Determinant(X), Q.orthogonal(X)) == S.One | `Determinant(X)` | `Determinant(X)` | d | orthogonal case -> original_wrong test |
| 93 | `verifier_matrix::test_determinant_reference_ask_parity` | det(X), Q.orthogonal(X): sympy 1 |  |  | d | orthogonal case removed from parity |
| 94 | `verifier_matrix::test_handlers_consult_patchable_upstream_ask` | log and log[0][0] == Q.symmetric(X) | `False` | `False` | a | pinned `handlers` |
| 95 | `verifier_matrix::test_inverse_positive` | refine(X.I, Q.unitary(X)) == X.conjugate() | `Adjoint(X)` | `Adjoint(X)` | d | unitary case -> original_wrong test |
| 96 | `verifier_matrix::test_inverse_reference_ask_parity` | X**-1, Q.unitary(X): sympy Adjoint(X.T) |  |  | d | unitary case removed from parity |
| 97 | `verifier_matrix::test_inverse_singular_divergence_from_upstream` | documented handlers-only raise |  |  | a | pinned `handlers` |
| 98 | `verifier_matrix::test_inverse_singular_raises` | documented handlers-only raise |  |  | a | pinned `handlers` |
| 99 | `verifier_matrix::test_inverse_singular_raises_under_scripted_ask` | scripted ask |  |  | a | pinned `handlers` |
| 100 | `verifier_matrix::test_inverse_unitary_soundness_counterexample` | X**-1, Q.unitary(X) |  |  | d | xfail condition limited to `handlers` (identities is sound: XPASS) |
| 101 | `verifier_matrix::test_matadd_single_term` | refine(MatAdd(X), True) == MatAdd(X) (+1 more) | `X` | `TypeError: GenericZeroMatrix does not have a speci` | c | xfail -> needs/test_default_matadd_single_term.py |
| 102 | `verifier_matrix::test_matmul_multifactor_orthogonal_cancellation` | refined.doit() == expected | `I` | `I` | b | accept I |
| 103 | `verifier_matrix::test_matmul_scalar_interleaving_preserves_value` | simplify(refined.subs(X, ROT90).doit()) == 2 * I2 (+1 more) | `2*I` | `Matrix([[2, 0], [0, 2]])` | c | value check kept (passes); MatMul(X, 2, Y) line -> xfail -> needs/test_default_matmul_scalar_factor.py |
| 104 | `verifier_matrix::test_matmul_symmetric_refines_factor_first` | result == MatMul(X, X) | `X**2` | `X**2` | b | accept X**2 |
| 105 | `verifier_matrix::test_matmul_unitary_soundness_counterexample` | conjugate(X)*X, Q.unitary(X) |  |  | d | xfail condition limited to `handlers` (XPASS) |
| 106 | `verifier_matrix::test_matrix_handler_keys_owned_by_their_modules` | handler.__module__ == f'satrefine.handlers.{module}' | `satrefine.handlers_v3.matrices` | `satrefine.handlers_identities._engine` | a | pinned `handlers` |
| 107 | `verifier_matrix::test_matrixelement_mixed_literal_symbol_not_distinct` | refine(A[i, 0], Q.diagonal(A)) == A[0, i] | `A[0, i]` | `A[i, 0]` | c | xfail -> needs/test_default_matrixelement_index_order.py |
| 108 | `verifier_matrix::test_singular_inverse_is_the_only_raising_path` | X**-1, Q.singular(X) |  |  | a | raise part split out and pinned |
| 109 | `verifier_matrix::test_transpose_rectangular_symbols` | refine(R.T, Q.symmetric(R)) == R | `R` | `R.T` | b | accept both (inconsistent premise) |
| 110 | `verifier_matrix::test_transpose_scripted_mixed_answers` | result in (X, X.T) | `False` | `False` | a | pinned `handlers` |
| 111 | `verifier_trig::test_hyperbolic_integer_shift_is_conservative` | refine(func(x + n * IPI), Q.integer(n)) == (-1) ** n * func(x) (+3 more) | `sinh(I*pi*n + x)` | `sinh(I*pi*n + x)` | c | xfail -> needs/test_default_hyperbolic_i_pi_shift.py |
| 112 | `verifier_trig::test_non_implying_assumptions_leave_expression_unchanged` | refine(expr, assumptions) == expr (+6 more) | `Abs(x)` | `Abs(x)` | b | 4 implying cases moved to a new test, numeric check |
| 113 | `verifier_trig::test_none_answers_leave_expression_unchanged` | refine(expr, assumptions) == expr (+3 more) | `acosh(cosh(x))` | `x` | a | pinned `handlers` |
| 114 | `verifier_trig::test_quoted_rule_outputs` | refine(sec(x + n * pi / 2), Q.odd(n)) == (-1) ** ((n + 1) / 2) * csc(x) | `(-1)**(n/2 + 1/2)*csc(x)` | `-(-1)**(n/2 + 3/2)*csc(x)` | c | line split out, xfail -> needs/test_default_odd_half_pi_sign_form.py |
| 115 | `verifier_trig::test_scope_keys_owned_by_expected_modules` | handler.__module__ == f'satrefine.handlers.{module}' (+2 more) | `satrefine.handlers_v3.trig` | `satrefine.handlers_identities._engine` | a | pinned `handlers` |


Judgement calls the user may want to revisit:
- **Mod/Rem.** `handlers` expands `Mod`/`Rem` of integers into the floor/ceiling definition. `handlers_identities` and v3 keep `Mod`/`Rem`, and turn `Mod` into `Rem` where the signs agree. I counted this as b: the same value, and the expansion is not a simplification. SymPy's refine does not expand either.
- **Singular inverse.** `handlers` raises `ValueError` for `X**-1` under `Q.singular(X)`. Upstream SymPy and `handlers_identities` leave `X**-1`, and the old tests call raising a "documented divergence from upstream". I counted it as a (pinned).
- **`gamma(n)` for positive integer `n`.** It becomes `factorial(n - 1)`. I counted this as b.
- **Inconsistent assumptions.** They no longer raise `ValueError`. I counted this as c, with a needs test, so the dispatcher owners decide.

## 5. Needs tests filed (tests/refine_identities/needs/)

Each fails under `handlers_identities` and passes under `handlers`, except the one marked. The last column says what v3 does.

| file | cases | what is asked | v3 |
|---|---|---|---|
| test_default_odd_half_pi_sign_form.py | 8 | `(-1)**((n + 1)/2)`, not `-(-1)**(n/2 + 3/2)`, for odd multiples of pi/2 in sin/cos/sec (SymPy's own test_sin_cos) | meets it |
| test_default_neg_one_power_exponent.py | 5 | `(-1)**((-1)**x/2 + c) -> (-1)**x` or `(-1)**(x + 1)` for integer x (SymPy's test_pow1/2) | meets it |
| test_default_pow_of_pow.py | 2 | `sqrt(1/x) -> 1/sqrt(x)` (x > 0); `(x**y)**z -> Abs(x)**(y*z)` (real x, even y) | meets the first |
| test_default_matrixelement_index_order.py | 3 | `x[i, j] -> x[j, i]` under symmetric/diagonal; `A[i, j] -> 0` under diagonal and `Q.ne(i, j)` | meets the swaps |
| test_default_floor_ceiling.py | 5 | `floor(x) -> x` for infinite x; floors/ceilings of integer-valued sums (SymPy's test_floor_ceiling) | no |
| test_default_arg_of_zero.py | 1 | `arg(x) -> nan` for zero x | no |
| test_default_infinite_arguments.py | 9 | `factorial(oo) = oo`; Max/Min with an argument known to be oo or -oo | no |
| test_default_hyperbolic_i_pi_shift.py | 4 | `f(x + n*I*pi) -> (-1)**n*f(x)` for sinh, cosh, sech, csch | no |
| test_default_rem_zero_dividend.py | 1 | `Rem(p, q) -> 0` for zero p | no |
| test_default_matadd_single_term.py | 2 | **crash:** `refine(MatAdd(X), True)` raises `TypeError: GenericZeroMatrix does not have a specified shape` | meets it |
| test_default_inconsistent_assumptions.py | 2 | `ValueError` for inconsistent assumptions, as the backends raise it | meets it |
| test_default_matmul_scalar_factor.py | 2 | `MatMul(X.T, 2, X) -> 2*I` (orthogonal); `MatMul(X, 2, Y) -> 2*X*Y` | no |

Under `handlers_identities` the needs directory gives 43 failed and 0 passed; under `handlers`, 45 passed.

Worth a look first: the `MatAdd` crash (the only crash); then the sign form and the `(-1)` power, because they are in SymPy's own test suite.

## 6. Gates

GATES

## 7. Other observations

- `test_refine_verifier_matrix.py` takes 79 s under `handlers_identities` against 17 s under `handlers`, on the same (loaded) machine. It is the slowest file in `tests/refine`; the time is not investigated here.
- `tests/refine` as a whole, in one process under the default: ONEPROC.
- CI (`.github/workflows/test.yml`) runs `pytest tests` in one process. The conftests of tests/refine_identities and tests/refine_v3 refuse to run when satrefine is already imported with another package, so that job cannot pass as written, before or after this change. Out of scope here.
