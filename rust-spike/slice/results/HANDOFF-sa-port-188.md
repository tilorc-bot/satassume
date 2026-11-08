# Handoff sa-port-188: step 5c10c (cones and construction), issue 323

## Done
- **Doc step (planner's ask):** INVENTORY-state.md (~/sa-rust-ids-work/sa-port-147/, not in git) :302-312 records the five
  reader sites that keep Session.solver/xfer/truncated on Python, checked at 4215655: none moved. Function names corrected
  against report 7a65a8b: relations.py:1689 is `_engage_transfer` (writes `s.xfer`), :1812 is `sync_transfer`, :1851
  `_xswitch`; engine.py:2145 `_put_result`, :2248 `_note_budget`.
- **Code (port/5c10c, fc0ae3a on 4215655, pushed):**
  - budget.rs: `struct_` (`_struct`), `cone_info` (`_cone_info`), `drop_cones` (`_drop_cones`) + pyfunctions `bud_struct`,
    `bud_cone_info`, `bud_drop_cones`; `union` calls `cone_info`/`struct_` directly (bud:cb_struct, bud:cb_cone_info now 0).
    5c9c's plants `em-kids-set-drop` and `em-qcones-clear-skip` moved onto Rust's own writes (store_kids, drop_cones).
    `budget_of` now None past 2**60 (Python fallback keeps `budget + 1` exact).
  - engmemo.rs: slots 8 `_cones` (map) and 9 `_constructing` (set as map to None; `remove`, py `add`/`discard`/`update`;
    `set_add`/`set_discard`/`contains` for Rust; convert takes a Python set). compile_loop.rs core_visit uses them directly.
  - session_live.py: `_BUDGET_METHODS` += the three rows; `CONE_SLOTS`, `ALL_SLOTS`, `cones_native()` (SLICE_CONES, default
    rust); `_install_engmemos` indexes slots by `ALL_SLOTS.index`; `_CONE_PLANTS`.
  - Counters 288-300 (session.rs NAMES now 301): em:py_cones, em:py_constructing, bud:struct, bud:cone_info, bud:drop_cones,
    bud:cb_templates, bud:cb_ext, bud:struct_wide, bud:kids_hit, bud:cones_hit, bud:py_struct, bud:py_cone_info,
    bud:py_drop_cones. Plants 223-230 (relations_core.rs): cn-discard-skip (223, the inventory's: a node left in
    `_constructing`), cone-struct-weight-one, cone-info-over-fits, cone-drop-skip-cones, em-cones-store-drop,
    cone-kids-no-bound (test-only), cone-cones-no-bound (test-only), cone-struct-wide-skip. The 6g stack adds no numeric
    counters or plants (its plants are named term plants in rows_tpl.rs), so no collision.
  - memo_check.py: `_cones`, `_constructing` join ENGMEMOS (`CONEMEMOS`); `bud:` counters kept; works on base trees.
  - test_cones_core.py (new): Python vs Rust; 10 passed on orion (every plant fires and moves a case; bounds driven directly).
- **Local results (orion, ~/sa-rust-ids-work/sa-port-188/):**
  - Switch digest, base 4215655 Rust (worktree `base/`, own build) vs 5c10c Rust, PYTHONHASHSEED=0, this step's memo_check
    copy (`bin/memo_check.py`): **MATCH on dev, fuzz, loop, zero, cert, scope** (`mc/{base,new}`); dev answers c9cf2db177fb842d,
    digest fa58cc766d98d539, equal to 5c10b's row.
  - Plant pass, memo_check rust on dev/loop/fuzz vs unplanted (`pl/`): 223 caught by answers and state on dev, fuzz, loop;
    227 caught by state (digest, em_sizes `_cones`) on all three; 224 caught on loop (em_content `_kids`), fires 0 on dev and
    fuzz (no node has both compiled patterns and formulas there); 225 and 230 fire 0 on all three (no over-budget walk / no
    sum wider than the default budget); 226 fires once per run but MATCH (the one `_drop_cones` runs with `_cones` empty).
    225, 226, 230 are caught in test_cones_core.py (budget 3/6, settings change, wide sums).
  - Suite subset under rust_plugin (test_writeback_provenance, test_memos, test_layering, test_p4_review, test_engine): 130
    passed, 3 failed, all three the provenance stubs (`NotImplementedError: the Rust solver has no provenance`, `_cowner`),
    i.e. among the 46 named stub failures. `test_cone_info`-style reads (test_writeback_provenance.py:444-454) pass through
    the view unedited.
  - test_engmemo_core, test_discovery_core, test_compile_loop_core, test_context_core: pass (54 passed, 3 skipped with mine).

## Left
1. Wait for the 6g stack (sa-port-187) to land; never land or start the bar while its bar runs. Rebase port/5c10c onto
   origin/rust-slice, rebuild, rerun test_cones_core.py.
2. Read STATUS.md's "90% about" line; the bar must end 1 h before it (5c10b's bar took 48 min).
3. Bar on pareto1 as in port-5c10b.md: PLANTS="cn-discard-skip cone-struct-weight-one cone-info-over-fits
   cone-drop-skip-cones em-cones-store-drop cone-struct-wide-skip", WLS="loop zero cert scope", SUITE_PLANTS=zero, TESTS =
   5c10b's list (pareto1 ~/sp19/sa-rust-ids-work/sa-port-186/bar-5c10b/config.txt) plus test_cones_core.py,
   DIRECT="relations_direct.py 300 0", BASE = the stack's landing bar suite.
4. Report results/port-5c10c.md in port-5c10b.md's form; port-ownership.tsv rows 79-81 (`_drop_cones`, `_struct`,
   `_cone_info` -> landed 5c10c, Rust) and 821-822 (state `_cones`, `_constructing` -> Rust-native, readers past 5c10c:
   `is_` :1998/:2001, `is_many` :2047/:2049 by view, em:py_cones/em:py_constructing, removed by 5c10d; `_Mark.add`/`rollback`
   term_live.py :156/:189-190, removed by the state step); row 814's crossing text (em:py_kids from `_struct`) is now gone;
   port-ownership.md :53 and a header line. Module count from ~/dev/architect/STATUS.md "Counted modules".
