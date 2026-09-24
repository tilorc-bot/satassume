# Design report: fuzzing and verification strategy for the refine handlers

- **Date:** 2026-09-23
- **Status:** design, not implemented. Measurements were taken on the
  `refine-monorepo` branch (the handler packages, `tools/refine_fuzz.py`,
  `tools/refine_oracle.py`, `satrefine/harness.py`) and on `main` (the
  Hypothesis-based engine fuzzers).
- **Read this if:** you add rules to a handler package or decide what
  verification runs before one is merged.
- **Stale after:** the handler packages land on `main`, or the relation
  theories on `main` change what `satassume` answers.

## 1. TL;DR

Every defect the adversarial verifiers found that the random fuzzer missed
sat at a point the fuzzer cannot reach or cannot judge: `0**0`, infinity, a
literal `pi/2` shift, a wrong `ask` answer. The changes with the best
value, in order:

1. **Exact evaluation at a fixed adversarial point list, with singular
   points classified rather than compared.** Half a day. Catches the
   `handlers_v2` log defect and four of the team's twelve.
2. **An ask audit**: record every query per case and re-check each `True`
   answer at the sample point. Two days. Catches the five defects caused
   by SymPy's `ask` being wrong, which no expression-level check can
   attribute.
3. **Precondition-driven generation** from each rule's stated
   precondition (satisfying, barely violating, boundary), with the rule
   table shared by handler and generator. Three to five days.
4. **Port the generator to Hypothesis** in the style `main` already uses
   for the engine: tuple grammars converted to SymPy late, shrinking, the
   example database as the regression corpus. Two to three days.

## 2. What the current tools do well and badly

### 2.1 `tools/refine_fuzz.py`

Good: identical inputs for the three packages (seeded per case since
today), SymPy's own `refine` on the same inputs so inherited bugs are told
apart, per-head fire counts (the fairest coverage table in the
three-implementations report), and fast enough to run on every change.

Bad, in order of damage:

- **Degenerate points are unreachable.** `draw()` gives integers in
  `[-6, 6]` and floats in `[-3, 3]`, never `oo`, `zoo` or `nan`, and the
  vocabulary has no `Q.infinite`. The team's `log(1/x)` at infinite `x`,
  `floor(y)` at infinite `y` and `KroneckerDelta` trusting `Q.eq` at
  `x = -oo` could not be found in principle.
- **Uniform sampling over 52 heads and 36 inner shapes.** The
  `handlers_v2` defect (rule L4: `log(x**n) -> n*log(Abs(x))`, which at
  `x = 0, n = 0` turns `log(1) = 0` into `0*zoo = nan`) needs head `log`,
  inner `a**b`, two combos that can draw 0 and both draws landing on 0:
  about one case in several hundred thousand, against runs of 1,500 to
  3,000. The `sinc` crash on a literal odd half-pi shift is reachable at
  roughly one in 40,000. `(-1)**(-n - 1/2)` is not in the grammar; matrix
  expressions are not in it at all, so the five matrix defects had no
  chance.
- **Contradictory assumptions are skipped** (line 247 drops any
  `ValueError` mentioning "inconsistent"), which hides exactly the team's
  "raised instead of returning unchanged" defect.
- **Float comparison** caused both false alarms: the vendored `im` rule at
  a removable `0/0` (one side `nan`, a singular mismatch, not a wrong
  value) and `atanh(tanh(x**3))`, where `tanh(27)` is `1` to twenty digits
  so the original is `oo` and the rewrite `27`. `numeric()` also folds
  `oo` and `zoo` into one string, so `Abs(0**e) = oo` against
  `Abs(0)**e = zoo`, the reason for the team's exponent guard, passes.
- **Branch cuts by chance**: nothing samples both sides of the negative
  axis; imaginary samples are `I*Float`, never `-1 + I*eps`.
- **No shrinking**: a failing 9-node expression is reported as is.

### 2.2 `tools/refine_oracle.py`

Good: exact points (integers, rationals, surds, Gaussian rationals)
filtered by the old system's `is_*` facts, `0` and `-1` always present, so
its template `log(x**n)` under `x` real, `n` even has `(0, 0)` among its
candidate points and would very likely catch the `handlers_v2` defect by
itself. `numval`/`close` (30 digits) separate "singular mismatch" from
"wrong value". `run_forked` kills a stuck case by wall clock, which
matters because `SIGALRM` cannot interrupt big-integer arithmetic. The
step log and `blame()` name the handler that produced a wrong
intermediate. Its matrix section with explicit 2x2 instances is the only
check of the matrix keys anywhere. Mode B mines SymPy's tests for free.

