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

Out of scope for now: relations (`Q.eq/ne/lt/le/gt/ge`, `Eq`, `x < 0`,
`Q.is_true(x < 0)`), matrix predicates and matrix arguments, custom
predicates, and replacing the old `expr.is_*` system.

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
| 2588 (7 more unreplayable) | 2283 (88.2%) | 16 | 284 | 0 | 5 |

"Extra answers" are definite answers where SymPy returned None; each one
was checked by hand. The five "raises" are one semantic choice: the engine
treats an assumption contradicting a symbol's declared facts
(`ask(Q.commutative(x), ~Q.commutative(x))`) as inconsistent and raises
`ValueError`, where SymPy's handler path trusts the assumption. The 284
misses are template gaps, by the head of the queried expression: Pow 75,
Add 54, Mul 34, exp 22, log 19, acos 18, cot 12, sin/cos 12, re/im 8,
plus the `hermitian`/`antihermitian` units of numbers and constants.

Out-of-scope records, returned as None by rule (informational):

| Category | Records | SymPy also None | SymPy answered |
|---|---|---|---|
| relations | 78 | 15 | 63 |
| matrix predicates or non-scalar arguments | 189 | 29 | 160 |
| custom predicates | 0 | | |
| not a Boolean proposition | 8 | 5 | 1 (SymPy raised on 2) |

Old-system `expr.is_*` records, replayed through `Engine.is_` (out of
scope, informational): 6343 replayable, 5998 agree (94.6%), 24 extra
answers, 321 None where SymPy answered, 0 wrong.

Time: satassume takes 2.35 s for the in-scope records against 8.26 s for
`sympy.ask` on the same records in the same process, but it is slower on
349 of them, almost all first queries under a new assumption set, which pay
for instantiating a session (286 of those take over 1 ms). "Faster on each"
is therefore not met yet.

Microbenchmarks (`tools/bench.py`, pure Python, this machine, 200 repetitions
per case, both sides return the same answer):

| Query | `sympy.ask` | satassume |
|---|---|---|
| `Q.positive(y + 1) \| Q.positive(y)` | 360 us | 60 us |
| `Q.zero(w*y) \| Q.finite(w) & Q.zero(y)` | 440 us | 83 us |
| `Q.real(w*y) \| Q.real(w) & Q.real(y)` | 341 us | 51 us |
| `Q.even(y + 1) \| Q.odd(y)` | 294 us | 49 us |
| `Q.positive(exp(y)) \| Q.real(y)` | 253 us | 41 us |
| `Q.positive(((y**2 + 1)**w)**2) \| Q.real(w) & Q.real(y)` | 1065 us | 128 us |
| `Q.positive(w**2 + y + z) \| Q.nonnegative(z) & Q.positive(y) & Q.real(w)` | 1067 us | 121 us |
| `Q.negative(y) \| Q.positive(y) \| Q.nonzero(y) & Q.real(y)` | 1195 us | 574 us |

## License

BSD-3-Clause. The rule strings and several structural rules are copied or
adapted from SymPy (BSD).
