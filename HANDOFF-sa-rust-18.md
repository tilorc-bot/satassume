# Handoff sa-rust-18: S step 4, settled items done, 3 jobs running (issue 323, branch rust-slice)

Handed off at 04:33 UTC, 7 Nov, at the architect's request. **The gate is not decided.** Read `rust-spike/slice/results/step4-gate.md` first: the three numbers (5,960 / 77 / 46) and every brief item but the last columns are in it. Don't redo them.

## Jobs, detached (setsid nohup), surviving this session
| Job | Finished marker | Progress at handoff | Resumes? |
|---|---|---|---|
| History 1 to 4 | `~/sa-rust-ids-work/slice/step4/hist/finished.txt` | 22 of **28** runs (not 56: sa-rust-17's count was wrong). Left: 6 fuzz runs, about an hour by my estimate | Yes: `run_history.sh` skips a run whose `.jsonl` has a `"total"` line |
| Live mutant columns | `~/sa-rust-ids-work/slice/step4/mut-live/finished.txt` | 44 of 104 cells, base row "no". About 1 to 2 hours | Yes: new `--resume` |
| Harness presets, run 5 | `~/sa-rust-ids-work/slice/step4/run5-harness-finished.txt` | Rust first, then Python. Duration unknown; each capped at 2 hours | No: rerun the script |

Live's timeout per cell is now 2,400 s (was 1,500), for load: a "hang" cell means rerun it, not "caught".

If a job has died and its marker is missing, restart it from ~/dev/sa-rust, with `S4=~/sa-rust-ids-work/slice/step4`:
```
setsid nohup bash rust-spike/slice/run_history.sh $S4/hist 3 > $S4/hist.log 2>&1 < /dev/null &
setsid nohup bash -c ". ~/sa-rust-ids-work/env.sh; export PYTHONPATH SA_EVAL_DATA PYTHONHASHSEED; exec \$PY rust-spike/slice/mutate_live.py $S4/mut-live $S4/live-ref --only 10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34 --jobs 4 --timeout 2400 --resume" > $S4/mut-live.log 2>&1 < /dev/null &
rm -f $S4/run5-harness-finished.tmp; setsid nohup bash rust-spike/slice/run5_harness.sh $S4 > /dev/null 2>&1 < /dev/null &
```
Note `env.sh` reassigns `W`, so don't name your own path `W`.

## What's left, once the markers appear
From ~/dev/sa-rust: `. ~/sa-rust-ids-work/env.sh; export PYTHONPATH SA_EVAL_DATA PYTHONHASHSEED; S4=~/sa-rust-ids-work/slice/step4`.
1. **History:** `$PY rust-spike/slice/historycmp.py $S4/hist > rust-spike/slice/results/step4-history.md`, then delete `step4-history-interim.md`. Every row must be finished with 0 differing; read the "against itself" table for query 873. **Run 6 doesn't come from that table:** its `0/0` column isn't a count, since the counters exist only under `--check raw`. Either run `live.py dev rust OUT --check raw` and the same for fuzz and read `backend_dropped` and `backend_created` in the total, or cite step 3's 918 of 918 and 3,133 of 3,133 on the same crate and say so.
2. **Live:** `cp $S4/mut-live/table.md rust-spike/slice/results/step4-mutants-live.md`. Base row must read "no". Score 27, 29, 30, 31 in these columns; they're already caught in nested.
3. **Harness:** `tail -1` each `$S4/run5-harness-{rust,python}.txt` must show solvers made on its own backend (`rust_made`, `py_made`), and rc. There's no compare tool: compare with timings removed: `diff <(sed -E 's/\([0-9.]+s\)//' $S4/run5-harness-rust.txt | head -n -1) <(sed -E 's/\([0-9.]+s\)//' $S4/run5-harness-python.txt | head -n -1)`, and read any mismatch group or differing line one by one. Don't use `--confirm` or `hashseed`: their subprocesses don't get the patch.
4. **Update `step4-gate.md`:** remove "not decided", fill history, live and harness. Restate the three numbers. Pass rule: every mutant caught, argued equivalent in writing, or stated as not caught. 5, 6, 7, 9 lean on the API fuzzer alone.
5. Commit, push to origin rust-slice, `agent report`, tell the architect. Then stop: step 5 is another session.
Optional: `mutate_boundary.py --suite FILES`, for whether the suite itself catches callback bugs. Not run.

## For step 5 (carried from sa-rust-17)
- `rust-spike/slice/run-slice.sh` still names `/work/src/base-9bafaa5` and runs `qtime.py`. It needs the current source and the Rust backend.
- **Crossing counts (step 3, measured):** hook calls 34,788 on dev and 1,241,630 on fuzz.
- **Plan section 2 correction:** its "80k on dev, 2.67M on fuzz" counted internal calls too. Real crossings are 44% and 46% of that, so the callback part of the estimate is about 2.2 times too high. Use the measured counts.
- Report full API and abi3 both (plan section 4).

## Running the tools
As in `HANDOFF-sa-rust-16.md`. Suite: `bash rust-spike/slice/run_suite.sh DIR rust|python [FILES]`; `suite_report.py RUST PYTHON [--list OUT]`. Audit-off: `SLICE_AUDIT_OFF=1` or `2`. Reach: `SLICE_SO=$S4/probe PROBE_FILE=FILE`. Don't `pkill -f` a pattern that's also in your own command.
