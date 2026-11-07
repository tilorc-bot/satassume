# Handoff: sa-port-38, component 3 (transfer core), issue 323

**Landed on `rust-slice`; nothing is left to do for component 3.** This file stays for its traps and map. No jobs are running.

## Source

| What | SHA |
|---|---|
| Tested, all runs | `port/3-landing-5` f9eb6de, on `rust-slice` dc3f15d, module sha256 bf4cf6d6ce78 |
| Landed, short check only | on dfa7b45, per the planner's rule; see `port-3.md` |

**The bar on f9eb6de is met, and the full results are in `rust-spike/slice/results/port-3.md`.** Suite 5,961 / 77 / 46, 0 changed. Fresh 10 of 10 byte-identical. Controls 6 of 8. History 14 runs, 0 differ. Firings 0 findings.

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
