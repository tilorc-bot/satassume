# Agent report: phase 3, track D, extended reals (B1–B7 follow-up)

- **Date:** 2026-09-26
- **Branch:** `ri/d-extended` (worktree `.claude/worktrees/ri-d-extended`), from `083aa0d`; merged `origin/refine-identities` at `5bbac1b` (ri/d-rows) in `0befcac`.
- **Commits:** `893e628`, `674b63e`, `6f3ea07`, `5d02090`, `63f0040`, `0befcac` (merge), `5dcbddf` (rows, backend guard, regressions, merge, accepted list), report commit on top.
- **Status:** done. All 14 rewrites lost to the B1–B7 fix fire again, in both modes: 8 battery, 6 differential. The 2 `acsch` battery cases stay unchanged on purpose (B6), and so do B4, B5 and B7. Beyond the 14, many more rewrites come back or are new in the ext differential (identities fired 148 → 230). Wrong 0 and crash 0. There is no new unsound result except one checker precision artefact (section 4).

## 1. How I found what the fix made unreachable

- **Scratch copy:** `_from_bounds` answers `True` for the finite predicates again, as before B1–B7. This is only in the scratchpad, never committed.
- **Battery:** I dumped every case in both modes and compared against the branch base (`083aa0d`). 10 cases differ in each mode, all from `test_inverse.py::test_hyperbolic_inverses_with_weaker_complex_facts`. They are the 10 in the bounds report.
- **Default differential:** I ran the identities worker for seeds 2, 3 and 7 at 1,500 cases, both modes, and compared per case. It found the 6 cases in the bounds report and no others.
- **Ext differential:** seeds 2 and 5 at 1,000 cases, both modes, compared per case. About 90 more cases per seed fire only in the relaxed copy. Most use the same rows (`conjugate`, `re`, `im`, `Abs`, `sign`, `sqrt(x**2)`, the hyperbolic inverses) under one-sided bounds or bounds at `±oo`. The rest are:
  - 7 of those rewrites are unsound at `±oo` and must stay lost: `acsch(csch(.))` ×6 (B6) and `sign(exp(n))` under `Q.lt(n, 0)` (B4).
  - `log(x) -> log(-x) + I*pi` at `x = -oo` fires only in generated mode (e.g. `atanh(log(k))`, `Rem(log(x), 3)`). It rests on SymPy's `log(-oo) = oo` convention. It stays unfired: that is `power_exp_log`'s log rows, which belong to the other track.
  - `DiracDelta(2*pi*m)` under `Q.ge(m, -oo)`: minmax_deltas, not touched.

## 2. Per row: the identity at ±oo, the decision, the verification

SymPy's values: `Abs(±oo) = oo`, `re(±oo) = ±oo`, `im(±oo) = 0`, `sign(±oo) = ±1`, `conjugate(±oo) = ±oo`, `asinh(sinh(±oo)) = ±oo`, `atanh(tanh(±oo)) = atanh(±1) = ±oo`, `acoth(coth(±oo)) = acoth(±1) = ±oo`, `acosh(cosh(±oo)) = oo`, `asech(sech(±oo)) = asech(0) = oo`, `acsch(csch(±oo)) = acsch(0) = zoo`.

**Form of the change.** Every extended condition is written `finite predicate | extended predicate` (for example `Q.nonnegative(a) | Q.extended_nonnegative(a)`), not the extended predicate alone.
- SymPy's `ask` proves `Q.real(sin(x))` for a real `x`, but not `Q.extended_real(sin(x))`: that handler goes by signs.
- With the extended predicate alone, 5 differential cases were lost (`atanh(tanh(sin(x)))`, `acosh(cosh(cos(y)))`, …).
- The finite predicate is asked first, so no finite case is lost and the extra ask happens only when the finite one fails.