Bad, as its own report says: the old system is sometimes wrong (discarded
numerically, but only when the point set exposes it); gap versus
equivalent form is judged by `count_ops` with slack 2; matrices have no
old-system equivalent beyond zero and identity; no infinities and no
cut-adjacent complex points; mode B replays only direct asserts. It is
also slow and hand-templated, so it checks only the shapes its author
imagined.

### 2.3 Hypothesis on `main`

Hypothesis is unused by the refine tools and on the `refine-monorepo`
branch, but `main` uses it for the engine:

- `tests/test_lra_fuzz.py`: `@st.composite` strategies for linear atoms
  and CNF cases, differential against an exact Fourier-Motzkin oracle over
  `Fraction` plus a rational-grid second opinion, the protocol checked live
  by `theory_harness.Recorder`; `settings(max_examples=150, deadline=None,
  suppress_health_check=[too_slow, data_too_large])`.
- `tests/test_euf_fuzz.py`: naive congruence closure as oracle,
  `EUF_FUZZ_EXAMPLES` to raise the count, clause minimality in an
  `xfail(strict=False)` test so a weak answer is reported, not failed.
- `tests/test_verify_soundness.py`: an ask-level differential fuzzer. Its
  strategies build a **tuple AST** and convert to SymPy only in
  `to_sympy`; the oracle evaluates atoms at concrete points (rationals,
  `I`, `oo`, `-oo`, `zoo`, optionally `nan`) and treats undecidable atoms
  as free Booleans. Default 60 examples, `VERIFY_SLOW=1` for 2,000, and a
  hand-picked `_EDGE` list run as parametrized tests.
- `tests/test_relations.py`: random order formulas against a grid model
  checker.

None uses `target()`, a custom example database or a deadline. Nothing in
`hypothesis.extra` knows SymPy; expression strategies are ours to write.

Two facts from `main` change the refine picture. Relations are in scope
there (`Q.lt/le/gt/ge/eq/ne` go to the LRA and EUF theories, guarded by
realness of the terms), so the scoreboard's `relation` out-of-scope
category shrinks to what the theories cannot interpret, and the fuzzer
must generate relational assumptions as first-class inputs rather than the
30 percent afterthought in `relations()`. And `satassume` now answers the
inverse-trig bounds itself: `refine(atan(tan(x)), Q.positive(x) &
Q.lt(x, 1))` took 276 ms under the combined backend and 7 ms under
`satassume` alone; SymPy's `ask` alone took 0.03 to 2.3 s per relation
query. Every budget below assumes `satassume` runs first.

## 3. Proposed design

The parts are independent; each can be built and run alone.

### 3.1 Precondition-driven generation

Every `handlers_v3` rule is documented as shape, precondition, result.
Make that table data, shared by the handler and the generator:

```python
Rule("L4", shape=log(Pow(B, E)),
     pre=Q.real(B) & Q.even(E) & (~Q.zero(E) | ~Q.zero(B)),
     result=lambda B, E: E*log(Abs(B)))
```

From each rule the generator derives **satisfying** inputs (assumption
sets that entail `pre`, checked with `satassume.ask`), **barely violating**
ones (one conjunct dropped or negated: the handler must not fire, or must
still be sound if it does) and **boundary** points (for each atom, the
values on its edge: `Q.even(E)` gives `0`, `Q.real(B)` gives `0`, `-1`,
`oo`, `~Q.zero(B)` gives the point where it fails). The `handlers_v2`
defect is the boundary of L4 without its guard. Sync: the handler calls a
module-level `fired("L4")` hook on every rewrite, the generator asserts
every rule id fires per run, and a test renders the docstring table from
the same objects. `handlers_v2/exp_log.py`'s `E1..L5` numbering is the
model; `handlers_v3` has the prose but no ids yet.

### 3.2 Hypothesis strategies, shrinking, settings

Generate a cheap tuple grammar and convert to SymPy at the end, as
`test_verify_soundness.py` does. My scratch prototype shows why: a uniform
`st.recursive` tree over ten constructors fired a wrong `log(b**e)` rule
on 7 of 500 examples and found nothing in 5.7 s; a strategy targeted at
the rule's shape fired on 31 of 400, found the defect, and Hypothesis
shrank it to `log(x**x) -> x*log(Abs(x))` at `x = 0` (4 nodes) in 2.2 s.
`st.builds` shrinks SymPy objects well enough because the shrinker works
on the choice sequence, not the object; no custom strategy is needed. Two
cautions: auto-evaluation inside `builds` can collapse a shape
(`Abs(exp(x))` becomes `exp(re(x))`), so heads the handler expects
unevaluated need `evaluate=False`; and the minimal example may reuse one
symbol for two roles (`x**x`), which is fine.

