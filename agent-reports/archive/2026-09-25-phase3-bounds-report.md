# Agent report: phase 3, track B (bounds on the extended reals, B1-B8)

- **Date:** 2026-09-25
- **Branch:** `ri/bounds` (from `9819814`, the B9 head of `ri/termination`), worktree `.claude/worktrees/ri-bounds`.
- **Commits:** `e007adc` (the fix), `c780a99` (affine bounds merged; B8 rebuild guard), `ae95da6` (tests, docs, needs test), `97f767d` (merge of `origin/refine-identities`: plan commits only; B9 was not merged there yet). Report commit on top.
- **Issue:** tilorc-bot/satassume#10, B1-B8. Not edited.
- **Status:** B1-B7 fixed. B8 is fixed in `_simple.rebuild`, but the dispatcher has to call it, and the dispatcher belongs to `ri/speed-a0`. That one-line change is filed as `tests/refine_identities/needs/test_bounds_acot_rebuild.py`.

## 1. Root cause (verified)

`_engine._ask_atom` passes a sign or realness atom that `ask` leaves open to `_from_bounds`. `_from_bounds` then read the interval from `_simple.stated_bounds` as an interval of finite reals:
- it answered `Q.real` from any bound;
- it answered `positive`, `nonnegative`, `negative`, `nonpositive` and `nonzero` from one side alone.

Every one of those predicates implies finite, but a relation holds at `+-oo`. Even `Q.ge(x, oo)`, which forces `x = oo`, proved `Q.positive(x)`.

The relation decider reaches the bounds only through these atoms:
- `Q.real(u)` in the `u < oo` proof form (`_lt_by_signs`), which caused B1;
- `Q.nonzero(u - v)` in the `ne` proof forms, which caused B2 (`Ne`/`Eq` of `x`, `2*x`) and B3 (KroneckerDelta);
- the extended forms in `_le_by_signs`/`_lt_by_signs` were never bound-decided before.

B4-B7 are rows conditioned on `Q.real`/`Q.positive` of the argument (`sign(exp(z))`, `log(b**e)`, `acsch(csch(z))`, `RisingFactorial`).

I checked each path with a trace of `_from_bounds` calls. All seven reproductions went through it.

## 2. The fix

**`_engine._from_bounds`:**
- A stated interval is an interval of the extended reals.
- It proves `Q.extended_real` and the extended signs. `extended_positive`, `extended_nonnegative`, `extended_negative`, `extended_nonpositive` and `extended_nonzero` are now in `_BOUND_DECIDED`.
- `Q.real` and the finite signs also need each infinity that the sign leaves possible to be excluded. Any one of these excludes it:
  - a finite endpoint on that side, or an open `oo` endpoint (`Q.lt(x, oo)`);
  - a sign fact among the bounds: `Q.positive(x - 1)` holds only for a finite `x`;
  - `ask(Q.finite(u))`, asked only when the bounds prove the extended sign but not finiteness.
- Integer refutation is unchanged.

**`_simple.stated_finite(u, assumptions)`:**
- New function. It returns `(bounds, finite)`, where `finite` says that a sign fact supplied a bound. The flag is carried through the affine map.
- `stated_bounds` keeps its 4-tuple for the floor rules.

**`_simple._stated`:**
- When the bounds stated on `u` itself leave a side open, it now merges them with the mapped bounds of the quantities `u` is affine in (`_merged`).
- Without this, `Q.nonpositive(t - 2*pi)` under `Q.le(t, 2*pi) & Q.ge(t, pi)` is lost: the upper side is stated on `t - 2*pi`, the lower on `t`. Before the fix only the upper side was needed.
- This also recovers 2 battery cases (`inverse` same 122 → 124 between my first and final gate run).

**Docs:** the module docstring of `_engine` (it used to say "a stated bound carries realness, as in handlers_v3") and the docstring of `_from_bounds`.

