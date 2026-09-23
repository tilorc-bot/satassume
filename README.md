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
touching the engine. That is scoping, not a fallback: the caller (SymPy's
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
same engine (the per-object `_assumptions` dictionary as the cache, level-0
facts written back to the nodes) remains the goal; it is deferred until this
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
ask(Q.positive(y), Q.gt(y, 0))                # None: out of scope (relation)
out_of_scope(Q.positive(y), Q.gt(y, 0))       # 'relation'

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
session, and the object's own `_assumptions` dictionary as the cache for
context-free facts. Assumptions enter the solver as solver assumptions under
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

## Running

```bash
# unit tests (no SymPy needed for solver/rules; templates and the API need SymPy)
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

Out-of-scope records, returned as None by rule (informational):

| Category | Records | SymPy also None | SymPy answered |
|---|---|---|---|
| relations | 78 | 15 | 63 |
| matrix predicates or non-scalar arguments | 189 | 29 | 160 |
| custom predicates | 0 | | |
| not a Boolean proposition | 8 | 5 | 1 (SymPy raised on 2) |

Old-system `expr.is_*` records, replayed through `Engine.is_` (out of
scope, informational): 6343 replayable, 6033 agree (95.1%), 27 extra
answers, 283 None where SymPy answered, 0 wrong.

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
