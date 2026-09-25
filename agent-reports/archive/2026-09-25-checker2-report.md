# Checker 2: adversarial pass over engine step 2, defs step 3 and the 0**e row

- **Date:** 2026-09-25
- **Branch:** `ri/check2`, from `refine-identities` f686dcc. It contains 2
  needs tests and this report. No production files were changed.
- **TL;DR:**
  - **Wrong results: 0.** Every candidate was checked numerically at
    concrete points, including `+-oo`, halves, and imaginary and Gaussian
    points.
  - **Crash: 1.** It predates step 2. The firing cap counts every firing
    in a call, so a wide input with more than 500 independent rewrites
    raises `RefineLoopError`. v3 handles the same input. Filed as
    `needs/test_checker2_firing_cap_on_wide_input.py`.
  - **Misses that v3 handles: 1 new.** `Eq(x, y)` with both arguments
    `+oo` (or both `-oo`) stays undecided. Filed as
    `needs/test_checker2_eq_of_equal_infinities.py`. The other misses v3
    handles are all `KroneckerDelta` of a real index against an imaginary
    one. That case is already an open problem in the engine report.
  - **Result cache:** I found no leak across assumptions, a case-split
    branch, a `Piecewise` branch, or a hash seed.

## 1. What was attacked, and how many cases

Two things ran on every case:
- a scratch harness that refines the input, then compares input and result
  numerically on a grid of values;
- the assumptions, evaluated at each grid point, with `subs(...,
  simultaneous=True)`.

A point counts only where the input evaluates to a value, meaning not `nan`,
not `AccumBounds` and not an exception. The grid was
`{-2, -1, 0, 1, 2, 1/2, -3/2, I, -I, 1+I, oo, -oo}`, with Gaussian and
half-integer points added for integer_funcs.

| Area | Hand-written cases | Result |
| --- | --- | --- |
| Min/Max: signs, extended signs, `+-oo` known and merely possible, relation chains, equalities, compound infinite arguments (`x+1`, `2*x`, `exp(x)`, `x*y`, `x-y`), 3- and 4-argument forms | 55 + 8 (the 8 run under hash seeds 1, 2, 3) | 0 wrong |
| KroneckerDelta (2-argument and ranged, including symbolic and empty ranges, imaginary and infinite indices) and Heaviside (0, `+-oo`, with and without `H0`, `H0` symbolic, imaginary or `nan`, non-real arguments) | 54 | 0 wrong |
| General `Piecewise` through the decider: `Eq`/`Ne`, `And`/`Or`/`Not`, `x < oo`, conditions at `-oo`, undecided branches refined under their condition, branch drop at infinity | 43 + 13 | 0 wrong |
| Result cache: the same subexpression inside and outside `Piecewise` branches and case splits (`log(x*y) + Abs(x)`), nested `Piecewise`, `atan2` | 20 | 0 wrong, no leak |
| Firing cap | 3 wide inputs | 1 crash (section 2.1) |
| integer_funcs: `frac` definition and bounds (`[k, k+1)`, half-open on each side, symbolic `n`), shift rows with integer, `I*n` and Gaussian `n`, `floor(y)`/`ceiling(y)` terms with finite, real, extended-real and unknown `y`, infinite `x`, and the Mod/Rem half-integer row (every sign combination, imaginary/infinite/zero divisor, `Mod(a/2, a)`, `Rem(3a/2, a)`) | 68 + 41 | 0 wrong |
| `0**e = zoo`: `1/x`, `x**-2`, `x**(-y)`, `1/sqrt(x)`, `1/(x*y)`, `1/(x+y)`, `log(1/x)`, `Abs(1/x)`, products and sums with other poles, extended, infinite and non-real exponents, `exp(-y*log(x))` | 29 | 0 wrong |
| `atan2` Piecewise now through the decider, infinite arguments | 19 | 0 wrong; see the note below |
| Raw `ask` probes: SymPy's `Q.eq`/`Q.le`/... at `+-oo` for 60 argument/fact pairs, compound arguments included | about 600 queries | The `-oo` guard is needed only where it applies: a known-infinite argument. No unsound answer for merely possible or compound infinities. |