| Family, row | At ±oo | Decision |
|---|---|---|
| complex_parts `Abs(a) -> a` / `-a` | `Abs(oo) = oo`, `Abs(-oo) = oo = -(-oo)` | `Q.nonnegative(a) \| Q.extended_nonnegative(a)`; likewise nonpositive |
| complex_parts `re(a) -> a`, `im(a) -> 0` | `re(±oo) = ±oo`, `im(±oo) = 0` | `Q.real(a) \| Q.extended_real(a)`. Needed for the hyperbolic facts, whose right sides contain `im(z)`. Not in my listed ownership, but the same family. |
| complex_parts `sign(a) -> ±1` | `sign(±oo) = ±1` | `Q.positive(a) \| Q.extended_positive(a)`; likewise negative |
| complex_parts `conjugate(a) -> a` | `conjugate(±oo) = ±oo` | `Q.real(a) \| Q.extended_real(a)`. Minimal: one condition. ri/d-rows' two new conjugate power rows are untouched. |
| complex_parts `sign(exp(z)) -> 1` | `sign(exp(-oo)) = 0` | **left** (B4) |
| complex_parts `conjugate(a) -> -a` (imaginary), `Abs(z) = z/sign(z)` (finite) | no extended form / `Abs(zoo)` | left |
| inverse `_OFF_CUT_LINES` (asinh, atanh, acoth facts) | hold, see above | `Q.real(z) \| Q.extended_real(z) \| ~Q.integer(im(z)/pi + 1/2)` |
| inverse `acsch(csch(z))` | `acsch(0) = zoo` | **left** at `Q.real(z) \| Q.finite(z) & …` (B6; the line is written out, no longer through `_OFF_CUT_LINES`) |
| inverse `acosh(cosh(t)) -> Abs(t)`, `asech(sech(t)) -> Abs(t)` | `oo = Abs(±oo)` | `Q.real(t) \| Q.extended_real(t)` |
| inverse `asin`/`acos`/`atan` facts, ranges | `sin(oo)` is an AccumBounds; `atan(oo) = pi/2` is outside the open range | left |
| hyperbolic `f(m*pi*I/2 + x)` shifts | conditions are parities, not realness | nothing to change |
| integer_funcs `floor`, factorial | `floor(sqrt(n**2))` and `factorial(sign(n))` came back through `Abs`/`sign`/Pow; `floor(±oo) = ±oo` is already a row (`Q.infinite`) | nothing to change |
| power_exp_log `(b**a)**e -> Abs(b)**(a*e)` (even a) | `((±oo)**a)**e = oo**e = Abs(±oo)**(a*e)` for `a > 0` (checked for `e` in ±1/2, 0, ±3, I, 1 + I, 1/3) | companion row `Q.extended_real(b) & Q.even(a) & Q.positive(a)`. For `a < 0`, `0**e` with `e < 0` is `zoo`, not `oo`: excluded. Needed for `conjugate(sqrt(y**2))` and `floor(sqrt(n**2))`. |
| power_exp_log `(b**a)**e -> b**(a*e)`, `Q.nonnegative(b) & Q.positive(a)` | `(oo**a)**e = oo**(a*e)` for `a > 0` | `(Q.nonnegative(b) \| Q.extended_nonnegative(b)) & Q.positive(a)` (`floor((x**3)**(1/3))`) |
| power_exp_log log rows (`LOG_FORMS`) | `log(oo**0) = 0` but `0*log(oo) = nan`; `log(oo**-1) = log(0) = zoo`, not `-oo` | see below: **B5 kept unfired**; `log(1/x)` under `Q.extended_positive(x)` now declines |

**B5 and `log(1/x)`: the power form in the log derivation.**
- Once `sign(a) -> 1` holds for an extended positive `a`, `arg(x)` collapses for `x` under `Q.gt(x, 1)`. The derived row `log(b**e) = e*log(b) + 2*pi*I*floor(…)` then fired, and B5 (`log(x**n)` under `Q.gt(x, 1) & Q.real(n)`) regressed.
- The power form `b**e == exp(e*log(b))` is false at `b = ±oo` for `e <= 0`.
- The log rows now derive with the form guarded: `LOG_FORMS`, the power form with `& (Q.finite(b) | Q.real(b) | Q.positive(e))`. `Q.real` is decided from bounds only when infinity is excluded.
- `EXP_FORMS` itself is unchanged, because complex_parts' `Abs(b**e) = Abs(b)**e` is right at `oo**0`. The family spec's `exp_forms` is `LOG_FORMS`, so `test_family_specs` holds.
- Results:
  - `log(x**n)` still fires under `Q.positive(x - 1)`, `Q.gt(x, 1) & Q.lt(x, 5)`, `Q.gt(x, 1) & Q.finite(x)` and `Q.gt(x, 1) & Q.real(x)`, and for an imaginary or complex base.
  - It stays unfired under `Q.gt(x, 1)` or `Q.extended_positive(x)` alone.
  - This also answers the coordinator's open item. `log(1/x)` under `Q.extended_positive(x)` is now unchanged, as in v3. `log(1/x)` under `Q.positive(x)` and under `Q.imaginary(x)` still gives `-log(x)`.
