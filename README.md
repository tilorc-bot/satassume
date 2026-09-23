# satassume

One incremental SAT-based assumptions engine intended to replace both of
SymPy's assumption systems: the old per-object `expr.is_positive` properties
and the newer `ask(Q.positive(expr), assumptions)` module.

Status: prototype. See [PLAN.md](PLAN.md) for the measurements behind the
design and the staged plan for landing it in SymPy.

## Idea in one paragraph

Both SymPy systems are propositional reasoning over the same predicate
vocabulary (`integer -> rational -> real -> complex`, `real == negative |
zero | positive`, ...) plus structural knowledge about expression classes.
The old system compiles its rules into per-object unit propagation and
caches results on the object; the new one rebuilds a CNF and runs DPLL for
every call. satassume keeps one rule base, one incremental CDCL solver per
session, and the object's own `_assumptions` dictionary as the cache. A
context-free query is root-level propagation over the node, its arguments
and their templates, with search only when propagation is inconclusive.
Everything the solver learns at decision level 0 is written back to the
nodes, so the hit path stays a dictionary lookup. Contextual assumptions are
solver assumptions under a selector literal and never touch the cache.

## Usage

```python
from sympy import Symbol, Q, exp
from satassume.sympy_api import is_, ask, install

x = Symbol('x', positive=True)
y = Symbol('y')
is_(x + 1, 'positive')                 # True   (replacement for (x + 1).is_positive)
ask(Q.positive(exp(y)), Q.real(y))     # True   (replacement for sympy.ask)

install()                              # route every expr.is_* cache miss through the engine
(x**2 + 1).is_zero                     # False, answered by satassume
```

## Layout

| Path | What |
|---|---|
| `satassume/rules.py` | the single rule base, in the old system's string syntax |
| `satassume/formula.py`, `compile.py` | atoms `P(pred, expr)`, formulas, clause compilation |
| `satassume/solver.py` | incremental CDCL with assumptions, root-level propagation, `entails` |
| `satassume/engine.py` | sessions, discovery, caching |
| `satassume/templates/` | structural rules per SymPy class |
| `satassume/sympy_api.py` | `is_`, `ask`, `install` |
| `tools/record_queries.py` | pytest plugin recording every query SymPy's tests make |
| `tools/compare.py` | replay a recorded corpus and report agreement |
| `tools/bench.py` | old vs new vs satassume microbenchmarks |

## Running

```bash
# unit tests (no SymPy needed for solver/rules; templates need SymPy)
PYTHONPATH=.:/path/to/sympy uv run --no-project --with pytest --with mpmath python -m pytest -q

# record SymPy's own queries, then replay them
cd /path/to/sympy
RECORD_OUT=/path/to/satassume/queries.jsonl PYTHONPATH=/path/to/satassume/tools:. \
  python -m pytest -p record_queries -p no:cacheprovider sympy/assumptions/tests sympy/core/tests/test_assumptions.py
cd /path/to/satassume
PYTHONPATH=.:/path/to/sympy python tools/compare.py queries.jsonl
```

## Results so far

Replay of 9230 queries recorded from SymPy's assumptions tests and the core
arithmetic and assumptions tests (`tools/compare.py`):

| Old-system `is_*` queries (6343) | New-system `ask` queries (2870) |
|---|---|
| 94% agree, 0 wrong, 24 extra answers | 82% agree, 0 wrong |

"Extra answers" are definite answers where SymPy returned None; each one
was checked by hand. The engine never contradicts SymPy on this corpus.
Five flagged cases are a semantic choice: this engine raises on assumptions
that contradict a symbol's declared facts (`ask(Q.commutative(x),
~Q.commutative(x))`) where SymPy silently trusts the assumption. The
remaining gap is templates not yet written (`Mod`, monotonicity such as
`pi/2 > 1`, deep parity through denominators) and, on the new-system side,
relations and matrix predicates, which are out of scope.

The engine answers only from its own rule base, templates and search; it
never consults SymPy's `_eval_is_*` handlers.

Microbenchmarks (`tools/bench.py`, pure Python, this machine):

| Query | SymPy | satassume |
|---|---|---|
| `ask(Q.positive(y + 1), Q.positive(y))` | 381 us | 57 us |
| `ask(Q.real(w*y), Q.real(w) & Q.real(y))` | 341 us | 48 us |
| `ask(Q.even(y + 1), Q.odd(y))` | 304 us | 48 us |
| `(p*q).is_positive`, fresh objects | 102 us | 962 us |
| `(u**2 + 1).is_zero`, fresh objects | 499 us | 1377 us |
| `(n + m).is_even`, unknown | 70 us | 1309 us |

Contextual queries are 5 to 8x faster than `sympy.ask`. The context-free
compute path is 3 to 15x slower than the old handlers; the cached hit path
is identical. Instantiating a node (33 variables, 105 rule clauses, 30 to 50
template clauses) costs about 300 us in pure Python, which is the whole gap.
Closing it needs pattern-compiled templates and a native propagation core;
see Stage 3 of [PLAN.md](PLAN.md).

## License

BSD-3-Clause. The rule strings and several structural rules are copied or
adapted from SymPy (BSD).