On the `atan2` row: under `Q.lt(x, 0) & Q.ge(y, 0)`, the result `atan(y/x) + pi` is
`nan` at `x = -oo, y = oo`, while `atan2(oo, -oo)` is `pi`. This is not a
defect. The backend treats relations as over the reals: `Q.lt(x, 0)`
excludes `x = -oo`, as the phase-1 checker recorded for Mod/Rem. v3 behaves
the same.

**Breadth runs** (PYTHONHASHSEED=0):

| Run | Result |
| --- | --- |
| Scratch mini-fuzzer, seeds 1 and 2: random Max/Min/Max3/KD/KD-range/Heaviside/2- and 3-branch Piecewise/frac/floor/ceiling/Mod/Rem/`a**-e` over infinite, extended and relation assumptions | 1,100 cases, 183 fired. 0 wrong, 0 crash, 0 timeout. **Unchecked: 150 of 183** (no grid point satisfied the assumptions with the input defined; most were infinite/odd/relation mixes). |
| `tools/refine_differential.py --seed 11 --cases 1500` | identities fired 504, 0 crash, 0 timeout, **unchecked 55**, unsound 3, all shared with v3 and spurious (`-inf == -inf` counted as a mismatch, and a `nan` input). 0 numerically different. 2 undecided, both under inconsistent assumptions. |
| `tools/refine_differential.py --seed 13 --cases 1500` | identities fired 437, 0 crash, 0 timeout, **unchecked 67**, unsound 1 (spurious `-inf == -inf`, shared with v3). 0 numerically different. 4 undecided: 2 under inconsistent assumptions, 1 correct (`asech(0) = oo`), and 1 note below. |
| `tools/refine_fuzz.py 5 1500` | 472 fired, **unchecked 65**, unsound 1 (spurious `-inf == -inf`), 0 crashes. |

The note on seed 13: `conjugate(1/sqrt(m))/sqrt(m)` under `Q.zero(m)` gives
`oo`. Its input value at `m = 0` is SymPy's unevaluated
`zoo*conjugate(zoo)`, so the input has no value there. The rewrite comes
from the conj_mul row, `|u|**2` at `u = zoo`. Not a defect.

In the differentials, only v3 fires on 4 + 3 `KroneckerDelta` cases (real
index against imaginary), which is the known open problem. One of v3's
answers is itself wrong: `KroneckerDelta(n, z) = 0` for two imaginary
indices, at `n = z = I`. A second v3 wrong I met along the way:
`KroneckerDelta(i, 2*i)` under `Q.extended_positive(i)` gives `0`, but at
`i = oo` both indices are `oo`. Identities refuses both, correctly.

## 2. Findings

### 2.1 Crash: the firing cap counts width, not loops (needs test filed)

```python
refine(Add(*[Abs(x + k) for k in range(1, 502)]), Q.positive(x))
# RefineLoopError: refine fired handlers more than 500 times; last rewrite Abs(x + 501) -> x + 501
```

Each term fires once and there is no loop. v3 rewrites the 599-term version
completely in 15 s. A 300-term `Abs(x - k)*Abs(x + k)` under
`Q.gt(x, 10**4)` fails the same way.

The cap is phase 1's: `2fd72b8` counts firings in the same way. The step-2
cache removes repeated work, not distinct work.

Suggested fix: cap firings per rewrite chain or per node. The iterative
`_refine` loop already holds the chain. Then the cap detects loops rather
than the width of the input.

Test: `tests/refine_identities/needs/test_checker2_firing_cap_on_wide_input.py`
(fails, 12 s).

### 2.2 Miss that v3 handles: `Eq` of two equal infinities (needs test filed)

```python
refine(Piecewise((1, Eq(x, y)), (0, True)), Q.positive_infinite(x) & Q.positive_infinite(y))
# identities: unchanged; v3: 1   (also for two -oo)
```

`ORDER['eq']` has no proof from signs (`S.false`). The relation forms are
switched off for a known infinite argument, which is the `-oo` guard and
right as a guard. A sign form would close the gap:
`(positive_infinite(u) & positive_infinite(v)) | (negative_infinite(u) &
negative_infinite(v))`.

`KroneckerDelta(oo, oo)` is left unevaluated by SymPy, so it has no value
to compare and I did not ask for it.

Test: `tests/refine_identities/needs/test_checker2_eq_of_equal_infinities.py`.

### 2.3 Misses v3 also has (not filed)

