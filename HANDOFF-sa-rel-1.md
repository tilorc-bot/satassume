# HANDOFF sa-rel-1 (relation work reuse across context builds)

Branch rel-reuse from 9bafaa5. Venv: `.venv` (py3.13, SymPy pin via .pth). Run
scripts from the clone root: `PYTHONHASHSEED=0 .venv/bin/python notes/sa-rel-bound/X.py`.
Workload: unique (prop, assumptions) pairs of /home/tilo/provable/data/stream.pkl
(8,393 of 16,232), one process, stream order. orion, unpinned: shares only.

## Bound (done, reported)

Unique pass about 5.3-5.5 s (orion, load ~8/12).

| piece | share of total |
|---|---:|
| context builds (`_build_context`, 4,450) | 40-43% |
| `Relations.process` inside builds | 18.5% |
| `Relations.process` inside `prepare_query` (query-specific) | 10.6% |
| `_complete_check` | 10.7% |
| repeat builds of a relation (glue) set, 887 builds, 1.24 ms each | 20.5% |
| first builds of a relation set, 755, 1.04 ms each | 14.7% |
| repeat builds of relation-free sets, 2,480, 0.11 ms each | 5.1% |

(a) pure memo of the SymPy side: SymPy code is 5.5% of a repeat relation
build (cProfile tottime), and most of that is `Basic.__hash__`/`__eq__` from
satassume's own dict lookups. LRA linearisation (`_INTERPRETED`) and
`sympy_atom` (`_SYMPY_ATOMS`) are already memoized across sessions
(a36d19f); `lra_adapter._lin` is 0.4% of the profiled pass. Bound <= 2%.
PR 133 (per-expression linear-form memo) has nothing left to win here.

(b) clone / recorded build of the post-build session per (set, scope):
- ceiling (free clone): 20.5% (relation sets), 25% (all sets).
- generic clone by pickle with SymPy objects, P atoms and the engine passed
  by reference (`picklebound.py clone`): answers identical on all 8,393
  queries, but load 0.81 ms per relation session (build 1.24 ms) and
  0.26 ms per relation-free one (build 0.11 ms), store 0.5 s: total 5.34 s
  -> 6.90 s (slower).
- lower bound on a hand-written clone (`shallowbound.py`): a relation
  session reaches 1,339 mutable containers / 5,018 elements; shallow-copying
  them all costs 0.149 ms (7-12% of a build). With the re-wiring a real
  clone needs (watch lists point at clause objects, theory maps, the
  Relations proxy), estimate 0.3-0.45 ms. Net estimate ~8-10% of the pass
  after storing one copy per first build, for a clone protocol over
  Session, VarTable, Solver (+_BlockClosure), LRATheory, EUFTheory,
  TransferTheory, EqualitySharing, the two adapters and Relations (~55
  attributes): 150-300 lines, every future mutable attribute a
  history-independence hazard, and solver.py is sa-wit-1's file.

Status: question to forward-chain-3b (see agent report).

## Decision (forward-chain-3b): clone PARKED (numbers above are the fallback)

## Bound 2: check once per set (`checkonce.py base|once`) -- ~0%, dropped

Query session = set assumed, no `_complete_check`; inconsistency from the
verdict memo, computed on a miss by the unchanged build (proposition None).
Answers: 0 differences on 8,393 queries. Time (two interleaved pairs):
base 5.195 / 5.354 s, once 5.320 / 5.171 s: no gain. Builds 2.19 s ->
1.57 s query builds + 0.22 s verdict builds (463, 354 memo misses), but
`Engine._ask` 2.16 s -> 2.60 s: escalations 2,077 -> 2,436, searches 2,975
-> 3,012; the query's own consistency search (`query_literal` checks the
assumptions before any answer) redoes what the check did.

## Bound 3: per-build session work (started; ownership split below)

forward-chain-3b's split: sa-rel owns engine.py's build path, relations.py, and
the solver's clause insertion and allocation (add_clause, _add_lits,
add_internal, _grow, register_block). sa-wit-1 owns theories/lra/* and the
solver's theory interface (_tpropagate, _theory_sync, _theory_check,
register_atom's theory path). Message the other before editing outside your part.

Measured so far:
- `_grow` one variable at a time: 1.6 us per call (microbench, a fresh
  solver with the rule block, 299 single-variable grows), 54,871 calls per
  unique pass -> ~0.09 s of ~5.3 s = ~1.7%. Under 3%: not worth batching.
- Whole-pass cProfile tottime (base.prof, profiler-inflated): _propagate
  0.95 s, _add_lits 0.82, list.append 0.70, len 0.70, dict.get 0.66,
  add_internal 0.41, _grow 0.36, _internal_lits 0.31, P dataclass __hash__
  0.59 cum (407k calls, est. 1-2% real), _emit_pattern 0.19 (1.84 cum).
  No single cut stands out. Each looks like 1-2%, and performance.md
  already dropped the larger related items: precompiled template emission
  2.2%, lazy watch lists, the hot-loop bundle.

Next steps for a successor (if forward-chain-3b wants one):
1. Bound the P.__hash__ cache (hash stored at construction in
   sat/formula.py, a shared file: tell forward-chain-3b) by a real A/B,
   not cProfile. It is probably 1-2%.
2. Bound `_add_lits`'s dead provenance branch (`owner is not BOTTOM`
   with track_owners False) and add_clause -> _internal_lits -> list()
   copies for engine emits. Probably <1% each.
3. If nothing reaches 3-5%, report Status: question recommending that
   the relation stream's remaining time be attacked through the theory
   interface (sa-wit-1's part) or the parked clone (numbers above).
