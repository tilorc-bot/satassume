# HANDOFF sa-port-361 (20 Nov, ~14:45Z): ruling (a) applied, pre-bar checks clean so far, the bar chained detached; a land-only step is left

Branch port/measured-next, pushed to the clone's origin. Worktree ~/sa-rust-ids-work/sa-port-356/wt in clone
~/dev/sa-port-5. Output: ~/sa-rust-ids-work/sa-port-361 on orion (pareto0 ~/sp19/sa-rust-ids-work/sa-port-361 and
~/sp19/dev/sa-port-361; pareto1 ~/sp19/sa-rust-ids-work/sa-port-361).

**TESTED SHA 5b20d1f2** = 00535462 plus the ruled one-line change of p1/convert_diff.sh (a shared bar tool, guarded
source). The crate is unchanged from 00535462 (`git diff --quiet 00535462 5b20d1f2 -- rust-spike/slice/solver_rs`), so
the .so are 359's builds: x86-64 venv 0f78ac2962f34b3a (the bar; orion sa-port-361/so/sa_solver-5b20d1f2.so), x86-64
bench 8b8041d3fe6223c2 (S1), aarch64 4d8921d9c510e99f. Base de88d9b9: venv 37b7560e245df518, bench 0b6f073f5c5a600b,
aarch64 e0365239348de148. Frozen branch: origin/bar/measured-next-5b20d1f2 (head 5b20d1f2).

## RUNNING DETACHED when this was written
- orion: `tools/chain361.sh 5b20d1f2 0f78ac2962f34b3a` (setsid; a copy of results/tools361/chain361.sh in
  ~/sa-rust-ids-work/sa-port-361/tools). It waits for pre-end.txt (gopre361.sh's marker; the pre job on pareto0 had
  only lra's last answer run left, about 15 minutes), then starts the bar with gobar361.sh ONLY IF cond3.txt is 4 of 4
  passed, convdiff/total.txt says differences 0 and `exit 0`, and its last line is `workloads 20; answer rows 60,
  MATCH 60`.
- **ONE end marker for both outcomes: ~/sa-rust-ids-work/sa-port-361/gobar-end.txt.** `NO-BAR reasons` is written by
  chain361.sh:18; `END rc <pareto0 bar-end.txt line 1> | time` by gobar361.sh:19 after the bar's small files are
  copied to sa-port-361/bar. On pareto0 the job's own marker is ~/sp19/sa-rust-ids-work/sa-port-361/bar-end.txt
  (job361bar.sh:62 `END rc time so8 head`, :65 `WATCHER-END`). chain.txt on orion says when the bar was started.
- gobar361.sh and job361bar.sh had NEVER RUN before this (tools360's, with paths changed; gobar361.sh:12 now reads the
  job from sa-port-361/tools). If the marker says END with a non-zero rc within minutes, read bar-launch.log,
  gobar.out and bar/bar.log's first lines before anything else. The last bar (354's, without convdiff) took 1h35m; the
  convdiff phase adds about 1h40m (lra) plus five plant differentials on dev and fuzz.

## Done by 361 (results/measured-next.md (6))
1. Ruling (a): 5b20d1f2. Condition 2: p1/bar_sum.py reads handler rows only from the bar's suite, live and extra rows
   (:28, :73, :107, :118, :161), never from convdiff; p1/bar.sh suite() :131 keeps the plugin.
2. Condition 3: the id at tests/test_noncommutative.py:546 under the bar's exact suite invocation, head and base,
   SLICE_CONVERT=py and =rust: 1 passed in about 1 s in all four cells (and in the four `-n 0` cells). Same on head and
   base: a footnote with [157].
3. Condition 4: the rerun differential from the changed script: 69,527 inputs, 0 differences, 14,267,639 reads, slow 1
   (the known row), reread 100 (rootof `finite`, the known row of convert-step.md:129), exit 0; suite alone 40,166
   inputs, 0 differences. Answers 57 of 57 MATCH when written; lra's 3 rows pending: READ pre-end.txt (it must say
   `answer rows 60, MATCH 60`; chain361.sh checks it).
4. The probe count: stays 21 of 32, convert.py does not start to count (default path equal to base in every probed
   file, 0 rows differ; under SLICE_CONVERT=rust convert.py 2,272,599 -> 58,980 calls over the 20 workloads).
   tools361/pc-tab.txt.

## Not done
- Read the bar (sa-port-361/bar on orion): every row, the plant table (each plant caught by an independent check),
  kept.txt ([700-too-deep] PASSED in plain pytest, 7 lines), convdiff/total.txt (differences 0) and
  convdiff-plants.txt (768-772 each differences > 0), so-loaded/build.txt (0f78ac29), env-summary.txt, sum.txt; [137e]'s
  keep-alive check if the planted-history test shows (a28c548's method; pareto0 sa-port-359/s1/plug/test_keepalive185.py).
- bar.sh land 5b20d1f2 in the worktree, read the incoming diff, the guard, PUSH=1, rule [91]; tell the architect
  rust-slice moved. measured-next.md (7): the bar and the landing.
- OWED items to name in the report: the memory-only base row (360's current() check); the 15 plugin-mode ids
  ([157](b)), undiagnosed; [157] itself now also explains why the differential's suite pass runs without the plugin.
- `git worktree remove ~/sa-rust-ids-work/sa-port-357/base` (clone -5) after the landing.
- Leases: the pre job's shared lease on pareto0 ends with the job; the bar takes its own (machine run).

## File:line map
- results/measured-next.md (6): the ruling, conditions 2-4, the probe count, the bar's launch. (4)(5): 360's reads.
- results/tools361: stage361.sh (trees on pareto0, no build), pre361.sh and gopre361.sh (conditions 3 and 4),
  gopc361.sh, pctab361.py, pc-tab.txt (the probe), job361bar.sh (rows :42-:52, kept.txt :56-:61, markers :62, :65),
  gobar361.sh (checks :8-:9, the lease :15, copy back :18, marker :19), chain361.sh (checks :13-:17, NO-BAR :18).
- p1/convert_diff.sh: the comment :21-:24, the suite pass :25, total :27, answers :29-:31.
  p1/bar.sh: land :50-:76 (guard :59-:64, PUSH :66-:75), suite() :123-:132, convdiff :228-:236, sum :237.
  p1/bar_sum.py: handlers() :26-:28, suite numbers :73-:80, live :107-:113, extra :118.
- Output on orion, ~/sa-rust-ids-work/sa-port-361: pre-5b20d1f2/ (cond3.txt, cond3-n0.txt, convdiff/total.txt,
  answers.txt), pre-end.txt, pc-5b20d1f2, pc-de88d9b9, pc-tab.txt, so/, chain.txt, gobar-end.txt, bar/.
- How the last bar was read: results/witness-native.md (7), :368 onward.
- Everything else: HANDOFF-sa-port-360.md "File:line map", then 359's, 358's, 357's, 356's. Plants from 774, counters
  from 747 (this step used none).
