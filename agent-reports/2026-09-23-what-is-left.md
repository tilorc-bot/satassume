# Agent report: what is left to replace SymPy's new and old assumption systems

- **Date:** 2026-09-23
- **Status:** roadmap; written after the scalar scope was finished at
  `744893c` (474 tests passing, in-scope corpus at 96.5 % agreement, 0
  contradictions)
- **Scope:** everything between the current repository and the long-term
  goal: `ask(Q.*)` complete, then `expr.is_*` replaced, then the duplicate
  machinery in SymPy removed
- **Read this if:** you are deciding what to do next in this repository or
  in `reasoning`, or estimating how far the long-term goal is
- **Stale after:** any change of scope, the relation or matrix work
  landing, or new measurements of the old-system cache-miss cost
- **TL;DR:** finishing the new-system replacement is weeks of known work
  (relations via a theory callback, matrix predicates, the SymPy
  integration PR). Replacing the old system is months and has one open
  technical question: a cache miss costs about 118 us per node visit
  here versus 95 us on average in the old system, and the old system is
  lazy per fact while the engine instantiates a node's whole predicate
  block and cone. Everything else on the old-system side is transcription
  and test review.

## 1. Where the repository stands

| | Value |
|---|---|
| In-scope corpus (unary scalar predicates, 2588 records) | 96.5 % agree, 16 extra answers, 70 None, 0 wrong, 5 raises |
| Old-system corpus (informational, 6343 records) | 95.1 % agree, 27 extra, 283 None, 0 wrong |
| Time over the in-scope corpus | 1.19 s satassume, 6.88 s `sympy.ask` |
| Records slower than SymPy | 51 of 2583 |
| Node visit cost | 118 us (was 767 us) |

The 70 remaining Nones are documented in the README: 67 are SymPy answers
refuted by a concrete value satisfying the assumptions, 3 need `Abs` of a
non-atomic base or `cos**2 + sin**2 = 1`.

## 2. Finishing the new-system replacement (weeks)

### 2.1 Relations

`Q.lt`, `Q.le`, `Q.gt`, `Q.ge`, `Q.eq`, `Q.ne` and relational propositions
(78 corpus records) return None. The right shape is a theory callback on
the CDCL solver, called on each assignment of a relation atom and able to
report a conflict clause: DPLL(T) with linear real arithmetic. The
`reasoning` repository already has this as an LRA `TheorySolver` following
the protocol of SymPy PR 30537; porting it means adding the callback hooks
to `satassume/solver.py` (assignment, new decision level, backtrack, final
check) and translating relation atoms to the theory's constraints in
`sympy_api.py`. Estimated one to two weeks including tests against
`sympy/assumptions/tests/test_rel_queries.py`.

### 2.2 Matrix predicates

189 records involve matrix predicates or non-scalar arguments. Needed: a
second predicate vocabulary (`square`, `invertible`, `symmetric`,
`orthogonal`, `unitary`, `fullrank`, `positive_definite`, `diagonal`, the
triangular pair, `real_elements`, `integer_elements`, `complex_elements`,
`singular`, `normal`) with its own single-node rule base from
`get_matrix_facts`, plus templates for `MatMul`, `MatAdd`, `Transpose`,
`Inverse`, `MatPow`, `BlockMatrix`, `BlockDiagMatrix`, `MatrixSlice`,
`Trace`, `Determinant`, `MatrixElement` and the special matrices, covering
what `handlers/matrices.py` does today (about 100 registrations). The
engine allocates variable blocks per vocabulary, so this is additive.
Estimated one week.

### 2.3 Decisions for the maintainer

- Assumptions contradicting a symbol's declared facts: raise (current) or
  trust the assumption (SymPy). Five corpus records.
- Whether to keep answers that are better than SymPy's where SymPy's are
  wrong (the 67 refuted cases and `(I**(3+I)).is_imaginary`), which
  changes expected outputs in SymPy's tests.

### 2.4 The 51 slower queries

All are undecided queries over a `Pow` cone with derived nodes: six nodes,
about 600 clauses, two CDCL solves. Options, in order of expected payoff:
answer "undecided" from one solve plus a model check instead of two
solves; skip search when the queried literal has no clause path to any
unit; cheaper session construction for first-seen constants. Templates
will not help here.

### 2.5 Integration into SymPy

- Route `sympy.assumptions.ask` through the engine for in-scope input;
  out-of-scope input keeps the existing path until 2.1 and 2.2 land.
- `Predicate.register` becomes a shim over `satassume.register`, so
  `test_key_extensibility` and friends pass unchanged.
- Honour `global_assumptions` and `assuming()` by passing the context as
  assumptions; the engine's session reuse keyed by assumption formula
  makes repeated queries under one context cheap.
- Then delete `handlers/`, `sathandlers.py`, `satask.py`, `lra_satask.py`,
  `ask_generated.py` and the duplicate fact definitions; `refine` stays as
  it is on top of `ask`.
- Fourteen modules outside the assumptions package call `ask` (matrix
  expressions, `core/power.py`, `functions/elementary/exponential.py`
  among them), so the acceptance test is the full SymPy suite, run with
  the engine behind a flag first.

### 2.6 Validation

