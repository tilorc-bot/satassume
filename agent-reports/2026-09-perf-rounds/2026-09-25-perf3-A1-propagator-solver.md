# Agent report: perf3 A1, the rule block as a propagator (solver side)

- **Date:** 2026-09-25
- **Status:** implemented on `perf3-solver`, one commit; landable alone
  (no engine change; with no `set_rule_block` call the solver behaves as
  before). **Finding for the A2 decision: the gain with the engine using
  the propagator is about 4.5% locally, not the design's 18 to 21%.**
- **Scope:** `satassume/solver.py`, `tests/test_solver.py`,
  `tests/test_solver_incremental.py`, `agent-reports/2026-09-perf-rounds/scripts/propagator_census.py`
- **Read this if:** you review A1, you implement A2 (API at the end), or
  you decide whether A2 is kept

## Measurement

Design (`2026-09-25-perf2-2.3-propagator-design.md`): insertion of the
block 10.0% of the pass plus 18.9% of propagation "attributable" to rule
clauses, realistic gain 18 to 21%.

What the propagator does on the replay, with A2 simulated (the engine's
`add_pattern(RULE_INTERNAL, b, NPRED)` redirected to `register_block(b)`;
`agent-reports/2026-09-perf-rounds/scripts/propagator_census.py`, instrumented, local):

| | clauses (today) | propagator |
|---|---:|---:|
| block insertion | 354 ms | 127 ms (7 ms `_rb_settle`, the rest `_grow` of the 33 new variables, paid by both) |
| `_propagate` (inner) | 810 ms | 1,026 ms |
| processed literals | 900,278 | 900,278 (829,577 in a block) |
| rule work per pass | 1,630,538 watch visits | 1,205,319 binary implications visited + 994,210 longer clauses evaluated |

- The insertion saving is real (about 230 ms, 6 to 7%).
- Propagation does not get cheaper; it gets about 200 ms slower. The
  "18.9% attributable" share was the rule clauses' share of watch-list
  visits. It was never a cost the propagator removes: the propagator
  processes the same 829k block literals, and in CPython the fixed cost
  per processed literal dominates (about 1 µs per literal in both
  versions). A binary implication costs about what a binary watch visit
  costs. The stateless occurrence scan evaluates every longer clause
  containing the falsified literal (994k evaluations), where two watched
  literals visit only the clauses watching it, and those watches drift
  away from false literals.
- Tried and dropped, all measured: an int-only binary table (antecedent
  encoded in the reason) and unrolled ternary tables are kept; they bring
  `_propagate` from +23% to about the same. No measurable change from:
  a combined per-literal table with guards on empty lists, reason codes
  computed only on assignment, a bound `trail.append`, and a hybrid with
  the 19 longer rules left as clauses (3.51 to 3.53 s against 3.36 to
  3.52 s for the full propagator).
- 1,615 of 8,260 blocks (19.5%) are registered over variables that already
  have values, 1,612 at root and 3 at a held level. The design's
  precondition ("no variable assigned") does not hold, so
  `register_block` handles assigned variables itself (see Change); with a
  strict precondition a fifth of the blocks would fall back to clauses.

## Change

- `set_rule_block(block, nvars=None)`: installs shared tables built once
  per block object (module cache `_rule_tables`, keyed on the block
  object; per-session cost a dict lookup). Per literal `rel` of the block
  that has just become true: `imp[rel]`, the literals implied by binary
  rules; `occ3[rel]`, `(idx, a, b)` for ternary rules containing `rel^1`;
  `occn[rel]`, `(idx, others)` for longer ones.
- `register_block(base)`: records `_rb_base[v] = base` for the block's
  variables and bumps `_stamp`, invalidates the witness. If some block
  variable is already assigned, it drops held levels when one is assigned
  above root, then `_rb_settle` finds the clauses unit or false at root
  from the tables of the block's true literals (complete: such a clause
  has a false literal whose negation is true). Units become root facts
  and are propagated at once; a false clause makes the problem UNSAT
  (returns False). Held levels are dropped only if the block adds a root
  fact, as a unit clause insertion does.
- The hook in `_propagate`: one `rb_base[p >> 1]` lookup per processed
  literal. Then the binary table, the unrolled ternary table and the
  generic loop for longer rules; implied literals are enqueued at the
  current level with an int reason. A rule conflict returns the
  materialized clause as `confl`, exactly like a clause conflict (the
  watch scan of that literal is skipped, as for a clause conflict).
- Reasons: `base << shift | x`, with `x < ncl` a clause index or
  `x = ncl + rel` for a binary rule fired by the true literal `rel`.
  `_rb_reason(v, r)` materializes the clause with `v`'s literal first. It
  is called at the only three places that read a reason: `_analyze` (the
  resolution loop, after the UIP test, so the UIP's reason is never
  built), `_analyze`'s minimization, and `_analyze_final`.
