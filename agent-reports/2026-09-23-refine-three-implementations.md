# Agent report: three implementations of the refine handlers, compared

- **Date:** 2026-09-23
- **Status:** measurement complete except where marked `[pending]`
- **Read this if:** you want to know whether a stronger model, or a parallel
  team of models, writes better refine handlers than the `reasoning` project's
  original, and which handler set to build on
- **Stale after:** any of the three handler packages changes, or the SymPy pin
  (`ddbb536`) moves

## 1. TL;DR

Three complete implementations of the same 56 `refine` registry keys now live
side by side behind one dispatcher (`SATREFINE_HANDLERS=handlers|handlers_v2|handlers_v3`):

| | `handlers` (original) | `handlers_v2` (single agent) | `handlers_v3` (parallel team) |
|---|---|---|---|
| Written by | the `reasoning` project's agents, with verifiers | one Fable 5.1 agent, whole problem, no verifier | 9 implementers (3 Fable, 6 Opus 5.5) + 9 verifiers (3 Fable, 6 Opus), one family each |
| Handler modules / lines | 33 / 1,887 | 18 / 1,709 | 9 / 3,207 |
| Own tests | 469 (6,245 lines) | 161 (1,110 lines) | 1,005 (3,552 lines) |
| Fuzz, seed 2, 1,500 identical inputs: rewrites fired | 385 | 424 | 453 |
| Fuzz: unsound / crash / non-SymPy return | 0 (2 nan-at-pole false alarms) / 0 / 3 | 0 (2 same false alarms) / 1 inherited recursion / 0 | 0 / 0 / 0 |
| Known unsound rules after verification | 3 (inherited SymPy matrix rules) | none found, but no adversarial pass | 0 (12 found and fixed by verifiers) |
| Agent cost (reported agent tokens) | n/a | ~240k, 39 min | ~1.7M across 18 agents, ~3 h elapsed under a 3-Fable/6-Opus cap |

The parallel team produced the soundest and broadest handler set, at roughly
seven times the token cost of the single agent. Half of that cost was the
verifier pass, which found 12 real defects the implementers had shipped
(9 of them in Opus-written families), so the verifier pass is where the
money went and where the quality came from. The single agent, unverified,
shipped nothing the fuzzer could break except a crash it inherited by
keeping SymPy's vendored re/im handler; it is the best cost-per-rule result
but its soundness claim is weaker because nobody attacked it.

Both rewrites refused the three unsound matrix rules the original inherited
from SymPy (orthogonal determinant is 1, unitary inverse is the elementwise
conjugate, conjugate(U)*U is the identity). Both rewrites also skip a dozen
or so rules the original has (factorial, gamma, Min/Max, conjugate, arg),
visible as their misses on the original's suite.

## 2. Setup

