# HANDOFF sa-port-100: 5c2 first part on port/5c, bar running (issue 323)

port/5c at 3246bb4 (pushed); rust-slice at 653d932 (5c1). Clone /home/tilo/dev/sa-port-7.

## Done
- `compile_loop.rs` (new): module `want_of`, `_split` (memos `_WANT`/`_SPLIT` stay Python dicts, read by module getattr each call), `_emit_pattern`, `_flush`, `_compile`, `_compile_pending`, `_compile_patterns`. discovery.rs now calls `_flush`, `_compile`, `_emit_pattern`, `_compile_pending` in Rust, not by name. Counters ses:want_of..ses:compile_patterns (session.rs 58-64, NAMES 65). Plants 38-44: drop-split-later, drop-emit-ment, drop-flush-custom, drop-compile-demand, drop-pend-compile, want-empty, drop-pat-demand (relations_core.rs; `_LOOP_PLANTS` in session_live.py).
- session_live.py: `_install_compile_loop` (SLICE_LOOP=py keeps Python's methods; note discovery.rs then still calls the Rust loop directly). `engine._split`/`engine.want_of` switched for every caller (they read no session).
- test_compile_loop_core.py: direct Python-against-Rust test on forged state (forged clauses for `_split`; vocabulary function for a custom predicate so `_flush`'s `_custom` matters; one mentioning the node itself so `_compile_pending` compiles parked formulas). 9 tests; all 7 plants fire and are seen. With test_discovery_core.py: 19 passed on orion (46 s, -n 4).
- Formula objects: read as Python reads them (`atom.expr`, `atom.pred`, `!=`), counted callbacks until the formula step (no boundary conversion here).

## Bar (finished by 22:51Z: lease released after 16m, exit 0; summary is the tail of the orion launch log and pareto1 sum.txt, not read by sa-port-100)
Detached on pareto1: `machine run` PID 517784 on orion, lease "sa-port-100 5c2 bar". Launch log ~/sa-rust-ids-work/sa-port-100/bar-launch.log (orion). Rows: pareto1 ~/sp19/sa-rust-ids-work/sa-port-100/ (sum.txt at the end). Tested source 3246bb4. Command as in the log's header: BASE=/home/tilo/sp19/sa-rust-ids-work/sa-port-96/suite, PLANTS = the 7 above, SUITE_PLANTS=zero, TESTS adds test_discovery_core.py test_compile_loop_core.py, DIRECT="relations_direct.py 300 0". Not read yet: read sum.txt, state the five items, and the void plants (dev/fuzz fired 0) and what catches them (test_compile_loop_core.py's plant tests). Count quiet catches at engine.py:1906.

## Next
1. Read the bar; if it holds, land as "5c2a" (`bar.sh land 3246bb4`, PUSH=1) with results/port-5c2a.md (form of port-5c1.md). Check `git log origin/rust-slice` first: sa-port-99 (wiring) or sa-port-98 (6e) may have landed; this slice touches session_live.py and the crate, not knowledge_live.py or rust_plugin.py. Rebase rule: full rerun only if the incoming diff changes code the runs execute.
2. Rest of 5c2: `_custom` engine.py:707 (26; Relations creation, `engine.stats["scope_misses"]`), `_visit` :572 (40; calls clause_templates, `_extensions.node_facts`, `atoms_of`, `register_block`; then Rust compile_patterns/compile/compile_pending directly), `Session._link` :481 (24; `_dv_node`, `def_implications`). Then switch session.rs `visit_id`'s `_core_visit` callback (session_live.py `_core_visit`, keeps `_constructing` and the census) to Rust `_visit`, and `flush`'s `_custom` call. Plant + direct case per method, appended to test_compile_loop_core.py.
3. Then 5c3 per HANDOFF-sa-port-93.md's split table.

## Map
- compile_loop.rs: want_of, split, emit_pattern, flush, compile, compile_pending, compile_patterns (pub(crate), each ticks its counter), ses_* pyfunctions, register.
- session_live.py: `PY_LOOP`, `_ses_*` wrappers, `_LOOP_METHODS`, `_LOOP_FUNCS`, `_LOOP_PLANTS`, `_install_compile_loop` (before `_install_relations`); install() `undo_loop`.
- test_compile_loop_core.py `_cases()`: split, want_of, emit:*, flush:*, compile:*, patterns:*, pending:*, pending-own:*.
- engine.py: `_visit` :572, `_custom` :707, `_link` :481, `_split` :2311, `want_of` :2340.
