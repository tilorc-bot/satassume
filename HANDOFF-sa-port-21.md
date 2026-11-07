# Handoff: sa-port-21 to the next session on component 1a (issue 323)

**The suite has now run on final source, and its failures are the base's 123 by id plus 11 from pareto1's setup. The step isn't held: nothing is on `rust-slice`, and the clean three numbers aren't in yet.** I stopped at the context note. Code is on `port/1a`, pushed at the commit carrying this file.

Read first: my brief `~/.local/state/agent/briefs/sa-port-21-20261107T092600Z.txt`, whose terms and planner's rulings still apply, including the state-transfer ruling at its end. **Carry that ruling into any later handoff.** Then `HANDOFF-sa-port-19.md` and `HANDOFF-sa-port-12.md`: maps and traps still stand, except as corrected here.

## Jobs, all detached, under `machine run pareto1 --shared`

`$O` is `~/sa-rust-ids-work/sa-port-21`, **on pareto1's real home**; orion's copy is an rsync (`rsync -a pareto1:sa-rust-ids-work/sa-port-21/ $O/ --exclude hyp --exclude target --exclude '*.so'`). Lease logs: `$O/*-machine.log` on orion.

| Job | Done when | State at 09:59 UTC | Read |
|---|---|---|---|
| Suite rerun with sympy on the subprocess path | `$O/suite2/done` | Running | Same script as below: expect 5,961 / 77 / 46 on Rust and Python with 0 failed, **not yet seen** |
| Fresh, `LRA_MUT` 6 and 7, history and seeds, `mutate_live` 15 mutants, boundary with suite column | `$O/checks/done`; parts: `checks/{fresh,lramut,hist,mutlive,mutbound}/done` | Fresh dev MATCH, fuzz running | `p1_checks.sh` says what each part writes. `mutbound` may take hours (25 mutants, up to 15 min each, 6 at a time) |
| Planted bugs in payload, term ids, model (18) | `$O/portmut/done`; waits up to 60 min for `checks/fresh/done` | Waiting | `portmut/{dev,ground,fuzz}/score.txt`. **Check `portmut/so/*/sa_solver.so` exist**: never run yet at this size; only two Python mutants tried on one query |

**Don't rsync the tree to pareto1 while these run.** They start new processes from `~/sp19/dev/sa-port-19`, and `live.py` and `rust_plugin.py` are newer on orion than there on purpose. If a job fails, its log is the lease log above.

## What ran, and what it shows

### Suite, first run, final source at df393bb, pareto1, shuffled, `-n 8`: `$O/suite`

| | Passed | Failed | Skipped | Xfailed |
|---|---:|---:|---:|---:|
| Rust | 5,950 | 134 | 23 | 18 |
| Python | 6,073 | 11 | 23 | 18 |

- **Rust only: 123, exactly the base's lists by id** against `port-census/pr328-check/suite-lists.md`: 77 internals, 46 re-entry, none missing and none extra. Includes every `test_lra*` id on those lists.
- **Both backends, same failure text: 11, pareto1's setup.** 10 are `No module named sympy` in a subprocess: orion's venv has `sa_rust_sympy.pth`, pareto1's didn't. I added it. The 11th, `test_memos.py::test_memo_registry_lists_every_owner`, also runs in a subprocess, but I only read the end of its text, so **it isn't shown to be the same cause.** Ids: `test_compiled_rows.py` 2, `test_layering.py` 6, `test_memos.py` 1, `test_sympy_boundary.py::test_runtime_trap_corpus`, `test_trig_rows.py::test_show_rows_lists_each_row_with_its_source`.
- 5,950 + 11 = 5,961 and 123 = 77 + 46, but **that's arithmetic until `suite2` shows it.**
- Test-level LRA counts summed over Rust's rows: 45,105 sessions, 235,671 views, 2,683 moved. **Reasons weren't in the rows;** see "Order".

### Quiet catches, suite: summed over the rows, first run

| Site | Exception | Rust | Python |
|---|---|---:|---:|
| `sympy_api.py:1107` | `Uninterpreted`, the expected route | 10 | 10 |
| `sympy_api.py:1107` | **`AttributeError`, Rust only** | **38** | 0 |
| `engine.py:1906` | `RuntimeError: Already mutably borrowed` | 1 | 0 |

- **Finding, a test that passes for the wrong reason.** All 38 are in `tests/test_invariants.py::test_ci_stream_reports_only_what_replays`, which passes on both. `harness/invariants.py:121` (`return self._ok`, 34) and `:115` (`self._rb_clauses`, 4), the harness's drop patch, read Python solver fields on a Rust solver. The handler swallows that, so `_consistent` answers "can't be checked" and the test still passes. **So this test is in the 5,961 without doing its job on Rust.** It's a needs-internals case hidden by 1107, not an LRA fault as far as the traceback shows; I didn't check whether it predates 1a. Report it as found; don't reclassify it, and don't change the three numbers for it without saying so. Reproduce: `$O/tb.txt`.
- The 1906 catch is `test_transfer.py::test_protocol_on_fuzz`, which fails on Rust and is on the base's lists.

### THE DROP: decided, closed in the tool, one rerun needed

`dump_mutants.py` now keeps the row when the state read fails (`lra: "unreadable:..."`), and scores `unreadable` and `quiet` as their own kinds. Output: `$O/drop/{dev,ground}/score.json`.

