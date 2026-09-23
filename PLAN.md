# Implementation plan: one SAT-based assumptions engine for SymPy

Goal: replace both SymPy assumption systems, the old per-object `expr.is_*`
properties and the new `ask(Q.*)` module, with a single engine that

* answers context-free queries at least as fast as the old system,
* answers contextual queries (`ask(prop, assumptions)`) with a complete
  propositional procedure instead of hand-written handler recursion,
* keeps one rule base instead of two, and
* passes SymPy's full test suite, not only `sympy/assumptions/tests`.

This repository is the standalone prototype. The plan below describes both
what the prototype does and how it would land in SymPy.

## 1. What the measurements say (SymPy master, September 2026)

Five core test files (arithmetic, expr, simplify, complexes, limits), 88 s:

| Measure | Value |
|---|---|
| `is_*` property accesses | 6.07 M |
| ... that reached the compute path `_ask` | 250 k (4 %) |
| `_eval_is_*` handler invocations | 1.44 M |
| Time inside `_ask` | 23.8 s (27 % of wall) |
| Share of that in `FactKB.deduce_all_facts` | ~30 % |
| New-system `ask()` calls | 4 |

Per-query costs:

| Path | Cost |
|---|---|
| old cached property hit | 0.09 us |
| old `FactKB` deduction of one fact | 7 us |
| old uncached `_ask`, workload average | 95 us |
| new `ask()` with a handler hit | 230 to 380 us |
| new `satask()` | 2.2 to 3.2 ms |

Conclusions that drive the design:

1. The hit path is everything. 96 % of queries never compute. Any replacement
   must keep a per-object cache with a dictionary-lookup hit path.
2. Propositional deduction is not the bottleneck of the old system; the
   expression work done inside `_eval_is_*` handlers is. Templates must not
   be more eager than the handlers they replace.
3. The new system is slow for accidental reasons: it re-encodes the 105
   known-fact clauses on every call and builds SymPy `Boolean` objects for
   CNF. Integer clauses and a persistent solver remove almost all of it.
4. On the assumptions test suite the SAT path already agrees with the
   handlers on 81 % of queries and never contradicts them (two LRA bugs
   aside). The remaining gap is half "bridge to old assumptions" and half
   missing structural rules.

## 2. Architecture (implemented here)

```
satassume/
  rules.py       one rule base (old string syntax + new-system extras) -> clause patterns
  formula.py     P(pred, expr) atoms; And/Or/Not/Implies/Equivalent/Exclusive; allargs/anyarg/exactlyonearg
  compile.py     formulas -> integer clauses (direct where clausal, Tseitin otherwise)
  solver.py      incremental CDCL: add_clause any time, root propagation, implied(), solve(assumptions), entails()
  engine.py      Engine: ObjectCache (the node's own _assumptions dict), Session (solver + atom table),
                 demand-driven discovery, level-0 write-back
  sympy_api.py   is_(expr, pred), ask(prop, assumptions), install()/uninstall()
  templates/     structural clause generators per SymPy class (Symbol, numbers, Add, Mul, Pow, functions)
tools/
  record_queries.py   pytest plugin: record every query SymPy's tests make (old and new system)
  compare.py          replay the corpus against the engine: agreement / misses / disagreements / time
  bench.py            microbenchmarks old vs new vs satassume
```

Query path for `is_(expr, pred)`:

1. cache hit in `expr._assumptions` -> return (0.1 us, unchanged from today);
2. visit `expr` in the current session: allocate 33 variables, instantiate
   the rule base (105 clauses), assert cached facts as units, assert the
   class templates, and breadth-first visit the child nodes they mention
   (bounded by `discovery_budget`);
3. root-level propagation. Every literal assigned at level 0 is a
   context-free fact and is written back to the cache of its node, so one
   query about `x + y` also caches facts about `x` and `y`;
4. if the query literal is still unassigned: CDCL `entails()` (two solves
   under assumptions `-q` and `q`); learned unit clauses become root facts.

The engine never consults SymPy's `_eval_is_*` handlers. Every answer comes
from the rule base, the templates and search, so coverage is exactly what
the templates encode.

Query path for `ask(prop, assumptions)`: the same session; the assumptions
formula is compiled under a fresh selector variable `s` and `s` is passed
as a solver assumption, so nothing derived under it is ever at level 0 and
nothing leaks into the cache. Learned clauses stay valid across queries.

