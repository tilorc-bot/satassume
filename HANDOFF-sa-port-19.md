# Handoff: sa-port-19 to the next session on component 1a (issue 323)

**Fresh fuzz is in and matches Python. The step isn't held: nothing is on `rust-slice`, the suite's three numbers aren't in, and no count against the 32 is claimed.** Code is on `port/1a`, pushed at the commit carrying this file. I stopped at the context note.

Read first: my brief `~/.local/state/agent/briefs/sa-port-19-20261107T085132Z.txt`, whose terms and planner's rulings still apply, including the state-transfer ruling at its end. **Carry that ruling into any later handoff.** Then `HANDOFF-sa-port-12.md`: its "Findings", "Traps", "Order from here" and file:line map still stand, except as corrected here. My progress report is 03e6f83 (`agent journal -v --session sa-port-19`).

## Jobs

`$B12` is `~/sa-rust-ids-work/sa-port-12`. `$P` is `~/sp19/out` on pareto1.

| Job | Where | Done when | State at handoff | If it's missing |
|---|---|---|---|---|
| sa-port-12's suite, Rust then Python | orion, `$B12/suite1-*` | `$B12/suite1.done` | Rust side still running 09:08 UTC, no `exit.txt` | Don't touch it. It's a reading anyway: use the pareto1 suite below |
| sa-port-12's dump mutants, dev | orion, `$B12/dm/dev` | `done`, `score.txt` | 77 of 83 at 09:08 UTC | Don't restart while it runs |
| Move at every 16th call, fuzz | pareto1, `$P/mv` | `$P/mv/done` | In its count phase | Restart command below |
| Ground workload | pareto1, `$P/ground` | `$P/ground/done` | Fresh compare done, rest running | Restart command below |

Mine were started from this session and may die with it. **Check the marker and `machine ls` first.** Restart: `machine run pareto1 --shared -r WHY -- bash /home/tilo/sp19/p1_job.sh /home/tilo/sp19/p1_move.sh` (or `p1_ground.sh`). Run it in the background, and move `$P/mv` aside first.

## What ran, and what it shows

| Run | Result | Where |
|---|---|---|
| Fuzz, **fresh** | 3,000 queries, 4,943 sessions, 0 differences in answer, message, session count, end, stream, LRA state. `answers_sha` 173502b6ef285ad6 both. **MATCH** | `$P/fresh2/fuzz.cmp` |
| Dev, fresh, rerun | 1,985 queries, 3,332 sessions, 0 differences. `answers_sha` 31cd0945c07f02a6, same as sa-port-12's on orion. **MATCH** | `$P/fresh2/dev.cmp` |
| Ground workload, fresh | 18 chosen queries, 24 sessions, 0 differences. **MATCH** | `$P/ground/fresh.cmp` |
| `test_lra_dirty.py`, `test_lra_raises.py` under pytest | 3 passed | `~/sa-rust-ids-work/sa-port-19/lra_tests_pytest.log` |
| Faults planted in LRA hooks, dev | Table under "1107" | `$P/exc/` |

`fresh2` ran one edit before 628a82c: that edit only adds `branching` to rows and `_moved_branches` at a move, so its rows have no branch counts. The final fresh rerun will have them.

### The group counts, sessions with an LRA theory, fresh

| Run | Rust throughout | Moved | Python from the start |
|---|---|---|---|
| dev | 113 | 109: 95 `constant` at call 0; 6 and 4 `constant coefficient` at calls 31, 32; 2 at call 60; 2 `constant offset` at call 31 | 0 |
| fuzz | 2,569 | 623: 501 `constant` at call 0, 122 at call 1 | 0 |

Every natural move is at level 0 and in the constants family. Queries kept wholly on Python aren't in these rows. Item 8's answer so far: nothing outside constants keeps the transfer alive on dev or fuzz; **the suite's reasons are still needed.** The ground workload's 19 Rust sessions were chosen, so don't add them to these.

### Quiet catches

`catch_count.py` counts exceptions on their way into both handlers, and `live.py` and `rust_plugin.py` put them in the row (`caught`). The suite's rows will carry them, so **sum them when the suite is read.**
- Counted so far: 0 at each site on fresh dev and fuzz, both backends.

### `sympy_api.py:1107`, read and run

`_consistent` catches `Exception` from `_formula` and `Engine.verdict` and returns False, meaning "can't be checked", so the caller answers under the whole set instead of a part. An exception raised outside 1906's `try`, or re-raised there, ends up here. A `BaseException` such as `TransferFailed` passes through.

Probe: a `RuntimeError` planted at every 5th hook call index on dev, 1,815 items. Answers only; state isn't compared.

| Fault | Raises out | Comes back with no error |
|---|---|---|
| Persistent, Rust | 1,671 | 144, all through 1107, on 12 queries (q1950 to q1961), references all `None` |
| Persistent, Python | 1,671 | 144, same 12 queries |
| Once, Rust | 1,101 | 714 on 87 queries (690 at 1906 only, 24 at 1107), all with the reference answer, including 326 with a True or False reference |

