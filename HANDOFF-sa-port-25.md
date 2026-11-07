# Handoff: sa-port-25, component 3 (transfer core), issue 323

**Not done, and not on `rust-slice`.** Handed off at the context note, 10:11 UTC. Everything is on `port/3`. Brief: `~/.local/state/agent/briefs/sa-port-25-20261107T100042Z.txt`; its terms still apply. `HANDOFF-sa-port-22.md` still has the older context; where the two differ, this file is newer.

**No fresh run with Rust `P` on final source, no suite, no boundary re-score and no counts have run.** What has a result: `part_p`, the `transfer_wanted` divergence, and the quiet counter's firing on Python raises. Progress report: f53014d.

## Running now: don't rebase or edit `satassume/` until all four end

All four import `satassume` from this clone. Their tools and `.so` are frozen copies, so editing `rust-spike/slice/` and rebuilding are safe (checked for m2 and s2: each has its own `tools/sa_solver.so`).

| Job | Where | Ends with | State at 10:10 UTC | What it is |
|---|---|---|---|---|
| m2 | `~/sa-rust-ids-work/sa-port-22/m2/` | `exit.txt`, `table.md`; `ended` is written at the end, though a stale one from a stopped run was there at start, so go by `exit.txt` | 16 rows of 85 (84 mutants + base), about 1.5 rows a minute | Old source. **Base row is clean in all five columns.** Its `f` and `w` rows are superseded by m3 |
| s2 | `~/sa-rust-ids-work/sa-port-22/s2/` | `DONE`, `progress` | Finished `transfer:2:1500` and `dev` at both seeds; on `fuzz` seed 0, `CMP` same so far; `corpus` not started | Rust mode has **Python's `P`**, so it doesn't test `P` |
| reach | `~/sa-rust-ids-work/sa-port-25/reach/` | `DONE`, `progress` | py mode running | `transfer2:7:1500`: `py --cover`, `rust`, `shadow`, seed 0. Rust mode has Rust `P` and the fixed `transfer_wanted` |
| m3 | `~/sa-rust-ids-work/sa-port-25/m3/` | `DONE`, `exit.txt`, `table.md` | Building, 0 rows | 20 `P` and `wanted` mutants on the new source: f01 to f12, w01 to w08. Exits early if its base isn't clean. **The rewritten mutant patterns have never applied yet, so read `log` first** |

## Found so far

1. **`transfer_wanted` diverged; now fixed.** On 9baaee2's build, 50 of 60 fixed cases differed:
   - Smallest wrong answer: `[P("lt","ab"), P("lt","ba")]`: Python False, Rust True.
   - `[P("lt",[1,2])]`: Python `TypeError`, Rust False.
   - `[P("lt",(1,2)), P("lt",(2,1)), P("lt",(1,2,3))]`: Rust always `ValueError`; Python depends on hash order (over 40 integer values of this shape, 29 True, 11 `ValueError`).
   - `P("lt",5)` and other non-pairs: same class, different text.

   Every `lt` atom I read in `relations.py` is an `Args` pair, and `Args` hashes and compares as a tuple, so I found no real query reaching this. **That isn't shown to be none.** After the fix: 0 differences on the 60 cases and 2,500 fuzz rounds at seeds 0 and 1, plus 10,000 rounds on the previous build of the same fix. Old output: `sa-port-25/p1/before-fix.out`; new: `final-0.out`, `final-1.out`.
2. **`P`: `part_p` compares 3,553 rows; 65 differed, 9 still do.** They're listed by exact row in `KNOWN` in `transfer_fuzz.py` and printed every run; any other row fails it:
   - `is_dataclass(P)` is False.
   - `P("a",1).__dict__` raises `AttributeError`.
   - `pickle.loads` of bytes written by Python's class raises `TypeError` (6 rows, one per protocol).
   - A subclass with a `pred` property: Python refuses to build it, Rust builds it and ignores the property.

   `rg` found no reader of the dataclass fields and no `P` subclass in `satassume` or `tests`. `tests/test_budget_cone.py:181` is the only `pickle.load`; it skips here because `~/.cache/satassume/stream.pkl` doesn't exist on orion. **Whether that file would hold a `P` wasn't established**, so say so in the report.
