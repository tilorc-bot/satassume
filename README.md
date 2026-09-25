# satassume

A SAT-based engine for SymPy's `ask(proposition, assumptions)`, currently
scoped to exactly one slice: **unary scalar predicates on scalar
expressions**, answered purely by the SAT engine. Propositions and
assumptions are Boolean combinations of `Q.<name>(expr)` where `name` is in
the vocabulary of `satassume/rules.py` (`integer`, `real`, `positive`,
`prime`, `hermitian`, ...) and `expr` is a scalar `Expr`. Everything is
answered from one rule base, one set of structural templates and one
incremental CDCL solver; the engine never consults SymPy's `_eval_is_*`
handlers or SymPy's own `ask`/`satask`.

Custom predicates are in scope once a clause-generating function is
registered for them with `satassume.register(pred, *classes)`, the
counterpart of SymPy's `Predicate.register` (see
`satassume/extensions.py`); a registered vocabulary predicate on a new
class makes objects of that class ordinary nodes.

Relations (`Q.eq/ne/lt/le/gt/ge`, `Eq`, `x < 0`, `Q.is_true(x < 0)`) are
being added through theory solvers on the CDCL solver (DPLL(T), LRA and EUF;
see `satassume/relations.py` and
`agent-reports/2026-09-23-theory-interface.md`); without an adapter that
interprets a relation, `ask` returns None as before.
Out of scope for now: matrix predicates and matrix arguments, unregistered
custom predicates, and replacing the old `expr.is_*` system.

**Routing rule.** Any out-of-scope query makes `ask` return `None` without
touching the engine. Relations are the exception once theory adapters are
present (the default when `satassume/lra_adapter.py` and
`satassume/euf_adapter.py` exist): they reach the engine, and `ask` returns
None only when no theory interprets one of them; `out_of_scope` still
reports them as `relation`. That is scoping, not a fallback: the caller (SymPy's
`ask`) is expected to route such inputs to its existing path (`satask`, the
LRA theory, the matrix handlers). `out_of_scope(prop, assumptions)` reports
the category (`relation`, `matrix`, `custom`, `other`) so the caller can
decide before asking. The engine itself contains no fallback to SymPy's old
handlers or to `satask`; adding one would defeat the purpose.

**Definition of done for this slice.**

1. Every in-scope query in the recorded corpus (`queries.jsonl`, recorded
   from SymPy's own tests) is answered identically to SymPy or better (a
   definite answer where SymPy returns None), with zero contradictions;
2. faster than `sympy.ask` on each in-scope query;
3. `Predicate.register` kept as a way to add clause-generating functions,
   so SymPy's extensibility tests keep passing.

Where it stands: 1 is met except for 70 records where SymPy's answer is
wrong for a concrete value or needs reasoning outside the templates (listed
under Results); 2 is met on 2532 of 2583 compared records; 3 is met by
`satassume.register`, with the hook inside SymPy's own `Predicate.register`
left for the landing step.

**Long-term goal.** Replacing the old per-object `expr.is_*` system with the
same engine remains the goal; it is deferred until this
slice is finished. `Engine.is_` exists because the engine uses it internally
for context-free queries and the corpus tools replay old-system records
through it for information, but nothing here hooks it into SymPy. See
[PLAN.md](PLAN.md).

## Usage

```python
from sympy import Symbol, Q, exp
from satassume.sympy_api import ask, out_of_scope

y = Symbol('y')
ask(Q.positive(exp(y)), Q.real(y))            # True
ask(Q.even(y + 1), Q.odd(y))                  # True
ask(Q.positive(y), Q.real(y))                 # None: undecided, in scope
ask(Q.positive(y), Q.gt(y, 0))                # None: y may be non-real, so y > 0 has no order meaning
ask(Q.positive(y), Q.gt(y, 0) & Q.real(y))    # True (LRA theory)
out_of_scope(Q.positive(y), Q.gt(y, 0))       # 'relation' (answered anyway when adapters are present)

from sympy import Integer, Predicate, log
from satassume import register, P, Implies
@register('mersenne', Integer)                # the counterpart of Q.mersenne.register(Integer)
def _(n):
    return Implies(P('integer', log(n + 1, 2)), P('mersenne', n))
ask(Predicate('mersenne')(Integer(31)))       # True
```

## How it answers

