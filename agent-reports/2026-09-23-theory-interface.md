# Agent report: theory solvers in satassume (DPLL(T), phases one and two)

- **Date:** 2026-09-23
- **Status:** phase one (protocol, solver hooks, harness) is on `main`.
  Phase two (relation atoms wired into the engine, unary links, equality
  sharing, end-to-end tests) is on the integration branch. The EUF adapter
  is merged and in use. The LRA adapter (branch of lra-impl, `9f5aa00`) was
  tested here from a scratch copy: all of SymPy's `test_rel_queries.py`
  passes and 75 of the 78 relational corpus records agree, 0 wrong.
- **Scope:** `satassume/theory.py`, the theory hooks in
  `satassume/solver.py`, `satassume/relations.py`, the relation routing in
  `satassume/engine.py` and `satassume/sympy_api.py`,
  `tests/theory_harness.py`, `tests/test_theory_hooks.py`,
  `tests/test_relations.py`, `tools/compare.py --relations-only`
- **Read this if:** you implement or test a theory (LRA, EUF) for
  satassume, write an adapter, or change how relations reach the engine
- **Stale after:** any change to `satassume/theory.py`,
  `satassume/relations.py` or the theory section of `satassume/solver.py`
- **TL;DR:** a theory implements `register_atom`, `assert_lit`, `check`,
  `push_level`, `pop_level` and optionally `propagate`. The solver reports
  only variables registered for that theory, keeps the theory's level equal
  to its own decision level, turns every conflict clause into a learnt
  clause and calls `check` just before answering SAT. Relations reach the
  engine as two atom kinds, `eq(a, b)` and `lt(a, b)`, with `<=` meaning
  "not the reversed `<`", which is SymPy's own definition. Each session
  has its own adapters. LRA atoms are guarded by `real` of their terms, so
  `<` on non-real or infinite arguments stays a free Boolean. EUF gets
  `eq` unconditionally. Theories share equalities over common terms
  through interface atoms (delayed theory combination). If no theory
  interprets one of the user's relations, `ask` returns None as before.

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

## 3. Adapters as wired (entry points announced by the builders)

The engine talks to an adapter only through these calls
(`satassume/relations.py`, `AdapterSpec(name, factory, guarded)`):

| call | LRA (`LRAAdapter`, guarded) | EUF (`EUFAdapter`, unguarded) |
|---|---|---|
| `factory()` | one adapter (and theory) per engine session | same; one solver per adapter |
| `register(solver, var, atom) -> bool` | `Q.lt(a, b)` / `Q.eq(a, b)` with `a - b` linear over opaque terms and rational coefficients; ground atoms such as `Q.lt(1, 2)` are fixed by the theory itself | `Q.eq(a, b)` over any Basic except nan; Add/Mul/Pow/applications are uninterpreted heads, binders opaque |
| `terms(atom)` | opaque terms of the linear form, including ones that cancel (`Q.lt(x, x + 1)` gives `[x]`); `[]` only for purely numeric atoms | not used |
| `shared_terms()` | every opaque term registered | every interned term, subterms included |
| numbers | exact rationals | only Integer/Rational are distinct values; Float, pi, oo, zoo opaque |

The engine calls `register` with atoms in normal form only: `Q.lt(a, b)`
and `Q.eq(a, b)`, the latter with `(a, b)` in `default_sort_key` order.
`Q.ne`, `<=`, `>=` and `>` arrive as negated or swapped literals of these
two. A guarded adapter never sees the user's variable `r`: it gets a fresh
`t` and the engine adds `real(u1) & ... & real(uk) -> (r <-> t)` over
`terms(atom)`, so it may assume every term is a finite real.

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

## 5. Phase two: relations in the engine

### 5.1 What SymPy means by `Q.lt` on non-real or infinite arguments

SymPy (read-only checkout, `sympy/assumptions/relation/binrel.py`,
`sympy/core/relational.py`, `sympy/assumptions/lra_satask.py`):

- `BinaryRelation.eval` evaluates through `is_eq`/`is_ge`. The `is_ge`
  docstring requires that "in cases where either x or y is non-real all
  comparisons will give None". Infinities get their extended-real order
  (`is_ge(oo, x)` is True for extended-real `x`).
- `lra_satask`, the only path with arithmetic reasoning, raises
  `UnhandledInput` unless every argument `is_real` (hence finite). It maps
  `extended_positive` to `positive` and treats `positive_infinite` as
  False, so its answers assume finite reals throughout.
- Negation is definitional: `~(x < 0)` *is* `x >= 0`, since
  `Relational.negated` and `BinaryRelation.negated` map `lt` to `ge` and
  `eq` to `ne`. `ask(Q.le(x, y), Q.gt(x, y))` is False even for plain
  symbols.

**Decision.** `a <= b` is `Not(a > b)` for any arguments, because that is
SymPy's definition and holds for reals. `a < b` has its order meaning only
when every opaque term of `a - b` is real, and so finite (the LRA guard).
Otherwise it is a free Boolean, which is sound whatever SymPy decides later
for complex or infinite arguments. `a == b` is equality of values in any
domain and goes to EUF unconditionally. `nan` is rejected, since
`Eq(nan, nan)` is False. Infinite arguments (`x < oo`) are not interpreted
by LRA, and a symbol that may be infinite (`extended_real`) fails the
guard.

### 5.2 Wiring

- `sympy_api.to_formula(expr, relations)` turns relations
  (`Relational`, `Q.eq/ne/lt/le/gt/ge`, `Q.is_true(rel)`) into atoms via
  `relations.relation_atom` when `Engine.relation_specs` is non-empty. With
  no specs it raises `Unsupported("relation")` exactly as before.
  `out_of_scope` still reports "relation" (the corpus tool uses it to
  group records).
