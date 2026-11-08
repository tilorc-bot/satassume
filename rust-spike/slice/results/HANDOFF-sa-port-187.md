# Handoff sa-port-187 (6g c3+c4+c5 stack, issue 323): bar running on af63d20, nothing landed yet

Handed off at the architect's request (174k, bar ~2.5 h away). My waiter shell is stopped.

## Running (detached)
- **Full bar on af63d20** (stack rebased on rust-slice 4215655, 5c10b), pareto1, started 20:42 UTC under
  `machine run pareto1 --shared` (orion launcher PID in `~/sa-rust-ids-work/sa-port-187/machine-run.pid`).
  **End marker: pareto1 `/home/tilo/sp19/sa-rust-ids-work/sa-port-187/bar-6g-c3c5r3/end.txt`** (written by the job,
  `~/sp19/job-sa-port-187.sh` = `~/sa-rust-ids-work/sa-port-187/job3.sh`), expected ~23:25 UTC.
  BASE = 5c10b's suite (`sa-port-186/bar-5c10b/suite`); config = bar-6g-c3c5r2's plus test_context_core.py.
  Already done in it: build, tests (743 passed, 3 skipped), suite: 5,991/127/23/18, 6,159 ids, vs 5c10b and vs
  bar-6g-c3c5r2 new 0 gone 0 changed 0, handler multiset = base (`sa-port-187/early-sum.txt` on pareto1).
- Land with `bash rust-spike/slice/p1/bar.sh land af63d20` (the HEAD commits on top are results/ only).

## Evidence taken
- Bar on 2c2990c (`sa-port-175/bar-6g-c3c5r2`, exit 0 20:38Z): equal to 5c10a base on every item; vs the first stack bar
  only the known id()-reuse id changed (`sa-port-175/sum-vs-stack1.txt`); per-plant fired/caught workload sets equal
  the first stack bar's for all 56 plants (`sa-port-175/plantagg-*.txt`, awk over sum.txt's plant table).
- Orion on af63d20: dispatch_direct plain exit 0, dispatch-user-off / -ignores-epoch / -redefines-off caught
  (`~/sa-rust-ids-work/sa-port-187/dispatch-direct-af63d20.txt`); shapes shadow 23 cases, mismatch 0
  (`shadow-af63d20.txt`, from `shadowcount.py`); retrace for the module count (`rc-{dev,f6,core,wiring}.txt`): 14 of 32.

## Report
`results/port-6g-c3c5-draft.md` is the filled section (from c3c5-section.md). Left to fill from bar-6g-c3c5r3:
R3_END, R3_SO, R3_SUITE, R3_SPLIT, R3_VS_R2, R3_PLANTSAME, R3_HANDLERS, R3_KEPT, R3_SUITEPLANTS, INCOMING_AT_LANDING; and
recheck the C3/C4/C5 counts and tables (filled from r2) by `mkfill.py` on r3 (diff against `fill-r2.txt`).
Then append it to port-6g.md, delete the draft and this file, commit, land, touch
`/home/tilo/dev/architect/markers/6g-stack-landed`, report.
