# HANDOFF sa-port-230: state part 3. Rebased onto (iii); sub-part 5 first part done (solver readers, scalars, direct calls); containers, probe, bar open

Branch port/state-part3, rebased onto origin/rust-slice 3203cb4 ((iii) landed, tested ba1ca22). Unbarred, unlanded.
Old head before the rebase: 55ca91a (local branch backup/state-part3-55ca91a). Results so far:
rust-spike/slice/results/port-state-part3.md (sub-parts 1-4, 6; not yet updated for sub-part 5).

## Done (sa-port-230)
- Rebase: one conflict, session.rs NAMES/COUNTS. Kept (iii)'s entries to 525, padded 526-554 "reserved:N", th:* at 555-558.
  Incoming diff c822173..3203cb4: 41 files, +4272/-210 (relkeys.rs new, relations_core.rs, session.rs, session_glue.rs,
  session_live.py, term/*, wiring.py, relations.py): it changes code every run executes, so the bar is a full one.
  Check after the rebase, before sub-part 5: 341 passed (test_theory_flags, test_install_order, test_rs/rd/rl_core,
  test_relations_core, test_discovery_core, test_core_derived_args), ~/sa-rust-ids-work/sa-port-230/rebase-check/.
- ebdf52e, sub-part 5 first part:
  - Rust's 15 `Session.solver` reads go through session.rs `solver_of` (the core's copy). A session with no core is read by
    attribute and counted `sb:attr` (0 in test_session_boundary; not yet read on the workloads).
  - `truncated`, `_link_pending`, `_neg_shared`, `sel`, `n_hold`, `verdict` are SessionCore scalars (`SS_NAMES`, struct
    `SesScalars`); `Session`'s attributes are views with a record method (session_live `_ses_sview`, `_SES_SVIEWS`). This
    closes OWED [100]'s two open sites in code (entry.rs:511, budget.rs:580 read the core); the report still owes the line.
  - **Correction to the inventory:** `_neg_shared` is not dead. session.rs `dvar_def` reads it and session_glue.rs
    `assume_formula` writes it; no workload reached the read. It moved into the core instead of being dropped. The writes of
    `defvars`, `_dv`, `_dv_node` are dropped (Rust's `St` holds the live state; Python's Session keeps its own).
  - `_interpret`, `_link`, `_share_guard` (relations_core.rs) and `_visit` (compile_loop.rs) are called directly from Rust
    through session.rs `named`: direct while the attribute is still session_live's own frame, by name when it was replaced.
  - **Wrappers that do more than forward (all four, not deleted):** `_rel_interpret`, `_rel_link`, `_rel_share_guard`,
    `_ses_visit` each pick Python's copy for a session with no core (satassume/ref.py keeps Python's VarTable) and are the
    by-name hook that a test's override (tests/test_session_limits.py `_object_case` for `_visit`) and SLICE_REL/LOOP=py
    replace. Rust no longer runs them (`sb:fwd_direct` counts the direct calls, `sb:fwd_named` the by-name ones, 0 in the
    test). They stay on the class for Python callers. No unruled callback found; no question sent to the planner.
  - Counters 559-564 (`sb:attr`, `sb:fwd_direct`, `sb:fwd_named`, `sb:scalar_core`, `sb:scalar_view`, `sb:scalar_record`);
    NAMES/COUNTS are 565. Plants 431-438 (`sb_plant`; session_live `_SB_PLANTS`): sb-truncated-stale, sb-link-pending-stale,
    sb-neg-shared-stale, sb-sel-zero, sb-hold-zero, sb-verdict-none, sb-fwd-skip-link, sb-solver-fresh.
  - test_session_boundary.py: 13 tests. Rust equals Python on 8 sets (answers, scalars after `_build_context` and each
    `_ask`, `Engine.verdict`, a truncated session's complete check); views equal the core's export; all 8 plants fire and are
    caught. 12 passed before the last test (`test_rust_repeats`) was added; that one runs in the slice run below.
- The slice test files on ebdf52e's tree (50 files; test_cf_diff.py is a script that exits at import and broke the first
  attempt, slice-5a): started detached, **not read**. End marker
  orion:~/sa-rust-ids-work/sa-port-230/slice-5b/end.txt, log pytest.log beside it. test_install_order.py may object to the six
  new `Session` properties install() adds (its install list has 191 entries): add them to the list with a test each if so.

## Not done
1. Read slice-5b; fix what it shows.
2. session_live module-wide probe, **before and after**: neither was run. Before = e90a0d1 (the rebased head without
   sub-part 5), after = the sub-part 5 head. `PYCALLS_FILE=rust-spike/slice/session_live.py` with pycalls.py on the seven
   workloads (fuzz dev zero loop scope budget cert); recipe: orion:~/sa-rust-ids-work/sa-port-229/readouts.sh (clone two
   trees under pareto1:~/sp19/dev, build each, `machine run pareto1 --shared`). Report `sb:*` per workload beside it.
3. Sub-part 5's containers into SessionCore: `frontier`, `pending`, `pending_c`, `demand`, `deferred`, `literals`,
   `_groups` (inventory rows in port-state-part3.md sub-part 1; node-keyed, so RelKeys ids per the RelKeys ruling). Rust
   sites by `rg '"(frontier|pending|pending_c|demand|deferred|literals|_groups)"' solver_rs/src`: discovery.rs 25,
   session_glue.rs 10, compile_loop.rs 10, query.rs 2, euf_py.rs 1. (iii)'s RSet/RDict/RList in relkeys.rs are keyed by a
   `Relations`; a session-owned set needs its own owner record. `relations`' reference held by the core is also open.
   Plants 439-449 and counters 565-579 remain.
4. Digest: cherry-pick digest/split-order 0e41490 (on c931c16), extend per the planner's (A)/(B) rulings in the brief, add
   twin to WLS, rk-class-split to PLANTS, test_moved_digest.py to TESTS. Tell the architect and sa-port-234 when taken.
5. Full bar on the merged tree (rust-spike/slice/p1/bar.sh; suite by id against base with the three numbers, dev/fuzz
   MATCH, plants 420-438 on dev/fuzz, handler rows, kept shares, fallbacks incl. ad:cbm_noid, kept_product mismatch once
   the counter exists), memo-cost timing on a quiet pareto1 lease, then land (`bar.sh land`, no PUSH first) and report.
6. results/port-state-part3.md: add sub-part 5 (the list above, the `_neg_shared` correction, OWED [100] closed sites).

## FILE:LINE MAP (at this head)
- rust-spike/slice/solver_rs/src/session.rs: :17 NAMES[565]; :687 SS_NAMES; :696 SesScalars; :711 sb_planted; :734 solver_of;
  :749 ses_flag; :773 ses_int; :797 ses_verdict; :825 named; :910 core_of; :959 SessionCore::flag (set_flag, int, set_int,
  verdict, set_verdict follow); :1747 ses_field; :1759 set_ses_field; :1771 ses_snapshot
- relations_core.rs :2277 (_share_guard), :2351 (_interpret), :2378 (_link, plant 437); compile_loop.rs :440 (_visit)
- session_glue.rs init ~:28-70 (scalar and dead writes removed), assume_formula ~:90-125, link_set ~:130, assumption_lits ~:150
- context.rs :100/:145/:195/:207/:250 verdict, :295 truncated; entry.rs :511, :802; budget.rs :580; discovery.rs :220
- rust-spike/slice/session_live.py: :206 _ses_sview, :226 _SES_SVIEWS, :1031 _SB_PLANTS, :1313 install(); wrappers
  `rg 'def _rel_|def _ses_'`
- rust-spike/slice/test_session_boundary.py; test_theory_flags.py; test_install_order.py; pycalls.py; p1/bar.sh
- satassume/engine.py:304 class Session, :813 escalate, :972 link_set, :2268 _note_budget, :2278 _NEG_SHARED
- OWED: ~/dev/architect/OWED-satassume-rust.md [100], [108], [109], [110]
- Outputs: orion:~/sa-rust-ids-work/sa-port-230/{rebase-check,slice-5b}; 229's on pareto1:~/sp19/sa-rust-ids-work/sa-port-229/
