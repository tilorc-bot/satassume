# Agent report: the theory-solver interface (DPLL(T) phase one)

- **Date:** 2026-09-23
- **Status:** phase one done on the integration branch: protocol, solver
  hooks, test harness, hook tests; 487 tests pass. No theory is
  implemented yet and nothing in `engine.py` or `sympy_api.py` changed.
- **Scope:** `satassume/theory.py`, the theory hooks in
  `satassume/solver.py`, `tests/theory_harness.py`,
  `tests/test_theory_hooks.py`
- **Read this if:** you implement or test a theory (LRA, EUF) for
  satassume, or you wire relation atoms into the engine
- **Stale after:** any change to `satassume/theory.py` or to the theory
  section of `satassume/solver.py`; phase two (engine wiring, combination)
- **TL;DR:** a theory implements `register_atom`, `assert_lit`, `check`,
  `push_level`, `pop_level` and optionally `propagate`. The solver reports
  only variables registered for that theory, keeps the theory's level equal
  to its own decision level, turns every conflict clause into a learnt
  clause and calls `check` just before answering SAT. The no-theory path
  costs about 1 % on engine queries and 0.5-2.5 % on raw solver
  benchmarks. Test a theory with `TheoryCase` and `check_*` from
  `tests/theory_harness.py` plus a brute-force oracle, and wrap it in a
  `Recorder` to check the protocol both ways.

## 1. The interface

```python
solver = Solver()
theory = LRATheory()                          # yours
solver.attach_theory(theory)                  # several theories allowed
solver.register_atom(theory, v, payload)      # v: positive solver variable
```

`Solver.register_atom` records `v -> theory` and calls
`theory.register_atom(v, payload)`. The payload is opaque to the solver: the
adapter builds it (a linear-constraint record for LRA, an equation between
terms for EUF). `solver.py` imports nothing from SymPy and never looks
inside a payload. One variable may be registered with several theories
(this is what delayed theory combination needs, section 5).

Theory methods (full contract in the `satassume/theory.py` docstrings):

| method | returns | called |
|---|---|---|
| `register_atom(v, payload)` | None | at root, any time, once per `(theory, v)` |
| `assert_lit(lit)` | None or `(False, clause)` | once per assignment of a registered variable; `-v` means the atom is false |
| `check()` | None, `(True, model)` or `(False, clause)` | only on a total assignment, everything reported, just before SAT |
| `push_level()` | None | when a decision level opens (also empty levels for already-true assumptions) |
| `pop_level()` | None | once per level undone, innermost first; must restore the state of the matching `push_level` exactly |
| `propagate()` (optional) | iterable of `(lit, reason_clause)` | after all current assignments were reported without conflict |

A *conflict clause* is a non-empty list of solver literals, valid in the
theory, each false under the current assignment (so: negations of asserted,
not yet popped literals). The solver raises `RuntimeError` otherwise.
A *reason clause* contains the implied literal and otherwise only false
literals. Soundness rule: never a conflict (or propagation) that a theory
model refutes. An incomplete `check` (returns None or `(True, ...)` when it
cannot decide) is safe: SAT only ever becomes "not entailed" (None) in
`Solver.entails`.

`Solver.theory_models()` gives the `check` model of each theory after a SAT
`solve`.

### Why this shape

- The four-method core is the one of `~/reasoning/reasoning/theory.py` and
  SymPy PR 30537, so a theory ported from there fits with only
  `register_atom` added.
- `register_atom` on the theory (rather than a constructor argument) is
  needed because engine sessions grow incrementally: atoms appear while the
  solver already has root facts. The solver asserts a newly registered atom
  at once if its variable is already fixed at root.
- `propagate` returns eager reasons instead of PR 30098's
  `provide_reason` callback: less protocol, and the cheap propagations a
  first theory would do (bounds in LRA, congruence in EUF) have the
  explanation at hand. Skipping `propagate` is always correct.
- Routing by registration means a theory never sees the thousands of rule
  base variables of a session, and the solver needs no per-literal test
  for unregistered variables beyond one dict lookup (theory path only).

## 2. Hook-sequence guarantees (tested in `tests/test_theory_hooks.py`)

1. The theory's level (pushes minus pops) always equals the solver's
   decision level; it is 0 whenever a public solver call returns. Level-0
   assertions are permanent.
