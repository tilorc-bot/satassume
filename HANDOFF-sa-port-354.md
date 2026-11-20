# HANDOFF sa-port-354: items 5 and 6 DONE and pushed; item 7's bar is RUNNING (launched 04:56Z 20 Nov); nothing landed

Stopped between items 6 and 7 at the context budget. Branch port/witness-native (pushed), head b6b71bb1 plus this
handoff commit, worktree ~/sa-rust-ids-work/sa-port-350/wt in clone ~/dev/sa-port-19, on rust-slice 6ee354f9. No
lease of mine is held except the bar's shared lease on pareto0, which the detached job releases itself. Read
results/witness-native.md (5) and (6) for what is measured; HANDOFF-sa-port-353.md, -352.md and -351.md for the map.

## Done

- Item 5 (322f6450): S1 on b7302f83 (the commit of item 4; later commits add results and tools only) against
  6ee354f9, quiet lease ed51ef36 on pareto1, 04:51Z to 05:13Z, load at most 1.19, 12 rounds, 9 arms. Bench .so
  0b6f073f5c5a600b (head) and 0982a28074215658 (base); the restage reproduced the pareto venv .so 37b7560e245df518.
  THE LANDING RULE HOLDS: head rust nat against base rust on32 dev -6.3%, fuzz -10.3%, budget -0.9%, wiring -5.1%,
  each faster beyond the spread, 0 of 12 rounds slower; the 16 unchanged-path rows (py and rust, off and on32) within
  the spread. On against off with the native check: dev -4.2%, fuzz -28.6%, budget +4.5%, wiring +4.0% (Python's
  check on the Rust path: +2.6%, -20.4%, +5.3%, +10.1%). wn:compile in the nat arm: 776, 2772, 19, 4814; one digest
  per workload on all 9 arms; certified 173, 1284, 0, 215. Table: tools354/s1-med.txt.
