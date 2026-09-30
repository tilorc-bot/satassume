# satrefine: refine from identities

How satrefine's default refine (`satrefine/identities/`, selected as
`handlers_identities`) works and why. What satrefine is for, the `ask`
backends and the tools are in the README's
[satrefine section](../README.md#satrefine-the-refine-layer-as-a-yardstick);
verification, fuzzing, gates, battery, scoreboard, the bug classes fixed and
the speed history in [refine-testing.md](refine-testing.md).

SymPy's `refine(expr, assumptions)` returns an expression equal to `expr`
wherever the assumptions hold. Its handlers are procedures, and every rewrite
on a branch cut is a case analysis done by hand. satrefine keeps SymPy's
dispatcher and sends every predicate question through one seam, its `ask`, so
the handlers run against satassume, SymPy's `ask` or both. The identities
package writes the handlers as data: identities that hold everywhere, with the
branch bookkeeping written out, and plain conditional rules where no identity
stands above them. The engine proves conditions through `ask` and derives the
cases; the conditional rules are generated and verified offline.

## Three implementations

Before the identities package, the same 56 keys of `handlers_dict` were
implemented three times, each selected with `SATREFINE_HANDLERS`:

| Package | What it was | Now |
|---|---|---|
| `handlers` | the `reasoning` project's layer (`feature/refine` at `12c3845`): one self-registering module per key, 33 modules, 469 tests | removed |
| `handlers_v2` | a blind rewrite by one agent, 18 modules, no adversarial pass, 161 tests | removed |
| `handlers_v3` | a blind rewrite by a parallel team, one module per family plus `_common.py`; an adversarial verifier per family found and fixed 12 defects; 1,005 tests | the reference, `satrefine/reference/v3/`, still selected as `handlers_v3` (alias `satrefine/handlers_v3.py`); suite `tests/refine_v3/` |

`git checkout 411038c` runs `handlers` and `handlers_v2` with their tests
(deleted, not archived: an archived copy would stop running).

The comparison (SymPy `ddbb536`): the original inherits three unsound matrix
rules from SymPy's refine (orthogonal determinant 1, unitary inverse the
elementwise conjugate, `conjugate(U)*U` the identity) and lets SymPy's
spurious "inconsistent assumptions" errors on relations through; both rewrites
refuse those rules and guard the relation asks. On the same 1,500 random
inputs they fired 395, 458 and 454 rewrites, none unsound. v3, the only
package with zero known defects after an adversarial pass, became the
reference: the battery is recorded from its suite, the differential compares
against it.

