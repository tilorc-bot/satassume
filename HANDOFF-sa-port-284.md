# HANDOFF sa-port-284 (B, formula's next step, issue 323): paused before item (1)

Paused by the planner's ruling (forward-chain-3b, ~10:28Z 11 Nov): weekly usage projects 90% before the 17 Nov reset.
**No item started, no source edited.** Branch port/formula = origin/rust-slice 50f1421 + this file only.
Items (1), (2), (3) are all still open, in that order. Plants 622-629 + 669 and counters 720-739 are unused.

## Item (1): PY_COMPILE refuse:object to 0 Python calls per workload (or named exceptions)

Counts to beat, per workload on 7b637e2 (sa-port-281's report): dev 17, fuzz 30, zero 94, transfer7 17, transfer2 2,
cls 3, scope 1. The suite count isn't measured yet.

**The whole refuse:object path is in session.rs, which is A's file (sa-port-283).** Before editing it, ask the planner
(forward-chain-3b) through SendMessage or a report. That question hasn't been asked yet.

What I read (file:line on 50f1421, under rust-spike/slice/solver_rs/src/):
- session.rs:18-20 `NAMES`; index 15 = "refuse:object". `REFUSE_OBJECT` const at session.rs:123.
- session.rs:1178 `nid_in_formula`: an atom `==` to a known node, but not the same object, whose node has no visit yet
  -> `refuse_object()` (session.rs:1188, sets `refused_object`, raises ValueError).
- session.rs:1203 `custom_in_formula`: a custom atom whose expr is a different object with no variable yet -> the same refusal.
- session.rs:1358 `to_f`: per atom occurrence it calls `pred_id`, `nid_in_formula`, `custom_in_formula`.
- session.rs:1397 `convert`: on a to_f Exception it ticks REFUSE_OBJECT (or REFUSE_CONVERT) and returns None. Then
  `compile` (session.rs:2176) / `literal` (session.rs:2185) return false/None, and Python's `compile_formula` runs.
  That fallback is the "Python call" being counted.
- Why it refuses: the node's slot keeps `objs[nid]`, which is the first object `nid_of` saw (session.rs:1145, push at :1154).
  `St::node_base` (session.rs:624; `PyCx::node_base` at :1693) stores only the nid. Python's `node_base` keeps the first
  object *compiled*, and `Pow`'s `same` row reads identity (comment at session.rs:1167). to_f gives every atom its nid
  before compile runs, so it can't tell which occurrence's object Python's compile would reach first.
- Candidate fix (not tried): give `F::Atom` an occurrence index (compile.rs `F`, `trait Cx` at compile.rs:46). When
  compile first calls `node_base(nid)` for a node with no visit, set `objs[nid]` to that occurrence's own object. This
  only works if compile::compile reaches atoms in the same order as Python's compile_formula, so check that first. It
  touches compile.rs and session.rs (A's). The other route is to name each remaining call as an exception under the
  count rule. First measure what the 17/30/94 cases are: atom classes, and whether it's the custom or the second-object
  path (the counter doesn't tell them apart yet; a counter from 720-739 could).
- Kept test that reads the counter: rust-spike/slice/test_session_limits.py:393 (`c['refuse:object'] > 0`).
  It will need changing if refuse:object goes to 0.

## Item (2): _noncommutative_atoms native

- Python: satassume/engine.py:170 `_noncommutative_atoms(*formulas)`; Python callers at engine.py:1964 and :2213.
- Rust callbacks into it: context.rs:337 (`ctx:cb_helpers`, from `assumptions`) and entry.rs:764 (`ent:cb_noncomm`,
  `(proposition, ctx_or_none)`). Neither file is on A's list. session.rs:401 mentions it in a doc comment only.
- tools-rust/coarse.py:33 lists it among the counted Python helpers, so the probe/count reads it there.

## Item (3): bar gaps (OWED [124] (c), sa-port-281's report)

- p1/bar.sh's tests phase (:108) runs test_cbm_noid.py on Python. Run it on Rust instead. sa-port-281 reran it on
  Rust: 9 passed (R1 + 660-663 kept tests are skipped on Python), in pareto0 ~/sp19/sa-rust-ids-work/sa-port-281/cbm.
- p1/bar_sum.py plants :119-:141: the fired column reads only plant_fired / rel:plant_fired, so term plants show 0.
- Other bar.sh lines: penv :85, suite() :96, fired() :101, plants :132, extra :148, fmrows :164.

## Results and notes to read

rust-spike/slice/results/gate2-282.md, results/pc282-172d690.md, HANDOFF-sa-port-281.md (file:line map of the bar).
Probe count on 172d690: 21/32.