- Item 6 (b6b71bb1): the count probe (sys.monitoring, nothing wrapped), pareto0, 20 workloads, 30,753 queries, 80 of
  80 rows ref 0 run 0 cmp 0. witness.py's calls 5,441,984 (Python's check) -> 127,039 (native); NOT 0: 2 to 4 per
  call of the check remain (`independent`, `witnesses`, `_patched`, `_users_knowledge`), dev 2.94, wiring 2.36, budget
  4.11, fuzz 30.9 (its 75 fallback queries). Boundary reads: wn:lookup 65,881; `_replaced` 11,415 calls x 23 =
  262,545 dictionary reads; NEW in this section: the table's symbol reads go through convert.py, 22,351 reads and
  156,457 more convert.py calls than under Python's check (7 Python calls a read). `_replaced` returned True 0 times
  on every workload (its calls equal wn:compile in all 20 rows; wn:fallback:off 334 is all lra's no-table). Default
  cell: every probed file equal to 6ee354f9 per workload and function; witness_live.py adds 5 calls a process at
  install. The probe count stays 21 of 32. Table: tools354/pc-tab.txt.

## To do: item 7

The bar was started early, in parallel with S1, on the frozen branch origin/bar/witness-native-b7302f83 (pushed; its
head is b7302f83) with the pareto venv .so 37b7560e245df518: `tools354/gobar354.sh b7302f83 37b7560e245df518`
(tools353's scripts with this session's paths), orion, setsid, pareto0 shared lease 508ab9ad, launched 04:56Z, about
90 minutes. At 05:15Z it had finished tests and the suite and was in the live phase.
1. End markers: orion ~/sa-rust-ids-work/sa-port-354/gobar-end.txt (the last line of gobar354.sh; it copies the
   bar's small files to ~/sa-rust-ids-work/sa-port-354/bar/ first); pareto0
   ~/sp19/sa-rust-ids-work/sa-port-354/bar-end.txt ("END rc ... so8 sha", then WATCHER-END). Wait on the orion marker
   with a background `until [ -e ... ]` shell.
2. Read: bar/bar/sum.txt (bar_sum.py; BASE is sa-port-348's bar on 82d4ddf3), bar/bar/kept.txt (6 lines: none and
   the five plants; every plant line must show its kept test FAILED, `none` rc 0), the plant table with wall times,
   tests.txt, the quiet catches, env-summary.txt (which SLICE_ variables each row's processes had), so-loaded.txt.
   Rows of this step: witness:on, wnative:on, wnative:wn-integer-half (760), wn-work-one (761), wn-skip-patched
   (762), wn-int-side (763), wn-skip-own (764), as workload rows on dev, fuzz and the 15 extra workloads and as
   suite rows. Expected: wnative:on MATCH everywhere; 760 DIFFER on dev and fuzz; 761 on all 17 workloads must MATCH
   or be caught (ruling for 354: report the row as it reads; it fires only when the work count lands on WORK); 764's
   suite row is expected to fail tests/test_witness.py::test_a_set_the_engine_knows_inconsistent_tries_no_point.
   Known base rows by id; the planted-history test ([137e]): if a row flips, run a28c548's method before calling it
   the id()-reuse flake.
3. Write results/witness-native.md (7) (replace the "Not done" paragraph at the end and the title's "item 7 open"),
   commit, then in the worktree: `bash rust-spike/slice/p1/bar.sh land b7302f83`, read the incoming diff (rust-slice
   was 6ee354f9 at 05:14Z; no sibling runs), then `PUSH=1 bash rust-spike/slice/p1/bar.sh land b7302f83`. The guard
   compares satassume/ and rust-spike/slice/ (results/ excepted) between b7302f83 and HEAD: empty now (checked at
   b6b71bb1). Rule [91]. Tell the architect when rust-slice moves.
4. Report (Status: done) with everything in "Must stay in every report" below, and name that the `_replaced` rule is
   accepted by the planner's ruling for 354 with three conditions: `_OWN` as configuration in the state inventory
   (NOT YET CHECKED by me: see whether harness/state.py or tests/test_history.py classifies witness_live._OWN; if it
   needs a source line, that moves the tested SHA and needs a new bar, so say it in the report first), the 23 reads
   under the count rule (done, (6)), the fallback's 0 from the counters (done, (6)).

## Report open points (still owed)

- The switch tie to SLICE_CONVERT=rust is not needed by the code. Shared files changed by this port: fresh.py
  (accepts term_discard's wrapper when SLICE_WITNESS_RUST=1), session_live.py `_write_report` (3 lines,
  witness_live.FIRED), harness/state.py (NATIVE in MODULE_CONFIG).
- New from item 6: 7 Python calls in convert.py per symbol read (`_Walk.read`, `_read_symbol`, a lambda of
  `rust_walk`, four of `_RustWalk`) is the walker's dispatch: a cheap reduction for a later step, not this one.
- Budget still pays +4.5% with the native check and certifies nothing; wiring +4.0%. That is the default question's
  answer for Tilo: a gain on dev and fuzz, a cost on budget and wiring.
- Quiet catches (engine.py:1906): 49 in every suite cell of 353, base among them; the bar's handler rows count the
  workloads.
- pareto0 has no rsync (gopc354.sh copies by tar). The bench image's Python is 3.12.15, the pareto venv's 3.12.14.

## FILE:LINE MAP (b6b71bb1; source is b7302f83's)

- rust-spike/slice/witness_live.py: `_BY_NAME` :40, `_OWN` :42, `_replaced` :54, `native` :66, `counts` :93,
  `install` :100, `plant` :104, `from_env` :110; term_live.py :1276-1277 calls `witness_live.from_env()`.
- solver_rs/src/witness.rs: PLANTS :63, `pred` :288, `side` :574, `formula` :591, `spend` :694, `roots` :703,
  `pools` :741, `run` :807, the `symbol_facts` read :931. convert.py `_read_symbol` :380.
- satassume/witness.py NATIVE :128, `witnesses` :829, the hook's call :836-840. harness/state.py :296-299.
- p1/bar.sh: land :50-75 (the guard :62), penv :102, pywit :111, fired :133, the plants command :189.
- results/witness-native.md: (5) S1 and (6) the count rule are the last two sections; "Not done" is the last
  paragraph.
- results/tools354: S1 time354.sh, onlease354.sh, gos1354.sh, med354.py, wn354.py, s1-med.txt; count probe pc354.sh,
  pcby354.py, pctab354.py, gopc354.sh, pc-tab.txt; bar gobar354.sh, job354bar.sh.
- Output: ~/sa-rust-ids-work/sa-port-354 (s1/med.txt, s1/timing-s1, s1/timing-bw, pc-b7302f83, pc-6ee354f9,
  pc-tab.txt, so/sa_solver-b7302f83.so, bar-launch.log, bar/ once the bar ends); pareto1
  ~/sa-rust-ids-work/sa-port-354/s1; pareto0 ~/sp19/sa-rust-ids-work/sa-port-354 and ~/sp19/dev/sa-port-354 (the
  bar's clone).

## Must stay in every report

Tested SHA b7302f83 (S1, the count probe and the bar; items 1-3 on b79f6657, the crate unchanged since 6746bfe3) on
rust-slice 6ee354f9; .so orion e0365239348de148, pareto venv 37b7560e245df518, bench 0b6f073f5c5a600b. SLICE_WITNESS
off by default, Python witness.py the default and the reference, the unchanged path the default. No SymPy
construction or evaluation at query time; no floats in any decision; "exact" rests on 325's 14-predicate table plus
2030cdc6's Q[pi] arguments (issue 247). Per query on dev, fuzz 424242, the 20 workloads and seeds 0/1/2/42: certified
set, witness_certified and Engine.stats equal Python's; suite by id (the same 127 base ids in every cell,
planted-history among them by id, [137e], id()-reuse) and iv. S1 from the quiet lease ed51ef36 only, with the numbers
above; on against off for the four workloads; witness.py's per-query Python calls (2 to 4 per call of the check
remain, the guards stay Python) and the lookups, `_replaced`'s reads and the symbol reads as boundary reads; the
probe count 21 of 32; fallbacks dev, wiring, budget 0, fuzz 2.7% (miss), lra 30.0% (no table on the second run of a
refused query), cls 71.4% (equal but distinct Function classes; no gain on cls), `_replaced` 0 everywhere; the
profile's numbers (10.1% of Rust dev, 9.4% of Rust wiring, 17.8% of Rust fuzz) as "before"; the switch tie not needed
by the code; fresh.py, session_live.py and harness/state.py (shared files) named; the `_replaced` rule named. Owed
from item 7: the bar row wall times, known base rows by id.
