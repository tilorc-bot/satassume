# HANDOFF sa-port-216: 6i(b), port/6i-b rebased on db7130a, bar 2 on e817aa1 running, unlanded (rule [91])

- **Bar 1 (fe250ff on 80665b5) read and written up** in results/port-6i-b.md (024f465): all phases exit 0, suite
  new/gone/changed 0, 13 workloads MATCH, plants 340-345 caught live, fallbacks and kept shares filled, value scaffold +48.
  Copies: `~/sa-rust-ids-work/sa-port-216/bar-6ib/{sum.txt,fb-cand.txt}`, base `~/sa-rust-ids-work/sa-port-216/fb-s2.txt`.
- **TSV:** `_value_units` (functions.py:421) reclassed "offline table plus per-query callback on a miss"; port-ownership.md
  section-2 note too.
- **Rebase:** origin/rust-slice 80665b5 -> db7130a (harness fix). Incoming diff: live.py, test_live_handler_plant.py,
  results/. Guarded, so **bar 2** on **e817aa1** (code = 186ae10): pareto1 `~/sp19/sa-rust-ids-work/sa-port-216/bar-6ib`,
  END MARKER pareto1:/home/tilo/sp19/sa-rust-ids-work/sa-port-216/bar-6ib/end.txt. Wrapper `run-bar-6ib.sh` there (orion
  copy `~/sa-rust-ids-work/sa-port-216/`), base suite `sa-port-209/bar-install-order/suite`, PLANTS = six fn-* +
  ctx-check-raise, TESTS + test_live_handler_plant.py. At 04:55Z build, tests, suite, live had exited 0.
- **Next:** read bar 2's sum.txt; replace `BAR2_SECTION` (port-6i-b.md:101) and `BAR2_LANDED` (:56); land after both
  sa-port-217's bar and sa-port-215's bar-6ic end (rule [91]); `bar.sh land e817aa1` (results-only commits on top are
  outside the guard), then PUSH=1.