3. **The quiet counter covers the whole `try` at both sites, on Python raises.** `quiet_fire.py` plants a one-shot `ValueError` at `s.assumption_lits`, `_complete_check`, `_formula` and `eng.verdict`: all reached, `transfer_shadow`'s counter saw 1 each and 0 unplanted. Port/2's `handler_count.py` gave the same results. Output: `sa-port-25/quiet/`.
   - **What the zero covers:** exceptions handled in the code objects of `_build_context` and `_consistent`, in `transfer_fresh.py` runs only. It may over-count: a `BaseException` enters the handler before matching.
   - **Not installed in `live.py` or `rust_plugin.py`.** For the suite, pass `-p handler_count` to `run_suite.sh` (it forwards `"$@"`); it writes `handlers.PID.jsonl` to `SLICE_SUITE_OUT`. Copied byte for byte from port/2. **Not yet run as a plugin on this branch.** For `run_live.sh`, nothing yet counts.
   - **Still owed:** p06 and p07, the Rust raises, in m2. They should show `q=N`. So far only t05 shows one (`q=7`, `transfer:1:300`).
4. **`check()`:** reached through the API, not yet through the engine.
   - API: 31 conflicts in 972 calls, 12 with a selector, all equal to Rust's (`--only theory --rounds 400 --seed 5`).
   - Engine: line 464 never ran. On `transfer:2:1500`, line 463 ran 2,196 times, so `out` is empty at every final check, not merely conflict-free.
   - t42 and t43 in m2 aren't read yet; expect the `api` column only, unless reach changes this.
   - **Not established:** that the engine can't reach it. The solver runs `_theory_check` from `solver.py:2399`; I didn't read enough of what precedes it to argue that. If reach doesn't get there, report it as uncovered in the engine.
5. **Lines of Python's `transfer.py` not run through the engine**, over `transfer:2:1500`, `dev` and `fuzz` seed 0, before reach and `corpus`: 179, 204, 212, 220, 243, 260, 266, 289, 293, 382 to 384, 395, 464 to 468, 511, 546, 547. Line 136 is listed too but is a comprehension's continuation line; I didn't confirm it means anything. Line 106 (`return False`) never ran on `transfer:2:1500` but did on `dev` (653) and `fuzz` (10,328). Recompute this union once reach and s2 end; **the script was inline**: load each `*-py-*.json`'s `lines`, subtract from the executable lines of `TransferTheory` and `transfer_wanted` compiled from the source.
6. **The coverage counter is sound.** I suspected it over line 179 against t04's catch, but t04 breaks line 182 (116,140 runs), not 179.

## Not run, in order

1. Read m2 when it ends: which bugs were caught by a comparison and which only by a crash, what `dev` alone catches, p06/p07's `q=N`, t42/t43. Read m3 for f and w. Read reach and the rest of s2. Add shapes for non-equivalent survivors and rerun those.
2. **Rebase** on `origin/rust-slice` (cc3055c when checked) after all four jobs end. A dry merge conflicted only in `solver_rs/src/lib.rs`, on the `mod` and `register` lines.
   - `handle.rs`: swap to `pub use crate::term::TermId;`. `term/mod.rs` has the same shape, `repr(transparent)` over a public u32. Update the file's comment, or delete it and update users, whichever is smaller.
   - `BASIS_INDEX`: `transfer_py.rs:88` reads it from Python per instance. D gives `term::offline::OfflineData::load(path, sources_root, sympy)` and `.basis()`, the predicates in `BASIS_INDEX` order, so polar's index is its position. **`load` re-hashes the sources, so don't call it per session.** I didn't find a shared accessor or see how `term/py.rs` uses `offline` (its line 2 imports it). Section 9, "Offline data, read once at load", is the rule. Check it against Python's value.
