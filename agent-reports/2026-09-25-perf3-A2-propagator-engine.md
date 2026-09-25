# Agent report: perf round 3, item A2, the rule-block propagator, engine side

- **Date:** 2026-09-25
- **Status:** prepared, waiting for A1. The edit is an untracked patch
  `.a2.patch` in the engine worktree (`/home/tilo/satassume/.worktrees/engine`),
  against `9e8c3eb`, written for the API in the solver agent's work in
  progress (`set_rule_block(block, nvars=None)`, `register_block(base) ->
  bool`), which matches the design. Not synced, not A/B'd. Adapt to the
  API A1's report publishes, then sync, gate and commit.
- **Scope:** `satassume/engine.py` (two call sites); nothing else changes
- **Read this if:** you land A2, review it, or read solver clause counts

## The edit (`.a2.patch`)

1. `Session.__init__`, right after `self.solver = Solver()`:
   `self.solver.set_rule_block(RULE_INTERNAL, NPRED)`.
2. `Session.node()`, step 2: replace
   `self.solver.add_pattern(RULE_INTERNAL, b, NPRED); self.nclauses += len(RULE_INTERNAL)`
   by `self.solver.register_block(b)`. The `else` branch (complete
   constants: `ensure_vars(b + NPRED - 1)`, no block) stays. The return
   value is ignored, as `add_pattern`'s is today: a False means the solver
   is UNSAT at root (`_ok` False), and the next `query_literal` raises
   `InconsistentAssumptions` from `solver.propagate()` exactly as now.

`RULE_INTERNAL` is the only rule-block call site in `satassume/`
(`grep add_pattern`): nothing else instantiates the block, so after the
edit no session holds a rule clause.

## What else reads the block

- **`compile.py`, templates, `rules.py`:** unchanged. `compile.py` never
  mentions the rule base; `_emit_pattern` emits templates only.
- **`Session.nclauses`:** statistics only, read by nothing (`grep`); it
  simply stops counting the 79 per node.
- **`Solver.stats()["clauses"]`** (= `len(solver._clauses)`) drops by
  79 per node. Readers: `tests/test_solver_incremental.py:220` and
  `tests/test_solver.py:145` (solver-owned; they read their own solvers,
  not engine sessions, so unaffected unless A1 changes them);
  `agent-reports/scripts/clone_bound.py` (reports clause counts per base
  session: the numbers in the 2.2 report would shrink, the script still
  runs), `witness_bound.py` (uses `len(_clauses)` as an index into the
  clause list, still consistent), `rule_propagation_share.py` (tags
  `add_pattern(RULE_INTERNAL)` calls; after A2 it sees none, by design).
  `tools/query_log.py`, `refine_replay.py`, `gate2.py`, `ab.py` read
  `vars`, the root trail and the solve counters only: unchanged.
  Engine tests read no clause counts (`grep` over `tests/`).
- **Fact cache, `writeback()`, `root_trail()`, `value()`:** an
  implication the propagator makes at level 0 is an ordinary root trail
  entry, so `root_trail()` (the trail up to the first level) and
  `writeback()` (the trail from `read_pos`) see it, and `value()` reads
  `_val`/`_level` as for any literal. The fixpoint of unit propagation is
  unique, so the set of root facts written to the cache is the same; only
  the order within the trail can differ, and `writeback` does not depend
  on it. Timing is also unchanged: the engine writes back only after
  `solver.propagate()` in `query_literal`, and both the clause path and the
  propagator derive root facts in `_propagate`.
- **Cached facts (step 3 of `node()`):** still unit clauses emitted after
  the block is registered; they land on the trail and the hook propagates
  them through the block.

## Measured: blocks registered over assigned variables

The design's precondition for `register_block` ("every variable of the
block is unassigned, true at the only call site") does **not** hold on the
stream. `agent-reports/scripts/block_precondition.py` (Pi, cold pass,
answers match) classifies the 8,260 rule blocks instantiated:

| block variables at instantiation | blocks | share |
|---|---:|---:|
| all unassigned | 6,645 | 80.4% |
| some assigned, all at root | 1,612 | 19.5% |
| some assigned at a held level | 3 | 0.0% |

(1,483 of the 1,615 with one assigned variable, 84 with two, 48 with
three.) A node's block is allocated by `VarTable.node_base` when a
parent's template first mentions it, and the parent's clauses (and the
propagation of a query in between) can fix one of its predicates before
the node itself is visited, typically a deferred node visited by
`escalate()` or a node of a later query in a reused session.

The solver agent's work in progress already handles this inside
`register_block` (it evaluates the block once when a variable is
assigned, dropping held levels if one is assigned above root), so the
engine calls `register_block` unconditionally and needs no `add_pattern`
fallback. If A1 ships a strict precondition instead, the engine must fall
back to `add_pattern` for a fifth of the blocks, which costs about a fifth
of the gain; the A1 fuzz should have operations that register a block over
variables assigned at root and at a held level.

## For A1: the per-session cost of `set_rule_block`

`Session.__init__` runs for every session, 1,597 on the stream (cone
rebuilds, context-free and first-sight sessions included). The work in
progress builds the tables in every call: timed locally on the solver
worktree's current `solver.py`, `Solver()` is 2 us and `set_rule_block`
adds **74 us**. At about 1,600 sessions that is about 120 ms, **about 3%
of the cold pass**, spent rebuilding identical tables. The tables depend
only on the block, so A1 should memoize them per block (module-level, keyed
by the block object's identity or by the tuple) and `set_rule_block` then
only binds `self._rb = cached`; the engine passes the same
`RULE_INTERNAL` object every time. If A1 does not, the engine can keep one
prototype solver's tables and assign them, but that reaches into private
attributes; the memo belongs in the solver.

## Plan once A1 is on `main`

1. Rebase `perf3-engine`, apply `.a2.patch` adapted to the published API.
2. Pi: suite, `tools/gate2.py`, `tools/ab.py --rounds 2` against
   `/work/src/perf-ref`; re-run `block_precondition.py`-style counts only if
   the answers differ.
3. Also run `tools/refine_replay.py --log` once and check the 0.3 log's
   cross-check totals (memo 5,971, searches 3,192, escalations 1,792, cone
   757; sessions 1,597) against `Engine.stats`: the propagator may change
   models but not which path a query takes (paths depend on propagation
   results, which are the same fixpoint).
4. One commit, message with the A/B and gate2 lines; this report updated
   with Measurement/A/B/Tests/Decision.

## Risks for review

- The engine ignores `register_block`'s return value, as it ignores
  `add_pattern`'s; relies on `_ok` being False after a False return.
- A session with no nodes still pays `set_rule_block` (see above).