```python
inner = st.recursive(atoms, lambda c: st.one_of(*[st.tuples(st.just(h), c, c) for h in INNER]), max_leaves=6)
case = st.builds(Case, head=st.sampled_from(sorted(HEADS)), inner=inner,
                 facts=solver_models(), rel=st.one_of(st.none(), relation()))
```

Assumption sets come from the solver (3.4), not `assume()`, so
`filter_too_much` never trips. Settings: `deadline=None` (a refine call is
50 to 400 ms, a relation ask seconds), `max_examples` from an environment
variable with a small default and a `slow` marker, suppress only
`too_slow` and `data_too_large`, `phases=[explicit, reuse]` for a
replay-only run. `target(rules_fired)` and `target(numeric_gap)` are cheap
to add but do not replace 3.1. The example database becomes the
regression corpus: a committed `DirectoryBasedExampleDatabase` under
`tests/refine_examples/` multiplexed with the local one, so every minimal
counterexample replays first on every run.

### 3.3 Exact evaluation on cut-adjacent points

One shared evaluator (lift `numval`, `close`, `NumVerdict` from the oracle
into `satrefine/harness.py`): `xreplace`, `doit`, classify `nan`, `zoo`,
`oo`, `-oo` and `AccumBounds` separately, only then `evalf(30)`. A fixed
list per class, always tried before random points:

| class | points |
|---|---|
| all | `0`, `1`, `-1`, `oo`, `-oo`, `zoo`, `I`, `-I` |
| log, Pow, sqrt, arg, inverse functions | `-2`, `-1/2`, `-1 +- I/1000`, `1 +- I/1000` |
| trig, sinc | `k*pi/2` for `k` in `-4..4`, `pi/2 + 1/1000` |
| hyperbolic | `k*pi*I/2` for `k` in `-4..4` |
| floor, ceiling, frac, Mod, Rem | integers, `n + 1/2`, `1 + I` |
| factorial, gamma, binomial | `0`, `-1`, `-2`, `-1/2`, `1/2` |

A singular mismatch is its own defect class, reported and never
suppressed; `oo` and `zoo` stay distinct.

### 3.4 Sampling with the satassume solver

`Session.assume_formula(facts)`, `Solver.solve()`, `Solver.model()` give
one consistent assignment of the 33 predicates per symbol; a blocking
clause and another `solve()` enumerate them. That yields every consistent
unary assumption set, including `negative_infinite`, `noninteger` and
`extended_nonpositive`, which no combo list has. Each model maps to sample
values through a small predicate-to-points table, and on `main`
`Solver.theory_models()` returns an LRA witness, a rational point
satisfying the relational part of the assumptions, so `Q.lt(x, y) &
Q.positive(y)` gets a point without rejection sampling.

### 3.5 Metamorphic checks without an oracle

For `r = refine(e, A)`: **sign flip** `x -> -x` with the sign facts
negated must give `r.subs(x, -x)`; **rotation** `x -> I*x` with `real` and
`imaginary` swapped, for the complex-part rules; **positive scaling**
`x -> 2*x` for the homogeneous rules (Abs, sign, arg, re, im);
**idempotence** `refine(r, A) == r`; **monotonicity**: adding a fact never
makes a rule stop firing. No evaluation is needed, and each failure is a
real inconsistency even when both results are sound.

### 3.6 Differential checks as the first filter

Run the three packages and SymPy's `refine` on every case, as today, but
evaluate fully only where they differ; agreeing cases get the adversarial
list alone. The expensive numeric work stays on the interesting few
percent.

### 3.7 Guarding against ask unsoundness

Five team defects were correct handler logic on a wrong `ask` answer
(`Q.symmetric` of a product, `Q.orthogonal` of a slice, `Q.unitary` from
`Q.orthogonal` for complex matrices, `Q.eq(y, x)` at `x = -oo`), and the
scoreboard found `Q.imaginary(I*t)` True at `t = 0`. An expression check
reports the rewrite as wrong but cannot say why. `satrefine.backend.observers`
already sees every `(proposition, assumptions, backend, answer)`: the
fuzzer registers an observer per case and, for every `True`, substitutes
the sample point into the proposition and evaluates it with the harness's
`_evaluate_boolean` (matrix predicates on the oracle's explicit 2x2
instances). A `True` that is false where the assumptions hold is reported
as "ask unsound" and the rewrite's failure is attributed to it. Running
under the `sympy`, `satassume` and `combined` backends says which engine
is wrong.

