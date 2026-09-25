# Agent report: plan for the next performance round

- **Date:** 2026-09-25
- **Status:** plan only; nothing here is implemented. Baseline is `main` at
  `b3d429b`, the tree left by the performance commits of 2026-09-25
  (`328bdbb`..`b3d429b`, review items in issue #8, background in issue #7)
- **Scope:** `satassume/solver.py`, `satassume/engine.py`,
  `satassume/sympy_api.py`, `satassume/extensions.py`, the theory adapters,
  `tools/refine_replay.py`, `tools/solver_diff_fuzz.py`
- **Read this if:** you are about to run the next speed round and want the
  measurements to take before writing code, the correctness argument each
  change needs, and the order that avoids doing work a later item makes moot

## 1. Where the time is now

`tools/refine_replay.py` over the recorded refine stream (13,877
`ask(prop, assumptions)` calls, `tools/refine_record.py` on the
`refine-identities` branch): **4.2 s cold** on `b3d429b`, down from 10.1 s
on `cbb971f`. The full `refine` battery with satassume alone: 15.2 s, of
which satassume is those 4.2 s and satrefine's own matching the rest.

Engine counters over the stream (`Engine.stats`): 7,906 queries reach the
engine (the other 6,017 hit the answer memo); they build 2,664 sessions, 757
of them cone rebuilds; 3,192 searches; 1,792 escalations. Profiled share:
about 45% search and propagation, 25% session re-creation (rule patterns
re-added to every session, assumptions re-grounded), 20% grounding SymPy
expressions into nodes and clauses, the rest hashing and API overhead.

Two facts from the last round shape this plan:

- **`None` is the expensive answer.** `Solver.entails` runs two total-model
  searches to return `None` (a model of `A ∧ ¬P` and one of `A ∧ P`); the
  solver agent counted 5,334 of 5,397 `entails` calls that reach search
  ending this way. `True`/`False` mostly fall out of unit propagation. Three
  properties of the current code make this worse than it need be:
  `_pick_branch` (solver.py) only stops when *every* session variable is
  assigned, so a search pays for every other query's nodes in the session;
  phase choice is a fixed negative default plus phase saving, not
  cost-aware; and escalation (`Session.escalate`) instantiates the whole
  cone before any search, with nothing loaded lazily during the search.
- **Sessions rebuild what they share.** Every one of the 2,664 sessions
  re-compiles and re-adds the rule patterns of its nodes and re-grounds its
  assumptions through SymPy, `relations.py` and the LRA adapter.

## 2. Ground rules

Every item below has four parts: a **measurement** that bounds the gain
before any code is written, a **sketch**, the **correctness argument** a
reviewer needs, and a **decision rule**. Two rules apply throughout:

- nothing is implemented whose measured bound is under 5% of the replay
  (3% for items that are ten lines);
- nothing is kept that does not show at least 5% in an interleaved A/B
  (reference, candidate, reference, candidate, best cold pass each) against
  an untouched `main` checkout, with every replay answer identical and the
  test suite unchanged (1656 passed, the 2 pre-existing `test_shared_facts`
  failures, 1 skipped, 4 xfailed, 1 xpassed).

Machines: the local box has 2 physical cores, so two agents measuring at
once interfere. Put one on the Pi container (`pi5-shell`; SymPy pin at
`/work/src/sympy-pin`, reference clone at `/work/src/perf-ref`, benchmark
under `/work/src/bench/`, python at `/work/.mamba/envs/sympy/bin/python`,
which is not on PATH there). Cap every command at 270 s; wrap remote runs
in `timeout 250`.

## 3. Phase 0: instrumentation and a second gate (first, about half a day)

The current gate covers one query distribution. Before the solver changes
again:

- **0.1 The fuzz as a test.** Turn `tools/solver_diff_fuzz.py` into
  `tests/test_solver_incremental.py`: one long-lived solver against fresh
  solvers of the *same* code over the same clauses, a few hundred seeds in
  CI time. Extend its operation mix as items land (witness reuse,
  component-restricted `entails`, theory mode). This is what makes held
  solver state safe to keep changing.
- **0.2 A second distribution.** Record SymPy's own assumption-test queries
  with `tools/record_queries.py`, replay them through `tools/compare.py` on
  `b3d429b`, and freeze the in-scope answers as a second gate. This also
  settles the open question in issue #8 about caching `None` answers on a
  workload other than the refine battery.
- **0.3 A per-query log.** Behind a flag in `tools/refine_replay.py`, log
  per query: the path taken (memo, propagation, escalation, search, cone
  rebuild), the outcome, decisions and conflicts per `solve`, the session's
  variable count and, for the measurements below, the model each successful
  `solve` found. Every measurement in phases 1 to 3 reads off this log.

## 4. Phase 1: make `None` cheap

### 1.1 Witness reuse (expected largest gain)

- *Measure* (offline, from the 0.3 log): for each search-path `None`, would
  a model found earlier in the same session, or under the same assumption
  set, have satisfied `A ∧ ¬P`, and `A ∧ P`? That count times the
  per-search cost is the bound. Count also the `True`/`False` searches a
  stored model would have short-cut: a model of `A ∧ ¬P` found earlier
  already proves "not entailed".
- *Sketch:* per solver, a small ring of models (start with 4), each tagged
  with the `_stamp` at which it was found. In `entails`, before each
  `_solve`, test the stored models against the target literals; a model
  older than the current stamp is re-validated against the clauses added
  since (an index slice of `_clauses`) and dropped if any is falsified.
  Sessions with theories: a Boolean model found earlier stays
  theory-consistent as long as no theory atom was registered since, so gate
  on a theory-atom stamp and otherwise drop the model.
- *Correctness:* a model is always checked against the actual clauses,
  never trusted; the theory-atom gate is conservative.
- *Decision:* keep at 5% or more. If the offline bound shows that most
  `None`s of a session share one model, also reconsider `entails` itself:
  find a model of `A` first and read `P` off it, searching only when `P` is
  forced.

### 1.2 Component-restricted search (removes the cone-search machinery if it works)

- *Measure:* per search, under the root and assumption assignment, the size
  of the connected component of the query variable in the clause graph
  (clauses with a true literal removed) against the session's unassigned
  variable count. The ratio is the wasted decision work; if the median
  component is already most of the session, skip this item.
- *Sketch:* the solver computes the component from the query literal (a
  breadth-first walk over the watches of unassigned literals) and
  `_pick_branch` decides only inside it, stopping when the component is
  assigned and propagation is at a fixpoint. The rest of the session is
  checked *once* per assumption set (is `A ∧ rest` satisfiable?), a normal
  solve whose model is stored as a witness (1.1) and reused for every later
  query on that session.
- *Correctness:* a factorization. Clauses outside the component share no
  unassigned variable with it, so `SAT(A ∧ ¬P ∧ session)` equals
  `SAT(component part) ∧ SAT(rest)`; `SAT(rest)` does not depend on `P`,
  and is what the once-per-assumption-set check establishes (if it is
  unsatisfiable the assumptions are inconsistent, already an error path).
  Unsatisfiability of the component part is unsatisfiability of the whole.
  Theories: the theory confirms the partial assignment on every propagation
  already, but the component walk must treat theory-linked atoms as
  connected (LRA atoms sharing a term, EUF atoms sharing a function
  symbol). That is the one place to get wrong; the fuzz gets a theory-mode
  variant for it.
- *Decision:* keep at 5% or more, and, the real prize, if it lets the
  cone-search threshold and rebuild path (`Engine.ask`, `cone_search`) be
  deleted with no regression. Then 2.2 is moot.

### 1.3 Phase heuristic (last, measure only)

- *Measure:* after 1.1 and 1.2, decisions per search, and how many
  decisions on relation atoms triggered a theory check that failed.
- *Sketch:* keep the negative default and phase saving; try (a) relation
  atoms decided last, (b) for a fresh variable, the phase that satisfies
  more currently unsatisfied watched clauses.
- *Decision:* keep at 5% or more. Probably a no.

## 5. Phase 2: stop rebuilding what every session shares

### 2.1 Where the 2,664 sessions come from (measurement only, from 0.3)

Split them into cone rebuilds (757; gone if 1.2 works), first sight of an
assumption set, and evictions from the 16-slot LRU of a set seen before.
Count the distinct assumption sets in the stream. If evictions dominate,
re-test `keep_sessions` at 32 and 64 *after* 1.2: the earlier finding that
larger LRUs were slower was made while search cost grew with pollution.

### 2.2 Base-session clone (only if cone rebuilds survive 1.2)

- *Bound:* the re-grounding share of rebuilt sessions (about 0.4 of 2.1 ms
  per cone search in the last round, about 7% then).
- *Sketch:* `Solver.clone()` at decision level 0: clauses copied, watches
  remapped, trail, values, reasons, activities and heap copied, each
  theory cloned and re-attached in order; the engine copies `VarTable`, the
  `Session` dicts and the adapters' state. The engine agent's report from
  the last round spells out the fields. Mechanical, but it touches every
  theory.

### 2.3 Rules as a propagator (the structural fix for the 25%)

- *Measure:* how much of `add_pattern`, `_compile_patterns` and
  `_emit_pattern` time is the unary-predicate implication rules (binary and
  Horn clauses: `positive → real`, `zero → ¬nonzero`, …) against the
  structural templates (`Q.positive(a*b)` from the signs of `a` and `b`).
  Only the first kind is a natural propagator.
- *Sketch:* a theory hook that, when a predicate literal of node `n` is
  assigned, propagates the implied predicate literals of `n` with a fixed
  reason clause, so the rule block is never materialized per node.
  Structural templates stay as clauses. SymPy PR #27835 does this for its
  whole rule set (its "FC theory" inside `dpll2`); here it is a hybrid.
- *Correctness:* the propagator must give the same reasons a clause would,
  so conflict analysis is unchanged. The fuzz gets a mode that runs the
  same problems with rules as clauses and as a propagator and compares
  `implied` and `entails`.
- *Decision:* implement only if the unary-rule share is 10% or more; it is
  the largest change in this plan.

### 2.4 Atomic fast path

- *Measure:* count queries whose proposition is an atom, or its negation,
  literally present in the assumptions or fixed at root in the fact cache.
- *Sketch:* answer in `sympy_api.ask` before any session is touched. Ten
  lines.
- *Decision:* keep at 3% or more.

## 6. Phase 3: engine-side leftovers from the last round

### 3.1 The roughly 6,200 `implied` misses

The solver agent's split: about 1,750 from root units fed into a live
contextual session (cached facts written back by `Session.writeback()` in
`query_literal`, which drops the held assumption levels), 1,646 from theory
sessions, which never hold levels, the rest first calls and changed sets.

- *Measure:* confirm the split on the 0.3 log after phase 1; 1.2 changes
  what a session looks like.
- *Root units:* first try batching the writeback (at session creation, or
  after the query rather than before it). The alternative is to let
  `_attach_held` accept a root unit consistent with the held trail by
  inserting it at the root position and keeping the held levels, which is
  only valid if the unit implies nothing new at those levels; check, else
  fall back to re-propagating.
- *Theory sessions:* find out what actually breaks when levels are held
  with a theory attached. LRA already backtracks within a search, so
  holding level *k* between calls may only need the theory's backtrack
  invoked lazily at the next call instead of eagerly at the end of the
  previous one. The theory harness in the fuzz decides.

### 3.2 A version counter on `Extensions`

Bump it on every registration; the answer memo then compares one integer
instead of snapshotting the handler dict on every call. Small and clean; do
it regardless of the measurement.

### 3.3 Memoize `clauses_for` per node and `to_formula`

About 1.5% each by profile. Do them together; keep if the pair shows 3% or
more.

## 7. Order, dependencies, staffing

```
Phase 0 (both gates, the log) --> 1.1 witness reuse --> 1.2 component search --> 1.3 phase
                              \-> 2.4 fast path, 3.2, 3.3 (independent, cheap)
1.2 result --> 2.1 session census --> 2.2 clone (only if rebuilds remain)
                                  \-> keep_sessions retest
2.3 propagator: after its measurement; independent of the rest; largest single item
3.1 after 1.2 (it changes the miss profile)
```

Two agents, disjoint files, one local and one on the Pi, interleaved A/B
against an untouched `main`, every command capped at 270 s:

- **Solver agent:** 0.1, then 1.1, 1.2, 1.3, then the theory-hold half of
  3.1. Owns `solver.py` and the new test.
- **Engine agent:** 0.2, 0.3, then 2.4, 3.2, 3.3, 2.1, the writeback half of
  3.1, then the 2.3 measurement and, if it clears 10%, the propagator. Owns
  `engine.py`, `sympy_api.py`, `extensions.py`, the adapters and `tools/`.

The one cross-cutting piece is the engine glue of 1.2 (passing the query
variable; the theory-connectivity rule for the component walk). The solver
agent specifies it, the engine agent wires it in.

## 8. Expected outcome

If 1.1 and 1.2 pay as bounded: the stream from 4.2 s to roughly 2 to 2.5 s,
the cone-search threshold deleted, and per-query cost decoupled from
session pollution, which matters more for real workloads than the battery
number. 2.3 is the only item with a shot at another 25% on top, at the cost
of a real design change. Beyond that the remaining levers are outside this
plan: a compiled core for the solver's hot loops, and asking fewer
questions on the refine side, which is now 11 of the battery's 15 s.
