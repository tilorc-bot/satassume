# HANDOFF sa-port-214: 6i(b), port/6i-b at fe250ff (tested), bar running, unlanded (week 90%)

- **fe250ff:** test_knowledge_f6_fallback.py's Float cases check the whole-query refusal (`refused:algebra: Float`, kept
  path). New test_knowledge_fn_direct.py: direct tests of fn_tpl.rs's guards, with the shared `_common._CACHE` cleared per
  side. Both plants are caught.
- **Probe (all 15 workloads, fe250ff):** functions.py has 0 per query everywhere. Base `~/sa-rust-ids-work/sa-port-212/probe/base`,
  cand `~/sa-rust-ids-work/sa-port-214/probe/cand`; summarise with `python3 ~/sa-rust-ids-work/sa-port-212/fnsumm.py DIR`.
- **fn:value:sympy pairs:** `~/sa-rust-ids-work/sa-port-214/vpairs-nocache.txt`. 265 distinct pairs on value, 0 elsewhere,
  all inside offline_data.json's unread `value_units` table.
- **Bar:** pareto1 `~/sp19/sa-rust-ids-work/sa-port-214/bar-6ib`, end marker
  pareto1:/home/tilo/sp19/sa-rust-ids-work/sa-port-214/bar-6ib/end.txt. Base suite rows: sa-port-208/bar-s2/suite.
  At 15:59Z, build, tests (811 passed, 4 skipped), suite, live and plants had exited 0, as had DIRECT.
- **Next:**
  1. Read sum.txt. Fill in results/port-6i-b.md's bar sections in port-6i-a.md's form, and add fallbacks with
     `python3 ~/sa-rust-ids-work/sa-port-212/fbcounts.py BAR_DIR`.
  2. Edit the TSV row for `_value_units`.
  3. After 04:00 UTC 10 Nov, with the week reading below 90%: `bar.sh land fe250ff`, then with PUSH=1.
