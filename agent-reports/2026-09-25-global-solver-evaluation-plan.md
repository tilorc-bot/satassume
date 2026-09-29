# Agent report: plan to evaluate one persistent solver per engine (selector literals, scoped search, client-held contexts)

- **Date:** 2026-09-25
- **Status:** plan only. Nothing implemented. Written for a fresh agent that
  starts from `main` with no other context; everything it needs is
  referenced here. Baseline: `main` at the end of performance round 3
  (report `2026-09-25-perf-round-3-report.md`; issues #9 and #11).
- **Scope:** `satassume/engine.py`, `solver.py`, `relations.py`, the
  theory adapters, `sympy_api.py`; a new client API; on the
  `refine-monorepo` branch, `satrefine/backend.py`
- **Read this if:** you are the agent evaluating this idea, or you decide
  whether to fund it

## 0. Read first

1. `README.md` and `PLAN.md` (what the engine is).
2. `agent-reports/2026-09-25-perf-round-2-report.md` and
   `2026-09-25-perf-round-3-report.md`: what was tried, what was measured,
   what was dropped. Do not re-measure dropped items.
3. `agent-reports/2026-09-perf-rounds/2026-09-25-perf3-B5-profile-after-A2.md`: where the time
   goes now, by area.
4. `agent-reports/2026-09-perf-rounds/2026-09-25-perf2-2.1-session-census.md` (sessions built,
   by reason) and `2026-09-perf-rounds/2026-09-25-perf3-B1-polluted-first-attempt.md` (why
   cone rebuilds exist and why skipping them changes answers).
5. `agent-reports/2026-09-perf-rounds/2026-09-25-perf2-1.2-component-search.md`: the one
   earlier attempt to search less than the whole session, and why it
   measured under 1% on sessions of about 70 variables.
6. Tooling: `tools/ab.py` (interleaved A/B), `tools/gate2.py` (second
   query distribution), `tools/refine_replay.py --log` and
   `tools/query_log.py` (per-query log), `tests/test_solver_incremental.py`
   (the solver differential fuzz; extend it, do not fork it).
7. Environment: local venv and SymPy pin, the Pi container, the stream at
   `~/.cache/satassume/stream.pkl`, in the memory notes and in the
   "Environment" section of the round 3 plan
   (`2026-09-perf-rounds/2026-09-25-perf-round-3-plan.md`). Two machines, one measuring
   workload each, every command under 270 s.

## 1. The idea

Today `Engine.ask(prop, assumptions)` (`engine.py:720`) answers from a memo
or builds/reuses a **session per assumption set** (`_context_session`,
`engine.py:642`; LRU of 16; `_fresh_session` at `:631`): a fresh `Solver`,
the assumptions grounded into it, every node the query touches grounded
again (`Session.node`, `:160`, templates plus the rule block), theories
attached lazily by `Relations`, facts copied in from the fact cache and
written back after (`writeback`, `:430`). A session that has accumulated
nodes from other queries is "polluted"; a query needing search there gets
a **cone session** rebuilt over its own cone (see `ask`), which replaces
the polluted one. Per pass over the stream: about 1,600 sessions built,
757 of them cone rebuilds; the cone path is 23% of the pass and session
construction plus assumption re-grounding another 10 to 15%. Every attempt
to make one piece of this cheaper (clone 1.6%, larger LRU 0.7%, skipping
the wasted first attempt 3.3%) measured under the 5% line, because the
machinery as a whole is the cost.

The alternative: **one persistent solver** (per engine, or per
client-held context) holding every node ever grounded, once. Each
assumption formula is grounded once under a fresh **selector literal**
(MiniSat-style activation literal); a query under set A is
`entails(lit, assumptions=[selectors of A])`. No session construction, no
re-grounding, no cone rebuild, no eviction. The fact cache *is* the
solver's root. The held-levels mechanism (round 1, `9e33d28`) already
makes consecutive queries under a shared prefix of selectors free.

Why it is not obviously a win: search cost grows with the number of nodes
in the session (round 1 measured 0.9 ms with one extra node, 6.3 ms
beyond 31) because CDCL assigns every variable before it declares a model,
and a persistent solver is maximally polluted. Round 2's component search
does not fix this (the component is most of a small session; it says
nothing about a session of 20,000 variables). Two mechanisms make the
design viable, and they are what this evaluation has to build and
measure:

- **Selector-guarded clauses and scoped termination.** Every clause that
  belongs to a case's nodes carries that case's selector as an extra
  literal (or the node's clauses are activated by a per-node selector that
  the case's selector implies). Clauses of inactive cases are satisfied
  by their false selector. The search terminates when **every active
  clause is satisfied**, not when every variable is assigned. Then nodes
  irrelevant to the query are never decided, and the persistent solver
  behaves like today's cone session without building it.
- **Theory atoms that stay inactive** until their selector is true, so
  LRA's tableau and EUF's congruence closure do not grow with everything
  ever seen (theory code is already 14.8% of the pass).

Two additions once that works:

- **Root-level work that amortizes.** In a persistent solver, anything
  derived at root is free forever: failed-literal probing at root, learnt
  unit clauses kept across queries, each node's rule closure computed once.
  This targets definite answers and reuse, **not** the `None` searches
  (3,130 of 3,192 searches on the stream end with both models found; no
  root fact changes an undetermined answer). Root facts must be
  assumption-free (declared symbol facts, templates, rules only), never
  derived under a selector; that is the invariant to check on every
  root-level addition.
- **A client-held context API.** Refine knows its structure (a case has
  base assumptions; handlers push hypotheses and discard them; the next
  case shares most of the base). `engine.context(base)` with `push(extra)`
  / `pop()` / `ask(prop)` lets the engine keep one selector set live per
  case and extend it by levels, instead of keying sessions on whole sets.

## 2. Acceptance rule (different from the rounds' rule)

The rounds required every answer identical. A persistent solver knows
more (it holds every case's relation atoms and facts), so it will answer
some `None` definitely. The rule for this evaluation:

1. No answer may **contradict** the current engine's: `True` vs `False`
   or vice versa is a bug, full stop.
2. The set of queries that raise `InconsistentAssumptions` must be
   identical (consistency of the assumption set is still checked: the
   selectors of A propagated together must not conflict; a conflict is
   the error).
3. Answers may become more definite (`None` → `True`/`False`). Count them,
   and verify a sample of at least 50 by hand or with SymPy's `ask`
   (`tools/refine_oracle.py` on the refine branch, or `tools/compare.py`).
4. The test suite: everything passes except tests that assert on session
   counts or cone-search policy, which are deleted with the mechanisms
   they test (list them in the report).
5. Speed: `tools/ab.py --rounds 3` against the baseline on the cold pass
   **and** on a second pass in the same process (`tools/refine_replay.py
   stream.pkl 2`), because a persistent solver's cost can grow with time;
   plus memory (`tracemalloc` peak) on both.
6. `tools/gate2.py` under the same rule (contradictions 0; more-definite
   counted).

## 3. Stages, each with a stop condition

### Stage 0: measurement from the stream and the log (about a day, no code)

Scripts under `agent-reports/scripts/` (a fresh directory; the rounds' scripts are archived under `agent-reports/2026-09-perf-rounds/scripts/`), report
`2026-09-25-global-solver-0-measurements.md`.

- How assumption sets relate between consecutive queries: identical,
  subset, superset, overlapping, disjoint; the number of distinct sets
  and distinct "base" sets (the intersection over a run of consecutive
  queries); the size of the deltas. This says how much a context API can
  reuse and how many selectors a case needs.
- Growth: replay the stream counting nodes ever grounded, variables,
  clauses and theory atoms as they would accumulate in one solver; the
  final size and the size at the median query.
- Pollution cost proxy on the current solver: replay with
  `Engine(keep_sessions=1, cone_search=False)` or with `cone_threshold`
  huge, so sessions accumulate nodes; measure decisions per search and
  ms per search against the session's variable count (the per-query log
  gives both). This is the cost the scoped termination must remove.
- Relevance: for each search, the number of *active* clauses (clauses of
  the query's assumption set and of nodes reachable from the query)
  against all clauses in a hypothetical persistent solver at that point.
  The ratio bounds what scoped termination saves.
- **Stop if:** the active-clause ratio at the median search is above
  about 0.5 (scoped termination would not help) *and* the growth makes
  the persistent solver larger than about 50 sessions' worth by mid-pass.
  Report and end.

### Stage 1: solver mechanisms (two to three days)

In `solver.py`, with the fuzz extended for each:

- **Selector-guarded clauses.** Either add the selector to each clause
  (simplest, correct, costs one literal per clause) or keep per-node
  activation. Decide from stage 0's counts. `entails`/`implied`/`solve`
  take selectors as assumptions; nothing else changes.
- **Scoped termination.** A count of unsatisfied *active* clauses
  maintained incrementally (a clause becomes satisfied when one of its
  literals is assigned true; inactive clauses count as satisfied), and
  `_search` returns SAT when the count reaches zero with propagation at
  fixpoint. `_pick_branch` picks only from variables of unsatisfied
  active clauses (a heap over those, or scan on demand; measure). The
  model is partial; `entails` must not read unassigned variables as
  false. Learnt clauses: analysis is unchanged; learnt clauses are always
  active.
- **Inactive theory atoms.** `register_atom` is deferred until the atom's
  selector is true (or the theory keeps the atom but ignores it while its
  selector is false; the interface in `theory.py` decides which is
  cheaper). `push_level`/`pop_level` must stay consistent.
- **Fuzz:** every mode of `tests/test_solver_incremental.py` plus a
  selector mode: random cases, each a set of clauses under a selector,
  queries under random selector subsets, compared against a fresh solver
  fed only the active clauses. Plain and with a theory. 4,000 seeds.
- **Stop if:** scoped search costs more than 10% over today's search on
  the current per-session workload (measure with `tools/ab.py` on the
  unchanged engine, which passes no selectors: the mechanism must be free
  when unused), or the fuzz finds a gap that needs a design change.

### Stage 2: the persistent engine (two to three days)

In `engine.py`, `relations.py`, the adapters, `sympy_api.py`:

- One `Session` per engine (or per context, stage 3). `VarTable`, node
  registry, fact cache and solver root merge. Assumption formulas are
  grounded once, memoized by formula, under a selector; an assumption
  *set* is the list of its formulas' selectors, sorted by first use so
  shared bases are prefixes (that is what makes held levels pay).
- Delete: the LRU (`keep_sessions`), `cone_search`/`cone_threshold`, the
  cone path in `ask`, `_fresh_session`, `writeback`, the failed-set memo
  of round 2 (`63504aa`; a set with an uninterpreted relation is then a
  selector whose grounding failed, remembered by the formula memo), and
  the tests that assert on them.
- Keep: the answer memo (still valid: keyed on set and registry version),
  the template/formula memos, `Extensions.version`.
- Consistency: before answering under a set, `implied(selectors)` must
  not conflict; conflict raises `InconsistentAssumptions`.
- Measure per the acceptance rule; the per-query log needs a new
  `session_new` value and loses the cone stages; keep the rest of the
  format so round 2's scripts still run.
- **Stop if:** the cold pass is slower than the baseline after a day of
  tuning, or the second pass is more than 20% slower than the first
  (unbounded growth), or memory exceeds about three times the baseline.

### Stage 2b: root-level work (one day, only if stage 2 is at or below baseline)

Separately measured, one commit each: (a) learnt units kept at root
forever; (b) failed-literal probing at root for variables of newly
grounded nodes, budgeted (probe only nodes touched by the last N queries);
(c) each node's rule closure computed once at grounding if the propagator
of round 3 (`b9f2151`, `747fb0e`) makes that cheap. Each must keep the
root assumption-free invariant; the fuzz gets a probe mode.

### Stage 3: the context API and refine (one to two days)

- `Engine.context(assumptions) -> Context` with `push(assumptions)`,
  `pop()`, `ask(prop)`, `close()`; the module-level `ask` becomes a
  one-shot context. Contexts share the persistent solver; a context's
  live selectors are the assumption levels held between its queries.
- On the `refine-monorepo` branch (which has not been merged with `main`
  since 2026-09-23; rebase or merge it first, expect conflicts in
  `tools/` and reports), `satrefine/backend.py`'s satassume and combined
  backends open one context per case and push/pop around hypotheses.
  Measure the full battery (`tools/refine_scoreboard.py`) before and
  after, and the number of engine queries (a context may also let refine
  ask fewer questions, which is the larger lever on the battery).

## 4. What "worth it" means

The prize is the session-construction and cone-path share (roughly 30 to
45% of the pass on `main`, see B5) minus the cost of scoped search and
inactive-atom bookkeeping, plus whatever refine gains from contexts. A
result of 20% or more on the cold pass with the acceptance rule met, and
no growth on the second pass, is a clear win. A result under 10% is not
worth the redesign; report it and stop. In between, the second-pass and
memory numbers decide, because a persistent solver's advantage should
grow with reuse, and if it does not, the design is wrong.

Expect the first working version of stage 2 to be *slower* than
baseline. Tune (selector ordering, heap scope, theory deferral) for a
day before judging; log every measurement in the stage report so the
tuning is visible.

## 5. Practicalities

- Work on a branch (`persistent-solver`), not straight to `main`; the
  acceptance rule differs from the rounds', so land only at the end with
  a review issue listing the answers that became definite.
- One agent for stages 0 and 1 (solver work needs the fuzz and the
  design in one head), the same or a second for stage 2; reviewers per
  stage. The user's rule for subagents at the time of writing: Opus 5.5
  only.
- Machines: solver fuzz and A/B locally; the engine measurements on the
  Pi; never both measuring on one machine.
- Reports per stage in `agent-reports/2026-09-25-global-solver-<stage>-*.md`
  as you go; the orchestrator's context fills, the reports survive.