- `Engine(relations=None)` takes the default specs: LRA and EUF when their
  modules import, only with the SymPy templates. `relations=[]` switches
  relations off.
- `Session.relations` (a `relations.Relations`) is created at the first
  user formula of a session. Relation atoms get ordinary custom variables
  (`VarTable.custom`); `Session._custom` queues them, and
  `Relations.process` interprets them at the end of `literal_of`,
  `assume_formula` and `Engine._literal`. At that point the session is not
  compiling, so visiting guard terms is safe. Cone-search sessions and
  context sessions each have their own adapters and theories.
- `relations.Uninterpreted` is raised when a relation of the query or the
  assumptions has no theory. `ask` turns it into None, matching the
  old behaviour. Internal atoms (links, interface equalities) never raise.

### 5.3 Links to the unary vocabulary (all in `relations.Relations._link`)

For each argument `e` of a user relation, and each argument of a
vocabulary atom of the user formulas once the session has relations
(numbers excluded):

| clause | reason it is sound |
|---|---|
| `positive(e) -> lt(0, e)` | positive means finite real > 0 |
| `lt(0, e) & real(e) -> positive(e)` | a finite real > 0 is positive |
| `negative(e) -> lt(e, 0)` | same |
| `lt(e, 0) & real(e) -> negative(e)` | same |
| `zero(e) <-> eq(e, 0)` | `Eq(e, 0)` holds iff `e` is 0, in any domain |

The rule base derives nonnegative, nonzero, extended_* and
positive_infinite from these three. Substituting equals into other unary
predicates (`prime(x)` from `x = y` and `prime(y)`) is not linked; SymPy
marks those tests XFAIL too.

### 5.4 Combination: kept apart by kind, sharing equalities

Each adapter interprets what it can. `eq` atoms go to both EUF and (under
the guard) LRA, `lt` atoms only to LRA. After each batch,
`theory.EqualitySharing` finds terms present in at least two adapters'
`shared_terms()`. For each new pair of shared terms it creates the atom
`eq(a, b)`, which is interpreted like any other `eq` atom. This is delayed
theory combination: the SAT solver decides the arrangement of shared
terms and each theory checks it. `ask(Q.eq(f(x), f(y)), (x <= y) & (y <= x))`
is True with sharing and None without it (tested with the dummy theories
and with the real EUF).

**When Nelson-Oppen equality propagation would be needed.** DTC is
complete here: LRA over the rationals and EUF are stably infinite with
disjoint signatures, and both are convex. The cost is a quadratic number of
interface atoms in the shared terms, all of them branching variables of
the search. Nelson-Oppen (each theory propagates the equalities between
shared terms that it entails) is worth doing when a session has more than
a few dozen shared terms, or when searches slow down because the solver
branches on interface atoms. LRA would then need equality detection
(bounds that pin `a - b` to 0, or tableau-row equality), exposed through
`propagate()` with an explanation. No record in the corpus comes close to
that size today.

### 5.5 Testing end to end (`tests/theory_harness.py`)

`relation_engine(specs)` builds a private engine: `None` gives the real
adapters, `dummy_specs()` the stand-ins `OrderAdapter` (dense order over
symbols and rationals, guarded) and `UFAdapter` (equality with
uninterpreted functions). `ask_with(engine, prop, assum)` returns the
answer, or `"inconsistent"`. `tests/test_relations.py` has the wiring,
link, guard and sharing tests, and a Hypothesis test that checks random
order formulas against a grid model checker. It also transcribes SymPy's
`test_rel_queries.py`: xfail while `satassume.lra_adapter` is missing,
strict once it is present. `python tools/compare.py queries.jsonl
--relations-only` replays the 78 relational corpus records.

### 5.6 Results

| relational corpus (78 records) | agree | none | wrong |
|---|---|---|---|
| no adapters (before) | 15 | 63 | 0 |
| dummy order + dummy UF | 71 | 7 | 0 |
| EUF only (main today) | 49 | 29 | 0 |
| LRA `9f5aa00` + EUF | 75 | 3 | 0 |

The 3 left need substitution of equals into non-relational templates
(`rational(x**y)` given `x = 1`, `prime(p**x)` given `x != 1`). In-scope
corpus answers are unchanged (2497 agree, 16 extra, 70 none, 0 wrong). The
alternating timing on a loaded machine showed no difference beyond noise
(2.6-3.0 s base, 2.4-3.2 s candidate).

### 5.7 Open questions

- Substitution of equals into unary predicates and templates (the 3
  records above, and SymPy's XFAIL `test_equality_failing`). This would
  need EUF equalities to reach the rule base (`eq(x, y) -> (P(x) <-> P(y))`
  for demanded predicates), which is quadratic and wants to be
  demand-driven.
- Nonlinear facts (SymPy's XFAIL multiplication tests) are out of reach of
  LRA. The templates know signs of products, so linking `lt(0, a*c)` to
  `positive(a*c)` already happens when `a*c` is a queried node.
- Integer reasoning: LRA is incomplete for integer symbols (it is sound,
  just weaker). SymPy refuses integer symbols in `lra_satask`; we answer
  what the combination can prove.

## 6. Timing of the solver hooks, phase one (cores 8,9, alternating base and candidate, best of runs)

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
solver hooks, the harness or `satassume/relations.py` go to the integration
agent (SendMessage to agent id `ab05214d89d4911cc`; names do not resolve,
the orchestrator `fable-rewrite-a8` lists the ids). Decisions others must know go into this note;
send the text to the integration agent, who edits it.
