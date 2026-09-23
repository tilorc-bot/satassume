# Implementation plan

## Current scope

The repository does one thing for now: answer `ask(proposition, assumptions)`
for **unary scalar predicates on scalar expressions**, purely with the SAT
engine. Propositions and assumptions are Boolean combinations of
`Q.<name>(expr)` with `name` in the vocabulary of `satassume/rules.py` and
`expr` a scalar `Expr`.

Custom predicates are in scope once a clause-generating function is
registered for them (`satassume.register`, see `satassume/extensions.py`).

Out of scope for now: relations (`Q.eq/ne/lt/le/gt/ge`, `Eq`, `x < 0`
propositions, `Q.is_true` over a relational), matrix predicates and matrix
arguments, unregistered custom predicates, and replacing the old
`expr.is_*` system. Out-of-scope input returns `None` from
`satassume.sympy_api.ask` by rule; the caller (SymPy's `ask`) routes it to
its existing path. There is no fallback to SymPy's `_eval_is_*` handlers or
to `satask` inside the engine, and none will be added: out of scope means
"return None", nothing else.

### Definition of done

1. Every in-scope query in the recorded corpus (`queries.jsonl`) is answered
   identically to SymPy or better (a definite answer where SymPy returns
   None), with zero contradictions (`tools/compare.py --in-scope-only`
   exits 0 and reports `none=0`);
2. faster than `sympy.ask` on each in-scope query
   (`tools/compare.py --in-scope-only --time-sympy` reports
   "satassume slower on 0 records"; `tools/bench.py` for the microbenchmarks);
3. `Predicate.register` kept as a way to add clause-generating functions, so
   SymPy's extensibility tests (`test_key_extensibility` and friends) keep
   passing.

### Where the slice stands (2026-09-23, `tools/compare.py`)

| In-scope records | Agree | Extra | None | Wrong | Raises |
|---|---|---|---|---|---|
| 2588 | 2497 (96.5%) | 16 | 70 | 0 | 5 |

The five "raises" are the documented semantic choice: assumptions
contradicting declared facts are inconsistent here, trusted by SymPy's
handler path. Out of scope by category: 78 relations, 189 matrix
predicates or non-scalar arguments, 0 custom predicates, 8 non-Boolean
propositions.

Against the definition of done:

1. **Not fully met, and will not be by adding rules.** The 70 remaining
   misses are listed in README.md: for 67 of them SymPy's answer is false
   for a value that satisfies the assumptions (a zero factor or term, an
   infinite argument, `acot(-1)`, `acos(1)`), and the other three need
   `Abs` of a non-atomic base or a trigonometric identity. Zero
   contradictions on 2588 records. Every template added has a soundness
   test (`tests/test_templates.py`) and API tests (`tests/test_sympy_api.py`)
   pin the records left undecided on purpose;
2. **Met on 2532 of 2583 compared records** (`--time-sympy` with garbage
   collection controlled): 1.19 s against 6.88 s in total, slower on 51.
   The slower ones are undecided queries over a `Pow` cone with its
   derived nodes (two CDCL solves over about 600 clauses, 1.5 to 2.7 ms
   against 0.9 to 1.8 ms for SymPy) and constants asked about for the
   first time in a process;
3. **Met** by `satassume.register(pred, *classes)`
   (`tests/test_extensibility.py` mirrors SymPy's four tests). Hooking
   SymPy's own `Predicate.register` to it is part of landing the slice.

Work list for the slice, in order:

1. (done) the in-scope misses: hermitian/antihermitian as scalar rules,
   infinite sums, imaginary and composite factors, unit-circle and
   exact-constant powers, `exp(I*pi*c*s)`, `log`/`acos`/`asin` with the
   derived node `x - 1`, a `cot` template. Templates may refer to derived
   nodes (`2*e`, `x - 1`, `b +- 1`), which the engine visits only on
   escalation;
2. (mostly done) per-query speed: templates hand the engine precompiled
   clause patterns, the rule base is minimised to what unit propagation
   needs (79 clauses), constants with a complete closure skip it, common
   patterns are built once per process, search runs over the query's cone
   when the reused session holds other queries. Left: the 51 records
   above, which need a cheaper search (a native propagation core or
   cone-restricted decisions) rather than more template work;
3. decide the semantics of assumptions that contradict declared facts
   (raise, as now, or trust the assumption like SymPy) with the maintainer;
4. (done) the registration API; the `Predicate.register` shim inside SymPy
   is a landing task.

### Refine as a yardstick

`satrefine/` (the `reasoning` project's refine layer, see README) asks its
predicate questions through a switchable backend, and
`tools/refine_scoreboard.py` runs its 470 tests under SymPy's `ask`, satassume
alone and the two combined. As of 2026-09-22 satassume has no in-scope gap on
that suite; every test it loses asks a relation or a matrix predicate, so the
scoreboard is the first thing that moves when either enters scope. Handlers
that only the combined backend can justify are the way to grow the suite
past what either engine does alone.

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
   of the old system must keep a per-object cache with a dictionary-lookup
   hit path.
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
  sympy_api.py   ask(prop, assumptions), out_of_scope(), to_formula(), Unsupported
  templates/     structural clause generators per SymPy class (Symbol, numbers, Add, Mul, Pow, functions)
tools/
  record_queries.py   pytest plugin: record every query SymPy's tests make (old and new system)
  compare.py          replay the corpus, classified in scope / out of scope: agreement / misses / contradictions / time
  bench.py            contextual ask microbenchmarks, SymPy versus satassume
```

Query path for `ask(prop, assumptions)`:

1. `to_formula` translates both SymPy Booleans; anything out of scope
   raises `Unsupported` and `ask` returns None;
2. the assumptions formula is compiled under a fresh selector variable `s`
   in a session keyed by the assumptions, and `s` is passed as a solver
   assumption, so nothing derived under it is ever at level 0 and nothing
   leaks into the cache. The session is reused while the assumptions stay
   the same (many questions under one `assuming(...)` block); learned
   clauses stay valid across queries;
3. visiting a node allocates 33 variables, instantiates the rule base (79
   clauses, the propagation-minimal form of the 110), asserts its cached
   context-free facts as units, emits the precompiled clause patterns of
   the class templates whose conclusions the query demands, and
   breadth-first visits the child nodes they mention (bounded by
   `discovery_budget`); derived nodes wait for escalation;
4. root-level propagation, then the assumptions' implied literals; every
   literal assigned at level 0 is a context-free fact and is written back to
   the cache of its node;
5. if the query literal is still undecided: escalate (compile the parked
   templates, visit the derived nodes), then CDCL `entails()` (two solves
   under assumptions), in a fresh session over the query's cone when the
   reused session already holds other queries' nodes.

A proposition with no assumptions is a context-free query and goes through
`Engine.is_`: cache hit in `expr._assumptions`, else a session of its own
over the cone of the expression. Sessions are generational: after
`session_limit` nodes the solver is discarded; level-0 facts already live
in the per-object caches, so nothing is lost and memory stays bounded.

Rules of engagement for templates:

* a template is only added with a soundness test (see
  `tests/test_templates.py`: instantiate with concrete values, evaluate the
  formula under the old system's concrete truth values, must be True);
* a template mentions the node and its direct arguments, plus at most a
  few *derived* nodes built from them when the vocabulary cannot express a
  fact otherwise (`2*e` for half-integer exponents, `x - 1` for `log(x)
  == 0`); deeper reasoning is the solver's job through discovery, and
  derived nodes are visited only when the direct structure does not decide
  the query;
* anything that needs numerical evaluation (`Add._eval_is_extended_positive`
  with `evalf`, `_monotonic_sign`) becomes a clause-generating function that
  does the arithmetic in Python and emits unit facts, kept separate from the
  purely structural templates.

## 3. Later stages

Everything below is deferred until the current scope meets its definition of
done. It is kept here because the long-term goal, one engine for both SymPy
assumption systems, drives several design choices already made (the
per-object cache, level-0 write-back, the single rule base pinned to the old
strings).

### Landing the slice in SymPy

* Route `sympy.assumptions.ask` through `sympy_api.ask` for in-scope
  queries, keeping the existing satask/LRA path for everything
  `out_of_scope` reports.
* `Predicate.register` as a shim that registers clause-generating functions.
* Exit criterion: `sympy/assumptions/tests` green with the engine routed in.

### Replacing the old `expr.is_*` system (long-term goal)

* Replace `sympy/core/assumptions.py::_assume_rules` and
  `sympy/assumptions/facts.py::get_number_facts` with `rules.py` (the test
  `test_rule_base_matches_sympy_old_rules` pins the old strings verbatim).
* An install hook replaces `sympy.core.assumptions._ask` so every `is_*`
  cache miss goes through `Engine.is_`. Coverage is whatever the templates
  encode, so the corpus replay must show zero regressions on the old-system
  records before this lands; the full SymPy suite is the acceptance test.
* For each class with `_eval_is_*` methods (435 methods in 46 files), write
  the equivalent template, then delete the handler. Order by call frequency
  in the recorded corpus: numbers and symbols, Add, Mul, Pow, then
  exp/log/Abs, trigonometric and hyperbolic functions, then the long tail.
  The fuzzer approach from the `reasoning` project (random expressions,
  compare old and new answers) runs in CI against the corpus.
* Exit criterion: full SymPy suite green; the compute path within 2x of
  the old `_ask` and the hit path unchanged.

Measured so far on the old-system records of the corpus (6343 replayable,
informational): 5998 agree (94.6%), 24 extra answers, 321 None where SymPy
answered, 0 wrong. Context-free microbenchmarks in pure Python: the
compute path is 3 to 15x slower than the old handlers (`(p*q).is_positive`
102 us old, 962 us satassume; `(u**2 + 1).is_zero` 499 us versus 1377 us;
`(n + m).is_even`, unknown, 70 us versus 1309 us); the cached hit path is
identical. Instantiating a node (33 variables, 105 rule clauses, 30 to 50
template clauses) costs about 300 us, which is the whole gap; closing it
needs the laziness below and a native propagation core. Estimated effort:
two to three months for parity, with the long tail in the full test suite
rather than the assumptions tests.

### Laziness and cost control (former Stage 3)

The prototype instantiates all 105 rule clauses and all demanded templates
for every visited node. The old system is lazy per fact. To match it on
large expressions:

* instantiate template formulas only when one of their conclusion atoms is
  watched (demanded by the query or by a clause under propagation);
* instantiate the rule base incrementally by predicate cluster (sign
  cluster, set cluster, parity cluster) rather than all at once;
* cap discovery by relevance (a child is visited only if one of its atoms
  appears in a clause that is not yet satisfied).

Part of this (session instantiation cost) is already on the current slice's
work list because of the per-query speed criterion.

### Contextual reasoning beyond propositional (former Stage 4)

* Relations (`Q.lt`, `Q.eq`) via the existing LRA theory as a theory
  callback on the same solver (DPLL(T)), replacing `lra_satask`;
* matrix predicates as a second vocabulary with its own rule base and
  templates (the current `get_matrix_facts` and `handlers/matrices.py`);
* `refine` rewritten on top of `ask` results, unchanged in interface.

## 4. Risks and how they are contained

| Risk | Mitigation |
|---|---|
| An unsound template corrupts every answer | Soundness tests per template; corpus replay must show zero contradictions; templates land one at a time |
| Eager instantiation is slower than lazy handlers on big expressions | Discovery budget now; laziness later |
| Re-entrancy: expression construction queries assumptions | Engine tolerates nested `is_` calls between solves; a template evaluating its own node returns None instead of recursing |
| Memory growth of a global solver | Generational sessions; caches live on the objects as today |
| Behaviour change across the full suite | Corpus replay gates every change at zero regressions; improvements that change expected outputs are reviewed one by one |
| Shared symbol knowledge bases | Only context-free, signature-determined facts are written back, which is what SymPy already stores there |
| Silent fallback hiding engine gaps | None exists; out-of-scope input returns None and in-scope misses are counted by `tools/compare.py` |