- One dispatcher (`satrefine/_upstream.py`, SymPy's `refine.py` vendored) and
  one selectable `ask` backend (`sympy`, `satassume`, `combined`); the handler
  package is chosen by `SATREFINE_HANDLERS` at import.
- The rewrites were blind: no implementer or verifier could read the other
  packages, their tests, or the `reasoning` reports. The parallel team got a
  package docstring assigning keys to modules, a shared `_common.py`
  (splitting an argument into `k*unit + rest`, parity, integrality), a
  conftest, and a registry test that fails on a key registered twice.
- Every family in `handlers_v3` was followed by an adversarial verifier
  (Fable for Pow/exp/log, inverse, complex parts; Opus for the rest) told to
  construct counterexamples, verify them numerically, fix confirmed problems
  minimally and add regression tests.
- Measurements: `tools/refine_scoreboard.py` (each suite under the three
  backends, with per-test out-of-scope counts), `tools/refine_fuzz.py`
  (random expressions and consistent assumption sets, numeric check at 20
  digits in the complex plane, SymPy's own refine run on the same inputs),
  every suite run against every package, and `tools/refine_oracle.py`
  (SymPy's old assumption system as an independent oracle, see section 6).

## 3. Verifier findings in `handlers_v3` (all fixed, with regression tests)

| Family (model) | Defects | What |
|---|---|---|
| matrices (Opus) | 5 | four rules trusted SymPy's `ask`, which calls a product of symmetric matrices symmetric, a diagonal block of an orthogonal matrix orthogonal, and derives unitary from orthogonal for complex matrices; negative index wrapping under `Q.diagonal` |
| Pow/exp/log (Fable) | 3 | inherited crash in the `(-1)**(sum)` rule (SymPy's own refine crashes identically); `log(x**a)` at `0**0`; `log(1/x)` firing for infinite x |
| integer functions (Opus) | 2 | `floor(y)` of a possibly infinite y pulled out as a whole number; contradictory assumptions raised instead of returning unchanged |
| Min/Max/deltas (Opus) | 1 | KroneckerDelta trusted `ask(Q.eq(x, y))`, which SymPy answers True for x = -oo and y extended-nonpositive |
| trig (Opus) | 1 | `sinc` crashed on a literal odd half-pi shift (built `sin(pi/2)`, which SymPy evaluates to 1) |
| complex parts (Fable) | 0 unsound, 1 coverage | a guard refused every literal negative exponent |
| combinatorial (Opus), inverse (Fable), hyperbolic (Opus) | 0 | test-harness fixes only |

Nine of the twelve defects were in Opus-written families; the three in a
Fable family were all at degenerate points (a crash inherited from SymPy,
`0**0`, infinity), none on a branch cut. The verifiers' own tooling also
misfired twice (sequential `subs` producing spurious `zoo`), which they
diagnosed themselves.

## 4. Coverage on identical inputs (fuzz, seed 2)

Rewrites fired per expression head, same 1,500 random inputs for each
package (higher is more coverage; every fired rewrite was numerically
checked and none was unsound):

| head | tried | original | single | parallel |
|---|---|---|---|---|
| Abs(...)**n | 34 | 11 | 19 | 23 |
| acosh(cosh) | 26 | 9 | 19 | 21 |
| asinh(sinh) | 25 | 14 | 11 | 19 |
| frac | 31 | 8 | 7 | 13 |
| binomial | 26 | 2 | 8 | 9 |
| Min / Max (2 and 3 args) | 96 | 18 | 20 | 24 |
| Mod / Rem | 49 | 8 | 9 | 9 |
| ceiling / floor | 42 | 13 | 15 | 20 |
| KroneckerDelta | 16 | 0 | 2 | 5 |
| asech / acsch / acoth | 68 | 3 | 8 | 12 |
| log(exp) | 29 | 25 | 17 | 19 |
| sign | 21 | 11 | 4 | 11 |
| sinc | 20 | 3 | 12 | 3 |
| csch | 21 | 7 | 7 | 1 |
| re / im | 51 | 48 | 40 | 47 |
| all heads | 1,482 | 385 | 424 | 453 |

The original leads on `log(exp(x))`, `csch`, and `sign`; the single agent on
`sinc` and `Abs`; the parallel team on most of the rest. Some of the original's
extra fires are rules the rewrites refused on purpose (its `sign` handler
asks without passing the assumptions and fires on symbol-declared facts; its
`log(exp)` fires on cases the rewrites consider unproven).

## 5. Every suite against every package (combined backend)

| Suite (tests) | `handlers` | `handlers_v2` | `handlers_v3` |
|---|---|---|---|
| original's, `tests/refine` (469) | 463 | 451 | 449 |
| single agent's, `tests/refine_v2` (161) | 110 | 161 | 126 |
| parallel team's, `tests/refine_v3` (1,005) | 956 | 963 | 1,005 |

Read with care: a suite encodes its authors' choices. Several of the single
agent's tests assert *correct* matrix behavior the original gets wrong
(orthogonal determinant left alone, unitary inverse via the adjoint), so the
original's 110 includes real soundness failures, not just missing rules. In
the other direction, many tests in the rewrites' suites check only that a
rewrite is sound, which a package passes by not firing, so the 956 and 963
overstate the original's and the single agent's coverage of the parallel
team's rules; the integer-function and combinatorial families are where they
actually diverge. The per-head fuzz table above is the fairer coverage
measure.

The two rewrites miss the same things on the original's suite: factorial
and gamma at infinite arguments, Min/Max order rules stated as relations the
rewrites route differently, conjugate and arg rules with preconditions the
rewrites judged too weak, plus 3 to 4 tests that scan the original's source
files.

## 5a. Each package's own suite under the three ask backends

| Package, suite | `sympy` | `satassume` | `combined` | satassume in-scope gaps |
|---|---|---|---|---|
| original, `tests/refine` (473 incl. xfails) | 462 | 412 | 463 | 0 (59 out-of-scope losses) |
| single agent, `tests/refine_v2` (161) | 160 | 143 | 161 | 0 (18 out-of-scope losses) |
| parallel team, `tests/refine_v3` (1,005) | 1,001 | 915 | 1,005 | 0 (87 out-of-scope losses; one flagged test relies on a wrong SymPy answer, see below) |

The pattern from the first scoreboard holds for all three suites: what
satassume alone loses is relations and matrix predicates, which are out of
its declared scope. The scoreboard flags one in-scope loss on the parallel
team's suite, the `arg(exp(I*t))` rule, whose handler asks
`Q.imaginary(I*t)` under `Q.real(t)`. SymPy answers True; satassume answers
`None`. satassume is right: SymPy's own definition says 0 is not imaginary,
`t` may be 0, and SymPy keeps answering True even under `Q.zero(t)`. With
`Q.nonzero(t)` added, satassume answers True. The satassume-only runs are 3
to 4 times faster than the SymPy-backed ones on every suite.

## 6. Old-assumption oracle

[pending: results of `tools/refine_oracle.py` on the three packages]

## 7. SymPy defects surfaced along the way

These are in SymPy at `ddbb536`, not in any handler set; every package has
to guard against them, and satassume inherits the matrix and relation ones
when it routes out-of-scope queries to SymPy's `ask`:

1. `ask(Q.ge(x, y), Q.positive(x) & Q.negative(y))` raises "inconsistent
   assumptions" (the facts about two different arguments are merged).
2. `ask` calls a product of symmetric matrices symmetric, a diagonal block of
   an orthogonal or unitary matrix orthogonal or unitary, and infers unitary
   from orthogonal for complex matrices.
3. `ask(Q.eq(y, x), Q.negative_infinite(x) & Q.extended_nonpositive(y))` is True.
4. `ask(Q.zero(y**2), Q.imaginary(y))` is True, because `Q.zero` is
   `~Q.nonzero & Q.real` and `Q.nonzero` means real and nonzero.
5. `sign((1-I)**2*(1+I))` auto-evaluates with the wrong sign.
5a. `ask(Q.imaginary(I*t), Q.real(t))` is True, and stays True under
   `Q.zero(t)`, although `Q.imaginary(0)` is False by SymPy's definition.
6. SymPy's own `refine`: the nested-power rewrite `(x**a)**b -> Abs(x)**(a*b)`
   is wrong for odd `a` and for imaginary `x`; `refine((-1)**(-n - 1/2), Q.even(n))`
   crashes; `re(x**z)` under `Q.imaginary(z) & Q.real(x)` recurses forever;
   `refine(sign(Abs(x)), Q.imaginary(x))` gives 0; the three matrix rules above.
7. Undecided relation queries cost 1 to 20 s each in SymPy's `ask`; every
   package had to ration them.

## 8. What to build on

Take `handlers_v3` as the base: it is the only package with zero known
defects after an adversarial pass, and it fires most often on identical
inputs. Port the original's missing rules one at a time after checking each
against the fuzzer and the oracle (the ones its suite shows: factorial and
gamma at infinity, the Min/Max relation forms, the conjugate and arg cases),
and take the single agent's `sinc`, `Abs` and `Mul` rules where they are
broader. Keep the three suites: run all of them against the chosen package
and let the deliberate refusals be recorded as such.

On process: one strong agent gets a sound, decent set cheaply; the parallel
team gets a broader and better-verified one at several times the cost, and
that cost is mostly the verifiers. If cost matters, the cheapest good
configuration this experiment suggests is a single strong implementer
followed by per-family verifiers, since the verifiers are what turned
twelve shipped defects into zero.