- No-block path: `_propagate` starts with `if not self._rb_n: return
  self._propagate_clauses()`, and `_propagate_clauses` is today's loop
  unchanged. A single loop with the per-literal check cost +1.2% (3
  rounds, twice), over the 1% bound. The watch loop now exists twice;
  change both.
- `_grow` extends `_rb_base`. `_solve`'s learnt-clause budget counts the
  virtual block clauses (`_rb_nclauses`), so `_reduce_db` fires as it
  would with the clauses. `stats()` gains `rule_blocks`.

Design claims checked against the code:

- **Backtracking:** `_backtrack` unassigns trail entries, and the hook
  keeps no state, so nothing changes. Confirmed.
- **Held levels:** registering over unassigned variables keeps the held
  trail a fixpoint (no block literal is assigned, so no rule can fire).
  With assigned variables the claim fails and `register_block` handles it
  (above). Enqueuing implications at a held level instead of dropping the
  levels would have to follow `_attach_held`'s cases: a unit below the top
  level, and a clause satisfied only above its false literals, would be
  lost on a later backjump because the hook never revisits processed
  literals. This happens for 3 blocks on the replay, so dropping is used.
- **`_attach_held`:** unchanged. A clause it propagates at the top level
  goes through `_propagate`, so through the hook. Confirmed.
- **Propagation cache:** the key `(assumptions, _stamp, root length)`.
  `register_block` bumps `_stamp`, and root facts from `_rb_settle` grow
  the root trail. Confirmed.
- **Theories:** hook implications are trail entries, reported by
  `_theory_sync`'s cursor. `_rb_settle` propagates root units with
  `_propagate` only, as `_add_lits` does for a unit clause; the theories
  hear of them at the next `propagate` or search. Checked by the fuzz's
  theory mode with a `Recorder` and `check_protocol`.
- **`_reduce_db`:** the lock test `reason[v] is c` never matches an int.
  **`_is_learnt`:** never sees an int. Confirmed.

## A/B

No-block overhead (the engine does not call the API yet), `tools/ab.py
.worktrees/ref . --rounds 2` on the final code:

    best-of-2: ref 3.481s  cand 3.517s  change +1.0% (slower); answers match

Earlier runs of the same no-block path (3 rounds): +0.2%, +0.8%. The
remaining cost is one extra method call per `_propagate` call on the
no-block path; within noise. gate2:

    gate2: 2863 records (2588 in scope); changed 0 (0 in scope); answers match; replay 1.97s (ask 1.03s)

A2 preview, for the decision (a scratch copy of this tree with the two
engine call sites of the design section 3 changed; nothing committed):

    best-of-3: ref 3.544s  cand 3.329s  change -6.1% (faster); answers match
    best-of-3: ref 3.459s  cand 3.346s  change -3.3% (faster); answers match
    best-of-3: ref 3.471s  cand 3.374s  change -2.8% (faster); answers match
    best-of-6: ref 3.479s  cand 3.320s  change -4.6% (faster); answers match   (per round 3.8 to 5.7%)
    gate2 (A2 preview): changed 0 (0 in scope); answers match

The full suite with the propagator active (A2 preview): 1692 passed (the
suite plus a check that the patched engine was imported), the same 2
known failures.

## Tests

- Fuzz, `tests/test_solver_incremental.py`, rule-block mode: the same
  harness and every existing check (implied, entails, solve, model
  validity against every clause, conflict cores unsat, value and
  root_trail). The oracle gets each block as clauses; the live solver
  runs it as the propagator (even seeds) or mixes propagator and
  `add_pattern` (odd seeds). The block is `RULE_INTERNAL` or a small
  random one. A `register_block` operation registers blocks on fresh
  variables, sometimes after constraining them: a root unit; a link
  implied at the top held level (a held-level value); or root values
  with levels held again by an `implied` call. It sometimes registers
  while levels are held, then links the block to the rest (a burst of
  3-clauses in hard seeds). Theory variant: a `ForbidTheory` (eager, lazy
  or propagating) with atoms on the first block's variables, the live
  copy in a `Recorder` checked by `check_protocol`. A mutation test (the
  propagator forgets a block clause) is caught. A coverage test requires
  propagator reasons read, hard conflicts, and blocks registered while
  held, over root values while held, and over held-level values.
- 4,000 seeds by hand, 0 mismatches, each mode (runs of 2,000 seeds,
  under 110 s each):
  - block mode: 27,046 conflicts (24,896 in hard seeds), 28,866
    propagator reasons read in analysis, 9,231 blocks registered (2,050
    over assigned variables, 713 over held-level values, 508 over root
    values while held, 3,487 while held), 52 reductions, 5,060 restarts;
  - theory mode: 23,632 conflicts (20,320 hard), 26,084 propagator
    reasons read, 8,699 blocks;
  - plain mode (unchanged path): 93,181 conflicts.
- 500 seeds per variant in CI (default `SOLVER_FUZZ_SEEDS`): the file
  goes from about 15 s to about 40 s.
