# Agent report: perf3 D, witness reuse (round 2's 1.1, re-measured and implemented)

- **Date:** 2026-09-25
- **Status:** one commit on `perf3-solver`, on top of C. **-4.7% to
  -6.4%** of the cold pass against `main` plus C (three A/Bs, about -5.6%
  on average).
- **Scope:** `satassume/solver.py` (`_solve`, `_ring_hit`,
  `_ring_blocks`, `register_block` records bases),
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
  - with theories: the same number of theories and atoms.

  A literal of a variable the model does not know does not count as
  satisfied.
- A hit answers True with that model, padded with False for variables
  created since, and with its theory models. No search, no state change;
  held levels stay as they were. `stats()["witness_hits"]` counts hits.
- On the replay: 1,344 hits (bound 1,360), 12 ms of checking. A ring of
  4 is not faster (+0.4%).

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

Against `main` plus C (`tools/ab.py`):

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
- The coverage tests now require witness hits in plain and block mode.
- 4,000 seeds in each of plain, block and theory mode, 0 mismatches:
  - plain: 8,865 hits, 4,292 by the witness operation, 93,467 conflicts;
  - block: 6,975 hits, 3,436, 27,750;
  - theory: 5,922 hits, 2,942, 24,025.
- Suite: `2 failed, 1692 passed, 1 skipped, 4 xfailed, 1 xpassed` (1691
  plus the mutation test; the 2 known `test_shared_facts` failures).

## Decision

Kept: -4.7% to -6.4%, above 5% on average (two of three runs). The
bound was 6.6%; part of the saving is lost because a skipped search no
longer leaves the held assumption levels that the next solve of the same
`entails` would continue from.

## Risks for review

- **`tests/test_theory_hooks.py`**, which is not one of my files: its
  `test_root_facts_are_reported_once_without_levels` asserted that a
  repeated `solve` makes exactly one `check()` call. With the ring, that
  solve is answered by the first solve's model (checked under the same
  atoms) and makes no theory call. The assertion now accepts
  `["check"]` or `[]`; its point (root facts not re-reported) is
  unchanged.
- The theory contract (`satassume/theory.py`) says `check` is called
  "only when" the assignment is total, before SAT. A SAT answer without a
  fresh `check` is within it, but the module docstring could say so; I
  did not edit it (not my file).
- A theory whose `check` depends on more than the atoms and their values
  (history, time) would see a stale verdict reused. LRA and EUF decide
  consistency from the asserted constraints.
- The model after a hit gives variables created since the stored model
  the value False; `model()` covers all current variables as before.
- The ring holds 2 lists of `nvars` values per solver (C-level copies,
  already made for the model since C).
