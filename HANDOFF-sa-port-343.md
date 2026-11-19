# HANDOFF sa-port-343: (2b) reverted and committed; the gate and S1 on the new SHA are RUNNING DETACHED, unread; dfb544e6's gate read; bar (7) NOT STARTED; NOTHING IS LANDED

Stopped at the context budget. Branch port/witness-reasons (pushed), worktree ~/sa-rust-ids-work/sa-port-340/wt in clone
~/dev/sa-port-19, from rust-slice 29c5a0db. No Rust change since 29c5a0db (stage343.sh checks it).

## Commits of this session (on 713c9c82)

- c4d6e92c witness: (2b) reverted on the planner's ruling. `_roots` leaves out a secant root that is not rational,
  `_own(sym)` reads the rational table again, `_near` and the keyed sort are gone, assumption 2 of the docstring says a
  symbol takes rational values only. Exact pi stays. Tests: the (2b) test is now
  `test_a_symbol_stands_for_rational_values_only`; the enclosure test uses rational points on both sides of pi.
  Orion: test_witness.py + test_sympy_api.py + test_layering.py 262 passed, switch off and on; test_witness.py under
  the plants: pi-sign 11, pi-rational 10, pi-enclosure 9 failed of 150.
- 01e8ca74 tools343 (stage343.sh, go343.sh, jobb343.sh, gos1343.sh, onlease343.sh, pc343.py, pc343.sh). **This is the
  SHA the running gate and S1 test** (satassume source c4d6e92c).
- e2088c05 harness/state.py (a shared file, 2 hunks): PI_TABLE, _LO, _HI, _BAD_LO, _BAD_HI classified as constants and
  FIRED as configuration. `tests/test_history.py::test_module_state_inventory_is_classified` failed on dfb544e6 (and
  will on 01e8ca74's suite rows: on, off, both backends) and passes from here (orion: test_history.py,
  test_sympy_boundary.py, test_witness.py, test_layering.py 377 passed, switch off and on).
- 89ab4895 tools343: cx343.sh, and pc343.py loads any workload by live.py's load().

## dfb544e6's gate, read (evidence for dfb544e6 only; rows in ~/sa-rust-ids-work/sa-port-342; NOT yet in witness-reasons.md)

- Suite by id (job-dfb544e6/suite-cmp.txt): on against off 0 ids differ, both backends. Rust on/off 6309 ids, 6139
  passed, 129 failed; base 6262 ids, 127 failed. Python on/off 6266 passed, 2 failed; base 6221 passed, 0 failed.
  Against base: 47 new ids (tests/test_witness.py) and **2 ids failed that pass on base**, the same on and off, both
  backends: test_history.py::test_module_state_inventory_is_classified (fixed by e2088c05) and
  test_sympy_boundary.py::test_static_check_passes_on_the_package (witness.py:678 `.assumptions0` read with a line
  between it and its `# sympy-boundary` comment; gone with c4d6e92c, the test passes on orion). Quiet catches recorded:
  rust 49 in 9 ids, python 10 in 7 ids, the same on, off and base.
- iv (iv-cmp.txt): 64 off + 64 on runs, failing ids off against on differ in 0 runs; rust fails
  test_transfer.py::test_models_respect_transfer and ::test_protocol_on_fuzz in 16 runs off and on (known:
  witness-check.md:111 and :199). Repeat check (pre/rep/rep-sum.txt): rust plain 0 of 20 off and on (assert 0 == 2 /
  1 == 2 at :204), rust keep-alive 20 of 20, python 20 of 20 in all four cells: the known id()-reuse shape.
- Digests (pre/dig/dig.jsonl): dev 31cd0945c07f02a6 and fuzz 173502b6ef285ad6 off and on, py and rust; certified 173
  and 1283. Plants on the workloads: pi-sign DIFFER on dev and fuzz; pi-rational and pi-enclosure MATCH on both (their
  catch is the suite row: test_witness.py 12 and 9 failed); integer-half and single DIFFER; skip-own, skip-patched,
  skip-users MATCH as before.