**`stated_bounds` on top of the relation decider:**
- This did not fall out of the fix. The fix is about what an interval means, not how it is read. The rewrite is left for track D.
- Engine lines went up from 1,510 to 1,567: `_engine` +22, `_simple` +35 (`_merged`, `stated_finite`, `rebuild`).

**B8, `_simple.rebuild(func, args, assumptions)`:**
- Returns `func(*args)`, except for `acot`/`acoth` with a non-numeric argument that `ask` does not prove nonzero, when evaluation would change the node. Those are built with `evaluate=False`.
- Changing the node means pulling out the sign, or `acoth(I*c) -> -I*acot(c)`.
- The dispatcher rebuilds nodes at `_dispatch._step` with `new = expr.func(*args)`. That line has to become `new = _simple.rebuild(expr.func, args, assumptions)`.
- I didn't edit `_dispatch.py` (ownership rule). I checked it in a scratch copy with that line changed: all 16 cases of the needs test pass in both modes.
- The only rows with `acot`/`acoth` are on left sides and range rows, so no row right side creates the sign pull.

## 3. Per bug, before and after (both modes identical)

| Bug | Call | Before | After |
|---|---|---|---|
| B1 | `Piecewise((0, x < oo), (1, True))`, `Q.gt(x, 1)` | `0` | unchanged |
| B1b | same, `Q.ge(x, oo)` | `0` | unchanged (v3 gives `1`; proving `x = oo` from `lo = oo` is not implemented) |
| B2 | `Piecewise((0, Eq(x, 2*x)), (1, True))`, `Q.gt(x, 1)`; `Ne` | `1`; `0` | unchanged |
| B3 | `KroneckerDelta(x, 2*x)`, `Q.gt(x, 1)`; `(x, 3*x + 1)` and `(x + 1, 2*x)`, `Q.lt(x, -1)` | `0` | unchanged |
| B4 | `sign(exp(-x))`, `Q.gt(x, 1)`; `sign(exp(x))`, `Q.lt(x, -1)` | `1` | unchanged |
| B5 | `log(x**n)`, `Q.gt(x, 1) & Q.real(n)` | `n*log(x)` | unchanged |
| B6 | `acsch(csch(x))`, `Q.gt(x, 1)` and `Q.lt(x, -1)` | `x` | unchanged |
| B7 | `RisingFactorial(x, y)`, `Q.gt(x, 1)` | `gamma(x + y)/gamma(x)` | unchanged |
| B8 | `acot(Abs(z))`, `Q.nonpositive(z)` (and 5 more) | `-acot(z)` | `acot(-z)` unevaluated, once the dispatcher calls `rebuild` |

These still fire where `x` is finite, in both modes: `log(x**n) -> n*log(x)` under
- `Q.positive(x - 1)`;
- `Q.gt(x, 1) & Q.lt(x, 5)`;
- `Q.gt(x, 1) & Q.finite(x)`;
- `Q.gt(x, 1) & Q.real(x)`.

The same holds for `sign(exp(-x))`, `acsch(csch(x))`, `KroneckerDelta`, both Piecewise cases, `RisingFactorial` under `Q.positive(x - 1)`, and `Abs(x)` under `Q.gt(x, 1) & Q.real(x)`.

One pre-existing mode difference, not from this change (base `9819814` gives the same): `log(x**n)` under `Q.gt(x, 1) & Q.lt(x, oo) & Q.real(n)` fires in generated mode but not in live mode.

**Tests:**
- `tests/refine_identities/test_engine_bounds_infinity.py`, 54 tests:
  - B1-B7 unchanged, 14 cases × 2 modes;
  - 11 finite cases that must still fire × 2 modes;
  - the predicate level: what `Q.gt`, `Q.ge(x, oo)`, `Q.lt(x, oo)`, `Q.le(x, oo)`, sign facts and `Q.finite` prove;
  - the unit behaviour of `rebuild`.
