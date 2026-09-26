# Phase 3, track D: refactor step 5, tests (issue #13)

Branch `ri/refactor-tests` (worktree `.claude/worktrees/ri-refactor-tests`), from a7f7ed8. `origin/refine-identities` had no new commits at gate time, so the merge was a no-op. Not merged into `refine-identities`.

## Summary

- `tests/refine_identities/` is laid out like the package: `core/`, `rules/`, `compat/`, `build/`, `tools/`, plus top-level files for the battery, the gate-level checks and the regression table. Files moved with `git mv`.
- The per-bug regressions are now 101 rows of one data module, `regressions.py`. They run from one parametrized test, `test_regressions.py`, in both identity modes and under each backend a row names.
- **Checks:** 156 distinct (input, assumptions, mode, backend) checks before, **220** after. No case was merged or dropped. The count went up because every row now runs in both modes.
- **Suite:** 2,662 → 2,733 passed. Test items: 152 removed (2 of them moved unchanged), 223 added (221 from `test_regressions.py`, plus the 2 moved). Skips, xfails and the 2 `needs/` failures are unchanged.
- **Gates:** identical to `specs-merged-a7f7ed8` apart from:
  - timings;
  - the suite's pass count (above);
  - the ext differential's 20 s timeout count, which depends on load (see Gates).
- `needs/` is not converted. Only two stale path strings in its docstrings were updated.

## Layout

| dir | tests | files |
|---|---|---|
| top level | battery, gate-level checks, regression table | `battery_v3.py`, `test_battery.py`, `test_engine_termination.py` (the gates name it; path unchanged), `test_import_direction.py`, `regressions.py`, `test_regressions.py`, `conftest.py` |
| `core/` | `satrefine.identities.core` | `test_engine.py`, `test_engine_conditions.py`, `test_engine_bounds_infinity.py` (now only `provable` on bounds), `test_engine_case_split_pretest.py`, `test_engine_case_split_zero_point.py`, `test_engine_pattern_shapes.py`, `test_engine_hash_seed.py`, `test_engine_{combinatorial,integer_funcs,minmax_deltas}.py` (matcher forms) |
| `rules/` | the families | `_rows.py`, `test_{combinatorial,complex_parts,hyperbolic,integer_funcs,inverse,minmax_deltas,power_exp_log,trig}.py`, `test_family_specs.py` |
| `compat/` | backend, matrices, SymPy fixes | `test_backend_nonzero_guard.py`, `test_backend_routing.py`, `test_earlier_calls_do_not_leak.py`, `test_matrices.py`, `test_engine_matrices.py`, `test_matrix_match_one_and_rest.py` (was `test_matrices_hadamard_duplicate.py`), `test_sympy_fixes_rebuild.py` (was `test_bounds_acot_rebuild.py`) |
| `build/` | `satrefine.build` | `test_generated.py`, `test_specialize.py`, `test_specialize_render_one_symbol.py` |
| `tools/` | `satrefine.tools` | `test_ablate.py`, `test_fuzz_ext.py`, `test_matrix_fuzz.py`, `test_tools_lib.py` |
| `needs/` | unchanged | the 2 open tests |

How the layout works:
- **No `__init__.py` in the new directories.** Test basenames stay unique, and pytest's prepend import mode puts each file's directory on `sys.path`. `_rows.py` moved to `rules/` next to its users. `battery_v3.py` stays at the top, where the termination test and `tools/lib/battery.py` import it from.
- **`build/` needs a conftest hook.** pytest's default `norecursedirs` skips every directory named `build`, so all 13 `build/` tests were silently dropped at first. `conftest.py` now has a `pytest_ignore_collect` hook that returns `False` for this one directory. A test-id diff against a7f7ed8 then showed every id present.
- **`build/test_generated.py`** imported `test_power_exp_log` as a sibling. It now loads `rules/test_power_exp_log.py` by path.
- The xdist setup, the `full` marker and the `shared` session fixture are unchanged in the top-level conftest, and they apply to every subdirectory. The gates' `full` task ran 3 passed and 1 skipped, as before.

Outside the tests:
- **`satrefine/tools/refine_ablate.py`** looked for `TESTS/test_{family}.py` and `TESTS/test_engine_{family}.py` and skipped missing files. After the move it would have run no tests. It now uses `rglob` for the same two names. This is one line plus its docstring.
- **Docstrings:** test paths were updated in `identities/core/spec.py`, `identities/generated/__init__.py`, `identities/rules/{hyperbolic,integer_funcs}.py` and `tools/lib/{grammar,assumptions}.py`.
- **`refine_gates.sh`** is unchanged, because the termination test's path did not change.

## The regression table (`tests/refine_identities/regressions.py`)

```
Case(expr, assumptions, expected, bug, reason, backends=None)
```

- **`expected`** is one of:
  - a SymPy object, compared with `==`;
  - `UNCHANGED`: the input comes back;
  - `NO_CRASH`: `refine` returns without raising;
  - `OneOf(a, b, ...)`: any of these results (`UNCHANGED` may be one of them);
  - `SameValueAt({z: 0})`: result and input agree at that point (the B8 rows);
  - `AfterDoit(v)`: `result.doit() == v`.

  `holds(case, result)` decides.
