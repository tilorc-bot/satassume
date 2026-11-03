# HANDOFF sa-clone-1 (generic clone of the post-build context session)

Branch `ctx-clone` from 9bafaa5 in ~/dev/sa-rel. Status: STOPPED at the brief's
stop condition (question to forward-chain-3b). No PR, nothing submitted.

## What was built (measurement prototype, kept for the record)

- `satassume/state/clone.py` (~120 lines): generic structural copier. Copies every
  list/dict/set/deque/bytearray/bound method/weak proxy and every satassume-class
  instance (`__dict__`, `__slots__`, list subclasses); shares numbers, str, SymPy,
  `P`, `Formula`, constfield `Element`, `_BlockClosure` (the shared rule-block memos),
  classes/functions, and tuples/frozensets of shared objects; the engine by seeding
  the memo. Fast path: a container whose element types are all shared is `.copy()`d in C.
- `engine.py`: `_build_context` keeps one pristine copy per (set, scope) for
  relation sessions (`_pristine`, bounded, cleared with `_verdict`) and returns a copy.
- notes/ctx-clone/: `census.py` (what a relation session reaches; what is identical
  between two builds = globals), `bound.py build|clone|pickle` (copy vs build per
  session, answers), `pk.py` (variant B: pickle with the shared objects pre-filled in
  the unpickler memo, so a load runs no Python), `where.py` (copy cost per attribute),
  `keys.py` (builds per key).

## Numbers (orion, load ~10; ratios within one process)

Unique stream, per session:

| | build | copy A (Python) | copy B (pickle, prefilled memo) |
|---|---:|---:|---:|
| relation, repeat (887) | 1.273 ms | 0.748 ms (59%) | 0.692 ms (54%) |
| relation-free, repeat (2,480) | 0.114 ms | 0.194 ms | 0.107 ms |
| store per first build | - | ~0.77 ms | ~0.39 ms (dump) |

End-to-end unique stream: base 5.54 s; A copying every set 6.42 s; B 5.69 s. Answers
identical in both (8,393 unique queries).

Projection (relation sets only, eager store; 755 keys, 887 repeat builds; lazy store
on the 2nd build is worse): net = 887 x (1.273 - c) - 755 x store. A: about -2%.
B: about +4% at best. 8% needs c <= ~0.3 ms (24% of a build, 2x the bare
shallow-copy floor of 0.149 ms that has no memo and no aliasing remap).

Dev set (`evalbench/dev.py`, prototype A, relation sessions only): answers
1985/1985 identical; total 0.854x (slower), None 0.817x, definite 0.864x. Only
91 of 918 sessions are repeats there; storing one copy per first build costs more.

Where copy A goes (`where.py`, 0.78 ms per relation session): solver `_watches`
0.22 ms (28%; watch lists of clause lists, every clause remapped through the memo),
`_clauses` 0.05, the rest is under 0.03 ms each over ~40 attributes. Even with the
watches free, the copy would be ~0.56 ms (44% of a build): still under 8%.

Python 3.13 notes for anyone retrying B: `Unpickler.memo = dict` is silently ignored
(load then fails with "Memo value not found", or segfaults with protocol 5 MEMOIZE);
copy the memo from a template unpickler filled by persistent ids instead. A
`reducer_override` that returns a reduction for a class segfaults; return
NotImplemented for classes and functions.

## Recommendation

Drop the generic clone: it is 54-59% of a relation build (at the 60% limit), it loses
on the dev set, and the stream projection is under 4%. Add a row to
docs/performance.md "What was measured and dropped". Not tried (out of scope,
parked): a per-class protocol that rebuilds watch lists from clauses.
