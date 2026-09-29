# Agent report: irrational constants as bounded LRA variables (item 2, landed)

- **Date:** 2026-09-26
- **Status:** landed on `main` (`b208af3`, test fix `b58e762`); risks and
  changed answers on the item 2 issue.
- **Read with:** `2026-09-25-irrational-0-measurements.md` (stage 0),
  `2026-09-25-irrational-1-build.md` (build), `2026-09-25-irrational-2-tuning.md`
  (cost). The build report describes evalf bounds; the landed code uses
  interval arithmetic (below).

## What landed

A real closed constant in a linear position of a relation (`pi` in
`x <= 3*pi/2`, `t > -pi/2`) is an LRA variable, one per constant (rational
factors and sums are split, so `pi/2`, `pi` and `-3*pi` share `pi`), with
rational bounds `lo < c < hi` asserted once per session. `pi*x` stays
unreadable (nonlinear); Floats stay unreadable (SymPy reads them exactly in
`<` but at precision in `Eq`; a decision for the owner).

**Bounds.** mpmath's interval context at 128 bits, outward rounded, over
rationals, pi, E, `+`, `*`, `**`, exp, log, sin, cos, tan, atan (atan by
monotonicity with directed rounding); every transcendental step widened by
`2**-120` relative; a domain violation (log of an interval reaching 0, tan
across a pole, a fractional power of a base reaching below 0) gives None,
so a result also proves the value real; every intermediate stays within
`2**±4096` (exp is sized before it is applied); tiny ends move outward to 0
or `2**-4096`. An exact zero SymPy cannot prove gets a narrow interval
around 0.

**Tuning.** A constant the engine knows to be real gets no guard node and
no interface equality (a relaxation: `Q.eq(f(x), f(pi)) | Q.eq(2*x, 2*pi)`
is None, as on the old `main`); irrational constant nodes do not count
towards the cone threshold (time only; differential of long-lived against
fresh engines: 0 differences).

## Review: five rounds, each found a defect

| round | finding | fix |
|---|---|---|
| 1 | `constant_bounds(exp(exp(exp(5))))`: `Rational(Float)` built a ~4e64-bit integer, the OOM killer took the session down | no bounds beyond `2**±4096` |
| 2 | strict evalf is loose outside its table: `sign(Z)` of an exact zero got bounds near 1, `ask(Q.lt(2*sign(Z), 3*sign(Z)))` True (wrong); `sin(exp(exp(exp(5))))` hung | whitelist of heads, arguments sized bottom-up |
| 3 | `tan` next to a pole and `log` next to 1 claim full accuracy; a saturating `atan` hid the 30/45-digit disagreement: wrong True/False | every argument needs its own bounds |
| 4 | (design change) evalf's error estimate replaced by interval arithmetic | `c05c00c` |
| 5 | mpmath's interval exp/log round an approximation in the requested direction: `exp(891)`, `log(156434)` have an upper end below the value; `pi*(log(156434) - Y)` wrong True; tiny values (`pi**-(10**20)`) raised OverflowError | `2**-120` widening, tiny ends outward |

Final differential (random trees near pi/2 multiples, 1 and 0, deliberate
cancellation, 600-digit reference): 19,813 checked, 2,918 without bounds,
0 wrong.

## Answers (stream, against `main` before this landing)

- 106 more definite (90 distinct, 26 sets): 60 agree with `sympy.ask`, 30
  where SymPy says None were checked by hand, 0 contradict.
- 24 new ValueErrors on 3 assumption sets, each truly inconsistent (`x`
  negative and positive, or positive and zero, next to a `pi` bound); SymPy
  raises on all 24.
- 0 less definite. gate2: 0 changed. Refine scoreboard: the 6 relation
  losses against `pi` are gone (417 -> 423 passed).

## Cost

Pi, `tools/ab.py` against `main`: +38% as built, +30% after tuning
(`d530e98`: 2.667 s -> 3.47 s); the interval bounds change nothing
measurable locally. All of it is in the 663 queries whose assumption sets
used to fail as unreadable (47 ms -> about 860 ms); the floor (pi replaced
by 355/113 in those queries) is about +0.73 s: the price of building and
searching sessions `main` abandoned. Item 3 (relevance) wins back about
10%.

## Risks

- Soundness rests on mpmath's interval functions being within `2**-120`
  relative after its own rounding (measured about `2**-140`). The Pi runs
  mpmath 1.4.1, locally 1.3.0; only 1.3.0 was probed.
- Deeply nested constants: evalf and the interval recursion are
  exponential in shared subtrees (no per-call memo); not reachable from
  SymPy-built expressions today.
- Distinct spellings of one value are unrelated variables (relaxation).
- Tiny constants (`pi**-(10**20)`) get bounds around 0 and cannot be shown
  positive.