3. Fresh `fuzz` and `corpus` at seeds 0 and 1 with Rust `P`, on final source, plus `transfer:1:300` and `transfer2:7:1500`. s2 can't stand in for this.
4. Suite by id against 5,961 / 77 / 46, on final source: rows in `~/sa-rust-ids-work/port-census/pr328-check/suite-rust` and `suite-python`, `suite-lists.md` beside them, and `rust-spike/slice/suite_report.py` in the clone (it isn't in `pr328-check/`). `test_protocol_on_fuzz` and `test_models_respect_transfer`, the two failures in `t1/`, are in `suite-lists.md` as `borrow RuntimeError` and `_solve`; **confirm by id that they're in the base's rows.** Recipe on pareto1: `~/sp19/p1_job.sh` under `machine run pareto1 --shared -r WHY -- CMD`, detached; otherwise orion at `PYTEST_N="-n 4"`.
5. `run_live.sh`, `run_history.sh`, boundary re-score, mutants 2, 5, 6, 7, 9 (`mutate_boundary.py`, `mutate_live.py`). The planner's text on 10 of 25 boundary mutants applies.
6. Counts: `transfer_fresh.py --sympy`, `py` against `rust`. `"sympy built": 0` without that flag means not counted, not zero.
7. How many of the 32 runtime modules this adds. Queries kept on Python, by reason.
8. Speed on a quiet lease on pareto1. New since the last measurement: `P` is now GC-tracked (`__traverse__`), and `transfer_wanted` builds a real set. Neither has been timed.
9. Landing: push without force, report the SHA and the three numbers, and name the standing items: S's standing, the `_n_conflicts` shim and its 64 tests, `pyset.rs` reproducing CPython 3.12's set order (hash order), and that this hasn't run on port/2's EUF.

## Traps

- **f189a61's commit message says "3,5xx rows"**, a placeholder I didn't fill in. The count is 3,553. Left as is, since fixing it would need a force push on `port/3`.
- `part_p` swaps `satassume.sat.formula.P` for its pickle rows and restores it in `finally`. It runs without `p_install`, so `P` in `transfer_fuzz.py` is Python's.
- The `api` mutant column runs every part, including `p`, so a new unnamed `part_p` difference fails base and stops the run. That's what the guard is for.
- `transfer:` must stay byte-identical, since earlier runs depend on it; new shapes go in `queries2` or a new generator.
- `sa-port-22`'s traps still apply: `pkill -f` matches its own shell, and mutants run from a frozen copy.

## File:line map (new or changed since sa-port-22)

| Topic | Where |
|---|---|
| `transfer_wanted`, `unpack2` | `solver_rs/src/transfer_py.rs:290` onward |
| `P`: `fields` (other's fields), `generic_set`, `is_frozen`, `__traverse__`, `tp_name` | `solver_rs/src/formula_py.rs` |
| `BASIS_INDEX` read, to replace | `solver_rs/src/transfer_py.rs:88` |
| Term handle, to swap | `solver_rs/src/handle.rs` |
| `part_p`, `part_wanted_edge`, `KNOWN`, `obs` | `transfer_fuzz.py`, after `part_theory` |
| Second generator | `transfer_workload.py`, `_shape2`, `queries2`; wired in `transfer_fresh.py:89`, `live.py:237` |
| Firing test | `quiet_fire.py`: `mine`, or `port2 PATH` |
| Suite handler counter | `handler_count.py` |
| New mutants | `mutate_transfer.py`: f07 to f12, w06 to w08; f02, f03, w03, w05 rewritten |
| Python reference | `satassume/sat/formula.py:13`; `satassume/theories/transfer.py:94`, `check` at `:456`, `_spread`'s conflict at `:382` |
| Solver's final check | `satassume/sat/solver.py:2091`, called at `:2399` |
| Quiet handlers | `satassume/engine.py:1906` in `_build_context` (:1878); `satassume/sympy_api.py:1107` in `_consistent` (:1088) |
| Job scripts | `~/sa-rust-ids-work/sa-port-25/reach.sh`, `m3.sh` |