- **`bug`** says where the bug is recorded: `#10 B1`…`#10 B10`, `default: …` (the default switch), `matfixes: …`, `checker: …`, `engine: …` or `diff: …`.
- **`reason`** is a few words on what went wrong.
- **`backends`**: `None` means the environment's backend, which is `combined` by default. Otherwise it is a tuple, and the row runs under each of those backends.
- `test_regression` runs every row under `driver.tables()` and `driver.live()`, and under each backend in `backends`, using `backend.using`. Ids look like `011-10_B6-live` (row number, bug, mode, backend).
- `test_rows_are_distinct` checks that no (expr, assumptions) pair appears twice.
- Each group has a comment naming the file it came from. `git log -- tests/refine_identities/<file>` gives the longer history.

## Case count, before and after

A check is one (input, assumptions, mode, backend). Before, a test without a mode switch counted as one mode: the environment's, which the gates set to generated.

| from | test items | checks before | rows | checks after |
|---|---:|---:|---:|---:|
| `test_engine_bounds_infinity.py` (B1–B7 + finite) | 50 | 50 | 25 | 50 |
| `test_bounds_acot_rebuild.py` (B8) | 16 | 18 | 9 | 18 |
| `test_fuzzext_acsch_infinite.py` (B10; 2 backends) | 14 | 14 | 4 | 14 |
| `test_matrices_hadamard_duplicate.py` | 10 | 10 | 5 | 10 |
| `test_default_inconsistent_assumptions.py` (3 backends) | 9 | 9 | 3 | 18 |
| `test_default_infinite_arguments.py` | 9 | 9 | 9 | 18 |
| `test_default_odd_half_pi_sign_form.py` | 8 | 8 | 8 | 16 |
| `test_default_floor_ceiling.py` | 5 | 5 | 5 | 10 |
| `test_default_neg_one_power_exponent.py` | 5 | 5 | 5 | 10 |
| `test_default_hyperbolic_i_pi_shift.py` | 4 | 4 | 4 | 8 |
| `test_engine_conditions.py` (3 atan2 firing-cap inputs, 2 of them live only; head refusing a child) | 4 | 4 | 4 | 8 |
| `test_matrices_matrixelement_index_order.py` | 3 | 6 | 6 | 12 |
| `test_engine_matrixelement_bounds.py` | 2 | 2 | 2 | 4 |
| `test_matrices_matadd_single_term.py` | 2 | 2 | 2 | 4 |
| `test_matrices_matmul_scalar_factor.py` | 2 | 2 | 2 | 4 |
| `test_power_exp_log_zero_base.py` | 2 | 2 | 2 | 4 |
| `test_engine_eq_of_equal_infinities.py` | 1 | 2 | 2 | 4 |
| `test_default_arg_of_zero.py`, `…pow_of_pow_positive_base.py`, `…rem_zero_dividend.py`, `test_engine_firing_cap_on_wide_input.py` | 4 | 4 | 4 | 8 |
| **total** | **150** | **156** | **101** | **220** |

- **Merged or dropped as duplicates:** none.
- **Tests that stayed as tests, because they check more than a result:**
  - `test_what_a_bound_proves` (`provable`), in `core/test_engine_bounds_infinity.py`;
  - the guarded `rebuild` unit test, now `compat/test_sympy_fixes_rebuild.py`;
  - the matcher's one-and-rest bindings, now `compat/test_matrix_match_one_and_rest.py`.
- The rest of `test_engine_conditions.py` also stays: `decide`, `provable`, handler internals and the result cache.
- These were left as tests on purpose:
  - `test_engine_hash_seed.py` and `test_earlier_calls_do_not_leak.py` run subprocesses;
  - `test_backend_*` tests the guard and the routing;
  - `test_engine_case_split_zero_point.py` calls `identity_handler` directly.
- Every row passes in both modes, including the two atan2 inputs that had been tested only in live mode.

## Gates

`JOBS=10 SLOTS=11 SUITE_WORKERS=4 satrefine/tools/refine_gates.sh .claude/gates/tests-8c36050 .claude/gates/specs-merged-a7f7ed8` (836 s). The differences, by section:

- **suite:** 2 failed (the same 2 `needs/` tests, listed in the other order), 2,662 → 2,733 passed, 1,920 skipped, 29 xfailed.
- **scoreboard, generated and live:** no change. Generated is 1,035/41/10/620/30 and live is 1,036/40/10/620/30. Wrong and crash are 0.
- **differential seeds 2, 3, 7 in both modes; satassume seed 2 in both modes; matrices in both modes:** only the time lines changed.
- **ext differential, seed 2:** timeouts went 3 → 6 in generated mode (unchanged 684 → 681) and 3 → 7 in live mode (684 → 680).
  - In generated mode, v3's timeouts also went 2 → 3, and the run took 735 s against 594 s.
  - Fired 148, unsound 0 and crash 0 are unchanged.
  - This branch changes no code that refine runs: the `satrefine/` diff against a7f7ed8 is docstrings plus the one `refine_ablate` test-path line.
  - So this is the load effect the previous refactor reports saw with the 20 s timeout. The 1-minute load was about 10 during the run.
- **full fixpoint:** 3 passed, 1 skipped. **termination:** 8 passed. Only the times changed.

## Commits

c434768 (layout moves), 8c36050 (regression table), plus this report.

## Notes

- `tests/refine/test_sympy_refine_suite.py` and `tests/refine/conftest.py` point at `tests/refine_identities/needs/test_default_<topic>.py`. Those paths did not change.
- A future test directory named `build` elsewhere would need the same `norecursedirs` exception.
