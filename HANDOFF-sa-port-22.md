# Handoff: sa-port-22, component 3 (transfer core), issue 323

**Not done, and not on `rust-slice`.** Handed off at the context note. Everything is on `port/3`. Brief: `~/.local/state/agent/briefs/sa-port-22-20261107T094508Z.txt`; its terms still apply. `HANDOFF-sa-port-17.md` is still the map for the theory core.

**No step of the brief has a finished result yet.** Two jobs are running detached on orion and need reading.

## Running now: don't rebase or edit `satassume/` until both end

Both import `satassume` from this clone. Their tools are frozen copies, so editing `rust-spike/slice/` is safe.

| Job | Where | Ends with | What it is |
|---|---|---|---|
| Mutants, step 1 | `~/sa-rust-ids-work/sa-port-22/m2/` | `DONE`, `exit.txt`, `table.md` | 84 planted bugs, 3 jobs. Columns: `api`, then `rust:` and `shadow:` on `dev` and `transfer:1:300`. **Read `results.jsonl`'s base row first.** It exits early if base isn't all `no`; then `log` says why |
| Coverage, step 2 | `~/sa-rust-ids-work/sa-port-22/s2/` | `DONE`, `progress` | `transfer:2:1500`, `dev`, `fuzz`, `corpus`; hash seeds 0 and 1; `py --cover`, `rust`, `shadow`, each compared by `cmp` |

**s2's limit:** its tools were copied before `P` and before the extended shadow's first full run, so its `rust` mode has **Python's `P`**. It tests the theory, sharing and `transfer_wanted`, not `P`. The `py` runs' `.json` has `lines`, per-line counts for Python's `transfer.py`. Those counts haven't been read yet.

## Found so far

