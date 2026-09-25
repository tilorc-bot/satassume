# Agent report: fact-lattice stage 1b, lazy rule-block writes inside the solver ("option 4")

- **Date:** 2026-09-25
- **Status:** built, reviewed (fit to land; two mention-mask bugs fixed on `facts-option4-land`, rebased on `main` `bd1a50a`), gates passed; **-6.1% against `facts-theory` on the
  Pi** (`ab.py --rounds 3`, interleaved, cold pass, strict: answers
  identical). Recommendation: land after an independent review (it is a
  solver change of the rule block's semantics towards `implied`, see
  Risks).
- **Scope:** `satassume/solver.py` (rule block: exact closure from the
  block's model table, per-block asserted set and closure, lazy writes,
  mention tracking, lazy variables, on-demand model completion, per-level
  undo of the block state), `satassume/engine.py` (mention masks of
  template patterns, the query literal), `satassume/theory.py` (a
  docstring), `tests/test_solver_incremental.py` (the harness compares
  `implied` on mentioned variables; late mentions), `tests/test_solver.py`
  (rule-block unit tests), `tests/theory_harness.py` (the total-assignment
  assertion); branch `facts-option4` on `facts-theory` (`db8e7d8`)
- **Read this if:** you decide whether the rule block's lazy-write route
  (stage 0 "option 4", named by both stage reports) lands, or review it

## Measurement

Pi, SymPy pin, `facts-theory` (`db8e7d8`) as reference in its own
worktree; stream replay 13,877 queries.

### Ceiling first (the cheap hack): not a bound

The brief asked for a cheap ceiling: skip the rule block's writes to
variables nothing outside the block mentions, answers unchecked. Done on a
scratch copy (mention marks in every clause-adding path, the query
literal, theory atoms; `_propagate` skips a rule-block write above root
for an unmentioned variable). It bounds nothing: skipping a write also
drops the implications *through* the skipped literal (`integer` implies
`rational` implies `algebraic` ... is a chain of trail literals in the
rule block), so propagation loses consequences and searches grow: 5x
slower (15.2 s against 3.1 s locally), answers still identical. A write
cannot simply be skipped; the chain has to be computed off the trail,
which is the per-block closure of the real design. So the real design was
built directly, measured at each step, with the "slower than
`facts-theory`" line as the stop.

### Final A/B

    ab.py --rounds 3 (strict), facts-theory -> facts-option4, Pi:
      round 1 ref 2.741s cand 2.575s
      round 2 ref 2.780s cand 2.581s
      round 3 ref 2.757s cand 2.593s
      best-of-3: ref 2.741s  cand 2.575s  change -6.1% (faster); answers match
    ab.py --rounds 4 --allow-more-definite (same code): -6.8%, answers match, 0 more definite

### How the versions went (Pi, best-of-3 or 4 against `facts-theory`)

| version | change |
|---|---:|
| lazy writes, exact closure per processed-literal mask, unmentioned variables still decided by the search | +11.0% |
| unmentioned block variables not decided (models completed per block at SAT) | not timed on the Pi (local counters: propagations 737k to 423k, decisions 91k to 37k) |
| mention masks from template patterns (no per-literal scan), model completion by slice | +3.7% |
| per-block mention update (flags by slice), on-demand model completion | +2.4% |
| late mentions written at the held level instead of dropping held levels (1,596 drops per pass before) | +1.2% |
| bit tables, closure by model sets, the node's own mentions passed to `register_block` | -0.5% |
| generic mentions batched per block, unit clauses not mentions | -1.3% |
| block state undone per level (saved at its first change) instead of per trail entry | -0.4% (neutral in a direct A/B, +0.2%) |
| **block state = asserted literals and their closure; a literal the block implied skips the block entirely** | **-6.8%** |
| final (cleanup, docstrings) | **-6.1%** (strict) |
| control: the final code writing *every* implied literal (no laziness, every variable decided) | +4.1% |

The control says the lazy writes are worth about 10% of the pass on top
of the exact-closure machinery; the exact closure alone (with its
bookkeeping) is slower than the old unit-propagation tables.

A per-*literal* refinement (a clause reads only the negations of its
literals, so only those need writing) was tried and dropped: `implied`'s
propagations fell only 7% while the search had to check the block before
each decision on a half-read variable: +9.3%. Tagged `opt4-perlit-try`
locally, not on the branch.

### What the solver does per pass (local counters, same stream)

| | `facts-theory` | `facts-option4` |
|---|---:|---:|
| trail literals processed (`propagations`) | 738,518 | 394,692 |
| decisions | 65,819 | 37,165 |
| conflicts | 434 | 498 |
| rule-block writes | 550,530 (stage 0) | 186,847 |
| block literals processed that the block had not implied | | 150,081, of which 85,068 new to the closure |
| closure computations (memo misses) | | 6,292 |
| explanations read by conflict analysis (misses) | | 554 (125) |
| late mentions while held: written at the held level / dropped held levels | | 2,268 / 0 |
| witness (stored model) hits | 1,344 | 1,320 |