- 20 workloads (jobb-dfb544e6): GATE answers equal on both trees; XANS 80 cells, answers and messages equal.
- Fuzz seeds (fz.txt): `FZ rows equal on every run`; 0 differ in every row of both SHAs, so **no reach of [151] on
  29c5a0db in these seeds**. Certified on: evalbench 17400 -> 20960 of 43988 calls (py and rust), harness 0 -> 4 of
  2908, harness-custom 0 -> 0 of 2424. Exceptions equal off and on (ValueError 2748, 472, 808).

## Running, detached (started about 16:03Z 19 Nov; nothing of mine waits on them)

All under orion ~/sa-rust-ids-work/sa-port-343 (tools/ flat, staged.txt: both paretos carry .so cad764d46471b1c6).

1. `tools/go343.sh 01e8ca74 29c5a0db`: pareto0, one shared lease: tools342/job342.sh (suite by id on/off/base, pre342.sh
   digests and plants, iv), then jobb343.sh (the 20 workloads and the fuzz seeds on 01e8ca74 only; the base's rows are
   sa-port-342's from pareto1, copied into pareto0 ~/sp19/sa-rust-ids-work/sa-port-343/jobb-01e8ca74 first). About 70
   minutes. End marker orion go-end.txt. Read as the handoff of 342 says: job-01e8ca74/suite-cmp.txt (expect exactly
   one id against base besides the new test ids: the inventory test, fixed by e2088c05), iv-cmp.txt,
   pre/dig/dig.jsonl, pre/tw/*.log, pre/rep/rep-sum.txt, jobb-01e8ca74/xans.txt, fz.txt, gate-01e8ca74/answers.txt.
   Expected certified at cap 32 without (2b): dev 173, fuzz 1284 (342's table: 14 and 224 in the pi class).
2. `tools/gos1343.sh 01e8ca74 29c5a0db`: pareto1, one quiet lease, bench .so 0982a28074215658: timing-s1 (dev, fuzz),
   timing-bw (budget, wiring), 8 arms SHA:MODE-WITNESS, 12 rounds, then timing-pc (pc343.sh: per-call rows on budget
   and wiring, both trees, py and rust, 3 passes). First three rounds of timing-s1 ran clean (err.txt empty, a minute a
   round). End marker orion gos1-end.txt; read s1/med-s1.txt and s1/med-bw.txt ("BEYOND THE SPREAD" per comparison),
   then s1/timing-pc/pc-SHA-WL-MODE-ROUND.json (keys `split`, `top`, `stats`, `calls`; never print `calls`).
3. cx: pareto0, shared lease, cx343.sh: pc343.py in py mode on the gate's 20 workloads, counts for the planner's (a).
   End marker orion cx-end.txt; rows cx/WL.json (`split` gives the count per exit), cx/rc.txt.

## Not done, in order

1. Read 1-3. A difference on the head: Status: question. Then run on e2088c05 or later (harness only differs from
   01e8ca74) at least tests/test_history.py on both backends; the bar's plain suite covers it.
2. witness-reasons.md, section "sa-port-343": the dfb544e6 rows above, the 01e8ca74 rows, the reasons table without
   (2b), S1, and the planner's three additions:
   (a) From the code: the check is called in `_engine_ask` (sympy_api.py:1136), after the relevance layer's answer
   memo (`_ask_general`, sympy_api.py:586-599, `eng.answers`: a hit never reaches the check) and before every cheap
   exit of `Engine.ask` (engine.py:2222 non-commutative, :2225 `_within_budget` then `_over_budget` :1860, the
   memoized INCONSISTENT in `_context_session` :1876, `_failed` in `_build_context_memoized` :1893). Counts per
   workload: cx/WL.json `split` (exits over-budget, noncommutative, no-build, session, certified).
   (b) timing-pc rows. Orion sizing only (py, one pass, NOT a quiet-lease time): budget 19 calls, 0 certified, 2.08 s
   in the check of 2.92 s; the 7 over-budget calls take 1.48 s in the check (median 213 ms, max 279 ms) and 0.12 s in
   the engine after it; the 12 session calls 0.60 s in the check and 0.49 s in the engine. wiring 4814 calls, 1503
   compiled, 0 certified, 1.26 s in the check of 5.55 s, median 13.8 us, 90% 167 us, max 4.4 ms; every exit is
   `session`; 884 answer-memo hits never reach the check.
   (c) One paragraph. What the sizing suggests: on budget the cost sits in queries the engine refuses by structure
   (over budget: None without a session), so running the check after `_within_budget` removes it with no cache; on
   wiring nothing is certified and the cost is the per-call compile, so a bound on the work (formula size times
   points), not on the point count, is the other lever. Check both against the lease rows before writing it.
3. Landing rule (planner): pi lands if dev and fuzz S1 show no loss beyond the spread against on-at-29c5a0db and pi
   does not make budget or wiring worse than at 29c5a0db; on against off there is a finding, not a block.
4. (7) the bar, not started. Pattern tools337/gobar337.sh and job337bar.sh (pareto0, no cargo): push the frozen branch
   origin/bar/witness-reasons-SHA at the branch head; copy SHA's p1/bar.sh as ~/sp19/bar-sa-port-343.sh; the .so is
   orion ~/sa-rust-ids-work/sa-port-340/so/sa_solver-29c5a0db.so (cad764d46471b1c6, want.txt); BASE
   ~/sp19/sa-rust-ids-work/sa-port-337/bar/suite (the last landing's bar, 786410d; rust-slice 29c5a0db adds test-only
   commits, so their ids show as new or changed); STEP rows `witness:on witness:pi-sign witness:pi-rational
   witness:pi-enclosure` as PLANTS and SUITE_PLANTS; phases `tests suite live plants extra suiteplants fmrows sum`
   with job337bar.sh's WLS, FM_WLS, FM_PLANTS, TESTS=all TESTS_SPLIT=1, N=6. 337's bar took 88 minutes with six rows.
   Then bar.sh land, PUSH=1, and witness-check.md's stale "pending" header in a results commit.

## FILE:LINE MAP (89ab4895)

- satassume/witness.py: _own :659; _roots :674 (the non-rational skip :690); _pools :703 (the [151] try :727);
  _holds :754; witnesses :778; FIRED :107; the pi section from :305 (_PiPoly :329, order comparisons :404-414, reached
  only by tests/test_witness.py:429 in test_witness.py and test_sympy_api.py: a removal candidate, not checked on
  the workloads); _sign :425; PI_TABLE :457; _pi_pred :526.
- satassume/sympy_api.py: _ask :566; _ask_general and the answer memo :583-602; _engine_ask :1118; the check :1136.
- satassume/engine.py: Engine.ask :2203 (exits :2222, :2225-2235); _within_budget :1814; _over_budget :1860;
  _context_session :1866; _build_context_memoized :1885.
- tests/test_witness.py: enclosure test :434; test_a_symbol_stands_for_rational_values_only :449.
- harness/state.py: witness constants :261-265, configuration :290-294.
- rust-spike/slice/results/tools343: stage343.sh, go343.sh, jobb343.sh, gos1343.sh, onlease343.sh, pc343.py, pc343.sh,
  cx343.sh; tools342 (job342.sh, pre342.sh, time342.sh, med342.py, xans342.py, fz342.py, fzcmp342.py, qt342.py);
  tools337 (gobar337.sh, job337bar.sh); tools328 (cmp329.py, ivcmp329.py, gate330.sh, suite331.sh, wit328.py).

## Must stay in every report

Tested SHAs and .so hash (base 29c5a0db; gate and S1 running on 01e8ca74 = source c4d6e92c; head 89ab4895 adds
harness/state.py and tools; pareto venv .so cad764d46471b1c6, bench .so 0982a28074215658); SLICE_WITNESS off by default
and the unchanged path the default; no SymPy construction or evaluation at query time; "exact" rests on 325's
14-predicate table plus (2)'s arguments: (T) pi transcendental, (E) the 50-decimal enclosure, proved again in the
tests by Machin's formula (issue 247: SymPy evaluation is not ground truth); the reasons table before/after (cap 32:
dev 159 -> 173, fuzz 1060 -> 1283 with (2b); without it 173 and 1284 by 342's rows, to be confirmed by the gate's
digest rows); bar row wall times (no bar yet); known base rows by id; S1 wall times from quiet-lease runs only
(pareto1; running). The Rust port of the per-call compile and pools follows this step and is not started. OWED still
open: [150]; [151] is fixed only on this branch until it lands.
