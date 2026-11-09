# HANDOFF sa-port-209: harness install order + Q2 handler plant (issue 323), bar CLEAN, unlanded (week 90%)

Branch harness/install-order, rebased on rust-slice 80665b5 (S2 landed). Tested source d77d3db (fix 268aedc = 206's
2b5c763 rebased; Q2 plant d77d3db); the head after it changes only results/. The full bar on d77d3db is clean (five items
in results/harness-install-order.md, "The bar and the landing"). Not pushed to rust-slice: the week was at 90% at 16:00Z,
and the architect said no landing until the reset (10 Nov 04:00 UTC).

## Left
1. After the reset, with the week below 90% (`agent usage`): in ~/dev/sa-port-19,
   `bash rust-spike/slice/p1/bar.sh land d77d3db` without PUSH. Read the incoming diff. If the guard lists files under
   satassume/ or rust-spike/slice/ (not results/), the incoming diff touches code the bar ran: run a new full bar on the rebased
   head (config: pareto1 ~/sp19/sa-rust-ids-work/sa-port-209/bar-install-order/config.txt, BASE = the latest landed bar's
   suite). Otherwise `PUSH=1 bash rust-spike/slice/p1/bar.sh land d77d3db`.
2. Fill the landed SHA and the incoming diff into "The bar and the landing", commit, push the branch, `agent report`
   Status: done, then SendMessage the name it prints.

## FILE:LINE MAP
- rust-spike/slice/live.py ~:385-410: load() and SLICE_PLANT_HANDLER, both after every install.
- rust-spike/slice/test_live_handler_plant.py (Q2 guard; fails 4 of 6 on the old order).
- rust-spike/slice/solver_rs/src/context.rs:45-60 (patch called by name), :169-191 (handler + handler_row), :264-267
  (ctx-check-raise); relevance.rs:619 (`verdict` by name), :631-638 (`_consistent` handler).
- rust-spike/slice/session_live.py ~:930-960 (_install_context: why a plant before install was void).
- rust-spike/slice/p1/bar.sh:36-62 (land and guard).
- Scratch: orion ~/sa-rust-ids-work/sa-port-209/; pareto1 ~/sp19/sa-rust-ids-work/sa-port-209/ (bar, fb.txt, fbcounts.py).