- `test_engine.py::test_provable_reads_stated_bounds`: only its docstring changed; its assertions pass unchanged.
- `tests/refine_identities/needs/test_bounds_acot_rebuild.py`: 14 cases fail until the dispatcher calls `rebuild`.

## 4. Lost rewrites, and why

**Battery** (both modes): `inverse` "fired where v3 expects unchanged" dropped from 16 to 6. Nothing else changed: same, other form, miss and wrong are equal to the baseline, and the 1 crash is the baseline's. All 10 are from `test_hyperbolic_inverses_with_weaker_complex_facts`, and v3 leaves all 10 unchanged.

| Case | Old result | At `+-oo` |
|---|---|---|
| `acsch(csch(x))`, `Q.ge(x, 1)` | `x` | **unsound** (B6: `acsch(0) = zoo`) |
| `acsch(csch(x))`, `Q.gt(x, 0)` | `x` | **unsound** (B6) |
| `acoth(coth(x))`, `Q.ge(x, 1)` / `Q.gt(x, 0)` | `x` | correct (`acoth(1) = oo`) |
| `acosh(cosh(x))`, `Q.ge(x, 0)` | `x` | correct |
| `acosh(cosh(x))`, `Q.gt(x, -1)` | `Abs(x)` | correct |
| `asech(sech(x))`, `Q.ge(x, 0)` / `Q.gt(x, -1)` | `x` / `Abs(x)` | correct (`asech(0) = oo`) |
| `asinh(sinh(x))`, `Q.ge(x, 0)` | `x` | correct |
| `atanh(tanh(x))`, `Q.ge(x, 0)` | `x` | correct (`atanh(1) = oo`) |

**Differential:** per-case comparison of the identities results at `9819814` and at `c780a99` (the same code as the final head), generated mode, seeds 2, 3 and 7. The live-mode totals move by the same amounts. v3 fires none of the 6 lost cases, so "only a fires" is unchanged on every seed.

| Seed, case | Input | Old | At `+-oo` |
|---|---|---|---|
| 2/561 | `factorial(sign(n))`, `Q.ge(n, pi/2)` | `1` | correct |
| 2/1216 | `acosh(cosh(conjugate(m)))`, `Q.le(m, pi/2)` | `Abs(m)` | correct |
| 3/262 | `conjugate(sqrt(y**2))`, `Q.gt(y, pi/2)` | `y` | correct |
| 3/1043 | `sign(y + 1)`, `Q.ge(y, 0)` | `1` | correct |
| 3/1101 | `pi*Abs(m)/2`, `Q.lt(m, 0)` | `-pi*m/2` | correct |
| 7/1249 | `floor(sqrt(n**2))`, `Q.lt(n, 0)` | `floor(-n)` | correct |
| 2/1273 (gained) | `Min(2*pi*x, exp(y))`, `Q.nonnegative(y) & Q.lt(x, -pi/2)` | now `2*pi*x` | correct (the extended signs are now bound-decided) |

**Why the rewrites that are correct at `+-oo` are lost:**
- The rows are stated over the finite reals (`Abs(a) -> a` if `Q.nonnegative(a)`, `sign(a) -> 1` if `Q.positive(a)`, `im(a) -> 0` if `Q.real(a)`, the inverse-hyperbolic rows with `Q.real`).
- A one-sided bound no longer proves those conditions, which is the decided semantics.
- The results happened to be right at `+-oo`, but they were derived from a false premise (`x` finite).
- Keeping them would take row conditions over extended predicates, for example `Abs(a) -> a` if `Q.extended_nonnegative(a)`, with each row checked at `+-oo` and the tables regenerated. That is a change to the family rows beyond this track. I didn't do it; it's a candidate for track D.

## 5. Gates