- This touches power_exp_log's derivation, which is outside my listed rows. It was needed to keep B5 unfired, and it was merged without conflict except the `SPEC` line (now `exp_forms=LOG_FORMS, rules=[ZERO] + RULES + LOG_RULES`).
- ri/d-rows' `log(b**e) -> e*log(Abs(b))` (even `e`) asks `Q.real(b)`, which is finite, so it is not reachable at `±oo`.

**A SymPy bug the extended rows exposed. Fixed in the combined backend (`compat/backend.py`, outside my listed ownership).**
- SymPy's `Q.extended_real` handler for `Add`/`Mul`/`Pow` is the closure of the extended reals, so `ask(Q.extended_real(sqrt(z)), Q.negative(z))` is `True`. `z**(1/3)` and `z**y` give `True` the same way.
- Under the combined backend with a `pi/2` relation, satassume leaves the question open and SymPy's `True` came through. `sqrt(z)*conjugate(sqrt(z))` under `Q.integer(z) & Q.le(z, -1) & Q.le(z, pi/2)` became `z` (unsound: ext differential seed 5, case 550).
- The fix sits next to the existing `Q.nonzero` guard:
  - while the combined or union backend asks SymPy, a `True` from the `Pow` handler is kept only for an integer exponent, or for an extended nonnegative base with a real exponent;
  - otherwise it becomes `None`;
  - the `sympy` backend stays SymPy's reference behaviour.
- This also removes two old results that relied on the bug, in v3 and identities alike: `Max(sqrt(n), pi*k*z)` with a negative `n` was `sqrt(n)` (seed 2, case 790), and `Max(1/sqrt(n), x + pi/2)` (seed 7, case 375). Both are unchanged now; their inputs are not real.
- The signs (`extended_positive`, …) have correct handlers: I probed `sqrt`, cube roots, symbolic powers, sums and products.
- A root-free pattern symbol in the rows was tried first. It does not work, because `part` binds only inside a two-symbol sum or product.

**Verification.**
- Specialize verifier:
  - `build/specs.EDGE_POINTS["inverse"]` now includes `oo` and `-oo`, so every generated inverse rule is also checked there.
  - Checked by hand with `verify` at `±oo`: the 13 rows pass, and `acsch(csch(z)) -> z` under `Q.extended_real(z)` fails, as it must.
  - The generated rule tables are unchanged apart from derivation comments: the extended cases run through the live handler, the fallback when the generated table declines.
  - Tables regenerated (`refine_specialize --write`) after each change and after the merge.
- `python -m satrefine.tools.refine_fuzz --ext`, 500 cases per run, both modes × combined/satassume:
  - **Final code (`5dcbddf`), seeds 31, 32, 33:** no new unsound result and 0 crashes. Seeds 31 and 32 have 0 unsound in every run. Seed 33 has 2 unsound in every configuration, and the base (`083aa0d`) has the same 2:
    - `RisingFactorial(n + 1, m)` at `m = -3/2`, `n = 1/2`: the checker's `inf` against `zoo`;
    - `acoth(coth(y**3))` under `Q.negative(y)` at `y = -3`: the precision artefact of section 4.
  - **Identities fired per run:**

    | Seed | Base, combined | Branch, combined | Base, satassume | Branch, satassume |
    |---|---|---|---|---|
    | 31 | 71 | 108 | 64 | 102 |
    | 32 | 67 | 99 | 61 | 89 |
    | 33 | 56 | 96 | 52 | 83 |

  - **Points checked at an infinity** (seeds 31 / 32, combined): 444 / 356 on the base against 725 / 631 on the branch.
  - On `5d02090` (before the `finite | extended` conditions), seeds 31 and 32 also gave 0 unsound and 0 crashes.
- `tests/refine_identities`: 2 failed (the two open needs tests), 2,833 passed.

## 3. Recovered cases

