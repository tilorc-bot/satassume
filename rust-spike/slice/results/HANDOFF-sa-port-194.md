# Handoff sa-port-194 (6g(c6)-(c9) one four-step stack bar running on pareto1), issue 323

## State
- **6g(c6) bar on 7890bf3 was clean** (pareto1 `sa-port-191/bar-6g-c6/`, end.txt `exit 0 2026-11-09T03:02:39Z`), but 5c10d's
  clean bar ended first (02:31Z), so 5c10d landed first (rust-slice b384ec1 -> 9529850). The c6 section is filled into
  port-6g.md (port/stack-6g-c3c5 1a4ab3b, carried here as cec872d). Its bar section is now superseded by the stack bar,
  but its numbers stay as evidence for c6 on 5c10c.
- Planner ruling `sa-port-6g-c6c9-stack-ruling.txt`: c6+c7+c8+c9 on one bar this once; plant tables per step; a differ means
  landing one step at a time with its own bar; one tested SHA equal to what lands; land only if the week reads below 90%.
- **Tested source: cec872d** (port/6g-c7, force-pushed) = rust-slice 9529850 + afd9324 (c6) + cee0997 (results) + da6a0ec
  (c7) + f9e82e9 (c8+c9) + cec872d (results/: c6 section). This handoff commit is results/ only (guard-excluded).
  Incoming diff from b384ec1: 5c10d's 17 guarded files (entry.rs new, session_live.py, engine.py, sympy_api.py,
  relations_core.rs, session.rs, budget.rs, term_live.py, test_entry_core.py, ...; 1,333+/57-), executed by the bar.
- Orion on cec872d: build OK; bar TESTS + test_entry_core.py, `-n 4`: **793 passed, 3 skipped** (770 + 23)
  (`~/sa-rust-ids-work/sa-port-194/tests.txt`).
- **Bar running**: pareto1 `~/sp19/sa-rust-ids-work/sa-port-194/bar-6g-c6c9/`, **end.txt written by the job**; started 03:12Z
  under shared lease 07b4b404, expected end ~06:30Z. Launcher pids on orion in `~/sa-rust-ids-work/sa-port-194/machine-run.pid`
  (output machine-run.out). Config `~/sa-rust-ids-work/sa-port-194/job-c6c9.sh`: 66 plants (bar-6g-c6's 60 + six c7-c9),
  BASE = 5c10d's suite (`sa-port-193/bar-5c10d-r2/suite`), KEPT_BASE = bar-6g-c6 (5c10d's bar ran only 5 of 11 WLS),
  TESTS + test_entry_core.py.

## Reading it
- Completeness check (suite rows for 6,159 ids, 13 workload cmps + seed1, 66 x 13 = 858 plant rows, 7 suite plants, handler
  rows), then plant table: `awk -f ~/sp19/sa-rust-ids-work/sa-port-187/plantagg.awk sum.txt`; the 60 old rows should equal
  `sa-port-194/plantagg-bar-6g-c6.txt`. Per-step tables: c6 (4 plants), c7 (cosh-shift-parity, cosh-plain-none), c8
  (exp-ipi-drop, exp-const-key-none), c9 (round-skip, round-key-none).
- Counts: pareto1 `~/sp19/sa-rust-ids-work/sa-port-194/mkfill6.py BAR BEFORE` (edit STEPS for c7-c9 names:
  `_cosh_shift`, `_cosh_shift_split`, `_exp_ipi`, `ipi_split`, `ipi_rules`, `parts_of_round_templates`), BEFORE = bar-6g-c6.
- Then `bash rust-spike/slice/p1/bar.sh land cec872d` (no PUSH), report section(s) in port-6g.md, delete this file,
  `agent usage` < 90%, `PUSH=1 bash rust-spike/slice/p1/bar.sh land cec872d`.
