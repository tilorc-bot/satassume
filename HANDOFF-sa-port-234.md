# HANDOFF sa-port-234: formula step (issue 323), second part

Branch `port/formula`, head = this commit, on rust-slice 3203cb4 ((iii) landed). rust-slice is now 0192b35 (docs only):
rebase onto it (no rerun needed for it). **Unbarred, unlanded.** Report: rust-spike/slice/results/port-formula.md (last
section). Handed off at the context budget.

## Done
1. Rebased onto (iii). Per-session node cache in `SessionCore`; `to_f` walks the node (7874c7d).
2. `atoms_of` callbacks B1-B7 replaced (a9b4073). B6/B7 have no session, so they convert on the spot (`fm:nosession`).
3. Short checks only: slice tests pass; dev, scope, budget, zero MATCH; plant 601 caught on dev, 602 fires and is NOT caught
   on dev (MATCH).

## Running detached when handed off (no waiter shell of mine is left)
`setsid` job from ~/sa-rust-ids-work/sa-port-234 (log detached1.log): plants 603-606 on dev, all six on zero
(`plants/plant-WL-PLANT.cmp`, `.session.json`; `plants/end-dev.txt`, `end-zero.txt`), then the after-probe
(`probe/probe-after/`, `end.txt` last). It imports from the clone and loads rust-spike/slice/sa_solver.so: **don't rebuild
or rebase the clone until `probe/probe-after/end.txt` exists** (a `cp` over the loaded .so can crash it).
Read with `python probe/summ.py probe/probe-after`.

## Next, in order
1. Read the plants and the after-probe; fill port-formula.md's after column (sat/formula.py and knowledge/compile.py per
   workload, `em:key_eq`, `pm:key_eq`, `rv:cb_formula`).
2. Rebase onto origin/rust-slice. When state part 3 has landed: C1/C2 (compile and literal without session_live's frame;
   `_rust_call` session_live.py:1252, part 3's `named` in session.rs), then D, E.
3. B6/B7's repeat conversion: the entry converts once and hands nodes down (entry.rs:703-792, context.rs:175 call
   `theory_scope` before the session exists), or ask the planner if a per-query cache is wanted.
4. `ad:cbm_noid` fix, `_common._CACHE` fix, the term_live fallback cause read (brief and port-formula.md "New rows").
5. Plant 602 needs a workload or comparison that catches it, or it is reported as not caught off the unit test.
6. The bar, with the digest extension as landed by sa-port-230; land after state part 3.

## File:line map (at this head)
- formula.rs: `N` :34, `Occ` :53, counters :61 (630-644), plants :95, `Walk::atom` :148, `Walk::walk` :177, `FNode` :248,
  `FNode::visit` :259, `FNode::atoms_of` :286, `Refused` :356, `convert_or` :368, `classes` :395, `atoms_py` :411,
  `atoms_nosession` :420, `counts_into` :435, `register` (reads SLICE_SESSION_PLANT) :468.
- session.rs: `session_counts` :519, `fnodes` :643 (init :1481, traverse/clear near :1700), `nid_in_formula` :905,
  `custom_in_formula` :930, `atom_fields` :1034, `fnode` :1045, `atoms_of` :1062, `to_f` :1075, `convert` :1114,
  `compile`/`literal` :1828/:1837.
- atoms from nodes: session_glue.rs:87, :185; compile_loop.rs:327, :376; query.rs:271, :287 (session);
  scope_core.rs:259, :291; budget.rs:61, :373, :465-466 (no session).
- compile by name (C): session_glue.rs:120; compile_loop.rs:182, :344; query.rs:248; entry.rs:781 (`basis_formula`).
- session_live.py: `_rust_call` :1252, `_compile_formula` :1264, `_formula_literal` :1274, `_core_rules` :34-39.
- test_scope_core.py:151-152 (the `scope:cb_atoms_of` assertion). rows_tpl.rs lines as in HANDOFF-sa-port-231.md.

## Watch
- Trial merge with origin/port/state-part3 (0377452) was clean (`git merge-tree`), though both edit session.rs,
  session_glue.rs, compile_loop.rs, query.rs, budget.rs.
- Slice tests: run per file under Rust (`$PY -m pytest -q -p no:cacheprovider FILE` from rust-spike/slice with the clone's
  PYTHONPATH); `-n 4` over several files ran nothing here.
- The budget workload takes about 15 minutes on Python.
- Plants 607-629 and counters 645-659 are free; 661-669 and counters 670-679 are free for the cbm_noid item.
