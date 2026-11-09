# HANDOFF sa-port-206: harness install order (issue 323), unlanded

Branch harness/install-order, head a653f90 (fix 2b5c763 + results draft), based on c3d0999. rust-slice is now 9e10f0d
(6i(a) 693fef9, state part 2 (ii) 9e10f0d). sa-port-207's full bar for (iii) part 1 (ce1092c) runs on pareto1 until
about 15:15Z. Architect (14:00Z): hold landing until that bar lands (rule [91]; live.py is code its bar runs), rebase onto
what's there, then bar, then land if week < 90%.

## Done
- Fix 2b5c763: rust-spike/slice/live.py, `pairs = load(args.wl)` moved from c3d0999 :332 to just after the
  `engine.Solver = ref.Solver = cls` block (now ~:395), on both modes, with a comment. Nothing else changed.
- Only scope builds an engine while it loads (probe/load.txt); loop (4) and value (2) bump the epoch only.
- audit.py probe on scope (plain and entry): clauses_for 518 -> 0, with_closed_units closure 518 -> 0; left _covers 22
  (+5 genexpr), _load 1 = twopass pass 1. Old-order control reproduces sa-port-203's numbers.
- Reruns, --check entry: scope 12e06b0586faee40, loop 09238b2537e54383, value 3ce3797a267d71a6, all MATCH, py and rust
  jsonl byte-identical old vs new.
- Bar list (20 landings) in results/harness-install-order.md.
- Finding: live.py's SLICE_PLANT_HANDLER plants can't fire on Rust (session_live.py:894 moves _build_context/verdict/
  _complete_check into Rust since 5c10b): 0 on scope and dev under Rust, 166 on scope under Python.
- Overlap: sa-port-205's (iii) part 1 (ce1092c) makes session_live's install rewrap a default engine built before it
  (scope with_closed_units 518 -> 0 product-side). After this harness fix scope no longer builds its engine early, so no
  bar workload exercises that rewrap; it needs its own test (state part 3's "build first, then install" test). Say so.

## Left
1. Wait for (iii) part 1 to land (or 207 to say it won't). `git fetch; git rebase origin/rust-slice` on
   harness/install-order. Check the rebase conflicts in live.py (none expected; (iii) touches session_live.py).
2. Rebuild (`sh rust-spike/slice/build_solver.sh`), quick check: `~/sa-rust-ids-work/sa-port-206/runwl.sh new2 scope`
   (MATCH, digest 12e06b0586faee40 expected unless (iii) changed answers), and rerun the probe on scope at the new head
   (`audit_run.sh new2-entry entry`; read with the python snippet in the report's method: rows with state converted).
3. Full bar on the rebased head (the push guard requires it: guard diff includes incoming source). On orion:
   `git push -f origin harness/install-order` (own branch only), `scp rust-spike/slice/p1/bar.sh pareto1:sp19/bar-sa-port-206.sh`,
   then detached: `machine run pareto1 --shared --wait 4h -r "sa-port-206 install-order bar on SHA" -- setsid env
   BASE=<last landed bar's suite dir, e.g. 207's (iii1) bar suite> PLANTS="ad-lra-not-expr ad-lra-kind-key
   ad-lra-slot-stale ad-lra-flag-key ad-lra-patch-guard ad-lra-pair-swap" WLS="f6 value rootof core opaque scope loop
   zero wiring cert budget" SUITE_PLANTS=zero N=6 TESTS="<copy TESTS from the latest landed bar's config.txt>"
   DIRECT="relations_direct.py 300 0" bash ~/sp19/bar-sa-port-206.sh sa-port-206 harness/install-order`
   with output to a file (never piped to tail). Config of sa-port-200's bar: pareto1
   ~/sp19/sa-rust-ids-work/sa-port-200/bar-state-relations-i/config.txt. Bar takes ~35-75 min. ad-lra-kind-key and
   ad-lra-pair-swap DIFFER on scope in earlier bars: that's the planted bug caught on scope at the new order.
4. Read sum.txt; state the five bar items; fallback reporting (dispatch.rs:242, rows_tpl.rs:413, ad:cbm_noid) and kept
   shares as in recent reports.
5. `agent usage` < 90% then `bar.sh land <tested SHA>` without PUSH, read the incoming diff, then PUSH=1.
6. Fill "The bar and the landing" in results/harness-install-order.md, commit, push; `agent report` Status: done;
   SendMessage the name it prints.

## FILE:LINE MAP
- rust-spike/slice/live.py: install section ~:304-394; load now after `engine.Solver = ref.Solver = cls`; load() :245.
- rust-spike/slice/scope_wl.py:26-37 (install() builds default_engine at :32).
- rust-spike/slice/knowledge_live.py:205-221 (registry.clauses_for -> Rust Dispatch); satassume/engine.py:1330-1341.
- rust-spike/slice/session_live.py:894 (ctx functions in Rust: why handler plants are void on Rust).
- rust-spike/slice/p1/bar.sh:1-62 (usage, land, guard at :44-55).
- Scratch: ~/sa-rust-ids-work/sa-port-206/ (old/, new/, audit/, probe/, plant/, runwl.sh, audit_run.sh, audit.py,
  oldlive/live.py).