## 4. Keep and retire

Keep: the oracle's `numval`, `close`, `NumVerdict`, `run_forked`, step
logging, `blame`, `matrix_instances` and mode B; the harness's
`assert_refinement_valid` interface, re-implemented on the shared
evaluator; `refine_scoreboard.py`; the fuzzer's per-head fire table and
its SymPy-on-the-same-inputs comparison.

Retire: the fuzzer's `draw`, `COMBOS`, `inner`/`OUTER` grammars and
`agree`; the "inconsistent" skip on line 247. The oracle's `count_ops`
gap judgement stays, labelled advisory.

## 5. Staged plan

| stage | effort | catches |
|---|---|---|
| 0. Shared exact evaluator, adversarial points, `oo`/`zoo`/`0` in every sample set, `Q.infinite`/`Q.zero` in the vocabulary, stop skipping inconsistency errors | half a day | `handlers_v2` `log(x**n)` at `0**0`; team: `log(x**a)` at `0**0`, `log(1/x)` infinite, `floor(y)` infinite, contradictory assumptions raising (4 of 12) |
| 1. Hypothesis port: tuple grammars per head, solver-drawn assumptions with first-class relations, shrinking, committed example database | 2 to 3 days | team: `sinc` at a literal `pi/2` shift and the `(-1)**(-n - 1/2)` crash, once the trig and Pow grammars include literal half-pi and half-integer shifts (2 more); stage 0's findings as minimal examples |
| 2. Rule table with ids, precondition generator, docstring sync test, matrix grammar over `MatrixSymbol` with explicit instances | 3 to 5 days | team: negative index wrapping under `Q.diagonal` (an index boundary); every rule that never fires |
| 3. Ask audit through `backend.observers`, metamorphic checks, differential-first filtering | 2 days | team: the four `ask`-trust matrix rules and `KroneckerDelta` at `-oo` (5 of 12); the `Q.imaginary(I*t)` finding |
| 4. Retire the old grammar, wire the slow run into the scoreboard, replay the database in CI | 1 day | regressions |

Stages 0 and 3 together (about three days) cover ten of the twelve team
defects and the `handlers_v2` defect; stages 1 and 2 cover the last two
and make every finding minimal and replayable.

## 6. Risks

- **Runtime.** Measured on `handlers_v3`: 50 to 400 ms per refine under
  the combined backend, SymPy relation asks 0.03 to 2.3 s (up to 20 s
  reported). Two hundred examples times four packages times a dozen
  points is minutes. Mitigations: `satassume` first, the differential
  filter, a 10-example default with the long run behind an environment
  variable as on `main`, and refine calls in forked workers with the
  oracle's hard kill.
- **Flaky numerics.** Exact first, 30 digits second, singular points
  classified not compared, both sides through `xreplace` then `doit`
  (sequential `subs` produced the verifiers' spurious `zoo`).
- **Hypothesis health checks.** Slow strategies trip `too_slow`, a base
  example that builds SymPy objects trips `large_base_example`, `assume()`
  on consistency trips `filter_too_much`. The tuple grammar and
  solver-drawn assumptions avoid all three.
- **Preconditions drifting from code.** Without the `fired(rule_id)` hook
  and the docstring-rendering test the generator silently tests last
  month's rules; budget the sync test into stage 2.
- **`ask` on `main` versus pinned SymPy.** The engine may now answer
  queries SymPy left `None`; the audit must run under both backends so a
  wrong new answer is caught before a handler relies on it.

## Summary

The random fuzzer misses the known defects because it never samples the
degenerate points, skips contradictory assumptions, and compares floats
where the difference is between finite and infinite; the oracle is
stronger on exact points and attribution but hand-templated and blind to
matrices beyond 2x2 instances. The proposal makes one exact evaluator with
a fixed adversarial point list the common core, generates inputs from the
handlers' own rule preconditions with assumption sets and witnesses drawn
from the satassume solver (relations included, since `main` answers them
now), audits every `True` ask answer at the sample point, adds oracle-free
metamorphic checks, and ports the generator to Hypothesis in the
tuple-grammar style `main` already uses, with a committed example database
as the regression corpus. Stages 0 and 3, about three days, would have
caught ten of the twelve team defects and the `handlers_v2` log defect;
the whole plan is about two weeks.