Both SymPy assumption systems are propositional reasoning over the same
predicate vocabulary (`integer -> rational -> real -> complex`, `real ==
negative | zero | positive`, ...) plus structural knowledge about expression
classes. satassume keeps one rule base, one incremental CDCL solver per
session, and a cache of its own (`DictCache`, keyed by node) for the
context-free facts it derives. It never reads or writes SymPy's per-object
`_assumptions`: those hold whatever SymPy's `_eval_is_*` handlers cached,
which can be wrong (`(0**n).is_finite` is True for a plain `n`), and a
`Symbol`'s `_assumptions` is one fact base shared by every symbol with the
same assumptions. SymPy objects enter only through the templates: the
assumptions a symbol was declared with, and the properties of fixed-value
constants. Assumptions enter the solver as solver assumptions under
a selector literal and never touch the cache; the session is reused while
the assumptions stay the same. Discovery visits only the cone of the queried
expression, root-level propagation decides most queries, and search runs
only when propagation is inconclusive.

## Layout

| Path | What |
|---|---|
| `satassume/rules.py` | the single rule base and predicate vocabulary, in the old system's string syntax |
| `satassume/formula.py`, `compile.py` | atoms `P(pred, expr)`, formulas, clause compilation |
| `satassume/solver.py` | incremental CDCL with assumptions, root-level propagation, `entails` |
| `satassume/engine.py` | sessions, discovery, caching |
| `satassume/templates/` | structural rules per SymPy class |
| `satassume/sympy_api.py` | `ask`, `out_of_scope`, `to_formula`, `Unsupported` |
| `satassume/extensions.py` | `register(pred, *classes)`: clause-generating functions for custom predicates and for vocabulary predicates on new classes |
| `tools/record_queries.py` | pytest plugin recording every query SymPy's tests make |
| `tools/compare.py` | replay a recorded corpus, classified in scope / out of scope, and report agreement |
| `tools/bench.py` | contextual `ask` microbenchmarks, SymPy versus satassume |
| `satrefine/` | the refine layer (SymPy's `refine` dispatcher plus 56 handlers) with a selectable `ask` backend; see below |
| `tests/refine/` | the refine handler tests, run under each backend |
| `tools/refine_scoreboard.py` | run `tests/refine` under every backend and compare outcomes |
| `satrefine/handlers_v2/`, `handlers_v3/` | two blind from-scratch rewrites of the same 56 keys (one agent; a parallel team with verifiers), selected with `SATREFINE_HANDLERS`; see `agent-reports/2026-09-23-refine-three-implementations.md` |
| `tests/refine_v2/`, `tests/refine_v3/` | their suites; any suite runs against any package |
| `tools/refine_fuzz.py` | random expressions and assumptions, numeric check of every rewrite, SymPy's refine on the same inputs |
| `tools/refine_oracle.py` | SymPy's old assumption system as an independent oracle for the handlers |
| `satrefine/handlers_identities/` | the nine handler families as tables of identities and conditional rules, with rules generated from identities and verified numerically; `tests/refine_identities/` (includes the 1,736-case v3 battery), `tools/refine_identity_scoreboard.py`, `refine_specialize.py`, `refine_differential.py`, `refine_ablate.py`; see `agent-reports/2026-09-24-refine-identities-phase-1-results.md` and `2026-09-25-refine-identities-phase-2-results.md` |

## satrefine: the refine layer as a yardstick

`satrefine/` is the `reasoning` project's refine layer
(https://github.com/tilorc-bot/reasoning, branch `feature/refine`, commit
`12c3845`): SymPy's `refine` dispatcher vendored in `satrefine/_upstream.py`
plus 56 self-registering handlers in `satrefine/handlers/`, with the test
harness and 470 tests in `tests/refine/`. Every handler asks its predicate
questions through one seam, `satrefine._upstream.ask`, and
`satrefine/backend.py` chooses who answers:

| Backend | `ask` | Use |
|---|---|---|
| `sympy` | `sympy.assumptions.ask.ask` | the reference |
| `satassume` | `satassume.sympy_api.ask` alone; out-of-scope and undecided queries are `None`, so the handler does not fire | the strict measurement of this engine |
| `combined` | satassume; SymPy only where satassume has no model (matrix or unregistered custom predicates, a relation bound no theory interprets such as `pi/2`), finds the assumptions inconsistent, or raises | the default |
| `union` | satassume first, SymPy for every `None` (the `combined` behaviour before 2026-09-25) | measurements |

Select with `SATREFINE_BACKEND=<name>` (read at import; default `combined`),
`satrefine.backend.set_backend(name)`, or `with satrefine.backend.using(name):`.

### The three handler packages

The same 56 registry keys are implemented three times, each package
self-contained and selected with `SATREFINE_HANDLERS`:

| Package | Tests | Written by | What it is |
|---|---|---|---|
| `satrefine/handlers/` (default) | `tests/refine/` (469) | the `reasoning` project's agents, then its verifiers | the original layer, copied from github.com/tilorc-bot/reasoning `feature/refine` at `12c3845`, one module per key, 33 modules |
| `satrefine/handlers_v2/` | `tests/refine_v2/` (161) | one Fable 5.1 agent, all 56 keys in one run, no verifier pass | a blind rewrite: the agent could not read the other packages, their tests or reports; 18 modules with shared helpers, rules named in the docstrings |
| `satrefine/handlers_v3/` | `tests/refine_v3/` (1,005) | nine agents (3 Fable, 6 Opus 5.5), one family each, then nine adversarial verifiers | a blind rewrite by a parallel team: one module per family (`trig`, `hyperbolic`, `inverse`, `power_exp_log`, `complex_parts`, `integer_funcs`, `combinatorial`, `minmax_deltas`, `matrices`), a shared `_common.py`, every rule stated with its precondition; the verifiers found and fixed 12 defects |

All three plug into the same dispatcher and backend switch, so any suite
runs against any package and every tool takes `--handlers`:

```bash
SATREFINE_HANDLERS=handlers_v3 PYTHONPATH=.:/path/to/sympy .venv/bin/python -m pytest -q tests/refine_v3
SATREFINE_HANDLERS=handlers_v2 PYTHONPATH=.:/path/to/sympy .venv/bin/python -m pytest -q tests/refine   # one package, another's suite
PYTHONPATH=.:/path/to/sympy .venv/bin/python tools/refine_scoreboard.py --handlers handlers_v3 --suite tests/refine_v3
PYTHONPATH=.:/path/to/sympy .venv/bin/python tools/refine_fuzz.py 2 1500 --handlers handlers_v2
PYTHONPATH=.:/path/to/sympy .venv/bin/python tools/refine_oracle.py --handlers handlers_v3
```

How they compare, and what to build on, is in
`agent-reports/2026-09-23-refine-three-implementations.md`. In short: the
original inherits three unsound matrix rules from SymPy and leaves relation
errors unguarded; both rewrites refuse those rules; the parallel team's
package is the only one with zero known defects after an adversarial pass
and covers the most on the branch-cut families, at about seven times the
single agent's cost, most of it the verifier pass. `handlers` stays the
default so the corpus numbers above keep their meaning.

A fourth package, `satrefine/handlers_identities/`, implements the same nine
handler families as tables: identity rows with the branch bookkeeping written out
(`log`, powers, inverse functions, complex parts) and plain conditional rows
(the other families), run by a shared engine that matches rows, decides
their conditions through `ask`, and generates conditional rules from
identities under assumption profiles, each verified numerically. Select it
with `SATREFINE_HANDLERS=handlers_identities`. On the 1,736-case battery
recorded from the `handlers_v3` suite it gives 0 wrong and 0 crash and
matches v3 on 1,073 of v3's 1,086 rewrites, in about a third of v3's
per-family code. Results are in
`agent-reports/2026-09-24-refine-identities-phase-1-results.md` and
`agent-reports/2026-09-25-refine-identities-phase-2-results.md`.

`tools/refine_scoreboard.py` runs `tests/refine` under each backend and
compares outcomes per test: satassume in-scope gaps (pass under `sympy`, fail
under `satassume` with only in-scope queries asked), out-of-scope failures
(relations or matrix predicates were asked, so the handler could not fire),
satassume wins, combination wins (pass under `combined` only) and refine gaps
(fail everywhere). The per-test scope counts come from an observer in
`tests/refine/conftest.py` that classifies every query with `out_of_scope`.

```bash
PYTHONPATH=.:/path/to/sympy .venv/bin/python tools/refine_scoreboard.py
PYTHONPATH=.:/path/to/sympy .venv/bin/python tools/refine_scoreboard.py --backends sympy,satassume --show-failures satassume
SATREFINE_BACKEND=satassume PYTHONPATH=.:/path/to/sympy .venv/bin/python -m pytest -q tests/refine
```

Scoreboard on 2026-09-22 (SymPy at `ddbb536`, the `reasoning` pin):

| Backend | Passed | Failed | xfailed | Time |
|---|---|---|---|---|
| `sympy` | 462 | 7 | 4 | 118 s |
| `satassume` | 412 | 59 | 2 | 27 s |
| `combined` | 463 | 6 | 4 | 120 s |

All 59 tests that pass under `sympy` and fail under `satassume` asked
relations (`Q.eq/ne/lt/le/gt/ge`: Min/Max order rules, KroneckerDelta,
binomial/factorial at a literal, inverse-trig principal branches) or matrix
predicates (the eight matrix handlers): the out-of-scope categories, none of
them in-scope engine gaps. The six tests that fail under `sympy` and pass
under `satassume` only because the handler did not fire are SymPy's own
`ask` raising "inconsistent assumptions" on `Q.ge(x, y)` under
`Q.positive(x) & Q.negative(y)`, and returning `None` for `Max` of two
negative-infinite arguments. The one in-scope satassume win is
`refine(Abs(x - y), Q.positive(x) & Q.negative(y))`, where SymPy's `ask`
cannot decide `Q.negative(x - y)`. No test passes under `combined` only yet:
the handlers were written against the `reasoning` engine and SymPy, so
simplifications that need both engines are the work still to do.

## Running

```bash
# unit tests (no SymPy needed for solver/rules; templates, the API and tests/refine need SymPy)
PYTHONPATH=.:/path/to/sympy uv run --no-project --with pytest --with mpmath python -m pytest -q tests

# record SymPy's own queries (only if queries.jsonl is missing), then replay them
cd /path/to/sympy
RECORD_OUT=/path/to/satassume/queries.jsonl PYTHONPATH=/path/to/satassume/tools:. \
  python -m pytest -p record_queries -p no:cacheprovider sympy/assumptions/tests sympy/core/tests/test_assumptions.py
cd /path/to/satassume
PYTHONPATH=.:/path/to/sympy python tools/compare.py queries.jsonl --in-scope-only --time-sympy

# microbenchmarks
PYTHONPATH=.:/path/to/sympy python tools/bench.py
```

`tools/compare.py` exits nonzero only when a definite answer contradicts
SymPy on an in-scope record. Without `--in-scope-only` it also replays the
out-of-scope and old-system records and reports them as informational.

## Results (corpus `queries.jsonl`, 9230 records, `tools/compare.py`)

In-scope new-system records (`ask` and `_ask_recursive` calls from
`sympy/assumptions/tests` and `sympy/core/tests/test_assumptions.py`):

| In-scope records | Agree | Extra answers | None where SymPy answered | Wrong | Raises where SymPy answered |
|---|---|---|---|---|---|
| 2588 (7 more unreplayable) | 2497 (96.5%) | 16 | 70 | 0 | 5 |

"Extra answers" are definite answers where SymPy returned None; each one
was checked by hand. The five "raises" are one semantic choice: the engine
treats an assumption contradicting a symbol's declared facts
(`ask(Q.commutative(x), ~Q.commutative(x))`) as inconsistent and raises
`ValueError`, where SymPy's handler path trusts the assumption.

The 70 misses are deliberate. For 67 of them SymPy's answer is false for a
value that satisfies the assumptions, so no sound rule can reproduce it:

* a zero argument (26): `Q.imaginary(I*x)` and `Q.imaginary(x*y)` under
  `Q.real` (the product is 0 for `x = 0`), `Q.imaginary(x + y)` and
  `Q.imaginary(x + I)` under an imaginary and a real term (the real term
  may be 0, or the imaginary terms may cancel: `I - I`), the matching
  `hermitian`/`antihermitian` records, `Q.integer(sqrt(2)*x)` for integer
  `x`, `Q.imaginary(x**y)` for negative `x` and `Q.integer(2*y)` (which
  includes integer `y`), `Q.nonzero(5**(2*I*pi*n))` for integer `n`;
* an infinite argument (37): `re`, `im`, `Abs`, `exp`, `sin` and `cos`
  are declared complex or finite by SymPy for every argument, but
  `re(oo) = oo`, `sin(oo*I) = oo*I`, `exp(oo) = oo`; `Q.finite(log(x))` for
  nonzero `x` (`log(oo)`), `Q.finite(2**x)` False for infinite `x`
  (`2**-oo = 0`), `Q.complex(x**y)` and `Q.algebraic(x**y)` for complex or
  algebraic `x` (`0**-1 = zoo`), `Q.finite(x*y)` for zero `y` and infinite
  `x` (`0*oo = nan`);
* four more: `Q.positive(acot(x))` for real `x` (`acot(-1) = -pi/4`),
  `Q.positive(acos(x))` on `[-1, 1]` (`acos(1) = 0`), and
  `Q.imaginary((2*I)**x)` False for imaginary `x` (true for
  `x = I*pi/(2*log(2))`).

The other three need reasoning the templates do not do: `(3*I)**I` and
`(1 + I)**I` are not real because `|b| != 1`, which needs `Abs` of a
non-atomic base; the primality of `cos(1)**2 + sin(1)**2 + 1234...` needs a
trigonometric identity.

Out-of-scope records, returned as None by rule (informational; relations
are answered by the theories, `tools/compare.py --relations-only`):

| Category | Records | SymPy also None | SymPy answered |
|---|---|---|---|
| relations | 78 | 15 | 63; with the LRA and EUF theories 75 of the 78 agree, 3 None, 0 wrong |
| matrix predicates or non-scalar arguments | 189 | 29 | 160 |
| custom predicates | 0 | | |
| not a Boolean proposition | 8 | 5 | 1 (SymPy raised on 2) |

Old-system `expr.is_*` records, replayed through `Engine.is_` (out of
scope, informational): 6343 replayable, 6033 agree (95.1%), 27 extra
answers, 283 None where SymPy answered, 0 wrong. (Before the engine
stopped reading SymPy's cached `_assumptions` it was 6041 / 30 / 272: part
of that agreement was SymPy's own cached answers read back.)

Time (`tools/compare.py --in-scope-only --time-sympy`, both sides in the
same process, garbage collection frozen and disabled inside the timed
calls, `sympy.ask` timed on an evaluated rebuild when it raises on the
unevaluated one and left out of the comparison if it still raises, 5
records): satassume takes 1.19 s for the in-scope records against 6.88 s
for `sympy.ask` on the 2583 compared records, and is slower on 51 of them
(20 by more than 0.3 ms). Those are undecided queries that need the full
instantiation of a `Pow` cone (six nodes with the derived `2*e`, `b - 1`,
`b + 1`) and two CDCL solves, at 1.5 to 2.7 ms against 0.9 to 1.8 ms for
SymPy, and constants asked about for the first time (their old-system
properties are read once). "Faster on each" is therefore met on 98% of
the records, not on all; the worst five: `Q.imaginary((2*I)**x) |
Q.imaginary(x)` 2.66 ms vs 1.76, `Q.nonzero(5**(2*I*pi*n)) | Q.integer(n)`
2.44 vs 1.59, `Q.complex(x**y) | Q.complex(x) & Q.complex(y)` 2.20 vs
0.85, `Q.real(x**(y/z)) | Q.positive(x) & Q.real(x) & Q.real(y/z)` 2.08 vs
1.33, `Q.imaginary(x**y) | Q.negative(x) & Q.rational(y) & Q.integer(2*y)`
2.02 vs 1.22.

Microbenchmarks (`tools/bench.py`, pure Python, this machine, 200 repetitions
per case, both sides return the same answer):

| Query | `sympy.ask` | satassume |
|---|---|---|
| `Q.positive(y + 1) \| Q.positive(y)` | 378 us | 52 us |
| `Q.zero(w*y) \| Q.finite(w) & Q.zero(y)` | 463 us | 74 us |
| `Q.real(w*y) \| Q.real(w) & Q.real(y)` | 343 us | 43 us |
| `Q.even(y + 1) \| Q.odd(y)` | 309 us | 44 us |
| `Q.positive(exp(y)) \| Q.real(y)` | 268 us | 39 us |
| `Q.positive(((y**2 + 1)**w)**2) \| Q.real(w) & Q.real(y)` | 1115 us | 134 us |
| `Q.positive(w**2 + y + z) \| Q.nonnegative(z) & Q.positive(y) & Q.real(w)` | 1111 us | 96 us |
| `Q.negative(y) \| Q.positive(y) \| Q.nonzero(y) & Q.real(y)` | 1271 us | 32 us |

## License

BSD-3-Clause. The rule strings and several structural rules are copied or
adapted from SymPy (BSD).