2. Each assignment of a registered variable is reported exactly once while
   it stands; a variable is reported again only after a `pop_level` undid
   it. Root facts are reported once, ever.
3. Reporting is lazy through a trail cursor: literals are reported after
   unit propagation finishes, in trail order, at the level they were made.
   A root unit added by `add_clause` is reported by the next `propagate`,
   `implied`, `entails`, `solve` or `register_atom`.
4. After a conflict from `assert_lit` or `check` there is no further
   `assert_lit`, `check` or `propagate` on any theory until a `pop_level`;
   a conflict at level 0 makes the solver UNSAT for good.
5. On a conflict clause whose highest level is below the current level the
   solver first backtracks to that level, then analyses; the clause is
   stored as a learnt clause (subject to normal learnt-clause deletion, so
   the theory must be able to find the conflict again).
6. `check` only on a total assignment with everything reported.
7. `implied` and the propagation stage of `entails` see `assert_lit`
   conflicts and `propagate` implications (`implied` returns None on a
   conflict) but never call `check`; `solve` and the search stage of
   `entails` are complete up to `check`.

With several theories attached, all see the same push/pop sequence; each
sees only its own variables. If theory A returns a conflict for a literal,
theories later in the attachment order may not see that literal; it is
undone before anything else happens.

## 3. Mapping SymPy relation atoms to payloads (sketch; adapters are owned by the impl agents)

- **LRA** (`satassume/lra_adapter.py`): `Q.lt/le/gt/ge/eq(a, b)` with `a - b`
  linear in its non-numeric terms and rational coefficients becomes a
  record like `(terms: dict[term, Fraction], constant: Fraction, strict: bool,
  equality: bool)` meaning `sum c*t (<, <=, =) constant`; the terms are
  SymPy expressions used only as keys. `Q.ne` is the negation of `Q.eq`
  (same variable, negative literal). Anything non-linear, non-real or
  infinite is not registered (left to SAT, sound). `~/reasoning/reasoning/lra_adapter.py`
  is a good model.
- **EUF** (`satassume/euf_adapter.py`): `Q.eq(a, b)` / `Eq(a, b)` between
  arbitrary terms becomes an equation between term handles; function
  applications are flattened to `f(t1, ..., tn)` over term handles so
  congruence closure can see them. Numbers are distinct constants
  (`1 != 2` is a theory fact the adapter can add as disequalities).
- Adapters expose something like `adapter.register(solver, var, sympy_atom)
  -> bool` that returns False when the atom is not interpreted, so the engine
  can offer every relation atom to each adapter.

## 4. Testing a theory with the harness

```python
from theory_harness import TheoryCase, Recorder, check_protocol, check_solve, check_entails, check_implied

rec = Recorder(MyTheory())
case = TheoryCase(rec, {1: payload1, 2: payload2}, clauses=[[1, 2], [-1, 3]])
check_solve(case, consistent)                       # brute force over 1..n
check_entails(case, consistent, 2, assumptions=[1])
check_implied(case, consistent, [1])
check_protocol(rec)                                 # solver side of the protocol
```

`consistent(assign)` gets `{var: bool}` for every registered atom and says
whether that conjunction of theory literals is satisfiable. It must be an
independent, simple checker: for LRA, exact Fourier-Motzkin elimination
over `Fraction` on the few variables of a test case (or evaluate on
enumerated candidate points only when that is provably complete); for EUF,
naive congruence closure with union-find to a fixed point, then the
disequalities. Do not use the implementation under test or SymPy's solver
as the oracle. `complete=False` relaxes the checks for a theory that may
answer None (only definite answers are checked). Keep cases at about 14
variables or fewer.

`Recorder` also checks live that `check` sees a total assignment and that
every conflict clause the theory returns is false under the solver's
assignment, so a fuzz test through `Recorder` checks the theory side of the
protocol too. `ForbidTheory` (a dummy theory where given partial
assignments are inconsistent, modes `eager`/`lazy`/`propagate`) shows the
expected shape of a theory in 60 lines. Theory unit tests without a solver
can call the five methods directly.

## 5. Open questions for phase two (integration agent, next)

