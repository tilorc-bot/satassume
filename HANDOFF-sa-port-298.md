# HANDOFF sa-port-298 (rk_key step, issue 323): (b) dropped per the 298 gate; the bar on the landing tree is running

Branch port/rk-key, head = the commit adding this file. Landing source 0bd82e4 (= rust-slice 63d5632 + ded9d0b (a) + 2b600f0
(revert of (b): 1b41dce, 1e7a4db, 86845aa) + 0bd82e4 test_rk_key_targets.py). Worktree ~/sa-rust-ids-work/sa-port-296/wt
(in ~/dev/sa-port-7). Env: `. ~/sa-rust-ids-work/sa-port-296/env296.sh` (python = $PY). Scratch ~/sa-rust-ids-work/sa-port-298/.
Results so far: rust-spike/slice/results/rk-key-step.md (S1 r3 table, (b) as tried with its size, thread check, the 6b8a5c2 bar).

## DONE
1. S1 r3 read (pareto0, one quiet lease): fuzz 6.391 -> 6.333 (-0.9%), median paired -0.042 (7/7 faster) = r2's 0.7% the gate calls
   within spread, and less than either arm's range (0.104/0.073): (b) DROPPED. Target "most of 0.127 s" NOT met (rk_key incl
   -0.056, relkeys D -0.041). Dev not slower (paired -0.001).
2. Bar on 6b8a5c2 ((a)+(b)) read: clean (tests 71/71, suite new 0, changed 1 = planted-history failed->passed, live/extra MATCH,
   kept reasons = base, fm rows 0 differ). Superseded: the landing code differs, so the bar is rerun on 0bd82e4.
3. Landing tree on orion: 115 passed (test_rk_key_targets, test_guard_method, test_entry_frame, test_relations_core, test_rs_core).

## RUNNING (detached on orion: ~/sa-rust-ids-work/sa-port-298/gd/go298.sh; end marker gd/go-end.txt "END bar <rc> <time>")
pareto1 --shared bar.sh build (OUT=~/sp19/sa-rust-ids-work/sa-port-298/build, clone ~/sp19/dev/sa-port-298) -> .so copied to
pareto0 ~/sp19/dev/sa-port-298 -> `machine run pareto0 --shared -- bash ~/sp19/bar298.sh` (bar297.sh minus rk plants) ->
pareto0 ~/sp19/sa-rust-ids-work/sa-port-298/bar (sum.txt, bar.log, bar-end.txt). 297's bar took 3.5 h, so expect ~09:00Z.
Logs: gd/build.log, gd/p0-bar.txt (.so sha256), gd/bar-p0.log.

## NEXT
1. Read the bar (sum.txt by grep, as in results/part3-followup-bar.md "Bar (five items)" + fm rows + suite plants + plant table).
   Known: planted-history flips both ways (a28c548); handler rows 39 = base. Any new difference -> don't land, hand off with diff.
2. In the worktree: `bash rust-spike/slice/p1/bar.sh land 0bd82e4` (prints incoming diff; results/HANDOFF commits pass the guard),
   then PUSH=1. rust-slice must still be 63d5632 (check `git log origin/rust-slice`; else rebase per LANDING ORDER).
3. Probe: copy pareto0 ~/sp19/sa-rust-ids-work/pc294.sh -> pc298.sh on the landed SHA, against 21/32 (base sa-port-294/pc;
   pcsum.py); knowledge_live per workload from the bar's live/*.knowledge.json and extra/*.knowledge.json vs sa-port-294/bar.
4. Fill the Status/landing/probe rows in results/rk-key-step.md, push, `agent report --status done`, tell the architect. Also tell
   the architect: `machine` lets a holder's own --shared lease start inside its quiet lease (cost S1 r1, from 297).

## FILE:LINE MAP (on 0bd82e4, rust-spike/slice/)
- solver_rs/src/relkeys.rs: is_basic :42, is_joinable :55, rk_key :83 (no cache; as at 63d5632).
- solver_rs/src/session_glue.rs: GuardMethod/EntMethod __module__/__reduce__ (ded9d0b); session_live.py passes the module.
- test_rk_key_targets.py (kept, new), test_guard_method.py:43 _lookups, test_entry_frame.py.
- p1/bar.sh (land mode :3, :46-66); bar298.sh in ~/sa-rust-ids-work/sa-port-298/gd.
- (b) as tried: 86845aa relkeys.rs :105/:109/:113 plants, :144 innermost, :257 plain, :279 guard; session.rs:761; test_rk_key.py.