**Battery** (both modes, `test_inverse.py::test_hyperbolic_inverses_with_weaker_complex_facts`):
- The 8 of the bounds report's 10 that are right at `±oo`:
  - `acoth(coth(x))` under `Q.ge(x, 1)` and `Q.gt(x, 0)` → `x`;
  - `acosh(cosh(x))` under `Q.ge(x, 0)` → `x`, and under `Q.gt(x, -1)` → `Abs(x)`;
  - `asech(sech(x))` likewise;
  - `asinh(sinh(x))` and `atanh(tanh(x))` under `Q.ge(x, 0)` → `x`.
- 5 more in the same test, under explicit extended facts:
  - `acoth(coth(x))` under `Q.extended_positive(x)`;
  - `acosh(cosh(x))` and `asech(sech(x))` under `Q.extended_nonnegative(x)`;
  - `asinh(sinh(x))` and `atanh(tanh(x))` under `Q.extended_real(x)`.
- In `test_complex_parts.py`: `arg(conjugate(x))` under `Q.negative_infinite(x)` → `pi`, which is exact (`arg(-oo) = pi`). v3 declines.
- Not recovered, on purpose: `acsch(csch(x))` under `Q.ge(x, 1)` and `Q.gt(x, 0)` (B6).
- `log(1/x)` under `Q.extended_positive(x)` now declines (as v3).
- The 14 new extras are in `satrefine/tools/lib/accepted.py`, so the scoreboard shows 0 open differences.

**Differential** (seeds 2, 3, 7, both modes): all 6 are back.