So a one-off Rust fault in the complete check doesn't show in answers, because the retry recovers it. A persistent one mostly raises, and where it doesn't, it can't be told from an ordinary unknown. One-fault mode on Python wasn't run. Python's split between handlers differs from Rust's (1,045 and 626 against 1,101 and 570) because Python's own internal hook calls also pass through the planted wrapper and advance the count; that's by reading, not tested.

## Findings to carry into the report

1. **Correction to sa-port-12's fresh dev row:** under `--fork`, `python solvers made 0 0 | reentry 0 0` showed nothing, because the totals stayed in the parent. Children now report them. Real values: Python solvers 3,332 and 0 on dev, 4,943 and 0 on fuzz; reentry 0. Row comparisons were never affected.
2. **`_ground` and `_pending_ground` are reachable by real queries,** e.g. `Q.lt(x + 1, x + 2)`. `live.py ground` (`ground_queries.py`) holds 18. They were picked to reach those fields, so they say nothing about frequency.
3. The rest of sa-port-12's findings and names still stand, including the shims (`_n_conflicts` with its 64 tests, `_view`, `certified`).

## Traps I hit

- **`pkill -f` matched my own shell** and killed it (exit 144). Stop a job by exact PID. No sibling was hit.
- **`livecmp` prints DIFFER if a file has no `total` row,** even with every count at 0. Use `p1/merge_shards.py` for shards. It rebuilds the total: my first fuzz merge didn't, and that output (`$P/fresh/fuzz.cmp`) shouldn't be quoted.
- **Fresh rows from pareto1 are the reference for pareto1 runs.** Dev's `answers_sha` agrees with orion's, but use one machine per compare.
- **Dates:** pareto1's local clock isn't UTC. Use `date -u`.

## pareto1

Setup was short, and it's 15 to 20 times faster than orion under load: fresh fuzz took under 3 minutes in shards. `~/sp19` holds a tree copy, venv, sympy, data and shim. `p1_job.sh` sets `HOME=~/sp19`, so the slice scripts find their own `env.sh`. Scripts are in `rust-spike/slice/p1/`, with copies in `~/sp19/`. **The tree there is an rsync, not a git clone:** run `rsync -a --exclude target --exclude '*.so' ~/dev/sa-port-19/ pareto1:sp19/dev/sa-port-19/`, then rebuild (`sh build_solver.sh` under `p1_job.sh`; it's already built at this source's crate). Orion is aarch64, pareto1 x86_64. Say which machine each number came from. The suite's base numbers (5,961 / 77 / 46) are from orion, so run Python on pareto1 beside Rust, and read any x86-only difference against that.

## Order from here

`HANDOFF-sa-port-12.md`'s items, with what's left:

1. **Suite:** run it on the final source, both backends, on pareto1 (`bash run_suite.sh WORK rust|python` under `p1_job.sh`, `SLICE_SUITE_SHUFFLE=1`, `PYTEST_N="-n 8"`). sa-port-12's ran before 496f250, so it's a reading only. Then `suite_report.py`, by id against 5,961 / 77 / 46, `test_lra*` id by id against `port-census/pr328-check/suite-lists.md`. Sum `lra` and `caught`.
2. **Dump mutants:** read `$B12/dm/dev/score.txt` and `$P/ground/dm/score.txt`. Name each one missed and each one never effective. `_rows`' outer order, `_cols` and `_forms` are compared sorted, so an order mutant there may need naming.
3. **Move on fuzz:** read `$P/mv/fuzz.cmp`, `count.txt`, `branch.txt`, `stride`. State it's sampled, and at what stride. Confirm branched and exhausted sessions are included; if `branch.txt` shows none, choose queries that branch. Fresh fuzz itself is done.
4. `LRA_MUT` 6, 7 on full dev and fuzz with `--so` and a mutant build (`--features mutants`). The pytest half is done.
5. `real_theory_fuzz`, `test_solver_real_theories`, `run_history.sh`, `historycmp.py`, hash seeds. All of these suit pareto1.
6. Solver mutants 2, 5, 6, 7, 9; boundary mutants including `--suite` and the 10 with no real-engine catch; new mutants in payload conversion, term ids, model rendering.
7. Native path, then timing on a quiet pareto1 lease, with the moved count beside the numbers.
8. The planner's question, once the suite's reasons are in.
9. Rebase on `origin/rust-slice`, rerun the suite if others' source came in, push without force, report.

**Not run at all:** the suite on final source, `LRA_MUT` on full workloads, history and hash seeds, solver and boundary mutants, native path, timing.

## File:line map (additions; the rest is in `HANDOFF-sa-port-12.md`)

| Topic | Where |
|---|---|
| Catch counter | `slice/catch_count.py`; wired at `live.py`'s `caught` and `rust_plugin.py`'s `caught=` |
| Fork totals in rows | `live.py`, `rec["child"]`, read back after `if args.fork:` near the totals |
| Fault probe | `slice/except_probe.py` (`--persist`, `--py`, `--stride`) |
| Branch counts | `state.py` `lra_branching`; `lra_backend.py` `_move`, `_moved_branches` |
| Ground workload | `slice/ground_queries.py`; `live.py` `load` |
| Handlers | `satassume/engine.py:1906`; `satassume/sympy_api.py:1107`, callers at `:973`, `:995`, `:1083` |