- A harness fix found by the theory mode: `add_clause` of a clause that
  becomes unit at root is propagated without the theories, so the
  harness no longer claims root completeness after it when a theory is
  attached (the oracle's `propagate()` includes the theory).
- Direct tests, `tests/test_solver.py` (9):
  - `RULE_INTERNAL` block against clauses for every predicate literal of
    two linked nodes;
  - a conflict found inside the propagator;
  - a conflict whose analysis resolves through two propagator reasons
    (counted);
  - a final conflict (`_analyze_final`) through propagator reasons;
  - random blocks against brute force (solve, models, cores);
  - held levels over registered blocks;
  - `register_block` while levels are held: over unassigned variables
    (levels kept, later propagate into the block), over a held-level
    value (dropped), over root values implying a root fact (dropped);
  - a conflict at registration;
  - API errors and shared tables.
- Full suite: `2 failed, 1691 passed, 1 skipped, 4 xfailed, 1 xpassed`
  (baseline 1668 plus 23 new; the 2 known `test_shared_facts` failures).

`agent-reports/2026-09-perf-rounds/scripts/rule_propagation_share.py` still runs unchanged.
On the A2 preview it gives the after picture:
- no rule clauses inserted;
- `_propagate` 1,022 ms against 830 ms;
- the 618,332 propagator implications appear as "untagged" reasons (int
  reasons);
- watch visits: templates 75%, other 22%.

## Decision

A1 kept as a landable commit: answers identical on both gates, no-block
path within noise, suite plus tests green. The orchestrator must decide
on A2 with the number above. Locally the propagator is worth about 4.5%
(best-of-6 -4.6%, runs from -2.8% to -6.1%), at the plan's 5%
threshold. The plan's rule was "if A2 shows under 5%, revert A1 too".
The Pi measurement (the engine agent's) decides. Where the rest of the
old estimate went: propagation is not cheaper in CPython (see
Measurement). For item C: `_grow` costs 163 ms per pass (15,039 calls:
list allocations for 33 variables per node, 66 of them watch lists) and
is now the largest part of block registration.

## Risks for review

- The watch-scan loop exists twice (`_propagate`, `_propagate_clauses`);
  a change to one must go to both.
- Trail order differs from the clause version (block implications come
  before the watch scan of the same literal). The fixpoint and root facts
  are the same, but the order of `root_trail()` and of `assert_lit` calls
  within a level changes. The engine's `read_pos` cursor only relies on
  appending. Both gates are identical.
- `register_block` over variables assigned at a held level drops the
  held levels (3 per pass). Correct, and slightly more eager than
  `add_pattern`'s slow path, which keeps them in some of those cases.
- `_RULE_TABLES` holds a reference to each block object (cleared at 64
  entries), so ids are not reused. Callers pass the module-level
  `RULE_INTERNAL`.
- `Solver.stats()["clauses"]` no longer counts the block once the engine
  registers it; `stats()["rule_blocks"]` counts blocks.

## API for A2 (engine agent)

    Solver.set_rule_block(block, nvars=None) -> None
    Solver.register_block(base: int) -> bool

- `block`: clauses in internal literals relative to variable 0, exactly
  what `add_pattern` takes: `RULE_INTERNAL` (tuple of tuples, each
  literal `2*i + neg` for predicate index `i`). `nvars`: variables per
  block, pass `NPRED`. Tables are cached per block object, so call it
  once per `Solver` (in `Session.__init__` right after `Solver()`; about
  1 µs). A second call with the same block is a no-op; a different block
  raises ValueError.
- `register_block(b)` replaces `add_pattern(RULE_INTERNAL, b, NPRED)` one
  for one, at the same point in `Session.node()`. It is valid at any time
  the `add_*` methods are:
  - before or after `add_clause`/`add_clauses`/`add_internal` on the
    block's variables, including template clauses and cached facts
    already there (units on its variables before or after: both fine);
  - while assumption levels are held;
  - with the block's variables unassigned, assigned at root, or assigned
    at a held level.

  It grows the variables as `add_pattern` does, so the `else` branch
  (`ensure_vars` for complete constants) stays as is. Returns False iff
  the problem became UNSAT at root (as `add_pattern`; the engine ignores
  that return today). Each variable may belong to one block only; a
  second `register_block` on overlapping variables raises ValueError. So
  a node must not be registered twice, and must not also get
  `add_pattern(RULE_INTERNAL, ...)` (that is allowed but redundant).
- `self.nclauses += len(RULE_INTERNAL)` goes away (statistics only).
- `stats()`: `clauses` counts stored problem clauses only (the block no
  longer); `rule_blocks` is new (registered blocks). `learnts`,
  `conflicts`, `decisions`, `propagations` keep their meaning.
  `propagations` still counts processed literals (block implications
  included).
- Nothing else in the engine, `compile.py` or `rules.py` changes; the
  measured A2 preview used exactly these two edits.
