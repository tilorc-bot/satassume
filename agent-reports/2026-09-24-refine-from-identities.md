# Agent report: refine handlers from identities, with the conditional rules generated

- **Date:** 2026-09-24
- **Status:** experiment complete on one key (`log`); code on branch
  `refine-identities` as `satrefine/handlers_identities/`,
  `tests/refine_identities/` (55 passed, 4 expected failures under both the
  released SymPy 1.14 and the development checkout at `6379c4da69`) and
  `tools/refine_specialize.py`
- **Read this if:** you are deciding whether refine handlers should be
  written as procedures (all three packages so far) or as mathematical
  identities with the case analysis generated, or you want the two
  infrastructure defects and the one wrong `ask` answer this surfaced
- **Stale after:** the vendored dispatcher gains the driver fix from
  section 5, or the SymPy `Q.zero` answer in section 6 is fixed
- **TL;DR:** the 83-line `handlers_v3` `log` handler (8 conditional rules)
  and the 24-line original (3 rules) are both specializations of two facts
  about the logarithm plus two exponential forms, four rows of
  `(lhs, rhs, domain)` with no hypotheses. Running those rows under a
  catalog of assumption profiles generates the familiar conditional rules
  (eight, all verified numerically under the combined backend), and the
  compiled table covers the team's firing inputs except four that need
  prover capabilities `refine` lacks (a two-branch case split, and interval
  reasoning for `arg` inside `floor`). The `log`-specific source is two
  lines. The cost is a rewrite ordering the procedural hypotheses supplied
  implicitly, a one-line fix to the `refine` driver, three simple `im`
  rules, and a dependency on `ask` being sound: under the `sympy` backend
  the generator's numeric check caught SymPy answering
  `ask(Q.zero(b**2), Q.imaginary(b)) -> True`; satassume answers it
  correctly, so the combined backend is unaffected.

## 1. The question

The three-implementation comparison
(`2026-09-23-refine-three-implementations.md`) shows the same `log` key
written three times, at 24, 27 and 83 lines, each a list of conditional
rewrites: `log(b**e) -> e*log(b)` when `b` is positive and `e` real,
`-> e*log(Abs(b))` when `b` is real and `e` even and one of them nonzero,
`-> e*log(-b) + I*pi` when `b` is negative and `e` odd, and so on. Every
one of those is a branch-cut question answered by hand. The question here:
can the list be replaced by the identities the rules are cases of, with
the cases derived by `refine` itself, and does that give fewer lines for
the same coverage.

## 2. The identities

SymPy's principal branch has imaginary part in `(-pi, pi]`. Write

    principal(w) = w + 2*pi*I*floor(1/2 - im(w)/(2*pi))

for the representative of `w` on that strip. Then, with no hypotheses
beyond the arguments being nonzero:

| row | identity | where it comes from |
|---|---|---|
| A | `log(exp(z)) = principal(z)` | `log` inverts `exp` up to the branch |
| D | `log(x) = log(Abs(x)) + I*arg(x)` | definition of the complex logarithm |
| B | `log(b**e) = principal(e*log(b))` | A composed with `b**e = exp(e*log(b))` |
| C | `log(p*r) = principal(log(p) + log(r))` | A composed with `p*r = exp(log(p) + log(r))` |

Only A and D are written in `satrefine/handlers_identities/log.py`. B and
C are produced at import by `derive()` from two *exponential forms*, rows
`(L, W, domain)` meaning `L == exp(W)`, which are facts about powers and
products rather than about `log` and are reusable by any function whose
branch behavior the exponential governs. A fifth row for the negated pair,
`log(p*r) = principal(log(-p) + log(-r))`, was in an earlier version and
turned out redundant: under two negative factors, row C's bookkeeping
collects two `I*pi` from row D and wraps them away.

Every conditional rule in the three packages is one of these rows with the
`floor` collapsed under that rule's hypothesis. For example, under
`Q.negative(b) & Q.odd(e)`, `im(e*log(b))` is `pi*e`, the floor becomes
`(1 - e)/2`, an integer, and row B reads `e*log(-b) + I*pi`, which is
`handlers_v3`'s rule. The nonzero guard the v3 verifier added to the even
rule reappears by itself, because `0*log(Abs(0))` is `nan` in the derived
form too.