`.claude/gates/bounds-97f767d`, against the baseline `.claude/gates/termination-9819814`. `PYTHONHASHSEED=0`, `JOBS=9 SLOTS=11 SUITE_WORKERS=4`, 341 s.

| Gate | Baseline | ri/bounds |
|---|---|---|
| suite | 2390 passed | 2444 passed, 14 failed (all in `needs/test_bounds_acot_rebuild.py`) |
| battery wrong / crash (both modes) | 0 / 1 | 0 / 1 |
| battery same + other (gen / live) | 1073 / 1073 | 1073 / 1073 |
| battery unchanged as expected | 628 | 638 |
| battery fired where v3 expects unchanged | 21 | 11 (the 10 above) |
| differential gen 2 / 3 / 7, identities fired | 483 / 485 / 455 | 482 / 482 / 454 |
| differential live 2 / 3 / 7, identities fired | 482 / 485 / 455 | 481 / 482 / 454 |
| differential unsound (identities, every run) | 2 / 3 / 1 | 2 / 3 / 1 (same cases' counts) |
| differential crash / timeout / inconsistent | 0 | 0 |

- No new unsound, crash or numerically different result.
- Differential with `SATREFINE_BACKEND=satassume`, seed 2: see section 8 (there is no satassume baseline to diff against).

**Infinity fuzz:**
- `inffuzz.py` was not in `.claude/phase3`, so I wrote one in my scratchpad.
  - Random `refine_fuzz` expressions with at most 2 symbols, each under one of 26 fact sets: one-sided and two-sided relations, `Q.ge(x, oo)`, extended signs, sign facts, `Q.finite`/`Q.real` together with a bound.
  - Input and output are compared at `+-oo` and 11 finite points that satisfy the facts.
- Three seeds (11, 12, 13) of 330 s each, on the base and on the fix. The case stream per seed is the same in both; the counts differ only because the runs are time-boxed:

| | Cases | Fired | Mismatches | Crashes |
|---|---|---|---|---|
| base | 3,767 | 767 | 28 | 0 |
| fix | 3,460 | 506 | 8 | 0 |

- **Base mismatches:**
  - `log(exp(k)) -> k` at `-oo`, and `log(z) -> log(-z) + I*pi` at `-oo`: SymPy conventions;
  - `DiracDelta(k - 1) -> 0` at `-oo`: input unevaluated;
  - the rest are the same artefacts as in the fixed run.
- **Fix mismatches:** none involves a bound.
  - Unevaluated input or output: `Rem(pi, 2)`, `RisingFactorial(E, oo)`.
  - `DiracDelta(2*pi*k) -> DiracDelta(k)/(2*pi)` at 0: scaling of a distribution.
  - Known conventions: `1/(1/(y + 1))` at `oo`; `log((k**3)**(1/3))` under `True` at `-oo`.

## 6. Borderline cases (plan section 3): documented, not changed

**`Abs(x*y)` under `Q.zero(y) & Q.infinite(x)`:**
- Live mode gives `0`; generated mode gives `y*Abs(x)`. This is unchanged by this branch.
- At the only allowed points, `x*y` is `0*(+-oo) = nan`, so the input has no value there and neither result is wrong.
- The `0` comes from `Abs(x)*Abs(y)` with `Abs(y) -> 0`, and then SymPy's own `0*Abs(x) = 0` on construction. SymPy treats `0*x` the same way for any symbolic `x`.
- Not a bug. The difference between the modes is only in form.

**`log(1/x)` under `Q.extended_positive(x)` gives `-log(x)`:**
- It differs from SymPy's values only at `x = oo`: `log(1/oo) = log(0) = zoo` against `-log(oo) = -oo`.
- `-oo` is the signed limit, and `zoo` is SymPy's unsigned convention for `log(0)`. SymPy's own auto-evaluation does the same for `log(exp(x))` with an extended-real `x`.
- It is already documented in `power_exp_log`'s module docstring, together with the rest of that class.
- The row cannot require `Q.finite` without losing the complex cases (`ask` cannot show `e*log(b)` finite for a complex `b`). Left as documented.

## 7. B8: SymPy issue draft (not filed; the coordinator decides)

> **Title:** `acot(-z)` and `acoth(-z)` auto-evaluate to `-acot(z)`/`-acoth(z)`, which is wrong at `z = 0`
>
> `acot` and `acoth` are odd except at 0: SymPy defines `acot(0) = pi/2` and `acoth(0) = I*pi/2`, and both are their own values at `-0`. `eval` pulls out a sign whenever `arg.could_extract_minus_sign()`, and it does not exclude an argument that may be zero:
>
> ```python
> >>> from sympy import *
> >>> z = Symbol('z')
> >>> acot(-z), acot(-z).subs(z, 0), acot(0)
> (-acot(z), -pi/2, pi/2)
> >>> acoth(-z).subs(z, 0), acoth(0)
> (-I*pi/2, I*pi/2)
> >>> acoth(I*z), acoth(I*z).subs(z, 0)        # the imaginary-coefficient path likewise
> (-I*acot(z), -I*pi/2)
> >>> acot(-I*z).subs(z, 0)
> -pi/2
> >>> w = Symbol('w', nonpositive=True)       # a correct simplification then gives a wrong value
> >>> acot(Abs(w)), acot(Abs(w)).subs(w, 0), acot(Abs(S(0)))
> (-acot(w), -pi/2, pi/2)
> ```
>
> (SymPy 1.15.0.dev, `6379c4da69`.) The same pattern in `asin`, `atan`, `asinh`, `atanh` is harmless (they vanish at 0), and in `acsc`/`acsch` too (`zoo = -zoo`). Only `acot` and `acoth` have a nonzero, non-infinite value at 0 that is not odd. A fix is to pull out the sign only when `arg.is_zero is False`. Otherwise the evaluation changes the value of expressions that are not simplified by the user at all, for example through `Abs` evaluating to `-w`.

## 8. Differential with the satassume backend, seed 2

Results are in `.claude/gates/bounds-97f767d/diff-satassume-{generated,live}-2.log`. There is no satassume baseline to diff against, so these are absolute numbers.

| Mode | Fired | Unchanged | Inconsistent | Crash / timeout | Unsound | Only v3 fires | Only identities fires | Both fire, numerically different |
|---|---|---|---|---|---|---|---|---|
| generated | 440 | 1,040 | 5 | 0 / 0 | 2 | 2 | 35 | 0 |
| live | 437 | 1,043 | 5 | 0 / 0 | 2 | 3 | 33 | 0 |

- **Unsound:** both are `-im(x)/(re(x)**2 + im(x)**2) -> 0` at `x = 0`, where the input is `nan`. These are the known artefacts of the check. v3 has the same 2.
- **Runtime:** 47 s against 225 s with the combined backend.

## 9. Open items

- **Needs test (dispatcher owner):** `_step` should call `_simple.rebuild`. This is one line; see the needs test's docstring.
- **Candidate for track D:** row conditions over extended predicates, to win back the rewrites in section 4 that are correct at `+-oo`: `Abs`/`sign`/`im`/`conjugate` of an extended-signed argument, `sqrt(x**2)`, and the inverse-hyperbolic pairs `acoth`/`acosh`/`asech`/`asinh`/`atanh`, all under a one-sided bound.
- **Candidate for track D:** `stated_bounds` on top of the relation decider (not done here).
- **B1b** gives unchanged, not `1`: nothing proves `x = oo` from `Q.ge(x, oo)`. This is sound; v3 is more complete here.
- **Pre-existing:** `log(x**n)` under `Q.gt(x, 1) & Q.lt(x, oo)` fires only in generated mode.
- The WIP gate directory `.claude/gates/bounds-e007adc` is from an intermediate commit. It is superseded by `bounds-97f767d`.
