# HANDOFF sa-port-336: witness check, (b) done, tree frozen at 786410d, three jobs running detached

Stopped at the context budget (190k note) after launching the jobs; NOTHING IS LANDED and no result has been read.
Branch port/witness-check, worktree ~/sa-rust-ids-work/sa-port-328/wt (clone ~/dev/sa-port-19), on rust-slice 32ba9a3.

## Done

- (b) 786410d (pushed): p1/bar.sh `witness:on` (SLICE_WITNESS=1 alone) and `witness:NAME` (SLICE_WITNESS_PLANT=NAME
  plus the switch), in PLANTS and SUITE_PLANTS. A certified query makes no session, so a witness row DIFFERs from
  Python-off in state (dev on orion: answer_diff 0, session_count_diff 161, stats_diff 1939). bar.sh therefore
  compares a witness workload row with this run's Python under SLICE_WITNESS=1 (WL-pywit.jsonl; the verdict; dev on
  orion: MATCH, every count 0) and a second time with Python-off (.offcmp); bar_sum.py prints that as the table
  "== witness rows" (answer_diff, msg_diff, session_count_diff, answers_sha, wall s). Simulated on orion, dev only:
  witness:on MATCH / answer_diff 0; witness:single DIFFER / answer_diff 627 (sha 52d6bc53c55fc204); skip-own MATCH.
- THE FROZEN TREE IS 786410d (da6eb2ee plus bar.sh and bar_sum.py). It is also origin `bar/witness-check-786410d`,
  which is what the bar checks out, so commits on port/witness-check (this file, results/) do not move the tested SHA.
- (a), partly: on orion, python, tests/test_memos.py + test_invariants.py + test_registry_versioning.py: 70 passed, 1
  skipped, 1 xfailed with the switch off and on. No row was needed in harness/state.py or tests/test_memos.py for the
  13th key or `_TEMPLATES`/`_THEORIES` there; the full suite (below) decides.
- Builds of 786410d's crate on pareto1 (build336.sh): venv build cad764d46471b1c6 (suite, iv, bar), bench-image build
  0982a280742156581 (S1 only). Base 32ba9a3 uses sa-port-334's c20c326f (crate source-equal to f4ce4b2, checked).
- results/witness-check.md: section 3 only ((f) and the Rust change), committed with this file. Sections 1, 2, 4
  (plant 754), 5, 8, 10, 11 are NOT updated.
- `_users_knowledge`, orion, dev (uk336.py): 159 calls a pass (= certified), median 10.6 us py / 14.3 us rust, 2 ms a
  pass; bare 7.6 us a call with 34 templates loaded. The S1 lease writes the pareto1 numbers to timing-r1/uk.jsonl.
- The witness call in sympy_api._engine_ask is outside any try: an exception from it is not caught quietly.

## Running detached (orion launchers under setsid; read the end markers, all under ~/sa-rust-ids-work/sa-port-336/)

1. S1: gos1336.sh 786410d r1, pareto1 quiet lease. END: gos1-end-r1.txt. Read timing-r1/med.txt (medians, on/off per
   arm, digests), timing-r1/uk.jsonl, load.txt, err.txt (must be empty), env.txt (.so 0982a280).
2. Suite by id on/off/base x rust/python, then pre336.sh (dev and fuzz digests off/on and under the five plants,
   test_witness.py, the repeat check), then iv336.sh (128 runs): go336.sh 786410d 32ba9a3, pareto0 shared lease. END:
   go-end-786410d.txt. Read job-786410d/suite-cmp.txt, iv-cmp.txt, pre/dig/dig.jsonl, pre/tw/*.log (tail),
   pre/rep/rep-sum.txt.
3. The bar: chain336.sh waits for 2's end marker, then gobar336.sh 786410d (job336bar.sh on pareto0, about 2 h; BASE
   sa-port-334's bar suite rows on f4ce4b2). END: gobar-end.txt. Copied back to sa-port-336/bar/ (bar/bar/sum.txt,
   bar-end.txt, env-summary.txt). Wall times: `python3 tools/wall336.py bar/bar`.
   If 2 shows something (a) must fix in source, the bar on 786410d is void: stop it, fix, refreeze, restage, rerun.

## Not done, in order

- Read 2; finish (a): update witness-check.md sections 1, 2, 4, 8, 10, 11.
- (2b) verdict from 2: any moved answer or id is Status: question.
- (3) verdict from 1: fuzz must gain beyond the spread; a Python dev loss beyond the spread is Status: question.
- (4) read the bar: witness:on rows MATCH against pywit and answer_diff 0 against off on all 17 workloads; 749 and 750
  caught by answers; 751, 752, 754 by kept tests in their suite rows; quiet handler rows; wall time per row.
- Land: `bash rust-spike/slice/p1/bar.sh land 786410d`, then PUSH=1. Delete origin bar/witness-check-786410d after.
- OWED to name: Engine.stats' 13th key on the default path; ent_record_certified has no tick; bar.sh's witness rows
  have no plant-fired counter (their catches are answers and kept tests).

## FILE:LINE MAP (786410d)

- rust-spike/slice/p1/bar.sh: penv :91, pref/woff/pywit :93-104, plants phase :165-171, extra :181-190.
- rust-spike/slice/p1/bar_sum.py: the "== witness rows" table, just before "== suite plants".
- rust-spike/slice/results/tools336/: stage336.sh, build336.sh, go336.sh, job336.sh, pre336.sh, iv336.sh, gos1336.sh,
  onlease336.sh, time336.sh, uk336.py, gobar336.sh, job336bar.sh, chain336.sh, wall336.py (copies run from
  ~/sa-rust-ids-work/sa-port-336/tools/).
- The rest is HANDOFF-sa-port-333.md's map (da6eb2ee), unchanged: witness.py, sympy_api.py:1136-1141,
  engine.py:1402-1409 and :1429, entry.rs KEYS :47, ent_record_certified :343 and :903.
- witness-check.md: section 4 :190, section 5 :211, section 8 :308, section 10 :377 (after this commit's +15 lines).