**Why identities replaced v3 as the default** (`satrefine.DEFAULT_HANDLERS`).
Every conditional rule of v3's `log` handler (83 lines, 8 rules) specializes
two facts about the logarithm and two exponential forms, and likewise for the
other branch-cut families. As identities, a rule is a theorem on the page and
a missing premise shows (v2's defect at `b = e = 0` was one); conditional
rules are generated and checked numerically, not written (the check caught
SymPy's `ask(Q.zero(b**2), Q.imaginary(b))` answering True); a new function
costs rows, not procedure. At `2fd72b8` the package gave 0 wrong and 0 crash
on the battery and matched 1,073 of v3's 1,086 rewrites, in 483 family code
lines against 1,595, though its engine (1,132 lines) made the totals about equal.
By `905be5d` every remaining difference from v3 was reviewed and accepted
(`satrefine/tools/lib/accepted.py`). At `075d1f8`, counted by
`satrefine/tools/lib/sizes.py`: families 685 lines, engine 1,855 (online
1,497, offline 358), v3 1,625.

## Layout

```
satrefine/
  identities/      online: runs on every refine call
    core/            driver, guard, prove, match, rewrite, split, measure, spec, hooks
    rules/           the families as specs; _tables (table API), _wraps, _simple
    generated/       checked-in rule tables, written offline
    compat/          expected to change: backend routing, SymPy workarounds,
                     the matrix family and matcher hook, the vendored dispatcher
    config.py        SATREFINE_HANDLERS, SATREFINE_IDENTITIES, SATREFINE_STRICT_LOOPS
  build/           offline: specialization, stages, verification, rendering, specs
  tools/           offline: scoreboard, differential, fuzz, oracle, ablation, gates
  testing/         offline: test harness
  reference/v3/    the reference implementation (measuring only)
```

`compat/upstream.py` is SymPy's `refine.py` vendored behaviour-identical;
all 14 of its handler keys are overridden. `load()` in
`satrefine/identities/__init__.py` (called by `satrefine/handlers_identities/`)
replaces `satrefine.refine` with the driver, installs the `_simple` fallbacks,
imports the generated tables and registers every family's `SPEC` and ranges.
Layout rules, checked by `tests/refine_identities/test_import_direction.py` and
`tests/refine_identities/rules/test_family_specs.py`:

- `build/`, `tools/` and `testing/` import `identities/`, never the reverse,
  and `identities/` never imports `reference/`; refine runs in a subprocess
  where the offline packages raise on import. `pyproject.toml` leaves them
  and `reference` out of the distribution.
- `core/` names no specific SymPy function or matrix type and imports neither
  `rules/` nor `compat/`. Particular heads are roles in `core/hooks.py`
  (`opaque`: `floor`, `im`, `arg`; `conditional`: `Piecewise`; `modulus`:
  `Abs`; `step`: `floor`), set by `rules/_simple.install`; the dispatcher, the
  matrix matcher, the SymPy workarounds and the generation observer plug in
  there too.
- Importing a family registers nothing: import-time registration once let one
  package's tests replace another's handlers.

## Families as data

A family module (`rules/*.py`, `compat/matrices.py`) states tables of rows and
ends with `SPEC = Family(...)` (`core/spec.py`). Row kinds:

| Kind | Shape | Meaning |
|---|---|---|
| identity (`facts`) | `(lhs, rhs, domain)` | equal wherever `domain` holds; the right side carries the bookkeeping, e.g. `principal(z) = z + 2*pi*I*floor(1/2 - im(z)/(2*pi))` (`rules/_wraps.py`) |
| rule (`rules`) | `(lhs, rhs, hypothesis)` | rewrite when the hypothesis is provable |
| exponential form (`exp_forms`) | `(L, W, domain)` | `L == exp(W)`; `derive(facts, exp_forms)` (`rules/_tables.py`) composes each `g(exp(z))` fact with each form |
| range (`ranges`) | `(head(y), interval, condition)` | range of a bounded head (`atan`, `acot`, `asin`, `acos`, `arg`), for the floor of a bounded quantity |

A **definition** is an identity row whose right side is a `Piecewise` or
another head (`Max(a, b) = Piecewise((a, a >= b), (b, a < b))`,
`frac(f) = f - floor(f)`, `Abs(f) = f/sign(f)`, `arg(d) = -I*log(sign(d))`).
`power_exp_log` states four facts (`log(exp(z)) = principal(z)`, the complex
logarithm, the principal power, `exp` as a homomorphism) and three exponential
forms, from which `derive` builds the `log(b**e)` and `log(p*r)` rows. Trig,
hyperbolic, combinatorial and matrices are plain rule tables.

**Hypotheses** are stated as in a maths text:

- `ASSUMED`, a set of facts per family, says once what a letter is: a fact
  joins the condition of every row whose left side holds all its variables
  (`spec.assume`). A fact `Eq(g, e1) | Eq(g, e2)` is a definition: each row
  holding `g` becomes one row per `e`. The letter convention (`t` real, `u`
  extended real, `n` integer, `d` nonzero, `v` imaginary, ...) is in
  `rules/__init__.py`. SymPy's symbol assumptions cannot do this:
  `floor(n + x)` with `Symbol('n', integer=True)` evaluates when written, and
  SymPy's integers exclude the Gaussian integers `integer_funcs` needs.
- `add_rules(rows, assuming=...)` gives a block of `(lhs, rhs)` rows their own
  hypothesis ("for 0 <= a < b") and returns complete rows, so the engine, the
  generator and the tools see exactly the conditions that apply.
- Order hypotheses are the relation alone (`Q.lt(u, v)`), which satassume
  proves from any spelling; only `_eq` (`rules/combinatorial.py`) spells both
  `Q.eq(u, v)` and `Q.zero(u - v)`, which satassume does not relate for a
  possibly non-real side. Extended conditions read `Q.nonnegative(a) |
  Q.extended_nonnegative(a)`: SymPy proves `Q.real(sin(x))`, not
  `Q.extended_real(sin(x))`.
- No `unless`: rows that had one only to avoid a wrong SymPy answer are the
  plain identities; the wrong answers are strict xfails in
  `tests/refine_identities/needs/test_sympy_ask_bugs.py`.

**`Family(handlers, facts=, ..., assumed=)`** maps each key to a part
(`Rules(rows, by_binding=)`, `Identities(rows, measure=, opaque=, splits=)`)
or a tuple of parts tried in order by `chain`, rules first, so nested nodes of
the same head are reduced by rules while an identity candidate is evaluated.
With `by_binding`, rows with the same left side form a group and each binding
is tried against the whole group before the next: the periodicity tables need
the whole coefficient of `pi/2` tried under both parities before a single term
of it (`sec(x + (2*n + 1)*pi/2)` is one odd shift, not an even shift and a
quarter turn).

## Proving conditions (`core/prove.py`)

`provable(cond, assumptions)` goes connective by connective: an `And` needs
every part (relation atoms last, they are the expensive ones), an `Or` one
alternative, an atom is one `ask` through the dispatcher, and an `ask` that
raises counts as undecided.

**`by_cases`.** A condition that holds only by cases (`floor(y)` is a
Gaussian integer for finite `y`, `y` itself otherwise) is never proved that
way (issue #18). A table marks such an `Or` `by_cases(...)` (an `Or` subclass
that prints as such). When no alternative is provable and two or more are
undecided, `provable` asks their `Or` whole through `hooks.ask_whole`:
satassume's answer, under `satassume` and `combined`, where it answers alone.
SymPy's `ask` never gets a whole `Or`: it does not split cases and calls an
`Or` true under inconsistent assumptions. Marked: the power and log forms' domains in
`power_exp_log`, `frac`'s `f`, and `u <= v` from signs in the order vocabulary.

**The order vocabulary.** `decide` (used for `Piecewise` conditions: the
definitions and `refine_piecewise` in `rules/_simple.py`) decides relations
by proof forms (`ORDER`): from signs and infinite endpoints; from stated
relations (`Q.le`, `Q.lt`, `Q.zero(u - v)`, ...) only when no argument is
known infinite, since SymPy's `ask` proves `Q.eq(i, j)` for `i = -oo`,
`j <= 0`; refuted when the negation holds. `Q.eq`/`Q.ne` are asked only when
the assumptions state a relation: SymPy's equality query cost about 0.6 s,
and Min/Max-heavy refusals went from 25.8 s to 5.9 s (23 battery cases,
pinned, `1610aeb`). Rule hypotheses ask their relations bare.

**Bounds.** When `ask` leaves a sign, realness or integer atom open,
`_from_bounds` reads the stated bounds on the argument (`stated_bounds`:
relations and sign facts affine in it with numeric coefficients). Two rules
keep it sound:

- **Infinity.** An interval is one of the extended reals: `Q.gt(x, 1)` holds
  at `x = oo`. A bound proves `Q.extended_real` and the `extended_*` signs;
  `Q.real` and the finite signs also need each possible infinity excluded (a
  finite endpoint on that side, a sign fact among the bounds, or `ask` proving
  `Q.finite`). Reading a one-sided bound as finite gave seven wrong results
  (issue #10, B1-B7).
- **Contradictions.** An empty interval (`Q.negative(k) & Q.gt(k, pi/2)`)
  proves nothing (`_checked`). It used to prove every sign, and rows
  conditioned on opposite signs undid each other forever (B9).

**The integer fallback is kept (issue #62).** `_from_bounds` refutes
`Q.integer(u)` when the interval holds no integer, by exact floor division
(`math.floor` goes through a float and misplaces an endpoint 6e-17 below 0).
Since #48 satassume refutes these queries itself for every exact bound, and
removing the fallback passes every test; it stays for one battery answer,
`atan(tan(x))` under `Q.le(x, 1.5707963267948966) & Q.gt(x, -pi/2)`, because
satassume does not read Float bounds. That answer rests on the float lying
6.1e-17 below `pi/2`, a rounding artifact (#64).

## Matching and rewriting

**Matching** (`core/match.py`; its docstring lists the pattern forms) is
structural over plain pattern symbols with linear special forms (one factor
against the rest, the coefficient of `pi/2`, `exponent('k')`, `part`, a
generic head `F`), not a commutative search or `sympy.unify`. Matrix
patterns are a hook (`compat/matrix_match.py`) whose variables bind only
`MatrixSymbol` atoms, which keeps the rows off expressions where SymPy's
matrix `ask` is wrong (products of symmetric matrices called symmetric,
blocks of orthogonal matrices called orthogonal).

**Rule rows** (`rule_handler`) are tried in table order: bind, prove the
hypothesis, substitute. **Identity rows** (`identity_handler`) fire when the
domain is provable and the substituted right side, refined with the handler
switched off, holds no `Piecewise` the input lacked (an undecided definition),
no opaque head (`floor`, `im`, `arg`) after the endpoint and case splits (the
bookkeeping collapsed), and is smaller under the table's measure
(`core/measure.py`: `default_measure`, `node_measure`, `count_measure`).

The measure is what makes identities terminate: without it the definition
`log(x) = log(Abs(x)) + I*arg(x)` and the product form undo each other on
`log(-x)` under `Q.negative(x)`. Switching the handler off while its candidate
is refined stops `log(Abs(b))` from reproducing itself; the candidate's own
nodes are rewritten after acceptance.

## Case splits (`core/split.py`)

When the bookkeeping stays opaque because a symbol under it has known reality
but unknown sign, `case_split` refines the candidate under each sign; agreeing
results, or one generalized by `Abs` that refines back to every case, are
accepted (checked at zero when zero is not excluded; an imaginary symbol is
split as `I` times a real one). So `log(x**2)` for real `x` becomes
`2*log(Abs(x))` without a `Piecewise`. `endpoint_split` handles a `floor`
constant on its interval except at one closed endpoint (`asin(sin(t))` on
`[-pi/2, pi/2]`). Limits: no split inside a split, which keeps the cost
linear; at most `MAX_SPLITS = 8` per call; opaque nodes the assumptions do not
link to the split symbol are not explored. Known loss: `Mod(a, b) -> b/2` for
odd `2*a/b` does not fire when the signs of both `a` and `b` are unknown.

## The driver and the termination guard

`core/driver.py` is the vendored dispatcher with these changes:

- **Re-refine after auto-evaluation.** SymPy's `refine` dispatches on a
  rebuilt node without refining the children its constructor just created
  (`im(e*(log(-b) + I*pi))` expands into unrefined `re`, `im`, `arg` terms);
  the driver refines a rebuilt node again when its structure changed.
- **A per-call result cache and memoized `ask`**, keyed on node, assumptions,
  mode and engine state (handlers switched off, a split exploring), so a
  cached result is what recomputing would give.
- **Generated table first**, then the live handler, then a `_simple` fallback.
- **Termination** (`core/guard.py`, argued in its docstring): at most
  `MAX_DEPTH = 100` nested refinements; no node re-entering its own
  refinement; at most `MAX_FIRINGS = 500` steps per rewrite chain, and
  backstops of 50,000 firings per call and 200,000 with explorations. The cap
  is per chain, so a wide input (`Add(*[Abs(x + k) for k in range(1, 502)])`)
  is not taken for a loop. Refine terminates whatever `ask` answers. A tripped
  guard returns the input (always correct; a partial result is only as good
  as the rows that looped) and logs to `loop_events`, or raises
  `RefineLoopError` under `SATREFINE_STRICT_LOOPS=1` (tests and gates).

**Inconsistent assumptions.** When `ask` raises "inconsistent assumptions",
the top-level call returns its input: every result is correct then, and
whether an error surfaced would depend on which question came first and which
backend detects which contradiction. Inside the call the error propagates, so
a case split or `refine_piecewise` drops an inconsistent branch.

## Generated tables

`generated/<family>.py` are plain rule tables written by
`python -m satrefine.tools.refine_specialize --write`. `build/specialize.py`
runs the live engine on each identity row's left side under per-variable
profiles (`CATALOG`: positive, negative, real, imaginary, even, odd, ...; more
per family in `build/specs.py`, including literals such as `e = -1`), keeps
the profiles where the bookkeeping collapsed, drops profiles stronger than
another with the same result, and merges symmetric rules. `build/verify.py`
checks each rule at a sample point of its hypothesis and at the edge points
0, 1, -1, `I`, `-I` plus the family's own; only verified rules are written.

`build/stages.py` generates the families in order (integer_funcs and
complex_parts, power_exp_log, inverse), each against the tables already
produced (supplied through the driver's observer hook), regenerating a family
only if a table it looked up changed, until a round changes nothing (at most
5 rounds; 2 at `3865d76`). Each rule carries its derivation record as a
comment (round, identity row and profile, rows fired, `ask` queries answered
True), which traces a failing rule to its cause and says what to rederive
when a row changes. Trig and hyperbolic have no identity rows; `minmax_deltas`
is not generated (`specs.NOT_GENERATED`), its definitions decide in
milliseconds. At `075d1f8` the tables hold 37 (complex_parts), 11
(integer_funcs), 18 (power_exp_log) and 7 (inverse) rules;
`SATREFINE_IDENTITIES=live` ignores them. Meant as a fast path, they did not
show as one in #13's refactor (against `2ba1873`, pinned): the full battery
run took about 82 s either way.

## The `ask` backend (`compat/backend.py`)

The README describes the four backends. Under `combined`, `route` keeps
satassume's answer, `None` included, except:

| Reason | When | Then |
|---|---|---|
| `matrix`, `custom`, `other`, `relation` | `to_formula` cannot translate the proposition or the assumptions: matrix predicates or arguments, unregistered custom predicates, untranslatable relations | SymPy's `ask` |
| `no-theory` | no satassume theory interprets a relation (a Float or `AccumBounds` bound) | SymPy's `ask` |
| `inconsistent` | satassume finds the assumptions inconsistent | raise `ValueError`; the driver returns the input |
| `error` | satassume raises anything else | SymPy's `ask`, `None` if that raises |

Translation is checked on both parts separately (`out_of_scope` reports only
the first category, `relation` before `matrix`). Relations satassume
interprets are not re-asked when it is undecided: SymPy almost never decides
them, and slowly. Asking SymPy for every `None` is kept as `union`, for
measurements: SymPy answered about 10% of those queries, some wrongly, for 82%
of refine's time (#7); routing took refine over the battery from 135 s to 36 s
at `cab778f`.

**What still goes to SymPy.** Matrices, which satassume does not model (under
the `satassume` backend the battery's matrices family drops from 50 cases
like v3 to 1 at `c0b7069`). SymPy's matrix answers are wrong in places, and
one reaches refine: `ask(Q.unitary(X), Q.orthogonal(X))` is True, so
`Adjoint(X)*X` under `Q.orthogonal(X)` refines to `I`, wrong for a complex
orthogonal `X` (strict xfail; #67). Outside matrices, only unread relations.

**Track C** (SymPy only for matrices). Issue #7's blocker is mostly gone:
satassume reads `oo` bounds (#26) and irrational constants exactly (#48),
merged here in #24, #35 and #60. `ask(Q.zero(pi), Q.nonnegative(x) &
Q.le(x, pi/2))` is False, and #7's battery case, `sqrt(asin(sin(x))**2)` under
that bound, fires under `satassume` alone. Float and `AccumBounds` bounds are
still unread: `ask(Q.real(x), Q.nonnegative(x) & Q.le(x, 1.5))` is None.
Issue #64 proposes `Engine(uninterpreted="free")` (an unread relation as an
opaque Boolean atom) as satassume's default; `route` must then keep the
"a relation went unread" signal, or the `no-theory` fallback disappears.

## SymPy defects and their handling

| Defect (SymPy 1.14) | Handling |
|---|---|
| `acot(-z)`, `acoth(-z)` evaluate to `-acot(z)`, `-acoth(z)`, wrong at `z = 0` (B8) | `compat/sympy_fixes.rebuild` keeps a rebuilt `acot`/`acoth` of a possibly zero argument unevaluated; reported as sympy/sympy#30588 (closed upstream) |
| `Q.extended_real(sqrt(z))` True for negative `z` (the `Pow` handler is the closure of the extended reals) | backend guard: a True is kept only for an integer exponent, or an extended nonnegative base and a real exponent; a neighbouring case is sympy/sympy#30619 |
| `Q.nonzero` ("real and nonzero") False for `Abs(x)`, `x**2`, `x*y` with imaginary `x`, so they are "zero" and `c**2*X` the zero matrix | backend guard: a False from those three handlers is replaced by an answer checked under SymPy's definition |
| `Pow._eval_refine`, `exp._eval_refine` call SymPy's `ask` directly | satrefine's copies (`sympy_fixes.EVAL_REFINE`) go through the backend and the memo |
| `refine_Pow`: wrong for `sqrt(x**2)` with imaginary `x`, `sqrt(x**3)` with real `x`, `(x**3)**(1/3)`; crashes on `(-1)**(n + 1/2)` | replaced by `power_exp_log`'s rows |
| the floor handler splits off integer terms only from an `Add` | `principal` writes its floor argument as `1/2 - im(w)/(2*pi)` |
| `Q.eq(i, j)` True for `i = -oo`, `j <= 0`; `Q.eq` raising "inconsistent" on consistent facts; `Q.unitary` from `Q.orthogonal` | no relation forms at infinity; a raising `ask` is undecided; strict xfails |

## Semantic decisions

- **A relation says its sides are extended real** (as satassume reads it since
  #26): `Q.gt(x, 1)` allows `x = oo` and proves `Q.extended_real(x)`, not
  `Q.real(x)`. `refine(im(x), Q.gt(x, 0))` is 0, which holds at `oo` too.
- **Rows hold on the extended reals where the identity does**: `Abs`, `re`,
  `im`, `sign`, `conjugate` of real and signed arguments; the `asinh`,
  `atanh`, `acoth`, `acosh`, `asech` facts; powers of powers with a positive
  even exponent. `acsch(csch(z))` (`acsch(0)` is `zoo`) and the log forms
  (`0*log(oo)` is `nan`) stay finite-only, so `log(1/x)` under
  `Q.extended_positive(x)` stays unchanged.
- **`Max`/`Min` of a non-real argument stay unrefined**, not `nan` (#56);
  `KroneckerDelta` and `Heaviside` keep `(nan, True)`, and
  `KroneckerDelta(i, j)` for `i = j = -oo` is 1, by the definition.
- **Declined on purpose** (strict xfails pointing at
  `tests/refine_identities/needs/`): `A[i, j] -> 0` under
  `Q.diagonal(A) & Q.ne(i, j)`, since a negative index wraps once `A` is
  explicit; `(x**y)**z -> Abs(x)**(y*z)` for real `x`, even `y`, wrong at
  `x = 0`, `y < 0`, `z = oo` under SymPy's `zoo**oo = 0`.

## Open decisions

- **Long-term target**: stay on `ask`, replace v3, or upstream to SymPy.
  Undecided; it decides the next item.
- **Explicit state and renames** (steps 8-9 of #13; 1-7 are done): a
  `Refiner` object (handlers, backend, mode, limits; environment read once)
  instead of the process-global `handlers_dict`, backend, mode, strict flag
  and split state; renames (`handlers_identities` to e.g. `satrefine.rules`,
  live/generated to direct/tables, `_simple`), most useful for upstreaming.
- **Engine size.** #13's target was below the 1,434 counted lines of
  `f83f195`; it ended at 1,793 (`905be5d`), 1,855 at `075d1f8`: the
  guard, the bounds fix, memos, the split pre-test, the hooks, the matcher's
  power and multiset forms. Further cuts remove features: the generated-table
  mode (about 30 online and 358 offline lines), case splits (about 160), the
  matrix matcher (83), the `_eval_refine` copies (about 40).
- **Track C** and the integer fallback (#62): wait for satassume (#64), or
  drop unread relations in `compat/backend.py` (sound, a few lines).
- **Merging into `main`**: `main`'s CI runs `pytest tests` in one process;
  refine's test trees need a process each.

## Tried and dropped

| Approach | Why dropped |
|---|---|
| `c-single-ask` (one satassume ask per whole condition, `4d5e9d7`) | superseded by `by_cases`; its `Max`/`Min` part landed as #56 |
| every undecided `Or` asked whole (#50 before #52) | +10% on the battery, 1,852 asks, none True: most `Or`s are `finite \| extended` pairs where one implies the other. The mark made it -1.3% |
| marking the #18 floor condition `by_cases` | about 3% of battery time, proved nothing: SymPy evaluates `floor(floor(y))` itself |
| `re`, `im`, `Abs`, `arg` defined through `conjugate` | reproduced 27 of 27 base rows but unsound at infinity, and loses facts about whole products (SymPy distributes `conjugate(x*y)` on construction); two definitions through `sign` kept |
| trig and hyperbolic through definitions (stage 4 of staged derivation) | about 6 rows saved for a 20-line fold; 6 to 14 trig battery cases in a worse form (`(-1)**(1/2 - k/2)`); hyperbolic through trig fires where v3 needs `m mod 4`. The rest of staged derivation (manifest, fixpoint, records) was kept |
| combinatorial through `gamma` | 0 rows replaced, 4 to 9 tests failing per function: hypotheses are equalities the engine does not substitute, zero and pole rows lie where the gamma ratio is not the definition, v3's forms need the `gamma -> factorial` rows anyway |
| `ceiling(x) = -floor(-x)`, `Mod(a, b) = a - b*floor(a/b)`, `Rem` by truncation | the first derives nothing; the second fails 7 tests and derives none of its rows (SymPy's `Mod` is not the formula for non-real arguments); the third likewise. Only `frac(x) = x - floor(x)` pays |
| generic heads `F`, `G` shared by floor/ceiling/frac and Mod/Rem | rows restated per head for readability (#17) |
| per-row conditions, `given()`, `_parities`, `_lt`/`_le`/`less`, `unless` | replaced by `ASSUMED` (#20), `add_rules` (#21), `by_binding` (#28), plain relations (#40), plain identities (#22) |
| a `Holds` node for `Piecewise` conditions | plain `Q.ge(a, b)` suffices; its 2 ms per refusal came from a process-wide `lru_cache` |
| an `ask` cache across calls | about 0 gain with satassume, and it brings back order dependence |
| an `Add` handler (`floor(x) + frac(x) -> x`) | it would run the matcher on every sum; refinement stays per node |
| Groebner bases | out of scope |
