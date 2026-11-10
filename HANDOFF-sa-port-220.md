# HANDOFF-sa-port-220: 6i(b) bar 2 read (clean), rebased on c822173, bar 3 on c59bb1a running, unlanded (issue 323)

## State
- Bar 2 (e817aa1, base db7130a) read: CLEAN. Written up in rust-spike/slice/results/port-6i-b.md:107-183.
  - Suite 5,991 / 127 / 23 (+18 xfailed); new 0, gone 0, changed 1. The changed one is the planted-history test passed ->
    failed: the known id()-reuse flip (a28c548). Passed 5,990 with no firing + 1 named
    (test_ci_stream_reports_only_what_replays). Handler multiset = base.
  - dev, fuzz and 11 WLS MATCH. fn plants as in bar 1.
  - ctx-check-raise caught on all 13 workloads: ctx:caught = complete checks = handler rows. So the plain Rust-side
    ctx:caught 0 on 13 is NOT void.
  - fbcounts deltas against the harness bar (d77d3db) = bar 1's exactly; ad:cbm_noid 0; rows:python = base; kept shares
    = base; scaffold:rebuilt value 221 -> 269 (+48); fn:value:sympy value 264, 0 elsewhere.
- Not landed: rust-slice moved db7130a -> c822173 (sa-port-221, (iii)(a)+(b) first move).
  - Rebase clean -> 797ac0b, plus results-only c59bb1a.
  - `bar.sh land e817aa1` without PUSH: guarded incoming diff in satassume/relations.py, session_live.py, term_live.py,
    relations_core.rs, session.rs, term/{algebra,py,relations,table}.rs, test_relc_core.py, test_term_ids.py.
    harness/state.py also changed. Output: ~/sa-rust-ids-work/sa-port-220/land1.txt.
- BAR 3: pareto1 ~/sp19/sa-rust-ids-work/sa-port-220/bar-6ib3 on c59bb1a.
  - Started 06:15Z 10 Nov under shared lease 08bf9f10; bar 2 took ~80 min, so expect ~07:35Z.
  - END MARKER pareto1:/home/tilo/sp19/sa-rust-ids-work/sa-port-220/bar-6ib3/end.txt.
  - Base suite rows: pareto1 ~/sp19/sa-rust-ids-work/sa-port-217/bar-state-relations-iii-ab/suite (022630c). c822173
    differs from 022630c only by harness/state.py (+2, RELATION_ATOM_IMPL classed). That fixes
    test_module_state_inventory_is_classified, which failed on 217's bar, so expect it as failed -> passed, explained.
  - Plants and WLS as bar 2; TESTS add test_relc_core.py.
  - Launcher: ~/sa-rust-ids-work/sa-port-220/run-bar-6ib3.sh; log at ~/sa-rust-ids-work/sa-port-220/machine-run.log.
- Fallback base for bar 3: run fbcounts.py on a copy of 217's bar's live/ and extra/ *-rust.knowledge.json.

## Map
- results/port-6i-b.md: SHAs :46; BAR3_TESTED/BAR3_LANDED :62; bar 2 :107; BAR3_SECTION :185; fallbacks :187; kept
  :227; probe :251; fn:value:sympy :276; module count :296; not run :304.
- ~/sa-rust-ids-work/sa-port-220/: bar2/ (bar 2 copies), fb-bar2.txt, fb-base209.txt, ctxcount.py (ctx:caught +
  ctx-check-raise handler rows per workload: `python3 ctxcount.py DIR`), land1.txt.
- rust-spike/slice/p1/bar.sh land: :35-57, guard :47.