1. **sa-port-17's quiet counter could never fire.** It required the catching function to start inside a line window, and the functions holding `engine.py:1906` and `sympy_api.py:1107` start at 1878 and 1088, before it. **So sa-port-17's "0 catches" says nothing.** It now keys on function name (`transfer_shadow.py`, `count_quiet_catches`) and also tallies every exception handled in a satassume frame (`handled` in the run's `.json`). **Not yet shown to fire:** mutants p06 and p07 in m2 are there to force it. Check they show `q=N`.
2. **`--so` never worked in `transfer_fresh.py`'s rust and shadow modes.** `backend` puts its own directory first on `sys.path`, so the driver loaded the unmutated build and refused to go on. Fixed, and tried on 10 queries in both modes.
3. **The first mutant run, m1, is void for every engine column.** Its base row is CRASH, and so is every other row's `rust:` and `shadow:` cell, from the harness and not from a mutant. **Never count those as catches.** Kept in `m1/results.jsonl`. Its `api` column was valid but is superseded by m2. The harness now stops if base isn't clean.
4. **The new workload reaches the lemma paths.** `transfer_workload.py`, `transfer:SEED:N`. On `transfer:1:300`, against dev's 52 of 3,332 sessions and 13 `explain` crossings:
   - Shadow, Python `P`: 310 of 650 sessions have a transfer theory; 58,168 calls, 0 differences; 4,571 lemmas; `decide` returned a variable 17 times. Not shown to catch anything until m2 is read.
   - `py` against `rust`, **with Rust `P`**: `cmp` identical. Crossings: rep 46,179, members 24,911, explain 2,564.
   - 71 of the 300 queries raise (`ValueError: inconsistent assumptions`), the same text on both backends.
   - **Gap: `check` was called 437 times and never returned a conflict**, so that path is still unexercised on this workload, and t42 and t43 may survive. Read the coverage counts, then add a shape if so.
   - These shapes were picked to reach those paths, so they say nothing about real queries.

## Step 3 (wiring): done, barely run

`live.py` calls `backend.install_transfer()` for non-`plain` checks and `p_install.install()` before its first satassume import. `rust_plugin.py` does both before collection. `SLICE_TRANSFER=py` or `SLICE_P=py` keeps Python's.

Only one test run so far, **before `P` was wired**: `run_suite.sh` over `test_transfer`, `test_scope`, `test_switched_glue`, `test_p3_review`, `test_relations`, `test_history` and `test_layering`: 2 failed, 363 passed, 15 skipped, 2 xfailed (`~/sa-rust-ids-work/sa-port-22/t1/`).

- `test_transfer.py::test_protocol_on_fuzz`: `RuntimeError: Already mutably borrowed`, `theory_harness.py:242`.
- `test_transfer.py::test_models_respect_transfer`: `Solver` has no `_solve`.

Both read solver internals, but **I haven't checked whether they're in the base's 77 or 46.** Compare by id. `run_live.sh`, `run_history.sh`: not run.

## `P`: ported, barely checked

One slice, in this session rather than its own, because it's a small stateless class. `solver_rs/src/formula_py.rs`; swapped by `p_install.py` as `satassume.sat.formula` finishes executing, with no source change.

Run so far: the 300-query compare above, and m2's f01 to f06 once they finish.

**Not done:**
- A `part_p` in `transfer_fuzz.py` comparing `sa_solver.P` with Python's directly: hash, `==` (subclass, `1` and `1.0`, NaN identity, a raising `__eq__`), repr with a custom `__format__`, operators, frozen errors, unhashable `expr`, copy and pickle round trip.
- `tests/test_budget_cone.py:181` does a `pickle.load`. I didn't read what it loads. A pickle holding Python's `P` would go through `__newobj__` and may fail on the crate's class.
- Knowingly not reproduced: `__dict__`, `__dataclass_fields__`. Slot wrappers `__rand__` and friends exist and answer NotImplemented.

## Not run, in order

1. Read m2 and s2. Say which bugs were caught by a comparison and which only by a crash, and what dev alone catches against the new workload. Add shapes for survivors that aren't equivalent, then rerun those.
2. `part_p`. **Known divergence test:** `transfer_wanted`, smallest cases to try, none run yet:
   - `[P("lt",(1,2)), P("lt",(2,1)), P("lt",(1,2,3))]`: Rust raises at the third atom; Python's result depends on set order.
   - `P("lt",[1,2])`: unhashable. Python raises `TypeError` building the set; by my reading Rust iterates it and returns False.
   - `P("lt",5)`: both `TypeError`, with different text.

   Report it with its smallest case; don't reclassify it. A real `set` in Rust would match Python exactly, if you decide to fix it after reporting.
3. Fresh `fuzz` and `corpus` at seeds 0 and 1 **with Rust `P`**, on final source.
4. Suite by id against 5,961 / 77 / 46, on final source. **I didn't find PR 328's rows.** `~/sa-rust-ids-work/slice/step4/run5-rust` and `run5-python` are the "before" runs by their names, unconfirmed; `results/pr328-check.md:36` says how they ran. Find them, or rerun the base.
5. **Remote machines have no env.** `~/sa-rust-ids-work` and the clone don't exist on mbp2015 or pareto1 (checked by ssh). mbp2015 has Python 3.13 and x86-64; orion is aarch64, so the `.so` must be rebuilt there, and `pyset.rs` is tied to 3.12. sa-port-21 has a suite queued on pareto1 and may have a recipe. Otherwise orion at `PYTEST_N="-n 4"`.
6. `run_live.sh`, `run_history.sh`, boundary re-score, mutants 2, 5, 6, 7, 9 (`mutate_boundary.py`, `mutate_live.py`). Planner's text on 10 of 25 boundary mutants still applies.
7. Counts: `transfer_fresh.py --sympy`. **`"sympy built": 0` in any run without that flag means not counted, not zero.** It's untried; compare `py` with `rust`.
8. How many of the 32 runtime modules this adds: I didn't find the list. `transfer.py` holds only `TransferTheory` and `transfer_wanted`, both replaced; `EqualitySharing` and `P` are parts of `sat/theory.py` and `sat/formula.py`.
9. Speed, on a quiet lease on pareto1. Landing: rebase on `origin/rust-slice`, rerun, push without force.

Still named facts from the last handoff: `pyset.rs` reproduces CPython 3.12's set order, which is hash order and must be reported as such. Not run on port/2's EUF.

## Traps

- `pkill -f PATTERN` matches its own shell's command line and kills it. Write `'[m]utate...'`. It cost me one call.
- `HERE`-relative tools: run mutants from a frozen copy, as `m2/run.sh` does, so edits don't reach a running job.

## File:line map (new or changed)

| Topic | Where |
|---|---|
| `P` | `solver_rs/src/formula_py.rs`; `slice/p_install.py`; `lib.rs` (`mod`, `register`) |
| Shadow of sharing and wanted, new; quiet counter, fixed | `slice/transfer_shadow.py`, `ShadowSharing`, `shadow_wanted`, `count_quiet_catches`; wired in `backend.py`, `install_transfer` |
| Workload | `slice/transfer_workload.py`; loaded by `transfer_fresh.py` and `live.py`, `load` |
| Driver flags | `slice/transfer_fresh.py`: `--cover`, `--sympy`, `--so`, the check that `P` was swapped |
| Mutants | `slice/mutate_transfer.py`: `M` list, `fresh` and `api` score a cell, base guard in `main` |
| Wiring | `slice/live.py`, `main`; `slice/rust_plugin.py`, top and after `SV.Solver = ...` |
| Python reference | `satassume/sat/formula.py:13`; `satassume/theories/transfer.py:94` |
| Quiet handlers | `satassume/engine.py:1906` in `_build_context` (:1878); `satassume/sympy_api.py:1107` in `_consistent` (:1088) |
