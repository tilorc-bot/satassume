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