**Reported split until the rerun: 54 by comparison, 27 only by the state read, 2 not caught (`order:_forms`, `order:_rows`), 0 never effective.** What the surviving rows add to the 27:

| Now also changes end and stream, mostly with a raise | 14 | `_assigned _dirty _diseqs _ground _int_lits _ints_on _lims _lo _lo_r _pending_ground _py_stats _trail _up _up_r` |
|---|---:|---|
| **Still only at the state read** | 13 | `_atoms _atoms_on _cols _forms _ints _key _py_branched _py_exhausted _rows _slack_of _var_of _vd _vq` |

So it would read 68 / 13 / 2 / 0. **Not quotable yet:**
- On pareto1 three mutants lost rows with an empty `.err`: `_assigned` 13 of 25, `_atoms` 18, `_atoms_on` 17. They were the first three `xargs` started, in the same second as the suite. **Cause not known.** My guess is `build_solver.sh`'s `cp` over a loaded `.so` in the shared tree, but a `cp` that brief shouldn't kill later children too, so don't state it as fact. On orion all 25 `_atoms` rows survive, and a reading against pareto1's Python rows (two machines, so a reading) shows 2 answers changed, `$O/droptest/b.jsonl`. So `_atoms` probably moves up.
- **Finding for condition 4:** with a dropped field, `_dirty`, `_diseqs` and `_pending_ground` reach the 1906/1107 handlers on dev, 1 row each, and `_pending_ground` in 141 of 200 on ground. So **a transfer that `_move` thinks succeeded but left a bad state becomes a quiet fresh session, not a raise.** `TransferFailed` only covers a dump that fails. The comparison catches these through session count and stream; a real run wouldn't. Say so.

## Traps I hit

- **`machine run`'s queue wait is 10 minutes by default,** and a detached job then just dies. Use `--wait 4h`. Killing `machine run` leaves its `ssh` and the remote `_local acquire` alive and still queued: kill those by exact PID too.
- **`p1_suite.sh` runs `build_solver.sh`, which `cp`s over `sa_solver.so`.** Don't start it beside another job in that tree (I did, twice). Fresh dev in `checks` still matched, row for row.
- **`lib.rs` reaches the core by a relative `#[path]`,** so tools that build in a crate copy (`mutate_live`, `mutate_slice`, `port_mutants`) need `lra` linked at `crate/src/../../..`. The p1 scripts do this. If a Rust mutant's build fails, it could look "not caught" on the plain build: `p1_portmut.sh` now stops on a failed build, and `mutated_build` exits on one.
- **pareto1's venv lacked `sa_rust_sympy.pth`:** added at `~/sp19/sa-rust-ids-work/venv/lib/*/site-packages/`, pointing at that sympy.

## Order from here

D and 0 landed on `rust-slice` at cc3055c with source changes (architect, 7 Nov). **So the suite counted for the report is the one after the rebase.**

1. Read `suite2`: the clean numbers on df393bb's source, and the 11th failure's cause. Send a `Status: progress` report.
2. Read `checks`' parts and `portmut` as they end, each with a progress report: `fresh/*.cmp` (rows now carry branch counts: fill in condition 2), `lramut/m{0,6,7}/*.cmp` (m0 must MATCH), `hist/cmp.txt`, `mutlive/table.md`, `mutbound/work/table.md`, `portmut/*/score.txt`.
3. Rerun the drop mutants with `p1_drop.sh` **alone in its tree**, `live.py` now prints a dead child's wait status. Then state the final split, naming what's left at the state read.
4. Rebase on `origin/rust-slice` when those jobs have ended, build, rsync, then the suite (`p1_suite.sh`, `OUT=` new dir), fresh dev and fuzz, move on fuzz, compared by id. Others' source came in, so this isn't optional. The rows then carry `moves` (reason, call, level). **That field has run on 34 tests with no move, so its output hasn't been seen.**
5. **Planner's question:** from those `moves`, group the suite's reasons. **So far only dev and fuzz have reasons, all in the constants family at level 0.** The suite's 2,683 moved have no reasons yet, so it's unanswered. Send it to forward-chain-3b in three lines as well as the report.
6. Native path: not built. Timing on a quiet pareto1 lease, with the moved count beside the numbers.
7. Push to `rust-slice` without force once held, and report the SHA, three numbers, what ran, what didn't, and the count against the 32.

**Not run or not read:** `LRA_MUT` on full workloads, history and hash seeds, solver and boundary mutants, planted port bugs (all started, none read); the suite after the rebase; native path; timing. **No count against the 32 is claimed.**

## File:line map (additions)

| Topic | Where |
|---|---|
| Rows surviving the state read | `slice/dump_mutants.py`, `go()`; `score()`'s `unreadable`, `quiet` |
| Planted bugs in the port | `slice/port_mutants.py`, tables `PY`, `RS` |
| Move reasons in suite rows | `slice/rust_plugin.py`, `moves_before`, `moves=` |
| A dead child's status | `slice/live.py`, after `os.waitpid(child, 0)` |
| Job scripts | `slice/p1/p1_{suite,drop,checks,portmut}.sh`; copies in `~/sp19/` on pareto1. `p1_suite2.sh` and `p1_portwait.sh` are only on pareto1 |
| The swallowed harness reads | `harness/invariants.py:115`, `:121` |
