# Agent report: perf round 3, item A2, the rule-block propagator, engine side

- **Date:** 2026-09-25
- **Status:** implemented and measured on the Pi; **decision is the
  orchestrator's** (A2 under 5% would revert A1 too). Commit
  `engine: install the rule block as a propagator per session (A2)` on
  `perf3-engine`, on top of A1 (`0b43aac` cherry-picked) on `main` at
  `8166d8f`. A2's own contribution: **-8.3% and -7.1%** (`ab.py --rounds 3`
  against a checkout of `8166d8f`); against the round's reference
  `895a6c2`: -14.5% and -14.1%. Every answer identical on both gates; the
  per-query log differs only in 25 solves' decision counts.
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
  `agent-reports/2026-09-perf-rounds/scripts/clone_bound.py` (reports clause counts per base
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
stream. `agent-reports/2026-09-perf-rounds/scripts/block_precondition.py` (Pi, cold pass,
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

## Result (A1 `0b43aac` + this commit, Pi)

The edit is `.a2.patch` as prepared, unchanged: A1's API matched it
(`set_rule_block(RULE_INTERNAL, NPRED)` in `Session.__init__`, tables
cached per block object; `register_block(b)` for `add_pattern(RULE_INTERNAL,
b, NPRED)` one for one; `ensure_vars` branch kept; `nclauses +=` dropped).

**A/B, `tools/ab.py --rounds 3`** (interleaved, cold, fresh process per
run; every run's answers match the recording):

| reference | run | ref rounds | cand rounds | best-of-3 | change |
|---|---|---|---|---|---:|
| `895a6c2` (`perf-ref`) | 1 | 3.652 / 3.617 / 3.649 | 3.092 / 3.105 / 3.118 | 3.617 → 3.092 | **-14.5%** |
| `895a6c2` (`perf-ref`) | 2 | 3.650 / 3.618 / 3.621 | 3.153 / 3.107 / 3.114 | 3.618 → 3.107 | **-14.1%** |
| `main` `8166d8f` (A2's own) | 1 | 3.423 / 3.387 / 3.379 | 3.125 / 3.110 / 3.098 | 3.379 → 3.098 | **-8.3%** |
| `main` `8166d8f` (A2's own) | 2 | 3.366 / 3.378 / 3.359 | 3.137 / 3.140 / 3.119 | 3.359 → 3.119 | **-7.1%** |

(The `8166d8f` reference was a temporary clone on the Pi, removed after.)
Every one of the 12 candidate rounds is below every one of the 12 `main`
rounds; the spread within a side is about 1%.

    tools/gate2.py: gate2: 2863 records (2588 in scope); changed 0 (0 in scope); answers match; replay 1.81s (ask 0.93s)

**Suite (Pi):** `2 failed, 1693 passed, 1 skipped, 4 xfailed, 1 xpassed`;
the 2 failures are the known `test_shared_facts` pair (main at `8166d8f`:
1670 passed; the difference is A1's new tests).

**Per-query log diff** (`tools/refine_replay.py --log` on `8166d8f` and on
this commit, compared record by record over 13,877 queries):

- identical in every record: `path`, `outcome`, `session_new`, `vars`,
  `root_len`, `via`, `nested`, `built`, `session_error`, `evict_reason`;
  1,597 sessions built and 1,534 answering sessions on both sides;
- solves: 6,384 on both sides, same `target`, `result`, `role`, `nvars`,
  `nassum` in every one; **25 solves differ in `decisions`** (81,320 →
  81,293 in total) and **1 in `conflicts`** (462 → 463). That is the
  expected kind of difference: the propagator puts the same fixpoint on the
  trail in a different order, so search starts from a different trail and
  can pick different decisions; `vars` and `root_len` unchanged confirm
  the variable layout and the root fixpoint are the same.
- logged pass 3,438 ms → 3,202 ms summed.

**My read (not a decision):** A2's own gain is 7.1 to 8.3% on the Pi,
above the 5% line in both runs by at least 2 points, with the two runs
consistent and no overlap between the sides. That is well under the
design's 18 to 21% estimate, which was made before B2a (B2a took 7 to 8%
of the pass, partly the same GC and allocation work) and on the local
machine; locally the solver agent saw 2.8 to 6.1%.

## Plan once A1 is on `main` (as it was written before the result)

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
