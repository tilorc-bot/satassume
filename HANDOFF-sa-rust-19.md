# Handoff sa-rust-19: S step 4 finished, gate as ruled not met (issue 323, branch rust-slice)

Written at the end of step 4. **The gate is decided: not met**, on the 46 stub failures in number 3. Read `rust-spike/slice/results/step4-gate.md`. No jobs are running. Step 5 is another session and hasn't started; whether it goes ahead with the gate unmet is a planner's question in my report.

## Settled, don't redo
- **Numbers:** 5,960 ran on Rust and passed / 77 kept on Python / 46 failed. All 46 are the borrow RuntimeError at `tests/theory_harness.py:242`.
- **History, harness:** 14 of 14 pairs and 78,000 harness queries, 0 differences.
- **Run 6:** measured, 918 of 918 and 3,133 of 3,133.
- **Mutants:** all 35 caught, none argued equivalent. Table: `results/step4-mutants-all.md`.
- **The 120 s TimeoutError:** audit failure's shrinking plus load, not a hang. `guard_probe.sh`, `guard_pinned.sh`.

## Not run
`mutate_boundary.py --suite`, for whether the suite itself catches callback bugs. Optional in the last handoff, still open.

## For step 5 (carried from sa-rust-17)
- `rust-spike/slice/run-slice.sh` still names `/work/src/base-9bafaa5` and runs `qtime.py`. It needs the current source and the Rust backend.
- **Crossing counts (step 3, measured):** hook calls 34,788 on dev and 1,241,630 on fuzz.
- **Plan section 2 correction:** its "80k on dev, 2.67M on fuzz" counted internal calls too. Real crossings are 44% and 46% of that, so the callback part of the estimate is about 2.2 times too high. Use the measured counts.
- Report full API and abi3 both (plan section 4).

## Running the tools
As in `HANDOFF-sa-rust-16.md`. Suite: `bash rust-spike/slice/run_suite.sh DIR rust|python [FILES]`; `suite_report.py RUST PYTHON [--list OUT]`. Audit-off: `SLICE_AUDIT_OFF=1` or `2`. Reach: `SLICE_SO=$S4/probe PROBE_FILE=FILE`. Mutant table: `mutants_joined.py API NESTED LIVE STEP3`. `S4=~/sa-rust-ids-work/slice/step4`. `env.sh` reassigns `W`. Don't `pkill -f` a pattern that's also in your own command.
