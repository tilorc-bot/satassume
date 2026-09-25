# Agent report: perf round 3, item B4, garbage collection and allocation

- **Date:** 2026-09-25
- **Status:** measured; nothing implemented. The collector costs about
  9.5% of the cold pass, but almost everything it scans is allocated by the
  solver (clause lists and per-variable watch lists), not by code the
  engine agent owns. The engine-side cuts are bounded under 1%, below the
  3% rule. Script `agent-reports/scripts/gc_alloc.py`. Pi, `main` at
  `6577484`, Python 3.13, default thresholds `(2000, 10, 10)`.
- **Scope:** measurement only
- **Read this if:** you work on A2, on item C (the solver's hot loops), or
  wonder why B2a beat its bound

## Measurement

**(1) The collector's share.** Interleaved single cold passes, one
process each (answers checked in every run). `gc.callbacks` time each
collection:

| mode | run 1 | run 2 | time in collections |
|---|---:|---:|---|
| default | 3.376 s | 3.348 s | 283 to 294 ms (8.5 to 8.7%): gen0 227 × 0.5 ms = 109 to 115 ms, gen1 21 collections 62 to 65 ms, gen2 2 collections 113 to 114 ms |
| `gc.disable()` after the imports | 3.032 s | 3.032 s | 0 |
| `gc.collect(); gc.freeze()` after the imports | 3.240 s | 3.245 s | 176 to 178 ms (gen2 falls to 11 to 13 ms) |

**Bound: 316 to 344 ms, 9.4 to 10.2% of the pass** is the collector (the
callbacks see 8.5 to 8.7%; the remaining 30 to 50 ms is outside the
collections, not attributed).
The two full (gen2) collections cost 113 ms because they walk the whole
heap, 109,000 tracked objects of which SymPy's import-time objects are
most. `gc.freeze()` removes that (-4%), but it is a process setting: not
something library code may do. Nearly nothing is garbage: gen0 collects
25,436 objects over the pass, gen1 1,685, gen2 56. The collections are
triggered by the *net* growth of tracked objects (short-lived sessions'
structures surviving 2,000 allocations) and find almost everything alive.

**(2) What the collector scans.** `scan` mode takes, at the start of each
collection, the objects of the generations it traverses, by kind:

| kind | gen0 (227 collections, 834,077 objects) | gen1 (21, 282,548) | gen2 (2, 267,922) |
|---|---:|---:|---:|
| list of int (clause lists: rule block and template clauses in the solver) | 46.9% | 42.0% | 5.9% |
| list of lists (watch lists holding clauses) | 28.8% | 26.4% | 3.3% |
| empty list (watch lists of literals with no watched clause) | 9.7% | 8.2% | 1.8% |
| tuple | 6.6% | 14.4% | 32.8% |
| set (engine: `demand` sets) | 1.1% | 0.7% | |
| dict, `P`, `Fraction`, function, cell, other | under 1% each | | SymPy import heap: functions 15.6%, `AppliedPredicate` 6.1%, dicts 6.1%, ... |

The solver allocates two watch lists per variable in `_grow`
(`[[] for _ in range(2 * k)]`), 66 per node block, about 590,000 on the
stream, and one list per clause: 8,260 blocks × 79 rule clauses = 652,540
rule clause lists plus about 171,000 template clauses. These live as long
as their session (most sessions are short: context-free queries, cone
rebuilds, LRU), so they survive a gen0 collection or two and are scanned
there. **Clause lists and watch lists are 85% of the gen0 scans and 77% of
the gen1 scans.** Engine-owned kinds (tuples of `pending_c` and the
B2a slot pairs, `demand` sets, session dicts, `P` atoms built on demand) are at most 10% of gen0/gen1 scans together.

Heap census (`heap` mode): 108,924 tracked objects after the imports,
123,600 to 144,300 during and after the pass. Live engine state is small:
16 sessions alive at the end (3,672 clause lists), fact cache 617 nodes,
answer memo 7,906 entries, formula memo 1,703.

**Per query path** (`paths` mode, collector off so the counters are not
reset; net tracked objects left behind per query):

| path | queries | net tracked objects per query |
|---|---:|---:|
| propagation>escalation>propagation>search | 1,349 | +262 |
| propagation>escalation>propagation | 66 | +305 |
| propagation / propagation>search | 4,398 | +8 / +10 |
| memo, none, is_cache, ask (Uninterpreted) | 7,307 | 0 to 3 |
| cone paths (the polluted session is freed) | 757 | -291 / -384 |

Growth comes from escalations in reused sessions (new nodes: their
clause and watch lists) and is released when a cone replaces the session.

## (3) Bounds for the cheapest cuts

| cut | where | bound |
|---|---|---|
| engine temporaries and containers (`demand` sets, `pending_c` tuples, session dicts; dicts cannot be pre-sized in Python) | `engine.py` | ≤ 10% of gen0+gen1 scan time (175 ms) = **under 0.5%** |
| shifted template clauses built as tuples instead of lists in `_emit_pattern` | `engine.py` | 0: `add_internal` copies each clause into a new list anyway; the temporaries die young and are not in the scans |
| `__slots__` on engine objects | `engine.py`, `compile.py` | `Session`/`VarTable` are one per session (1,597 each); nothing measurable |
| freeze the import heap | process setting | -4%, **not allowed** in library code |
| no rule clause lists (A2) | `solver.py` / A2 | about 80% of the "list of int" scans, roughly 35% of gen0/gen1 collection time, 60 ms or **about 2%** on top of A2's own estimate |
| lazily allocated watch lists (a watch list only for literals that get a watched clause; after A2 most rule-only literals never do) | `solver.py` (item C) | watch lists are 38% of gen0 scans: up to about 65 ms, **about 2%**, plus the allocation itself (590,000 lists per pass) |

## Decision

Measurement only. No engine-side cut reaches 3%: the objects the
collector spends its time on are the solver's. For the orchestrator:

- A2's A/B will contain a GC share on top of the design's 18 to 21%
  estimate (the 652,540 rule clause lists and their watch entries stop
  existing), as B2a's did (its bound was 5.2%, its A/B 7.1 to 8.0%).
- For item C (solver agent): watch lists allocated on first use
  (`_grow` extends with a shared sentinel or `None`, `_watch` creates the
  list) is the one allocation cut with a bound near 2%, larger after A2
  when rule-only literals stop getting watches.
- The two gen2 collections (113 ms) are driven by the size of the SymPy
  import heap, not by satassume; only the embedding application can freeze
  it.

## Risks for review

None (no code). `paths` counts net tracked objects (the generation-0
counter is decremented on deallocation), so it shows what survives a
query, not gross allocation; `scan` is what the collector traverses,
which is what costs.
