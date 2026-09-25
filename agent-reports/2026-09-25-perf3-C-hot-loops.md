# Agent report: perf3 C, the solver's hot loops

- **Date:** 2026-09-25
- **Status:** **dropped after rework.** Only the model slice survives,
  moved into item D (which needs it). History:
  - First version (six cuts): -6.0 to -7.2% locally; the reviewer
    measured -6.8%. Review: "land minus".
  - Two cuts reverted for readability (lazy watch lists, the
    `_backtrack` rewrite); the shared literal table made per solver
    (C').
  - C' measured **-2.4% to -3.2%** against its parent `747fb0e`. The
    reverted cuts were worth 3 to 4 points in combination, not the
    ~1% their single A/Bs showed.
  - C' is under the 5% rule and not a ten-liner, so it is dropped (the
    orchestrator's decision).
  - The model slice goes with D: D's ring stores the slice, and the
    reviewer judged that hunk clearer than the old dict. The
    external-literal table and the tightened propagation loops are not
    kept.
- **Scope:** `satassume/solver.py`; measurement scripts in the scratch
  directory (described below)
- **Read this if:** you review C, or want to know what a compiled core
  would buy

## Measurement

Tree: `main` (A1, A2, B2a); all A/Bs local, `tools/ab.py`, cold passes.
The replay is 3.16 to 3.18 s. Line-level sampling profile (SIGPROF
every CPU tick, 3,944 samples over 5 cold passes; wrapper self-times are
unreliable at this call rate):

| where | share of samples |
|---|---:|
| `_propagate` | 30.0% |
| &nbsp;&nbsp;binary rule loop of the hook | about 10% |
| &nbsp;&nbsp;ternary rule loop | about 6.5% |
| &nbsp;&nbsp;the three 4-literal rules | about 2.3% |
| &nbsp;&nbsp;main loop, empty watch lists skipped | about 7% |
| &nbsp;&nbsp;watch scans (template, formula, learnt clauses) | about 3.3% |
| `_backtrack` | 3.9% |
| `_grow` | 3.8% |
| `_pick_branch` | 3.4% |
| `_solve` (the model dict after every SAT solve) | 3.3% |
| `add_internal` + `_add_lits` | 4.9% |
| `_theory_sync` | 2.7% |
| `implied` + `root_trail` (trail to external literals) | 3.5% |
| engine and SymPy | the rest |

- The collector is 2.5 to 2.8% of the local pass on this tree (80 to
  88 ms, `gc.callbacks`). The Pi figure of 3.7 to 4.4% is from the B5
  report. A2 removed the rule clause lists that made it 9 to 10% in B4.
- 70,000 of the 84,000 `_add_lits` calls come from `add_internal`
  template clauses that meet an assigned literal (49,000 of them
  satisfied at root, 19,000 reduced, 2,000 units).

## Change: the six parts, each measured (A/B against `main`)

| part | alone | in the reworked commit |
|---|---:|---|
| model kept as the C-level slice `val[2::2]`; the dict of `model()` and `_model` (read by `tools/query_log.py`) built on demand; the witness check indexes the slice | **-2.1%** (4 rounds) | kept |
| trail to external literals through a table (`map(ext.__getitem__, trail)`) in `implied` and `root_trail` | -1.4% (3 rounds, shared module-level table) | kept, **made per solver and grown in `_grow`** (review: a shared table grown without a lock could be extended twice by two solvers and shift permanently). A per-solver table grown lazily at conversion measured the same (-3.2% for the whole commit). |
| both propagation loops: no per-literal counter (`_n_props` from the queue head), `len(trail)` read only when the known part is done, truth test before `len(ws)`, reason codes computed on assignment | -1.1% (3 rounds) | kept |
| watch lists created on first use (the empty tuple until then) | -0.9% (3 rounds) | **reverted** (review: under about 1%, and every watch append became a four-line branch) |
| `_backtrack` iterates a reversed slice and skips the heap test while no variable is out of the heap (`_nout`) | about 0 to -0.5% (noise) | **reverted** (review: no measurable gain, an extra invariant in the heap code) |
| first version, all six | -7.2% (4 rounds), -6.0% (3 rounds) against `main` | |
| **reworked commit** (three kept, per-solver table) | against `747fb0e`: **-3.1%** (3 rounds, `ref 3.194s cand 3.094s`), **-2.4%** (4 rounds, `ref 3.140s cand 3.063s`); against `.worktrees/ref` (`895a6c2`): -11.5% (3 rounds, `ref 3.501s cand 3.097s`) | answers match |

The reverted cuts were worth more together than their single numbers
(about 3 to 4 points against about 1). Measured one at a time on a noisy
2-core machine, cuts this small do not add up exactly.

Measured and dropped:

| candidate | A/B | why |
|---|---:|---|
| `_pick_branch` scan by `val.index(None, 2v)` in C | +0.1% | its profile share was mostly wrapper overhead |
| closure of the binary rules per literal (assign the transitive closure at once, skip the binary loop for literals it assigned) | **+3.5%** (slower) | closures are much longer than the direct lists, and a node's several facts walk overlapping closures |
| `add_internal` dropping root-satisfied template clauses without the copy and `_add_lits` | about 0 | |
| `_theory_sync` iterating a slice with a bound `dict.get` | +0.7% | |
| per-literal combined rule table with guards on empty lists; bound `trail.append` | 0 (micro-benchmark) | |

The coordinator's suggestion, a memoized per-node closure keyed by the
node's asserted-predicate set as a bitset, was bounded but not coded:
- Each of the 620,000 implied literals still has to be written (value,
  level, reason, trail) and taken off the trail for its watch list: about
  0.2 µs each, about 140 ms, which stays.
- What a memo could remove is the rest of the hook's per-literal work,
  about 0.3 µs for each implied literal, about 190 ms.
- The key has to be built per processed non-implied block literal
  (about 210,000 per pass): a slice of the node's 66 literal slots, a
  tuple and a hash, about 1 to 1.5 µs, 210 to 315 ms. Maintaining a
  bitmask incrementally instead needs an undo log on backtracking, which
  adds per-literal work back.
- Net bound: -3% to +4%. The binary-closure experiment above is the
  measured cheap half of the idea, and it lost 3.5%. Not pursued.

## Correctness

- `_n_props` counts exactly the processed literals as before (at a
  conflict, up to the literal that found it).
- `_witness_satisfies` indexes the witness list with the assumption
  literal, where the old code used `dict.get`. An assumption that is
  not an int (e.g. `3.0`) now raises `TypeError` instead of silently
  missing. `entails` passes its raw assumption list here, so
  `entails(x, [3.0])` can now raise `TypeError` (only when an earlier
  model exists) where it answered before; acceptable per review, since
  literals are documented as ints.
- `_mvals` and `_witness` are the same list object. That is safe only
  while nothing mutates it: both are only read or replaced (comment at
  the assignment).
- The witness is the same assignment as a list: a variable beyond its
  length is skipped, as `dict.get` did.
- The model dict is built from the same values.

Gates on the reworked commit:
- Fuzz, 4,000 seeds in each of plain, block and theory mode, 0
  mismatches (93,181 / 27,046 / 23,632 conflicts; the same counts as
  before C).
- gate2:
  `gate2: 2863 records (2588 in scope); changed 0 (0 in scope); answers match; replay 1.86s (ask 0.90s)`.
- Suite: `2 failed, 1693 passed, 1 skipped, 4 xfailed, 1 xpassed` (the
  suite of `747fb0e`, unchanged; the 2 known `test_shared_facts`
  failures).

## Decision

Dropped. The reworked commit (C', `54b0e08`, not landed) is -2.4 to
-3.2%, under the 5% of item C. The first version cleared it only with
the two cuts the review asked to revert. The model slice is part of
item D (`2026-09-25-perf3-D-witness-reuse.md`). The measurements above
remain the record of what each cut is worth. Pure-Python tightening of
the loops is at the 1% level per cut, which is why the compiled-core
section below is the lever left.

## What a compiled core would buy

On this profile the solver is about 60% of the pass:
- `_propagate` 30%;
- search internals (`_search`, `_solve`, `_pick_branch`, `_backtrack`,
  heap) about 13%;
- insertion (`add_internal`, `_add_lits`, `add_clauses`,
  `register_block`) about 7%;
- `_grow` 3 to 4%;
- `implied`/`root_trail`/`_internal_lits` about 4%;
- `_theory_sync` about 3%.

Pure-Python tightening is exhausted at the 1% level per cut. The fixed
cost per processed literal (about 1 µs) is interpreter overhead, the
same for clause and propagator propagation. A compiled core (C
extension, Cython or Rust with the same API, integer literals, flat
arrays) typically runs this kind of code 20 to 50 times faster:
- It would take the solver's share from about 60% to 2 to 3%, a pass of
  3.0 s would fall to about 1.3 s, leaving the engine, SymPy and the
  Python/C boundary.
- The boundary matters: `implied` returns whole trails (converted per
  call) and the engine calls the solver about 100,000 times per pass, so
  the realistic figure is 1.4 to 1.6 s, about half of today's pass.
- The theories (LRA, EUF) stay in Python, and `_theory_sync`'s callbacks
  into them remain.

No other lever left in the solver is above a few percent.

## Risks for review

- `_model` is now a read-only property. `tools/query_log.py` reads it
  and still works.
- `_ext` is per solver: two ints per variable, extended in `_grow`.
- The commit sits on A1/A2 (it touches `_propagate` and
  `_propagate_clauses` both). Reverting A1 alone would need a manual
  merge of the propagation loop.