## 3. The engine

`satrefine/handlers_identities/_engine.py`, shared by any handler written
this way:

- **Matching.** A row's left side is a pattern over plain symbols. A symbol
  binds anything; a product of two symbols binds one factor against the
  rest, once per factor (linear, no commutative search); any other head is
  matched structurally. This is the one-factor-plus-rest matcher, not
  `sympy.unify`.
- **Firing.** For a binding: the domain must be provable through
  `_upstream.ask`; the substituted right side is refined; it is rejected if
  any `floor`, `im` or `arg` survives; it is accepted only if a rewrite
  ordering strictly decreases.
- **The ordering** is `(factors under logarithms of exponentials, powers
  and products; logarithms whose argument is not provably positive)`. It
  is what the procedural hypotheses supplied implicitly. Without it rows
  C and D undo each other on `log(-x)` under `Q.negative(x)` forever; with
  it `log(-x)` stays and `log(x)` becomes `log(-x) + I*pi`, matching
  `handlers_v3`. Any identity-based engine has to state such an ordering
  explicitly, per function family.
- **Re-entrancy.** Candidates are refined with the `log` handler switched
  off; their own logarithms are rewritten by the dispatcher after
  acceptance, under the same ordering. Without this, row D on
  `log(Abs(b))` reproduces itself and recursion never ends.
- **Three simple `im` rules** (`im(log w) = arg w`, `im` distributes over
  sums, real factors pull out), registered on `im` ahead of the vendored
  handler, which expands into real and imaginary parts and leaves
  `arg(re(w) + I*im(w))` that nothing can refine.

## 4. Results on the comparison battery

The 27 inputs of the three-implementation report, identity engine live
(`tests/refine_identities/test_log.py`, combined backend):

| relation to `handlers_v3` | inputs |
|---|---|
| both fire, same form | 14 |
| both fire, different but correct form | 1 |
| team fires, identities do not | 4 |
| identities fire, team declined | 1 |
| neither fires | 7 |
| numerically wrong outputs | 0 |

The different form is `log(x**n)` under a negative base and odd exponent:
`log(-x**n) + I*pi` through row D rather than `n*log(-x) + I*pi` through
row B, because `ask` cannot show `(1 - n)/2` is an integer for odd `n`
(it can for `n/2` with even `n`). The extra firing is `log(x**(1/3))` under
a negative base, which the team's docstring declined; the exact identity
gives `log(-x)/3 + I*pi/3` and has no reason to refuse.

The four misses are three prover gaps, none of them about `log`:

| input | needs |
|---|---|
| `log(x**2)`, `Q.real(x)` -> `2*log(Abs(x))` | a two-branch case split on the sign of `x` whose branches agree |
| `log(x**2)`, `Q.imaginary(x)` -> `2*log(Abs(x)) + I*pi` | the same, on the quadrant |
| `log(x*y)`, `Q.positive(x) & Q.complex(y)` -> `log(x) + log(y)` | `arg(y)` in `(-pi, pi]` inside `floor` |
| `log(1/x)`, `Q.imaginary(x)` -> `-log(x)` | `arg(x)` in `(-pi, pi)` inside `floor` |

`handlers_v3` encodes each of these by hand inside `log`. Here they are
missing `refine` capabilities (interval reasoning for `floor`, merging a
`Piecewise` whose branches agree) that would serve every handler once
added. The identity engine already handles the parity case `x**2` under
`Q.negative(x)` -> `2*log(-x)` and the mixed-sign products, including the
three-factor one, from the rows alone.

## 5. Generating the conditional rules

`tools/refine_specialize.py` (library in
`satrefine/handlers_identities/_specialize.py`): for each distinct left
side, assign to each variable one of `{none, positive, negative,
nonnegative, real, imaginary, even, odd, integer, even(v/2), odd(v/2)}`,
run the engine, keep the profiles whose bookkeeping collapsed, add back the
domain atoms the profile does not prove, drop profiles strictly stronger
than another with the same result, merge rules equal under swapping the two
product factors, and check each survivor numerically at a point satisfying
its hypothesis. Output on the development checkout:

```
generated 8 rules from 4 identity rows in 31s

  ok    Rule(log(exp(z)), z, Q.real(z))
  ok    Rule(log(b**e), e*log(b), Q.positive(b) & Q.real(e))
  ok    Rule(log(b**e), e*log(-b), Q.even(e) & Q.negative(b))
  ok    Rule(log(b**e), log(-b**e) + I*pi, Q.negative(b) & Q.odd(e))
  ok    Rule(log(p*r), log(p) + log(r), Q.positive(p) & Q.positive(r))
  ok    Rule(log(p*r), log(p) + log(-r) + I*pi, Q.negative(r) & Q.positive(p))
  ok    Rule(log(p*r), log(-p) + log(-r), Q.negative(p) & Q.negative(r))
  ok    Rule(log(x), log(-x) + I*pi, Q.negative(x))
```

Under `SATREFINE_BACKEND=sympy` the same run emits a ninth rule, for an
imaginary base and imaginary exponent, marked WRONG by the numeric check;
section 6 traces it to a wrong `ask` answer that satassume does not give,
so the combined backend never sees it.

Compiled into match-and-substitute handlers and run on the same 27 inputs,
the table gives 13 same-form, 2 different-form, 4 misses, 0 wrong: the
procedural `log` handler, generated. The one row the live engine has and
the table lacks is the rational-exponent case, because the catalog has no
rational profile.

**On the metric "fewer lines for the same cases".** `log`-specific source:
2 fact rows and 2 exponential-form rows, against 83 lines in `handlers_v3`
and 24 in the original. Shared infrastructure, counted once for all
handlers: the engine (about 120 lines), the three `im` rules, and the
generator. Of the team's 15 firing cases, the rows reproduce 11 exactly and
2 in another correct form, and miss 4 pending the capabilities above.

## 6. Defects surfaced

1. **`refine` driver.** After rebuilding a node from refined children,
   `refine` looks up a handler for the rebuilt node's head without
   refining the children the constructor just created by auto-evaluation.
   `im(e*(log(-b) + I*pi))` auto-expands into `re(e)`, `im(e)`, `arg(-b)`
   terms and returns unrefined. The fix, in `_engine.refine`, is to refine
   the rebuilt node again whenever its structure changed. The vendored
   `_upstream.refine` is unchanged (it must stay behavior-identical); the
   identity handler uses the fixed driver for candidate evaluation only.
   The same fix applies to SymPy's `refine`.
2. **Wrong `ask` answer in SymPy.** On the development checkout,
   SymPy's `ask(Q.zero(b**2), Q.imaginary(b))` returns `True` (it correctly
   says the square is real and not imaginary, then concludes zero; `b**3`
   is fine). Through the `FinitePredicate` handler for `log` this makes
   `log(b**2)` "infinite", the floor handler returns its argument, and
   under `SATREFINE_BACKEND=sympy` the generator emits a rule for an
   imaginary base and imaginary exponent that its numeric check marks
   WRONG. satassume answers `False`, so the `satassume` and `combined`
   backends never produce the rule: an in-scope case where the engine is
   right and SymPy is wrong, found by a numeric verifier rather than by
   the corpus. The check is why the generator must verify every rule.
3. **`refine_floor_ceiling` splits only an `Add`.** The identity's floor
   argument had to be written as `1/2 - im(w)/(2*pi)` rather than
   `(pi - im(w))/(2*pi)` for the integer term to be split off.

## 7. What this does and does not settle

Settled: for `log`, the procedural rule list is redundant with four rows,
the rows are printable as theorems and reviewable as such (the v2 defect
at `b = e = 0` is a missing premise on the page), and the conditional
table can be generated and verified rather than written. Not settled: cost
(every candidate refines a floor of an `im` or `arg`, and the product row
tries every factor; the generated table is the answer to that, and it was
not timed against the packages), whether the ordering generalizes to
other families (trig and `floor` want their own measure), and the three
prover gaps, which are `refine` work rather than handler work.