**Combining LRA and EUF.** Plan: start disjoint, one theory per atom by
kind (LRA for linear real relations, EUF for `eq/ne` over other terms),
no sharing. Sound, incomplete across the boundary (`f(x) = f(y)` from
`x <= y, y <= x`). Then delayed theory combination: for each pair of terms
shared by both theories create an interface equality variable and register
it with *both* theories; the SAT solver branches on it and each theory
checks it. This needs nothing new in the solver (multi-theory registration
already works) and no equality propagation inside LRA; Nelson-Oppen with
equality propagation (both theories are convex) is the faster alternative
if the number of interface equalities blows up. Decide after measuring on
`sympy/assumptions/tests/test_rel_queries.py`.

**Where relation atoms enter.** Today `sympy_api.to_formula` raises
`Unsupported("relation")` for a `Relational` or a `Q.eq/lt/...` applied
predicate, so `ask` returns None. Phase two:

1. `to_formula` turns `Q.lt(a, b)` (and `a < b`, `Q.is_true(a < b)`) into an
   atom `P('lt', Args((a, b)))`, normalised so that `gt/ge` become `lt/le`
   with swapped arguments and `ne` becomes `Not(eq)`. `out_of_scope` stops
   reporting "relation" for the supported kinds.
2. `VarTable.var` already gives a non-vocabulary atom one variable of its own
   and queues it in `new_custom`; `Session._flush` hands it to
   `Session._custom`. `_custom` gets a branch for relation predicates that
   offers the atom to the session's adapters, which call
   `solver.register_atom`. Theories live on the `Session` (created lazily
   at the first relation atom and attached to `session.solver`), so
   cone-search fresh sessions and context sessions each get their own.
3. Bridging unary predicates: when a term `t` occurs in a registered LRA
   atom, `ensure(t, {'positive','negative','zero','real', 'finite'})` and
   register fresh atoms `t > 0`, `t < 0`, `t = 0` with clauses
   `positive(t) <-> (real(t) & finite(t) & [t > 0])` and similarly, so that
   `ask(Q.negative(x), Q.lt(x, y) & Q.lt(y, 0))` works. LRA is over finite
   reals: every term in an LRA atom must be known real and finite (or the
   relation atom must imply it) before its constraint is registered; the
   exact SymPy semantics of `Q.lt` on non-real or infinite arguments has
   to be fixed first (open).
4. Caches: `writeback` sends root values of relation atoms to
   `custom_cache`; only context-free sessions may do that (context sessions
   already guard assumptions by a selector, so their root trail is
   context-free too, which keeps this correct).

**`ask(Q.lt(x, y), assumptions)` end to end.** `to_formula` -> atom
`P('lt', Args((x, y)))` -> `Engine.ask` -> `_context_session` (assumption
relation atoms registered via `assume_formula`) -> `_literal` ->
`literal_of` allocates the variable and registers the atom with LRA ->
`query_literal`: `implied(assumptions)` (unit propagation plus `assert_lit`
and `propagate`) may already decide; else `entails` runs `solve` twice with
`check` as the final arbiter; a cone search builds a fresh session that
registers its own atoms. No engine code needs to know about theories beyond
steps 2-3.

**Engine changes needed (not made in phase one):** a relation branch in
`Session._custom`; theory instances on `Session`; the bridge clauses of
step 3; `out_of_scope`/`to_formula` in `sympy_api.py`. The solver side
needs nothing more unless measurements ask for lazy explanations
(`provide_reason`) or theory-driven decisions.

## 6. Timing (cores 8,9, alternating base and candidate, best of runs)

| benchmark | before | after |
|---|---|---|
| 12 random 3-SAT instances, 90 vars, ratio 4.26 (search) | 168.5 ms | 173.2 ms (+2.8 %) |
| 200 x (`implied` + `entails`) on a 9000-variable chain (propagation) | 929 ms | 934 ms (+0.5 %) |
| `tools/bench.py` cases, satassume only, sum of per-call means | 616 us | 624 us (+1.2 %) |
| same cases, 40 fresh engines | 283 ms | 283 ms (noise) |

The hot loops test one attribute or local per call, per decision or per
backtrack; `_propagate` itself is unchanged. The search overhead did not
come from any single hook when they were removed one at a time.

## 7. Contact

Interface questions and requests to change `satassume/theory.py`, the
solver hooks or the harness go to the integration agent (SendMessage; find
its name with ListAgents). Decisions others must know go into this note;
send the text to the integration agent, who edits it.
