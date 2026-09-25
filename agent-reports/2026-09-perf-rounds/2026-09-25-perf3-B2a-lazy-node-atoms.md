# Agent report: perf round 3, item B2a, lazy node atoms

- **Date:** 2026-09-25
- **Status:** done, kept (-8.0% and -7.8% in two `ab.py --rounds 2` runs on
  the Pi; ten-line rule 3%).
- **Scope:** `satassume/compile.py` (`VarTable`), `satassume/engine.py`
  (`Session.writeback`), `tests/test_lazy_atoms.py` (new). Script
  `agent-reports/2026-09-perf-rounds/scripts/node_atoms.py` (measures the eager table; run it
  on the reference).
- **Read this if:** you read `VarTable.atom_of`, or add a reader of the
  atom behind a solver variable

## Measurement

`VarTable.node_base` allocated a node's `NPRED` = 33 variables and
created their 33 atoms at once, `P(pred, node)` each, a frozen dataclass
(its `__init__` sets both fields through `object.__setattr__`). On the
stream (Pi, cold pass, `node_atoms.py`, answers checked, on the eager
code):

- 8,900 node blocks in 1,597 tables: 293,700 atoms created;
- **49,566 of them (16.9%) are ever read**, by anyone (the table's list
  recorded every index access). The only readers are `Session.writeback`
  (the atom of each root-trail literal, to cache the fact) and
  `VarTable.lit_name` (debugging; not called on the stream);
- the allocating calls take 189 ms in the pass, **5.2%** of the 3.63 s cold
  pass (timer included). Re-timed alone on the same 8,900 blocks: eager
  291 ms, a shared placeholder repeated 33 times 6 ms.

## Change

- `VarTable.slots[v]` replaces the eager list: `None` (auxiliary
  variable), the custom atom `P` itself, or for a node block's variables
  one shared pair `(node, base)`, stored with `extend([(node, b)] * 33)`.
- `VarTable.atom(v)` builds `P(PREDICATES[v - base], node)` on demand;
  `lit_name` uses it. `atom_of` stays as a read-only property that
  materializes the old list (inspection only; nothing in the repo reads
  it).
- `Session.writeback` reads `slots` directly: for a block variable it
  puts `(node, PREDICATES[v - base], lit > 0)` into the fact cache without
  building the `P`; custom atoms and auxiliaries take the old code.

Correctness: variable numbering is unchanged (`len(slots)` is what
`len(atom_of)` was, one entry per variable, same allocation order), so the
solver sees the identical problem. For a node variable `v` with base `b`
the old entry was `P(PREDICATES[v - b], node)` (created in `PREDICATES`
order starting at `b`); `atom(v)` returns an equal `P`, and `writeback`
calls `cache.put` with the same node object, the same predicate and value
as `atom.expr, atom.pred` gave (a node atom's predicate is always in
`PRED_INDEX`, so the old code took the `cache` branch for it). Custom and
auxiliary entries are stored as before. A `tuple` is never a custom atom
(`P` is a dataclass), so the type test cannot misroute.

## A/B (Pi)

    tools/ab.py --rounds 2:  best-of-2: ref 3.653s  cand 3.361s  change -8.0% (faster); answers match
    tools/ab.py --rounds 2:  best-of-2: ref 3.645s  cand 3.361s  change -7.8% (faster); answers match
    tools/gate2.py:          gate2: 2863 records (2588 in scope); changed 0 (0 in scope); answers match; replay 1.97s (ask 1.08s)

The gain exceeds the 5.2% timed bound: 244,000 fewer objects per pass
also means fewer cyclic-GC generation passes, which are not in the timed
calls. `tools/refine_replay.py --log` on the candidate: paths, 5,971 memo
hits and 1,597 sessions built are identical to the 0.3 log of `eae6070`.

## Tests

Pi, full suite: `2 failed, 1670 passed, 1 skipped, 4 xfailed, 1 xpassed`
(the known `test_shared_facts` pair; 1668 plus the 2 new tests).
`tests/test_lazy_atoms.py`: the lazy table's atoms, `atom_of`, `len`,
`lit_name`, `new_nodes`/`new_custom` against the eager layout (node,
auxiliary, custom, node interleaved), and `writeback` caching node facts.

## Decision

Kept: -8.0% / -7.8% (3% rule), answers identical on both gates.

## Risks for review

- Code outside the repo that indexed `VarTable.atom_of` now gets a fresh
  list built per access (correct, but O(variables)); that includes any
  local debugging helper.
- A2 does not touch `VarTable`; the patch still applies (`engine.py`
  hunks are away from `writeback`).
