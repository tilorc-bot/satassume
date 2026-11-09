# HANDOFF sa-port-208: step S2 (the rule block), issue 323

Branch port/s2 **bb92b07** (pushed), one commit, stacked on sa-port-207's tested **ce1092c** (state part 2 (iii) first
part, which sits on rust-slice 9e10f0d). Unstacked copy: local branch port/s2-on-rust-slice b09516e (same change on
9e10f0d). Handoff at the 190k context note; what's left is reading the bar, landing and the report.

## Running (detached, end markers written by the jobs)
- **Bar** on pareto1, shared lease fd71825e, started 14:01Z: `~/sp19/sa-rust-ids-work/sa-port-208/bar-s2/` on pareto1, end
  marker `bar-s2/end.txt`. Wrapper `~/sp19/sa-rust-ids-work/sa-port-208/run-bar-s2.sh` (orion copy:
  `~/sa-rust-ids-work/sa-port-208/run-bar-s2.sh`), bar.sh copied to `~/sp19/bar-sa-port-208.sh`. BASE suite rows =
  sa-port-207's bar on ce1092c: `~/sp19/sa-rust-ids-work/sa-port-207/bar-state-relations-iii1b/suite` (that bar was
  still running at 14:01; it ends ~15:15). PLANTS rb-gen-model-flip rb-built-model-drop rb-gen-any rb-check-skip;
  SUITE_PLANTS=zero (expect the last three: no workload passes a block other than RULE_INTERNAL); WLS the 11; TESTS
  sa-port-207's list + test_rule_tables.py + the 4 knowledge tests of 6i(a); DIRECT relations_direct.py 300 0; N=6.
  machine run launcher pid in `~/sa-rust-ids-work/sa-port-208/bar-machine-run.pid` (orion).
- **Candidate probe** at bb92b07 on orion: `~/sa-rust-ids-work/sa-port-208/probe-cand/` (end marker done.txt), tree
  `~/sa-rust-ids-work/sa-port-208/cand-tree` (worktree of the clone + copied .so). Summarize with
  `python3 ~/sa-rust-ids-work/sa-port-208/tools/summ.py DIR`.

## Done
- Measured base: probe (pycalls.py, PYCALLS_FILE=satassume/sat/solver.py, 15 workloads, all exit 0) at 693fef9
  (`probe-base/`) and again at 9e10f0d (`probe-base2/`), identical. `_rule_tables` calls per workload (1 miss, the rest memo
  hits): dev 918, fuzz 3133, f6 2902, value 3550, rootof 4784, core 1635, opaque 2373, scope 171, loop 384, zero 667,
  wiring 5818, cert 87, budget 17, dev-s1 918, fuzz-s1 3133. Plus `_block_models` 188 calls and `_BlockClosure` 2 per
  workload (one enumeration per process). Kept-query calls inside those: dev 6 out-of-scope, f6 13, value 15, opaque 7,
  wiring 1 refused. Tables in `probe-base*/summary.tsv`.
- Candidate b09516e (same change on 9e10f0d, `probe-cand-b09516e/`): **0 non-import calls on all 15 workloads**. The
  probe is live: it still sees solver.py's 6 import-time calls (noquery).
- Offline or ported: **both, by case.** RULE_INTERNAL (rules.py:422) is a pure function of the static RULES (rules.py:96,
  174, 418). Registration (knowledge/extensions.py) adds clauses or atoms and never changes the block. Every engine path
  passes RULE_INTERNAL, NPRED: engine.py:317, ref.py:218, session_glue.rs:41. Other blocks reach set_rule_block only
  through the public Solver API: tests/test_solver.py :565 :785 :804 :833 :843 :855 :860,
  tests/test_solver_incremental.py:162 (random small blocks), slice fuzz.py:424 :656 :784 :786, check_step1.py:97-120,
  replay. So the engine block is **generated offline**, and any other block is **ported** (checked and enumerated in Rust).
  Python's `_rule_tables` is unchanged (pure-Python path).
- Quick live check on orion (q1, dev and fuzz, b09516e): Rust vs Python MATCH. rb-gen-model-flip fired 918 / 3133 and was
  caught on both workloads (state diffs: end 477, stream 477, lra 29 on dev; answers equal). `rb:generated` 918 / 3133,
  `rb:built` 0, ctx:caught 0.
- test_rule_tables.py: 14 passed on bb92b07's build; each of the 4 plants is caught there.
- Ownership: solver.py's 4 rows (`_block_models`, `_BlockClosure`, `_BlockClosure.__init__`, `_rule_tables`) to S2, and
  port-ownership.md's "Updated by sa-port-208" paragraph, in the commit.

## Left
1. Read the bar (`bar-s2/sum.txt`): suite by id vs base (3 numbers, passed split by firing), handler multiset,
   ctx:caught per workload, plants table (rb-gen-model-flip on dev/fuzz/WLS; the other three on the suite and in
   test_rule_tables.py), fallback counts: copy `~/sa-rust-ids-work/sa-port-204/fbcounts.py` and run it on the bar dir;
   base = 207's bar dir. ad:cbm_noid is in each `*.session.json` counts.
2. Read probe-cand at bb92b07; the count: solver.py joins (19 of 32) if it reads 0 per query on every workload, checked
   against STATUS "Counted modules" (18 of 32).
3. Land: wait until 207 has landed ce1092c, then `agent usage` (< 90% to land; it was 89% at 13:59), then
   `sh rust-spike/slice/p1/bar.sh land bb92b07` without PUSH and read the incoming diff (guard: source must equal bb92b07),
   then PUSH=1. If 207 lands something other than ce1092c, the guard decides whether a full rerun is needed.
4. results/port-s2.md in port-6i-a.md's form; final ownership rows ("landed S2 <sha>"); `agent report`; push the branch.
5. Install order: sa-port-206's fix has NOT landed (HANDOFF-sa-port-206 9991ccf), so scope's MATCH rests on the old order.

## FILE:LINE MAP (bb92b07)
- rust-spike/slice/solver_rs/src/block.rs: `rule_tables` :34 (generated-or-built choice, plants 320-322), `check` :60
  (`_rule_tables`' checks, plant 323), `flip_one` :84, `block_models` :150 (port of `_block_models`).
- rust-spike/slice/solver_rs/src/rule_tables_gen.rs: generated (NVARS, CLAUSES, MODELS). Generator
  rust-spike/slice/gen_rule_tables.py (`--check`).
- rust-spike/slice/solver_rs/src/lib.rs: set_rule_block :338, `int_i64` :572, `read_rule_block` :589,
  `rule_block_tables` :616 (tests).
- session.rs: counters rb:generated/rb:built/rb:check_error 420-422 (:84, consts :469); 345-419 "reserved:".
- relations_core.rs: plants 320-323 (:398, names :640). session_live.py `_RULE_BLOCK_PLANTS` :895, from_env :1255.
- satassume/sat/solver.py `_rule_tables` :362 unchanged.
