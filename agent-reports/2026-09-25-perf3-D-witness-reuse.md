# Agent report: perf3 D, witness reuse (round 2's 1.1, re-measured and implemented)

- **Date:** 2026-09-25
- **Status:** one commit (D'') on `perf3-solver`, directly on
  `747fb0e` (A2), after the report-only commit that drops C.
  - It carries the model slice from the dropped C (the ring stores the
    slice).
  - Revised after the Pi review (-5.6% and -5.2% there, rejected for
    the gap below): the theory gate counts `register_atom` calls instead
    of theory variables, and a propagation gap in `register_atom`
    exposed by the new fuzz case is fixed.
  - **-7.8%** against `747fb0e` (best of 3; witness reuse plus the
    slice), **-15.8%** against `.worktrees/ref`.
- **Scope:** `satassume/solver.py` (the model slice, `_solve`,
  `_ring_hit`, `_ring_blocks`, `register_block` records bases,
  `register_atom`/`_theory_sync`, `entails`), `satassume/theory.py` (one
  sentence),
  `tests/test_solver_incremental.py` (a witness operation and a mutation
  test), `tests/test_theory_hooks.py` (one assertion relaxed, see Risks)
- **Read this if:** you review D, or wonder why round 2's drop is
  reversed

## Measurement

`agent-reports/scripts/witness_bound.py` (unchanged) on `main` plus C,
local:
- 6,384 solves, 1.21 s inside `_solve`, 37.6% of the instrumented pass
  (3.23 s).
- Ring of 2: 1,360 hits (840 on the `not_p` solve, 520 on `p`), 0 on an
  unsat solve. It saves 0.203 s of solve time for 0.008 s of checking:
  **6.1% of the instrumented pass, about 6.6% of the uninstrumented
  2.97 s.**
- Ring 4 or 16: 6.4%.

Round 2 bounded the same saving (0.20 s) at 4.8% of a 4.22 s pass; the
pass is now 2.97 s.

## Change

- **Model slice** (from the dropped C): after a satisfiable search the
  model is kept as the C-level slice `val[2::2]`. The dict of `model()`
  (and `_model`, read by `tools/query_log.py`) is built on demand.
  `_mvals`, `_witness` and the ring entry are one list object that
  nothing mutates (comment at the assignment). Alone this was -2.1% in
  C's measurements.

- After every satisfiable search, `_solve` stores in a ring of the last
  2 models per solver:
  - the model (the C-level slice of C);
  - the number of problem clauses and registered rule blocks;
  - the root trail length;
  - the theory and atom counts;
  - the theory models.
- Before searching, `_ring_hit` tests the stored models, most recent
  first, against:
  - the call's assumption literals;
  - the root literals fixed since;
  - the problem clauses added since (a slice of `_clauses`);
  - the rule blocks registered since (their 79 clauses at each new base;
    after A2 blocks are not in `_clauses`);
  - with theories: the same number of theories and of `register_atom`
    calls. The first version compared the number of theory variables,
    which misses a variable registered with a second theory: the
    constraint is new, the count is not. The Pi review found this. The
    counter `_n_registered` is bumped by every registration.

  A literal of a variable the model does not know does not count as
  satisfied.
- A hit answers True with that model, padded with False for variables
  created since, and with its theory models. No search, no state change;
  held levels stay as they were. `stats()["witness_hits"]` counts hits.
- On the replay: 1,344 hits (bound 1,360), 12 ms of checking. A ring of
  4 is not faster (+0.4%).

Also fixed (exposed by the new fuzz case, older than D):
- `register_atom` on a variable already fixed at root and past the
  report cursor tells the theory at once. Before, a propagating theory
  was then never asked to `propagate()`: `_theory_sync` returned early
  when no trail entry was new, so `implied` could miss the theory's
  implication.
- A flag (`_tpending`) now makes the next sync ask.

Correctness:
- A stored model satisfied every clause, block and root literal of its
  time, and passed the theories' final check.
- The formula only grows: problem clauses and blocks are only added,
  root literals only fixed, and learnt and theory clauses are
  consequences. So a model that also satisfies everything added since is
  a model of the current formula; with the same theories and atoms it is
  theory-consistent as before.
- Theory lemmas are valid in the theory, so they hold in it.

## A/B

