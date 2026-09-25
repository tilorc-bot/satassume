# Agent report: perf3 C, the solver's hot loops

- **Date:** 2026-09-25
- **Status:** one commit on `perf3-solver` (on top of A1): six small
  solver-side cuts, **-6.0% to -7.2%** of the cold pass together. **No
  single part clears 3% alone** (each is 0 to 2.1%), so the commit is
  item C as the plan defines it (the solver's hot loops, keep at 5%), not
  six kept changes. The orchestrator decides whether that reading
  stands.
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

| part | alone | notes |
|---|---:|---|
| model kept as the C-level slice `val[2::2]`; the dict of `model()` and `_model` (read by `tools/query_log.py`) built on demand; the witness check indexes the slice | **-2.1%** (4 rounds) | the dict over every variable after every SAT solve was the whole cost |
| trail to external literals through one shared table (`map(_EXT.__getitem__, trail)`, grown on demand) in `implied` and `root_trail` | -1.4% (3 rounds) | |
| both propagation loops: no per-literal counter (`_n_props` from the queue head), `len(trail)` read only when the known part is done, truth test before `len(ws)`, reason codes computed on assignment | -1.1% (3 rounds) | |
| watch lists created on first use (the empty tuple until then; `_watch` helper, inlined in the insertion paths and `_propagate`) | -0.9% (3 rounds) | removes 2 list allocations per variable in `_grow`; the collector share left to take is small after A2 |
| `_backtrack` iterates a reversed slice and skips the heap test while no variable is out of the heap (`_nout`, kept by pop and insert) | about 0 to -0.5% (inside the noise) | kept in the bundle: it removes 2 of 7 operations per undone literal |
| **all six** | **-7.2%** (4 rounds, `ref 3.222s cand 2.990s`), **-6.0%** (3 rounds against current `main`, `ref 3.158s cand 2.968s`) | answers match |

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

- Watch lists: every append site handles the empty-tuple sentinel. A
  list emptied by compaction stays a list. `_reduce_db` rebuilds only
  non-empty lists. The watch scan returns before touching an empty entry.
- `_n_props` counts exactly the processed literals as before (at a
  conflict, up to the literal that found it).
- The witness is the same assignment as a list: a variable beyond its
  length is skipped, as `dict.get` did.
- The model dict is built from the same values.
- `_nout` changes only where a variable leaves or re-enters the heap.

Gates:
- Fuzz, 4,000 seeds in each of plain, block and theory mode, 0
  mismatches (93,181 / 27,046 / 23,632 conflicts; the plain count is the
  same as without C).
- gate2 on `main` plus C:
  `gate2: 2863 records (2588 in scope); changed 0 (0 in scope); answers match; replay 1.74s (ask 0.79s)`.
- Suite (worktree): `2 failed, 1691 passed, 1 skipped, 4 xfailed, 1 xpassed` (unchanged).

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

- `_watches` entries may be the empty tuple: code reading them must not
  mutate an entry without the `_watch` pattern. The analysis scripts in
  `agent-reports/scripts/` only read them.
- `_model` is now a read-only property. `tools/query_log.py` reads it
  and still works.
- `_EXT` is module-level, grows to the largest variable any solver used,
  and is never shrunk (two ints per variable).
- The commit sits on A1 (it touches `_propagate` and
  `_propagate_clauses` both). Reverting A1 alone would need a manual
  merge of the propagation loop.
