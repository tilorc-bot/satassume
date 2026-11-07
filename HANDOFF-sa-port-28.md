# Handoff: sa-port-28, component 3 (transfer core), issue 323

**Not landed. Nothing of component 3 is on `rust-slice`.** Handed off at the context note. Landing branch: `origin/port/3-landing-2`, this commit, rebased on e5dd23f (component 2, EUF). Older branches: `port/3` (sa-port-25's), `port/3-landing` (1e36724, on ceb6ceb). `HANDOFF-sa-port-25.md` still has the older context and map; where they differ, this file is newer.

**The bar is now** `~/dev/architect/briefs/addenda/sa-port-landing-bar-ruling.txt`, on the landing source after rebase. It replaces HELD TO for landing.

## The e5dd23f rebase isn't trivial

Conflicts in `backend.py`, `live.py`, `rust_plugin.py`, `lib.rs`, all resolved by keeping both installs. More important: `rust` mode now means **Rust EUF and Rust transfer together**, and `PyClasses` reads Rust's `RepView` and `MembersView`. That pair has had only a smoke check: `transfer:1:300` byte-identical to Python with the same crossing counts, and `transfer_fuzz --only basis,wanted`. **Nothing from 1e36724 counts toward landing.** `shadow` mode on Rust EUF hasn't run by hand.

## Running now (detached, started at this handoff)

| Job | Where | Ends with | What |
|---|---|---|---|
| fresh | pareto0 `~/sp19/out28b/fresh` | `DONE`, `progress` | dev, fuzz, transfer:1:300, transfer2:7:1500, corpus; seeds 0, 1; py, rust, shadow. Took 14 min on 1e36724 |
| suite | pareto0 `~/sp19/out28b/suite` | `DONE`, `rust/exit.txt`, `python/exit.txt`, `plant-*.out` | Both backends with `-p handler_count`; plant control first |
| ctl | pareto1 `~/sp19/out28b/mut/ctl` | `../ctl.DONE`, `../ctl.exit`, `table.md` | Controls w01 w02 t05 t42 t43 p03 p06 p07, for bar item 3 |
| surv (old) | pareto1 `~/sp19/out28/mut/surv` | `../DONE`, `table.md` | **On 1e36724**, tree `~/sp19/dev/sa-port-28`: m2's survivors on transfer2:7:1500 and fuzz. Informational, not on the bar. Don't touch that tree until it ends |

Logs on orion: `~/sa-rust-ids-work/sa-port-28/jobs/*.machine.log`. Read a job's `tree.txt` for the SHA, and rerun if `rust-slice` moves source again. `machine run` runs on the host; pareto0 has no rsync or cargo, so its `.so` is pareto1's copied by `scp` (same sha256 was checked for 1e36724; check again).

## Results on 1e36724 (Rust `P`, Python's EUF): not landing evidence

- **Fresh:** all 10 workload and seed pairs, exits 0, `rust` and `shadow` byte-identical to `py`.
- **Suite:** Rust 5,960 passed, 124 failed, 23 skipped, 18 xfailed. Python 6,083 passed, 1 failed. Against the base: 0 new ids, 0 gone, Python 0 changed, Rust 1 changed.
  - `tests/test_constfield.py::test_powers_are_refused_quickly`, passed to failed: `assert time.perf_counter() - t < 0.5` read 0.641 s, `test_constfield.py:713`, with two suites and two fresh streams on a shared machine. **Load is a candidate, not a shown cause.** If it fails on the landing run, run it alone on both backends, and on Rust's base tree at comparable load.
  - Python's one failure is `test_performance_smoke_300_vars`, which also fails in the base's Python rows.
- **Firings (`suite_split.py`):** passed with no Rust-only firing 5,959; with one, 1, the ruling's named `test_ci_stream_reports_only_what_replays` (`_ok`, `_rb_clauses`). Findings 0. Python-only firings 0.
  - In a test that didn't pass: `test_transfer.py::test_protocol_on_fuzz`, `Engine._build_context`, `RuntimeError: Already mutably borrowed`, 1. List it. That test is in `suite-lists.md` as `borrow RuntimeError`.
  - Pulled to `~/sa-rust-ids-work/sa-port-28/s1/`, `split.jsonl` there.
- **Controls (ctl, exit 0, base clean):** p03, p06, p07, t05, t42, t43, w01, w02 have rows. w01 `answer@1721 state@1709` on dev is a comparison catch; t42 and t43 show API only so far. Read the new table for the bar.

## Settled, keep naming

- **Counter on a Rust raise fires:** p06 q=50 on dev, q=239 on transfer:1:300; p07 q=264 on transfer:1:300. p07 on dev has no q, so that raise wasn't in a handler.
- **Counter as a suite plugin fires:** planted raise at both sites on both backends (`suite_plant_handlers.py`), control 38 firings on Rust, 0 on Python.
- **transfer.py:464 not reached by the engine** on transfer2:7:1500 (:463 ran 3,234 times); `_spread`'s :382 to :384 neither. Named gap, not shown unreachable, doesn't block.
- **stream.pkl holds no `P`:** the copy matching 94db857d9d5d has 0 occurrences of "satassume" in its bytes, read without loading. Likewise battery-stream and gate2-stream.
- **`P`'s 9 differences, causes shown by running them** (bar item 5), `sa-port-28/smoke/p_cause.py`:
  - `is_dataclass` False, `__dict__` AttributeError: fixed slots, no instance dict, no `__dataclass_fields__`.
  - 6 pickle rows: Python's bytes rebuild with no arguments, then BUILD a dict. Protocols 0, 1: `object.__new__(P) is not safe`. 2 to 5: `P.__new__() missing 2 required positional arguments`. Rust's bytes load on both classes.
  - Subclass with a `pred` property: Python's frozen init writes through the property and raises; Rust's `__new__` writes its slot, so it builds and the property wins on read.
- **`transfer_wanted`'s fix stays named** (`HANDOFF-sa-port-25.md`, Found 1).
- **Mutants, older source.** m2: of 84, 58 engine comparison, 11 API only (t18 t23 t28 t42 t43 t46 t58 t59 p02 y01 y02), no catch t20 t29 t30 t32 t34 t35 t47 t57 p04 (not argued equivalent), 6 superseded f rows; none by crash only. m3: 20 of 20 by API; through the engine only w01 to w05, so **all 12 `P` mutants have no engine catch**.
- **s2** had Python's `P`: same on all 16 comparisons.

## Not run, in order

1. Read the fresh, suite and ctl jobs above against the bar's five items. A difference is reported with its smallest case, never reclassified. If the pair differs, compare `SLICE_EUF=py` to separate the two components.
2. Land: `git push origin HEAD:rust-slice`, no force, if the source hasn't moved. Otherwise rebase, say what moved, rerun if it's source.
3. Landing report: SHA, the three numbers (S's standing per the planner's wording, the 46 kept listed), split, what was and wasn't run, how many of the 32 runtime modules this adds, queries kept on Python by reason, the `_n_conflicts` shim and its 64 tests, `pyset.rs` tied to 3.12's set order. List the bar's "before any backend PR" items as not run; don't quote withdrawn conditions as met. Update section 10's row.
4. Not done, on the PR list: `run_live.sh`, `run_history.sh`, boundary re-score, mutants 2, 5, 6, 7, 9, counts with `--sympy`, speed.

## Traps

- `tail --pid=$!` after `setsid` waits on nothing, since setsid forks: it returned at once. Find the `machine run` PID with `ps` and `rg '[m]achine run'`.
- `suite_split.py` refuses a directory with no handlers files, so the base's rows can't be its Python side.
- `read_offline` hashes `satassume/knowledge/*` against `offline_data.json`: editing those sources refuses at import. By design.
- `~/dev/sa-port-17`'s `sa_solver.so` is from older source: build before using it. The worktree `~/sa-rust-ids-work/sa-port-28/wt` holds `port/3-rebase-wip`.

## File:line map (new or changed)

| Topic | Where |
|---|---|
| Polar read once, `read_offline`, `_polar_index` | `solver_rs/src/transfer_py.rs`, above `impl PyTransfer` |
| Called from | `backend.py` top; `transfer_fuzz.py` top, with `UNREAD` and `part_basis` |
| Term handle | `solver_rs/src/handle.rs` |
| Both installs | `backend.py` `install`; `live.py:293`; `rust_plugin.py:73` |
| Rust EUF's views | `solver_rs/src/euf_py.rs:172`, `:178`, `:226`; read by `transfer_py.rs` `PyClasses` |
| Split | `suite_split.py`; plant `suite_plant_handlers.py` |
| Job scripts | `~/sa-rust-ids-work/sa-port-28/jobs/`, copied to `~/sp19/` on both paretos |