Sessions are generational: after `session_limit` nodes the solver is
discarded and a fresh one started. All level-0 facts already live in the
per-object caches, so nothing is lost and memory stays bounded.

## 3. Landing it in SymPy, stage by stage

### Stage 0: measure (done, tools in this repo)

`tools/record_queries.py` captures every query the test suite makes, for
both systems. `tools/compare.py` replays them. Agreement and "answers where
SymPy did not" are fine; "disagree" must stay at zero; "None where SymPy
answered" is the work list.

### Stage 1: one rule base, one propositional core

* Replace `sympy/core/assumptions.py::_assume_rules` and
  `sympy/assumptions/facts.py::get_number_facts` with `rules.py` (the test
  `test_rule_base_matches_sympy_old_rules` pins the old strings verbatim).
* `install()` replaces `sympy.core.assumptions._ask`. Every `is_*` cache
  miss now goes through the engine. Coverage is whatever the templates
  encode, so the corpus replay must show zero regressions on the old-system
  queries before this lands; the full SymPy suite is the acceptance test.
* Route `sympy.assumptions.ask` through `sympy_api.ask` for unary scalar
  predicates, keeping the existing satask/LRA path for relations and matrix
  predicates.
* Exit criterion: full SymPy suite green; `tools/bench.py` shows the compute
  path within 2x of the old `_ask` and the hit path unchanged.

Estimated effort: two to four weeks, dominated by suite fallout, not code.

### Stage 2: templates replace handlers, class by class

For each class with `_eval_is_*` methods (435 methods in 46 files), write the
equivalent template, then delete the handler. Order by call frequency in
the recorded corpus: numbers and symbols, Add, Mul, Pow, then exp/log/Abs,
trigonometric and hyperbolic functions, then the long tail.

Rules of engagement:

* a template is only added with a soundness test (see
  `tests/test_templates.py`: instantiate with concrete values, evaluate the
  formula under the old system's concrete truth values, must be True);
* a template mentions only the node and its direct arguments; deeper
  reasoning is the solver's job through discovery;
* anything that needs numerical evaluation (`Add._eval_is_extended_positive`
  with `evalf`, `_monotonic_sign`) becomes a clause-generating function that
  does the arithmetic in Python and emits unit facts, kept separate from the
  purely structural templates;
* the fuzzer approach from the `reasoning` project (random expressions,
  compare old and new answers) runs in CI against the corpus.

Estimated effort: two to three months for parity, with the long tail
in the full test suite rather than the assumptions tests.

### Stage 3: laziness and cost control

The prototype instantiates all 105 rule clauses and all templates for every
visited node. The old system is lazy per fact. To match it on large
expressions:

* instantiate template formulas only when one of their conclusion atoms is
  watched (demanded by the query or by a clause under propagation);
* instantiate the rule base incrementally by predicate cluster (sign
  cluster, set cluster, parity cluster) rather than all at once;
* cap discovery by relevance (a child is visited only if one of its atoms
  appears in a clause that is not yet satisfied).

### Stage 4: contextual reasoning beyond propositional

* Relations (`Q.lt`, `Q.eq`) via the existing LRA theory as a theory
  callback on the same solver (DPLL(T)), replacing `lra_satask`;
* matrix predicates as a second vocabulary with its own rule base and
  templates (the current `get_matrix_facts` and `handlers/matrices.py`);
* `refine` rewritten on top of `ask` results, unchanged in interface.

## 4. Risks and how they are contained

| Risk | Mitigation |
|---|---|
| An unsound template corrupts every answer | Soundness tests per template; corpus replay must show zero disagreements; templates land one at a time |
| Eager instantiation is slower than lazy handlers on big expressions | Discovery budget now; Stage 3 laziness |
| Re-entrancy: expression construction queries assumptions | Engine tolerates nested `is_` calls between solves; a template evaluating its own node returns None instead of recursing |
| Memory growth of a global solver | Generational sessions; caches live on the objects as today |
| Behaviour change across the full suite | Corpus replay gates every change at zero regressions; improvements that change expected outputs are reviewed one by one |
| Shared symbol knowledge bases | Only context-free, signature-determined facts are written back, which is what SymPy already stores there |

## 5. Out of scope for the prototype

Relations, matrix predicates, `refine`, `Q.is_true` over relationals,
polar, and the multipledispatch handler registration API. The test
`test_key_extensibility` and friends pass only if `Predicate.register`
survives as a way to register clause-generating functions; that is a small
shim in Stage 1.