- `Max(x, y, z)` under `Q.negative_infinite(z)` alone, and `Min` under
  `Q.positive_infinite(z)`. Where the input is defined, `x` and `y` are
  real, so `Max(x, y)` would be right. The decider needs `Q.extended_real`
  of the other argument. With `Q.real(x)` it fires.
- `Min(x, y, z)` under `x <= y <= z` gives `Min(x, z)`, not `x`. This
  needs transitivity. `Max` gets `z` because of the order of the pairs.
- `Max(w, x, y, z)` with `Q.lt(w, 0)` and `x > 0` stays `Max(w, x)`.
- `Max(x, y)` under `Q.lt(y, z) & Q.lt(z, x)` is not decided
  (transitivity).
- `KroneckerDelta(i, j, (1, 3))` under `Q.gt(j, 3)`: only `i` is checked
  against the range.
- `frac(x)` on `[n, n+1)` for a symbolic integer `n`.
- `Heaviside(x, 1)` under `Q.extended_nonnegative(x)`: this needs merging
  the cases.
- `atan2(y, x)` under `Q.positive_infinite(x) & Q.real(y)`.
- `Piecewise((Abs(x), x >= y), (0, True))` under `Q.positive(y)`: the
  branch is not refined from its relational condition.
- `x**(-y)` under `Q.zero(x) & Q.negative(y)` (that is `0`).

## 3. Clean, checked specifically

- **The `-oo` guard.** SymPy's `ask` is unsound for `Q.eq`/`Q.ne` only when
  an argument is known infinite. Examples: `Q.eq(x, y)` is "True" for
  `x = -oo, y <= 0`; for `x = y = +oo`, `Q.lt` is "False", which is correct.
  - For merely possible infinities (extended signs), `ask` answers `None`.
  - For compound arguments (`x+1`, `2*x`, `-x`, `x**3`, `exp(x)`, `x*y`,
    `1/x`) with `x = +-oo`, every non-`None` answer was correct.
  - `Q.infinite(u)` is provable for all of these except `x + y` with
    opposite infinities, where `ask` answers nothing unsound either.
- **Relation decider.** Refutation through the negation, and `And` refuted
  after an undecided conjunct, gave no wrong result. `Ne` through `Q.lt`
  and `x < oo` / `x > -oo` also behaved (refuted at `+oo`, undecided for
  extended real, true for real). Under inconsistent assumptions nothing
  reaches the `(nan, True)` default.
- **Undecided `Piecewise` declined.** No definition returned a `Piecewise`
  it had introduced. Nested `Piecewise` inputs keep their undecided
  branches, and each branch is refined under its condition.
- **Branch drop on `ValueError`.** I looked for spurious `ValueError`s in
  branch refinement: infinite facts with relational conditions, and
  `Pow._eval_refine`'s bare `ask`. I found none, so no branch was dropped
  wrongly.
- **Result cache.**
  - The key has the assumptions, the mode and the state, so the same node
    under a branch's added condition, inside a split, and at top level gave
    three independent results. In 20 mixed expressions, none leaked.
  - Results are identical under PYTHONHASHSEED 0 to 3 on the 3- and
    4-argument Max/Min cases.
- **integer_funcs.**
  - `frac(x) = x - floor(x)`: its domain excludes `+-oo` correctly
    (unchanged under `Q.infinite`), and it fires on Gaussian integers
    (`frac(1+I) = 0`).
  - The shift row with Gaussian or `I*n` terms: checked at 90 to 540
    points per case.
  - `floor(y)` and `ceiling(y)` terms shift only for finite or real `y`.
    They stay for extended-real or unknown `y`.
  - Mod/Rem `b*G(sign(a/b), 2)/2`: checked for all four sign combinations.
    The imaginary, infinite and zero divisors stay unchanged.
- **`0**e = zoo`.**
  - It fires only for a zero base with a negative (finite, real) exponent.
  - It does not fire for extended-negative, `-oo`, nonpositive or
    imaginary exponents, or `re(e) < 0`.
  - Downstream (`log`, `Abs`, `sin`, `exp`, sums and products of poles),
    every result equals the input's value at the pole, or the input is
    `nan` there.

## 4. Commits on `ri/check2`

- needs test: firing cap
- needs test: `Eq` of equal infinities
- this report

No processes left running.