## Change

All solver-internal; no Python theory interface per literal.

- **Exact closure from a model table** (`_BlockClosure`, per block
  object, shared by all solvers): the block's models are enumerated once
  (48 for `RULE_INTERNAL`; DPLL); per relative literal the set of models
  containing it; the closure of a literal set is the AND of the models in
  the intersection of those sets (memoized per set and per model set); an
  empty intersection is a conflict. Explanations for conflict analysis: a
  subset of the asserted set that still entails the literal (or is still
  inconsistent), greedy over the models to exclude, then minimal by
  deletion, memoized.
- **Per block state**: the *asserted* literals (block literals on the
  trail that the block did not imply itself: decisions, assumptions,
  clause and theory propagations) and their closure. `_propagate`: a
  literal with a block reason (int) skips the block entirely; any other
  block literal already in the closure also does; otherwise the closure is
  extended (a memo lookup) and the literals new to it are written, **above
  root only for mentioned variables**, at root all of them (the root trail
  feeds the fact cache). Reasons are ints `asserted_mask << 32 | base`,
  turned into clauses by `_rb_reason` only when analysis reads them.
- **Undo** of the block state per level: saved at its first change at a
  level (`_rb_undo`, `_rb_ulim` parallel to `_trail_lim`, level ids
  `_uid`), restored by `_backtrack`; the per-entry backtrack loop is the
  original one.
- **Mentions**: a variable is mentioned by any clause added through the
  `add_*` methods (unit clauses excepted: root facts), assumptions of
  `implied`/`solve`/`entails`, `entails`' literal, theory atoms, and the
  new `Solver.mention(lits)` (the engine calls it for the query literal).
  `mention_blocks((base, mask), ...)` takes per-block masks: the engine
  precomputes them per template pattern and demand set (`engine._split`,
  memoized; the filtering it replaces was recomputed per node), and passes
  the node's own mask to `register_block(b, mentions)`.
- **Late mention**: a variable mentioned while levels are held and implied
  there by its block gets its literal written at the top held level with
  its reason and propagated, if the block literals below that level do
  not already imply it; otherwise held levels are dropped (never on the
  stream: 2,268 written, 0 dropped).
- **Lazy variables**: a block variable nothing mentions is not decided by
  the search (`_pick_branch` skips it); the exact closure guarantees the
  block stays satisfiable, so a model of the rest extends. A stored model
  (the witness ring) gets a lazy variable's value on demand (`_fill`: the
  block's segment is completed from a block model containing its
  assigned values). Theories' `check` is called on an assignment total
  except for lazy variables (never theory atoms); docstring and the test
  harness's protocol check updated.
- Rule tables reduced to the clauses (for the witness check) and the
  closure; the old unit-propagation tables are gone.

## Gates

- **Answers**: `ab.py` strict on the stream: identical to the recording
  (13,877; no more-definite answer); `gate2.py` strict: `2863 records
  (2588 in scope); changed 0; answers match`. The exact closure's extra
  strength reaches no answer of either gate (stage 0 predicted this).
- **Suite** (Pi, `-n 3`): `2 failed, 1701 passed, 1 skipped, 4 xfailed,
  1 xpassed` (the known `test_shared_facts` pair), including the
  incremental fuzz at its default 500 seeds per mode and the harness
  self-tests (a dropped clause, a weak propagator, a stale witness are
  still caught).
- **Solver fuzz** (`tests/test_solver_incremental.py`), 4,000 seeds per
  mode: plain 0 to 3,999 ok; block (propagator and mixed) 0 to 3,999
  ok (21,011 propagator reasons read, 103,099 oracle literals of
  unmentioned variables skipped, 2,898 late mentions while held: 324
  written at the held level, 165 dropped held levels); block with
  theories 0 to 3,999 ok (14,427 / 81,349 / 2,196: 235 written, 132
  dropped). The harness
  now tracks what the live solver was told outside its propagator blocks
  (`Harness.mentioned`) and compares `implied` on those variables (every
  other literal of the oracle is counted as `implied_lazy_skipped`; extra
  literals are checked entailed); a new operation `late_mention` makes an
  unmentioned block variable mentioned (by `Solver.mention` or a clause),
  usually while the assumption levels are held, then compares `implied`
  under the same assumptions. The coverage test requires
  `late_mentions_written_held`, `late_mentions_dropped_held` and
  `implied_lazy_skipped` besides the old counters. Checked that the
  harness catches a planted bug in the new undo (levels not renumbered on
  backtrack): mismatch at seed 1.