| Seed, case | Input | Result |
|---|---|---|
| 2/561 | `factorial(sign(n))`, `Q.ge(n, pi/2)` | `1` |
| 2/1216 | `acosh(cosh(conjugate(m)))`, `Q.le(m, pi/2)` | `Abs(m)` |
| 3/262 | `conjugate(sqrt(y**2))`, `Q.gt(y, pi/2)` | `y` (combined; satassume leaves it, since it cannot read `pi/2` bounds, issue #7) |
| 3/1043 | `sign(y + 1)`, `Q.ge(y, 0)` | `1` |
| 3/1101 | `pi*Abs(m)/2`, `Q.lt(m, 0)` | `-pi*m/2` |
| 7/1249 | `floor(sqrt(n**2))`, `Q.lt(n, 0)` | `floor(-n)` |

Also new:
- seed 2 case 926, `asinh(sinh(x**x))` under `Q.integer(x) & Q.le(x, pi/2)` → `x**x`: exact, because an integer power of an integer is real;
- seed 2 case 1107, live only: a form change under inconsistent assumptions (`Q.prime(z) & Q.le(z, -pi/2)`).

**Regression table** (`tests/refine_identities/regressions.py`):
- **Bug id "B1-B7 extended"**, 36 rows, both modes: each recovered case with a one-sided bound and with the infinite point itself (`Q.positive_infinite`, `Q.negative_infinite`, or `Q.infinite` with an extended sign), plus the base rows `Abs`, `sign`, `conjugate`, `im`.
- **B5:** new rows keep `log(x**n)` unchanged under `Q.extended_positive(x) & Q.real(n)` and `Q.positive_infinite(x) & Q.real(n)`.
- **B10:** the two rows under `Q.extended_negative(z) & Q.infinite(z)` and `Q.gt(n, 0)` now accept the inner `Abs` rewrite (`-acsch(csch(z))` and `acsch(csch(n))`); `acsch(csch(.))` itself must still not collapse.
- **`test_power_exp_log`:** `log(1/x)` under `Q.extended_positive(x)` is now "neither".
- **`test_complex_parts`:** the `arg(conjugate(-oo))` row is now "extra", sampled at `±oo` through a new symbol `u`.

## 4. Gates

`.claude/gates/d-extended-0befcac` against `.claude/gates/d-rows-merged-5bbac1b` (BASELINE). `PYTHONHASHSEED=0`, `JOBS=10 SLOTS=11 SUITE_WORKERS=4`, 743 s. The accepted-list commit `5dcbddf` changes only the scoreboard's accepted/open split; it is gated in `d-extended-5dcbddf` (see the end of this section).

| Gate | Baseline | ri/d-extended |
|---|---|---|
| suite | 2 failed (needs), 2,757 passed | 2 failed (the same needs), 2,833 passed |
| battery wrong / crash (both modes) | 0 / 0 | 0 / 0 |
| battery same (gen / live) | 1,042 / 1,043 | 1,042 / 1,043 |
| battery unchanged as expected | 620 | 607 |
| battery fired where v3 expects unchanged | 30 (open 1) | 43 (open 14 at `0befcac`, 0 at `5dcbddf`) |
| differential gen 2 / 3 / 7, identities fired | 484 / 484 / 456 | 486 / 487 / 456 |
| differential live 2 / 3 / 7, identities fired | 483 / 484 / 456 | 485 / 487 / 456 |
| differential unsound, identities (every seed, mode) | 2 / 2 / 1 | 2 / 2 / 1 (same) |
| differential both-fire numerically different | seed 3: 1 | seed 3: 1 (same) |
| v3 side (shared backend) gen 2 / 7 fired | 456 / 434 | 455 / 433 (the two `Max(sqrt(n), …)` cases, section 2) |
| satassume gen / live seed 2, identities fired | 442 / 439 | 451 / 448, unsound 2 / 2 (same) |
| ext gen / live seed 2, identities fired | 148 / 147 | 230 / 230 |
| ext cases checked at an infinite point | 60 / 59 | 129 / 129 |
| ext unsound | 0 / 0 | 1 / 1 (checker precision, below) |
| ext timeouts | 8 / 10 | 1 / 2 |
| matrices gen / live | unchanged | unchanged |
| full fixpoint, termination | 3 passed 1 skipped; 8 passed | same |
| crash / inconsistent, every section | 0 | 0 |

**The one ext unsound result is a checker precision artefact, not a wrong rewrite.**
- The case is ext seed 2, case 621: `acoth(coth(x**x))` → `x**x` under `Q.extended_nonnegative(x)`, at `x = 3`.
- The checker reports 27.0327 against 27. The exact value is 27, because `acoth(coth(t)) = t` for real `t` and `x**x` is real for `x >= 0`.
- `coth(27) = 1 + 7e-24`, and `acoth` of it needs more digits than the check carries: even SymPy at 40 digits gives 26.99999999999999999992. This is the same class as the `atanh(tanh(x**3))` artefact in the fuzz-ext report.
- The rewrite fires now through the `Q.extended_real` fact domain; `x` may be `oo`, where the value `oo = oo**oo` is also right.

**Final gate `d-extended-5dcbddf`** (731 s, same baseline):
- It matches `d-extended-0befcac` except for the scoreboard, where "fired where v3 expects unchanged" is now accepted 43, open 0, with 0 open differences in both modes.
- The only other change is the ext section's load-dependent timeout count (1 against 2).
- Suite: 2 failed (the two needs tests), 2,833 passed. Core-purity and import-direction tests pass; they are part of the suite.

## 5. Open items

- The ext differential's checker loses precision for `acoth(coth(t))` at large `t` (above). A fix would evaluate the input at more digits when the argument of `acoth`/`atanh` is within 1e-15 of ±1. That is tools code; I did not change it.
- The `sympy` backend (reference mode) still carries SymPy's `Q.extended_real` closure. Under it, `conjugate(sqrt(z))` under `Q.negative(z)` becomes `sqrt(z)`. The guard is on only for combined and union, like the `Q.nonzero` guard.
- **SymPy issue draft** (not filed; outward-facing, needs the user's OK): `ask(Q.extended_real(sqrt(z)), Q.negative(z))` is `True`. `ExtendedRealPredicate` registers `test_closed_group` for `Add`, `Mul` and `Pow` (`sympy/assumptions/handlers/sets.py`). The `Pow` closure is wrong for a negative base with a non-integer exponent. The `Add` and `Mul` closures are also wrong where `oo - oo` or `0*oo` is `nan`. `Q.real` has a careful `Pow` handler; `Q.extended_real` should use one too.
- `acoth(coth(Abs(x)))` under `Q.lt(x, 0)` now comes out as `acoth(-coth(x))`, not `-x`: the inner `Abs` refines first, and B8's rebuild guard keeps `acoth(-u)` unevaluated. The value is right. Before, the outer row fired through B10's `im(Abs(x)) = 0` path. This case is only in the ext stream.
- Still unfired (other ownership): `log(x) -> log(-x) + I*pi` at `x = -oo` (SymPy's `log(-oo) = oo` convention; generated mode only), and the `DiracDelta` scaling under a bound.