- Run the `reasoning` soundness fuzzer (`tools/check_soundness.py` there)
  against `satassume.sympy_api.ask`; it checks definite answers against
  concrete models and shrinks with Hypothesis.
- Record the corpus from the whole SymPy suite, not only
  `sympy/assumptions/tests`, `test_assumptions.py` and `test_arit.py`, so
  the routing and the matrix and relation work are measured on everything
  SymPy actually asks.
- A shared benchmark case set with `reasoning`, so speed claims are
  comparable.

## 3. Replacing the old system (months)

### 3.1 The open question: cache-miss cost

Measured on five core test files: 6.07 M `is_*` accesses, 250 k reaching
the compute path, 23.8 s inside it (27 % of wall). The hit path is a
dictionary lookup in both systems and stays unchanged because the engine
writes root-level facts into `expr._assumptions`. The miss path is the
problem: the old `_ask` averages 95 us because it asks only for the one
fact it needs and calls handlers lazily; the engine visits the node's
whole 33-predicate block and its cone at 118 us per node, so a three-node
expression costs three to four times the old path. At the measured miss
rate that would roughly triple the time SymPy spends there.

Since a native core is not planned, the cost has to come down in pure
Python:

- instantiate only the rule clauses and templates that can reach the
  queried predicate (the rule graph is nearly connected, so this needs a
  precomputed reachability table per predicate, not the distance-1
  neighbourhood tried earlier);
- reuse per-class pattern state across nodes so a visit is a handful of
  list extensions;
- never search on the context-free path unless propagation left the
  literal free and a clause path to a unit exists;
- measure on the same five-file workload with the engine installed, not
  on microbenchmarks.

If this cannot reach parity, the honest alternative is to replace the old
system only for the classes where the engine is faster and keep
`_eval_is_*` elsewhere, which is a different design from "one engine".

### 3.2 Coverage

95.1 % of the recorded old-system queries agree. Known gaps: `Mod`,
`floor` and `ceiling` of quotients, monotonicity facts such as
`pi/2 > 1`, and anything the old handlers decide by numerical evaluation
(`Add._eval_is_extended_positive` with `evalf`, `_monotonic_sign`). Those
become clause-generating functions that do the arithmetic in Python and
emit unit facts, kept apart from the structural templates.

Beyond the corpus: 435 `_eval_is_*` methods in 46 files. Templates exist
for `Symbol`, numbers, `Add`, `Mul`, `Pow`, `Abs`, `exp`, `log`, `re`,
`im`, `sign`, `conjugate`, `floor`, `ceiling`, `factorial`, trigonometric,
hyperbolic and inverse trigonometric functions. Missing: `Piecewise`,
`Sum`, `Product`, `Integral`, special functions, combinatorial functions,
`Mod`, `Min`/`Max`, and the scalar parts of matrix expressions. Each is a
template with a soundness test; order by call frequency in a corpus
recorded from the full suite.

### 3.3 Living underneath expression construction

`Mul.flatten` and `Add` canonicalisation query `is_zero`, `is_commutative`
and `is_infinite` while building expressions, and handlers build new
expressions that query again. The engine must be re-entrant (a query
arriving while another query's session is between solves), must not hold
a lock on shared state, and must import nothing heavy. The current guard
that makes a template's query about its own node return None is a start;
a test that installs the engine and runs `sympy/core/tests` is the real
check.

### 3.4 Replacing `_ask` and `FactKB`

`install()` existed and replaced `sympy.core.assumptions._ask` with one
function; it was removed with the scope change and comes back at this
stage. What must keep working unchanged: `Symbol('x', positive=True)`
creating its knowledge base, the shared knowledge base per assumption
signature in `Symbol._canonical_assumptions` (safe, since only
context-free facts are written back), `assumptions0`, symbol equality and
hashing, and the helpers `assumptions()`, `check_assumptions()`,
`common_assumptions()`, `failing_assumptions()`.

### 3.5 Fidelity versus correctness

The engine disagrees with the old system where the old system is wrong.
Every such case changes some simplification output somewhere in the suite
and has to be reviewed one by one. Thousands of tests depend on `is_*`
results indirectly; this is the long tail and cannot be estimated from
the corpus.

## 4. Cleanup once both are in

- One rule base: delete `sympy/core/assumptions.py`'s string list,
  `assumptions_generated.py`, `facts.py`'s number facts and
  `ask_generated.py` in favour of `rules.py`.
- One template registry replacing `handlers/`, `sathandlers.py` and the
  `_eval_is_*` methods.
- A readable template notation. The current index-slot form is faster to
  compile but harder to audit than `sathandlers`; a declarative layer over
  the same pattern compiler (`allargs('real') >> node.real`) and a dump
  tool that prints the compiled rules for a given expression shape would
  restore that without touching per-node cost.

## 5. Suggested order

1. Relations (2.1) and matrix predicates (2.2): they complete a slice that
   can land.
2. The SymPy integration PR behind a flag (2.5), with the fuzzer and the
   full-suite corpus (2.6).
3. The old-system miss-cost work (3.1), because it is the one open
   technical question; the rest of section 3 is a known amount of
   transcription and review and should wait for its answer.
4. Cleanup and the readable template layer (4).