- **Real-theory fuzz** (`tests/real_theory_fuzz.py`, LRA/EUF, no rule
  block but the same `_assume`/`_search` paths): 1,000 seeds per mode
  (lra, euf, both): 0 mismatches, 0 implied-misses.
- `tests/test_solver.py`'s rule-block tests rewritten for the new
  semantics: `implied` agrees with clause propagation on mentioned
  variables and is otherwise entailed; the exact closure needs no
  conflict where clauses do (`(x1|x2), (x1|-x2)`); reasons are read
  through an unwritten intermediate literal; a late mention while held is
  written at the held level; at root the closure is a superset of clause
  propagation, all of it entailed.

## Risks for review

- **`implied` is weaker by design** for variables nothing mentions: the
  block's implication is not on the trail. The engine reads `implied`
  only for the query literal, which it now mentions; any other caller of
  `implied` that reads a literal must mention it first. `value` and
  `root_trail` are unaffected (root writes everything).
- **The exact closure is stronger than clause propagation**, so the
  search differs (fewer decisions, 498 conflicts instead of 434) and an
  answer that depends on history (stage 0's 4 less-definite cases) could
  move; none did on either gate.
- **Model completion**: a stored model has None for lazy variables until
  read; `_ring_hit`, `_ring_blocks`, `_witness_satisfies` and `model()`
  complete on read. A new reader of `_mvals`/`_witness` must do the same.
- **Memo growth**: the closure and explanation memos are bounded
  (cleared at 400,000 / 200,000 entries); the model-set memo (`cls`) is
  not bounded but is at most one entry per distinct model set, a few
  hundred.
- `_rb_late` writes a late-mentioned literal at the top held level only
  if the block literals below it do not imply it; the fuzz exercises both
  branches (dropped and written), the stream only the first.
- The per-level undo depends on every level being created at the four
  `trail_lim.append` sites (each now also pushes `_rb_ulim` and bumps
  `_uid`); a new site must do the same.
- Mention marks cost a pass over the clauses of the generic `add_*`
  paths; the engine's template path uses precomputed masks. A caller that
  adds many clauses through `add_clause` pays the scan.

## Landing branch `facts-option4-land` (after review)

An Opus review found the change fit to land for the engine, with two real
bugs in public solver calls the engine does not make, fixed here:

1. `register_block(base, mentions)` read only the positive bit of each
   variable in `mentions`; a negative-only bit left the variable lazy
   (undecided) and later mentions with the same bit changed nothing: an
   unsatisfiable problem solved True. Masks are now normalised (either
   bit mentions the variable) in `register_block` and `mention_blocks`.
2. `mention_blocks((b, mask))` with `b` not a block's base (inside a
   registered block) was kept at `b` and lost. Now a pair whose base is
   inside a registered block, or whose range touches one, is mentioned
   literal by literal; a mask kept at an unregistered base is collected
   by any registration overlapping it (shifted onto the new block), not
   only by one at the same base.
3. Blocks over 64 variables raise ValueError (the bit tables cover 128
   literals).

Regression tests for 1, 2 and the overlapping registration in
`tests/test_solver.py` (all three fail on `facts-option4`). The
reviewer's fuzz is folded into `tests/test_solver_incremental.py` as
mode `mentions` (`MentionSolver`: the engine's paths `mention_blocks`,
`add_internal(mentions)`, `register_block(mentions)`, with negative-only
and positive-only bits and bases inside blocks; `root` also checks that
everything clause propagation derives at root is on the root trail; test
`test_engine_mention_paths_match_clauses` and a coverage test). It fails
on `facts-option4` at seed 0.

Rebased onto `main` `bd1a50a` (stage 2, facts shared between equal terms;
the transfer theory registers every predicate variable of a node block
as a theory atom, so in sessions where it is engaged those variables are
all mentioned and nothing is lazy) and squashed into three commits
(solver; engine; tests) plus this report.

Gates, local (the Pi is reserved; the landing side runs the Pi A/B):

| gate | result |
|---|---|
| `ab.py main-worktree cand --allow-more-definite` | answers match; ref 15 more definite, cand the same 15 |
| `gate2.py` | strict: the same 1 change as `main` (`Q.prime` transfer, out of scope); with `--allow-more-definite`: answers match |
| solver fuzz, 4,000 seeds per mode | plain, block, theory, mentions, mentions with theories: all ok (mentions: 3,021 root-completeness checks, 408 late mentions written held, 217 dropped; with theories 1,454 / 186 / 92) |
| `real_theory_fuzz.py`, 1,000 seeds per mode | lra, euf, both: 0 mismatches, 0 implied-misses |
| `test_transfer_fuzz.py`, 1,000 seeds (5 chunks) | all passed |
| suite | 2 failed (the known `test_shared_facts` pair), 1751 passed, 1 skipped, 3 xfailed, 1 xpassed |
