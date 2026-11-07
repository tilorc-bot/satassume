# HANDOFF sa-port-96: step 5c1 landed, 5c2 next (issue 323)

rust-slice and port/5c at 653d932 (5c1 landed; tested 7fc958d; report results/port-5c1.md). Clone /home/tilo/dev/sa-port-7.

## Done
- bar.sh's first full run (pareto1, ~/sp19/sa-rust-ids-work/sa-port-96/sum.txt) ran every phase with no fix; 19 min wall for the whole bar with SUITE_PLANTS=zero (3 suite plants). seed1 runs only with SEED1=1.
- test_discovery_core.py: direct Python-against-Rust test of discovery on forged state; its pattern (subprocess per mode, per-step state incl. solver digest, add_internal recorded, a vocabulary function registered for Add to fill `pending`) is the template for 5c2's direct test.
- drop-discover-flush is caught on full dev and fuzz (not on dev's first 200). Void on the workloads: drop-discover-visit, drop-esc-compile, truncated-never (both), drop-esc-deferred (fuzz).

## Next: 5c2, the compile loop (253 lines)
`_visit` 40, `_compile_patterns` 39, `_emit_pattern` 9, `_compile` 22, `_flush` 19, `_custom` 26, `_compile_pending` 37, `Session._link` 24, module `_split` 27, `want_of` 10. Smallest first is a fine order: `want_of`, `_split`, `_emit_pattern`, `_flush`, `_compile_pending`, then `_compile`, `_compile_patterns`, `_custom`, `_visit`, `_link`. `discovery.rs` calls `_flush`, `_compile`, `_emit_pattern`, `_compile_pending` back through Python by name (`s.call_method1`): switch those to Rust calls as each moves. Not started.

## Map
- engine.py: `_visit` :572, `node` :545, `_compile_patterns` :614, `_emit_pattern` :654, `_compile` :664, `_flush` :687, `_custom` :707, `_compile_pending` ~:735, `emit` :539. `_split`/`want_of`: rg `^def _split|^def want_of` in engine.py.
- Rust: discovery.rs (5c1; `node()` is session_live._node's body, calls `core.visit`); session.rs `visit_id` :517 (allocates, then calls the shell's `_core_visit` → Python `_visit`), `emit_direct` :359, `base_get`/`visit` pub(crate). Plants: relations_core.rs consts (5c1 used 30-37), `rel_plant` names, `planted()` :859. Counters: session.rs NAMES.
- Python wrappers: session_live.py `_core_visit` :230, `_node` :195, `_DISC_METHODS` :469, `_install_discovery` :475, `from_env` :567 (`_DISC_PLANTS` must list new plants).
- Plant counter for the direct tests: `counts()['rel:plant_fired']`.
- Bar command: as in HANDOFF-sa-port-93.md step 1 with NAME and PLANTS changed; add `test_discovery_core.py` to TESTS.
