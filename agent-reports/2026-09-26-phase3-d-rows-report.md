# Phase 3, track D: differences from v3, new rows, cleanup (d-rows)

Branch `ri/d-rows` (worktree `.claude/worktrees/ri-d-rows`), from 083aa0d. `origin/refine-identities` had no new commits at gate time. Not merged into `refine-identities`.

## Summary

- **Scoreboard, generated mode:** same/other/miss/quiet/extra went from 1,035/41/10/620/30 to **1,042/41/3/620/30**.
- **Scoreboard, live mode:** from 1,036/40/10/620/30 to **1,043/40/3/620/30**.
- Wrong and crash stay at 0 in both modes.
- **Accepted differences:** they are now data, in `satrefine/tools/lib/accepted.py`, with 73 entries. The scoreboard prints each category as "accepted N, open M". It also lists the open cases, stale entries (an accepted case whose result changed) and every extra it could not check numerically.
- **One open difference is left:** `log(1/x) | Q.extended_positive(x) -> -log(x)`. It is wrong at `x = oo` under SymPy's convention: `log(1/oo)` is `zoo`, while `-log(oo)` is `-oo`. See "Open".
- **Fixes:**
  - **Conjugate powers:** a new pattern symbol, `exponent()`, is a generic matcher feature, so core still names no SymPy function. `b**exponent('k')` also matches a target that is not a power, as `target**1`. Two new rows use it for unequal conjugate powers.
  - **Log of an even power:** a new rule row, `log(b**e) -> e*log(Abs(b))`.
  - **`(-1)` exponent row:** its hypothesis is relaxed, so `(-1)**((-1)**n/2 + m/2)` now fires.
- **Misses:** 10 went to 3. The remaining 3 are the combinatorial cases where v3's expectation is questionable, and they are accepted.
- **Cleanup:**
  - The `satrefine._upstream` alias is removed. Its 7 test importers now import `satrefine.identities.compat.upstream`.
  - The import-direction test now also forbids `satrefine.identities` from importing `satrefine.reference`.
  - README no longer refers to `satrefine.backend`.
- **Gates:** no new unsound results, crashes or numeric differences in any section. The suite fails only the 2 `needs/` tests.

## The difference table (current head; generated mode, live noted)

kind: other = fired, other form; miss = did not fire, v3 expects a result; extra = fired where v3 expects unchanged.

