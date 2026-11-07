# Handoff: sa-port-38, component 3 (transfer core), issue 323

**Not landed. Nothing of component 3 is on `rust-slice`.** No jobs are running. The architect asked me to hold at dfa7b45 and asked the planner whether component 3 must rerun for it.

## Source

| What | SHA |
|---|---|
| Tested, all runs | `port/3-landing-5` f9eb6de, on `rust-slice` dc3f15d, module sha256 bf4cf6d6ce78 |
| Rebased, nothing but smoke on it | `port/3-landing-6`, this commit, on dfa7b45 |

**The bar on f9eb6de is met, and the full results are in `rust-spike/slice/results/port-3.md`.** Suite 5,961 / 77 / 46, 0 changed. Fresh 10 of 10 byte-identical. Controls 6 of 8. History 14 runs, 0 differ. Firings 0 findings.

## Evidence for the planner's question: f9eb6de against dfa7b45

- 7 files differ, knowledge tools and docs only; 0 diff lines in `solver_rs`, `lra`, `satassume`, `tests`.
- `backend.install()` doesn't load `knowledge_live`; `transfer:1:300` on orion byte-identical for py, rust, shadow on the rebased tree.
- **Not traced:** `convert.py` names `knowledge_live`. `convert.py` itself didn't change in this move.

## Not run, in order

1. Get the planner's answer through the architect. Don't restart for dfa7b45 before it.
2. **No rerun needed:** `git fetch`; if `rust-slice` is still dfa7b45, `git push origin HEAD:rust-slice`, no force. If it moved, rebase, say what moved, and apply the same rule.
3. **Rerun needed:** `cd ~/sa-rust-ids-work/sa-port-38/jobs; setsid nohup bash land38.sh SHA BRANCH > land.log 2>&1 < /dev/null &`. About 17 minutes when the paretos are free. Read `s1` as below, then update the report's numbers.
4. Report, per the brief's DONE WHEN.

## Reading a run

Pull rows to `~/sa-rust-ids-work/sa-port-38/s1/`, then `suite_split_named.py RUST PYTHON --list FILE`. By-id comparison: `byid.py` in my scratchpad was inline and won't survive; compare `rows.*.jsonl` `outcome` against `port-census/pr328-check/suite-rust`.

## Incidents

- **Orphan from the 11:47 kill:** `ssh ... acquire` under holder sa-port-28, not touched. It and my stopped build's request were then granted with nothing behind them. I released `432d2772` and `94413142` on pareto1 by id, after checking holder, reason and that no process held them.
- **My own stale history run:** stopping the old run on 69639da left its `xargs` alive (PID 3421986, parent init), and it respawned `live.py`. It ran unleased for about 3 minutes; journal entry 8cb0c62 says about 8, which is wrong. Stopped by PID. That run's `done.txt` got 2 `rc=143` rows, and the later run on f9eb6de cleared them: 28 rows, all 0.

## Traps

- **Stopping `machine run` doesn't stop the job on the host.** Also stop its job there, including `xargs`, which holds no output path in its command line. Check by elapsed time so a new job isn't caught.
- `land38.sh` removes `~/sp19/out38` on both hosts; pull what you need first.
- `mutate_transfer.py`'s copied crate needs `lra/port/src` beside its work directory: `mut38.sh` does it, the tool isn't fixed. `mutate_slice` has the same gap, and `mutate_live.py --handlers` raises "tool 4 is already in use" (sa-port-39, not used here).
- `rust_plugin` loads `handler_count` in `run_suite.sh` now.
- Local branch name in this clone is `port/3-landing-2`, which has diverged from its remote. Use `git checkout -B port/3-landing-6 origin/port/3-landing-6`.

## File:line map

| Topic | Where |
|---|---|
| Report | `rust-spike/slice/results/port-3.md` |
| Inventory row | `rust-spike/PORT-INVENTORY.md`, section 10, row 3 |
| Both-backend split | `rust-spike/slice/suite_split_named.py`; `suite_split.py` is component 6's |
| Installs, EUF, transfer, LRA | `rust-spike/slice/backend.py` `install`, `rust_plugin.py`, `live.py` |
| Polar read, term handle | `solver_rs/src/transfer_py.rs`, `solver_rs/src/handle.rs` |
| Job scripts | `~/sa-rust-ids-work/sa-port-38/jobs/`: `land38.sh`, `fresh38.sh`, `suite38.sh`, `mut38.sh`, `hist38.sh`, `setup38.sh`, `p38_env.sh` |
| Output | `~/sp19/out38/` on pareto0 (fresh, suite) and pareto1 (mut, hist); `~/sa-rust-ids-work/sa-port-38/s1/` on orion |
| Older context | `HANDOFF-sa-port-28.md`, `HANDOFF-sa-port-25.md` |