D'' against its parent `747fb0e` (witness reuse plus the slice), and
against the round's reference:

    best-of-3: ref 3.170s  cand 2.922s  change -7.8% (faster); answers match
    best-of-3: ref 3.471s  cand 2.921s  change -15.8% (faster); answers match   (.worktrees/ref)

Earlier measurements of the ring alone: -5.9% against C' (best of 3);
the Pi review against the first C, -5.6% and -5.2%. Against the first
C, locally:

    best-of-3: ref 2.976s  cand 2.809s  change -5.6% (faster); answers match
    best-of-4: ref 2.988s  cand 2.848s  change -4.7% (faster); answers match
    best-of-4: ref 3.007s  cand 2.813s  change -6.4% (faster); answers match   (per round 4.6 to 7.1%)

Without hits in theory sessions it would be -1.9%: most hits are in
sessions with LRA/EUF attached. gate2:

    gate2: 2863 records (2588 in scope); changed 0 (0 in scope); answers match; replay 1.82s (ask 0.82s)

## Tests

- New fuzz operation `solve_witness`: solve on assumptions read off one
  of the live solver's stored models, sometimes plus a random literal.
  Every `solve` (with a hit or not) has its model checked against every
  clause and its answer against the fresh oracle.
- New mutation test: a ring that skips the "added since" checks is caught
  within 60 seeds.
- Theory mode has a second theory with no initial atoms, and an
  operation `register_second` registers a variable of the first theory
  with it (the oracle replays those registrations). With the old
  `len(_tmap)` gate this fuzz fails at seed 96.
- Direct tests: the reviewer's case, and a theory that must propagate
  after a root-fixed variable is registered (fails without the
  `_tpending` fix).
- The coverage tests now require witness hits in plain and block mode.
- 4,000 seeds in each of plain, block and theory mode on top of C', 0
  mismatches:
  - plain: 8,865 hits, 4,292 by the witness operation, 93,467 conflicts;
  - block: 6,975 hits, 3,436, 27,750;
  - theory: 4,789 hits, 2,384, 20,668 conflicts, 2,541 second-theory
    registrations.
- Suite on D'': `2 failed, 1696 passed, 1 skipped, 4 xfailed, 1 xpassed`
  (the suite of `747fb0e` plus 3; the 2 known `test_shared_facts`
  failures). The float-assumption test was added after this run;
  `tests/test_solver.py` was re-run green (39 passed).
- gate2 on D'':
  `gate2: 2863 records (2588 in scope); changed 0 (0 in scope); answers match; replay 1.79s (ask 0.86s)`.
- The fuzz counts are the same on D'' as on D' (the dropped C's loops do
  not change search).

## Decision

Kept: -4.7% to -6.4%, above 5% on average (two of three runs). The
bound was 6.6%; part of the saving is lost because a skipped search no
longer leaves the held assumption levels that the next solve of the same
`entails` would continue from.

## Public API: float assumptions

With the model slice, `_witness_satisfies` indexes the witness list
with the assumption, where the old dict used `.get`. `entails` passed
its raw assumption list there, so `entails(x, [3.0])` could raise
`TypeError` once an earlier model existed. `entails` now converts its
assumptions with `int()`, as `_assume` does, so the behaviour is as
before. The guard costs nothing measurable (D'' without it against D'':
`+0.1%`, best of 3). There is a direct test.

## Risks for review

- **`tests/test_theory_hooks.py`**, which is not one of my files: its
  `test_root_facts_are_reported_once_without_levels` asserted that a
  repeated `solve` makes exactly one `check()` call. With the ring, that
  solve is answered by the first solve's model (checked under the same
  atoms) and makes no theory call. The assertion now accepts
  `["check"]` or `[]`; its point (root facts not re-reported) is
  unchanged.
- `satassume/theory.py`'s contract now says that a satisfiable answer
  may reuse a model that passed `check` earlier under the same theories
  and registered atoms, with no theory call.
- A theory whose `check` depends on more than the atoms and their values
  (history, time) would see a stale verdict reused. LRA and EUF decide
  consistency from the asserted constraints.
- The model after a hit gives variables created since the stored model
  the value False; `model()` covers all current variables as before.
- The ring holds 2 lists of `nvars` values per solver (C-level copies,
  already made for the model since C). The ring entry, `_mvals` and
  `_witness` share one list object; nothing mutates it (comment at the
  assignment).