| cases | kind | example | decision | reason |
|---:|---|---|---|---|
| 30 | other | `sinh(I*pi*k) \| Q.even(k) -> 0` (v3 `I*sin(pi*k)`), `sech(I*pi*k) \| Q.integer(k) -> (-1)**(-k)`, `csch(I*pi*(k/2)) \| Q.odd(k) -> -(-1)**(1/2 - k/2)*I` | accepted: ours better | an exact value, where v3 leaves the same number unevaluated. 3 exponents read awkwardly but are right |
| 16 | extra | `sinh(I*pi*k + x) \| Q.integer(k) -> (-1)**k*sinh(x)`, `cosh(I*pi*k/2 + x) \| Q.odd(k) -> (-1)**(k/2 + 3/2)*I*sinh(x)` | accepted: ours better | an exact period or half period. v3 declines when it does not know the parity |
| 6 | extra | `acos(cos(x)) \| -pi <= x <= pi -> Abs(x)`, `asin(cos(x)) \| pi <= x <= 2*pi -> x - 3*pi/2`, `atan(cot(x)) \| pi < x < 2*pi -> 3*pi/2 - x` | accepted: ours better | exact on the whole interval. The sampler cannot draw points under `pi` bounds, so these are checked at 41 exact points each in `tests/refine_identities/tools/test_accepted.py` |
| 2 | other | `acosh(cosh(x)) \| Q.zero(x) -> 0` (v3 `x`) | accepted | same value |
| 1 | extra | `exp(I*pi*n/2 + x) \| Q.odd(n) -> (-1)**(n/2 + 3/2)*I*exp(x)` | accepted | exact; the exponent is awkward |
| 1 | other | `log(1/x) \| Q.zero(x) -> zoo` (v3 `-log(x)`) | accepted | same value |
| 1 | extra | `log(1/x) \| Q.infinite(x) -> zoo` | accepted | exact: `1/x = 0`, and `log(0) = zoo` (test_accepted) |
| 1 | extra | `log(2*x) \| True -> log(x) + log(2)` | accepted | exact, including at 0 |
| 1 | extra | `log(1/x) \| Q.extended_positive(x) -> -log(x)` | **open** | wrong at `x = oo` (SymPy: `log(0) = zoo`) |
| 1 (generated only) | other | `Abs(x*y) \| Q.zero(y) -> y*Abs(x)` (v3 `0`) | accepted | exact also for an infinite `x`. v3's `0`, and live mode's, is not |
| 5 | other | `Abs(x**(-2)) \| Q.real(x) -> x**(-2)`, `re(x**(-3)) \| Q.real(x) -> x**(-3)` | accepted: ours better | exact and simpler (`zoo` on both sides at 0) |
| 1 | extra | `arg(x) \| Q.zero(x) -> nan` | accepted | SymPy's `arg(0)` is `nan` |
| 1 | extra | `arg(x*y) \| Q.negative(y) -> arg(-x)` | accepted | exact |
| 2 | other | `conjugate(x + y) \| Q.real(y) -> y + conjugate(x)` | accepted: ours better | simpler |
| 1 | extra | `floor(x + floor(y)) \| True -> floor(x) + floor(y)` | accepted | exact; the scoreboard checks it numerically |
| 1 | extra | `Max(x, y) \| Q.positive_infinite(x) -> x` | accepted | exact (test_accepted) |
| 3 | miss | `binomial(n, n) \| ~Q.integer(n)` (v3 `1`), `binomial(n, n - 1)` (v3 `n`), `rf(x, k) \| ~Q.integer(x)` (v3 `gamma(k + x)/gamma(x)`) | accepted: v3 questionable | `~integer` allows infinity, and poles in rf's case |
| 3 | miss → **same** | `x**3*conjugate(x)` (×2), `x*conjugate(x)**2` | fixed | `exponent()` rows |
| 1 | miss → **same** | `sign(x**2*conjugate(x)) \| Q.complex(x) -> sign(x*Abs(x)**2)` | fixed (now v3's form) | v3's form. `sign(x)` would be simpler. The case is numerically unchecked through the battery's known oracle limit, which is why the unchecked count goes from 187 to 188 |
| 2 | miss → **same** | `log(x**(-2)) \| Q.real(x)`, `log(x**n) \| Q.even(n) & Q.nonzero(n) & Q.real(x)` | fixed | the new log row |
| 1 | miss → **same** | `(-1)**((-1)**n/2 + m/2) \| Q.integer(n)` | fixed | the relaxed `(-1)` row |

Totals: 41 other (41 accepted), 3 miss (3 accepted), 30 extra (29 accepted, 1 open).

**Numeric checks of the extras:** the scoreboard checks 22 of the 30 numerically. The 8 it cannot check are the 6 inverse cases, `log(1/x) | Q.infinite(x)` and `Max | Q.positive_infinite`. They are listed by the scoreboard, and `test_accepted.py` checks them at 256 exact points: 0 failures.

**Changes vs the plan's list:** the 3 `X[i, j]` misses no longer appear; they had already turned into "same" before this branch, at 083aa0d. The 10 misses at 083aa0d are the ones above.

## Fixes

- **`exponent()`** (`core/match.py`, +17 counted lines): `b**exponent('k')` binds `k` to the exponent of a power whose base matches `b`. Otherwise it binds `k = 1` and matches `b` against the whole target. A plain exponent symbol is unchanged. It is exported through `rules/_tables`. The purity test passes (`Pow` is not a function head).
- **complex_parts** has 2 new Mul rows:
  - `w**k*conjugate(w)**m -> Abs(w)**(2*m)*w**(k - m)` for integers with `m > 0` and `k - m > 0`;
  - the mirror row, `-> Abs(w)**(2*k)*conjugate(w)**(m - k)`.

  Exact at `w = 0`, `±oo` and `±I*oo`. At `zoo`, SymPy leaves `conjugate(zoo)` unevaluated, as the existing equal-power row does. Checked for all `1 <= k, m <= 4` at 10 points.
- **power_exp_log, `LOG_RULES`:** the new row is `log(b**e) -> e*log(Abs(b))` under `Q.real(b) & Q.even(e) & (~Q.zero(e) | ~Q.zero(b))`.
  - It is tried after the log identities, so existing results do not change.
  - **B5:** at `b = 0` both sides are `zoo`, but at `e = 0`, `0*log(0)` is `nan`, hence the hypothesis. `Q.real` excludes infinite `b`. At `±oo` with `e < 0` the row would be wrong (`log(0) = zoo` against `-oo`), and it does not fire there.
  - `log(x**n) | Q.even(n) & Q.real(x)` stays unchanged, as v3 expects.
- **power_exp_log, the `(-1)` row:** the hypothesis of `(-1)**((-1)**x/2 + r) -> (-1)**(x + r + 1/2)` is now `Q.integer(x)` (it was `& Q.integer(r + 1/2)`). The identity holds for any `r`, because `(-1)**z = exp(I*pi*z)` has period 2. Checked at 70 points, including infinite `r`.
- **Tables:** regenerated. The only change is a derivation comment index in `generated/power_exp_log.py`, shifted by the two new complex_parts rows.
- **Tests:** the family tests have the new rows as "same". The 2 xfailed "miss" rows now pass, so the suite's xfailed count goes from 29 to 27. There is a matcher test, and `tests/refine_identities/tools/test_accepted.py` checks that the accepted entries are distinct and well formed, and checks the 8 unchecked extras exactly.
- **Scoreboard and gates:** the summary shows the accepted/open split, the open cases and stale entries (`refine_gates.sh`, totals tail 8 → 10).

Row ownership: I edited only complex_parts' conjugate rows, power_exp_log's log and `(-1)` rows, the matcher, tools and tests. inverse, hyperbolic and integer_funcs are untouched.

## Cleanup

- `satrefine/_upstream.py` is removed, with the references to it in 7 test files and in a v3 docstring. README no longer calls it an alias.
- `test_import_direction.py` has a new test, `test_the_reference_is_not_imported_by_identities`.
- README: `satrefine.backend.set_backend/using` is now `satrefine.identities.compat.backend.…`.

## Gates

`JOBS=10 SLOTS=11 SUITE_WORKERS=4 refine_gates.sh .claude/gates/d-rows-ff5ba40 .claude/gates/refactor-done-083aa0d` took 823 s.

- **Suite:** 2 failed (the 2 `needs/` tests). Passed went from 2,733 to 2,757 and xfailed from 29 to 27, as explained above. 1,920 skipped.
- **Scoreboard:** the numbers above. The engine grows from 1,775 to 1,792 lines (match +17), and the families from 467 to 475.
- **Differentials:**
  - Seeds 2, 3 and 7 in both modes, satassume seed 2 in both modes, and matrices in both modes: only the time lines changed.
  - Ext seed 2: identities timeouts went 3 → 4 in both modes, and unchanged 684 → 683. In live mode, v3's timeouts also went 2 → 3. This is the known load-dependent 20 s timeout. Fired 148, unsound 0 and crash 0 are unchanged.
- **Full fixpoint** 3 passed, 1 skipped. **Termination** 8 passed.

## Open

- **`log(1/x) | Q.extended_positive(x) -> -log(x)`** is wrong at `x = oo` by SymPy's convention (`log(0) = zoo`). It comes from the `log(exp(z)) = principal(z)` fact at `z = -oo`. The fix needs a finiteness condition on the derived power-form rows without losing the complex cases. That is the family docstring's known class, and it belongs with the extended-reals restatement.
- **Live mode's `Abs(x*y) | Q.zero(y) -> 0`** matches v3 but is not exact for an infinite `x`. Generated mode gives `y*Abs(x)`.
- **`sign(x**2*conjugate(x))`** gives v3's `sign(x*Abs(x)**2)`. The simpler `sign(x)` would need a sign row for a nonnegative factor.

## Commits

c17b276 (rows, matcher, alias removal, scoreboard), b36f26e (tests), ff5ba40 (accepted-extras test, gate summary), plus this report.
