# HANDOFF sa-port-339: witness check, land-only step: everything read, Status: question on one point; NOTHING IS LANDED

Branch port/witness-check, worktree ~/sa-rust-ids-work/sa-port-328/wt (clone ~/dev/sa-port-19), on rust-slice 32ba9a3.
Bar SHA 786410d (also origin `bar/witness-check-786410d`, kept); suite by id, order runs, plants and repeat check on
**81e6561e, the SHA to land**; venv .so cad764d46471b1c6, bench .so 0982a28074215658. This step changed no source and
no test; its commit holds results/witness-check.md (header, section 12), results/tools339 and this file.

## The question (the only thing between this and the landing)

The planner's addition (2): Status: question if the bar's suite rows show anything other than the 21 [149] ids and
the known base rows. The 786410d bar's `suite-witness:on` row shows **the 7 ids of section 8 and none of the 21**. The 7
failed in the one worker that ran test_p4_review.py's leaking test before all 102 ids of test_witness.py; none of the
21 ran after `[template]` in any worker of any row. On 81e6561e the 7 pass (24 order runs, suite by id both backends).
I read the condition as not met as written and did not land. If the ruling is "the 7 are known, land": step 1 below.

## Read and decided (results/witness-check.md section 12 has the tables)

- (a) 338's suite by id on 81e6561e: python on/off/base 0 ids differ; rust 1 id, the planted-history test (base
  failed, off passed, on failed). Repeat check rerun on 81e6561e (pareto1): Rust plain 0 of 20 off and on, keep-alive
  20 of 20; Python plain 20 of 20 off, 19 of 20 on, keep-alive 20 of 20: the known id()-reuse flake's shape.
  24 order runs: 538 passed, seven_passed 7/7 each.
- (b) 337's bar on 786410d: valid (END 0, .so cad764d4, direct.txt exit 0, no "suite: no rows"). Plain suite against
  base: changed outcome 0. witness:on MATCH on 17 workloads, answer_diff 0 against off. 749 and 750 caught by answers;
  751 by answers on core and zero; 752 and 754 MATCH on workloads. Suite rows: 752 caught by test_ddmin only (the 12 P1
  cases ran after a leaked template and passed under the plant: masked); 754's row is confounded by the leak.
- Planner's addition (1), 81e6561e, SLICE_WITNESS=1, test_witness.py alone: no plant 103 passed; 749/750/751/752/754
  fail 6/45/4/9/6, the same on orion python, pareto1 python and pareto1 rust.
- Wall times: bar 90 m 07 s; rows in section 12.

## Not done, in order

1. On a ruling to land: `cd` the worktree, `bash rust-spike/slice/p1/bar.sh land 81e6561e` (read it; dry run passed
   here, see the report), then `PUSH=1 bash rust-spike/slice/p1/bar.sh land 81e6561e`. If the guard refuses, Status:
   question; do not bypass. Then `git push origin --delete bar/witness-check-786410d`, set the header of
   results/witness-check.md to LANDED with the SHA, and report. Rule [91]: not while another session's full bar runs.
2. OWED to name: [148], [149] as ruled; Engine.stats' 13th key on the default path; ent_record_certified has no tick;
   bar.sh witness rows have no plant-fired counter ([147]); a void bar exits 0 (337). New: under xdist a test that
   leaves a user's template on the default registry masks plant 752's P1 cases and confounds 754's suite row (fixed
   for test_witness.py by 81e6561e's fixture; any future leaking test elsewhere is contained the same way).

## FILE:LINE MAP

- results/witness-check.md: header :3-22, section 4 (plants), section 7 (repeat check), section 8, section 12 (this step).
- results/tools339/: workers339.py (per-worker order of a bar's suite rows; run on pareto0 against
  ~/sp19/sa-rust-ids-work/sa-port-337/bar), plants339.sh (plants on test_witness.py and the repeat check on a frozen
  tree), go339.sh, workers-337bar-786410d.txt. Outputs: orion ~/sa-rust-ids-work/sa-port-339/{orion/out,p1}.
- rust-spike/slice/p1/bar.sh: land :3-4 (usage), the guard and PUSH :64-73.
- The rest: HANDOFF-sa-port-338.md's map (tests), -337's (bar reading), -336's (bar.sh, tools336), -333's (source).

## Must stay in every report

Tested SHAs (bar 786410d, suite by id 81e6561e) and .so cad764d46471b1c6 / bench 0982a28074215658; SLICE_WITNESS off by
default and the unchanged path the default, except Engine.stats' 13th key witness_certified, 0 with the switch off; no
SymPy construction or evaluation at query time; "exact" rests on 325's 14-predicate table (issue 247); bar row wall
times (section 12); known base rows by id (section 12); S1 is the landing measure (fuzz -28.2% py, -19.2% rust; dev
-2.7% py, +1.1% rust), shares from shared-lease runs are not wall times; the Rust change (entry.rs KEYS 13,
ent_record_certified without a tick); the planted-history test's Python rate with the switch on (1 of 20 plain runs
failed on 786410d and again on 81e6561e, keep-alive 20 of 20).
