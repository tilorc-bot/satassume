# Phase 3, track D: refactor step 7, retire the old refine implementations (issue #13)

Branch `ri/refactor-retire` (worktree `.claude/worktrees/ri-refactor-retire`), from a7f7ed8.
`origin/refine-identities` had no new commits at gate time, so the merge was a no-op.
Not merged into `refine-identities`.

## Summary

- **`handlers_v3`** moved to `satrefine/reference/v3/` (git mv). `SATREFINE_HANDLERS=handlers_v3` still works through `satrefine/handlers_v3.py`, an alias module. Under `handlers_v3` and under `handlers_identities`, `handlers_dict` is identical to a7f7ed8: same keys, same order, same handler names.
- **`satrefine/_upstream.py`** (the vendored dispatcher and its 14 upstream-derived handlers) moved to `satrefine/identities/compat/upstream.py` (git mv, one file). `satrefine/_upstream.py` is now an alias: the same module object in `sys.modules`. It stays for this phase because 7 files in `tests/refine_identities` import the old name. `core/` reaches the dispatcher through a new hook, `core.hooks.dispatcher`, so `core` still imports nothing from `compat`.
- **`handlers` and `handlers_v2`** were deleted with `tests/refine_v2` and the `tests/refine` tests of `handlers` internals. Nothing else used them. Git history keeps them: `git checkout 411038c` runs both with all their tests.
- **Packaging:** the distribution also leaves out `satrefine.reference*`. The two deleted packages are gone from the wheel with the source.
- **Gates** (`.claude/gates/retire-8a24a5e` against `specs-merged-a7f7ed8`, 712 s): no result changed, and every v3 column in the scoreboard and the differential is unchanged. Apart from timings, three things differ. The scoreboard's engine line lists one more module, with the same total (1,775 = online 1,421 + offline 354). The ext differential in live mode has one extra identities timeout (the known load-dependent 20 s timeout). Suite progress dots differ. Details are in the Gates section.
- **Tests:** tests/refine went from 452 passed, 47 skipped, 4 xfailed to 448 passed, 0 skipped, 4 xfailed. tests/refine_v3 is unchanged (1 failed, 1,004 passed). tests/refine_v2 is deleted (it was 1 failed, 160 passed). The one-way import test passes.

## What each old package was used for (at a7f7ed8)

| package | importers and users | gates | outcome |
|---|---|---|---|
| `satrefine/handlers` (35 files, 1,887 lines) | selectable with `SATREFINE_HANDLERS=handlers` (not the default since 2026-09-25). Used only by tests of its own internals in `tests/refine`: 47 tests marked `@pytest.mark.handlers("handlers")` (41 functions plus `test_refine_trighelper.py` with 6), skipped under the default, and 4 unmarked tests that read `satrefine/handlers/*.py` sources (key ownership, duplicate keys). Also the conftest markers `handlers` and `original_wrong`, and an autouse check against importing its modules. No tool used it (`refine_oracle` named it only in its usage text). | none | **deleted** |
| `satrefine/handlers_v2` (21 files, 1,709 lines) | `tests/refine_v2` (18 files, 161 tests) only. Tools named it only in usage examples (`refine_fuzz`, the scoreboard's `--handlers` help, `refine_oracle`), and README. | none | **deleted** with `tests/refine_v2` |
| `satrefine/handlers_v3` | the differential's `--a` default in all 7 differential gate runs; the battery (`tests/refine_identities/battery_v3.py`, captured from it) and `test_battery.py` (runs under it); `refine_battery_capture`, `refine_battery_generate`; `tests/refine_v3` (10 files, 1,005 tests) | differential (v3 columns) | **moved** to `satrefine/reference/v3/`, alias `satrefine/handlers_v3.py` |
| `satrefine/_upstream.py` (644 lines) | the dispatcher every package plugs into: `satrefine/__init__` (`refine`, `ask`, `handlers_dict` and the 14 `refine_*` re-exports); identities `core/` (driver, prove, split, match, measure), `identities/__init__.load`, `compat/sympy_fixes`; `build/` (hooks, specialize); tools (`refine_oracle`, `refine_battery_capture`, `refine_ablate`, `lib/matrices`); `testing/harness`; all three old packages. Tests: `tests/refine` (1 file), `tests/refine_v3` (8), `tests/refine_identities` (7). | all | **moved** to `satrefine/identities/compat/upstream.py`, alias `satrefine/_upstream.py` |

Satassume's own `tools/` (ab, bench, compare, gate2, ...) use none of them. The `tools/refine_*` shims only forward to `satrefine/tools/`.

## Decisions

- **Delete, not archive, `handlers` and `handlers_v2`.** An archived copy under `archive/` could not run. Both packages import `satrefine._upstream` relatively and the tests import `satrefine.testing.harness`, and those will keep changing. Code that cannot run would sit there getting further out of date. Checked out at `411038c`, the whole tree still runs them unchanged, with `SATREFINE_HANDLERS`, their suites and the tools. README's "three handler packages" section now names that commit. `agent-reports/2026-09-23-refine-three-implementations.md` still describes them.
- **The upstream-derived handlers stay in the vendored file, with the dispatcher.** The file is a vendored SymPy module (`LICENSE.sympy`) that must stay behavior-identical, and splitting it would make that harder to check. Three more reasons:
  - Its `handlers_dict` literal fixes the order of the first 14 keys, which registration and table generation follow.
  - v3 calls `upstream.refine_Pow` and `upstream.refine_matrixelement` directly.
  - Under both `handlers_identities` and `handlers_v3`, none of the 14 upstream handlers is still registered: every key is overridden.
- **`core.hooks.dispatcher` instead of importing `compat.upstream` in core.** `test_core_imports_no_rules_or_compat` (step 3/4) forbids `core` importing `compat`, and #13 puts the vendored dispatcher in `compat`. `compat/__init__.py` sets `hooks.dispatcher` to the module. Core reads `hooks.dispatcher.ask` and `hooks.dispatcher.handlers_dict` at call time, so patching `ask` (tests, `build.hooks`, the driver's per-call memo) works as before. The test is not edited.
- **Single-module aliases.** `satrefine/_upstream.py` and `satrefine/handlers_v3.py` replace themselves in `sys.modules` with the real module. `handlers_v3.py` also imports the reference package's public modules and binds `satrefine.handlers_v3.<module>` to them. Old and new names give the same objects, so no module is loaded twice and nothing registers twice. `satrefine._load_handlers` is unchanged: `importlib.import_module` returns the replacing module, so the loader walks `reference/v3`'s path.
- **`tests/refine_v3` keeps its name.** It matches the selector `handlers_v3`, and gate commands, README and the battery tools cite it. Its imports now use `satrefine.reference.v3` and `satrefine.identities.compat.upstream`.
- **`satrefine.reference` is left out of the distribution.** It is measuring material, like `satrefine.tools`. In an installed wheel, `SATREFINE_HANDLERS=handlers_v3` fails with `No module named 'satrefine.reference'`. The alias's docstring says so.
- **The scoreboard's engine count leaves out `compat/upstream.py`**, as it already left out `compat/backend.py`. The vendored dispatcher was never counted as `_upstream.py`, and counting it would have added 289 lines. `compat/__init__.py`'s 3 lines of hook wiring are counted. Core lost 4 import lines and gained 1 for the hook attribute, so the total is unchanged at 1,775.

## tests/refine changes

- Removed the 47 marked tests, the 4 tests that read `satrefine/handlers` sources, and the owner tables only they used (`IN_SCOPE_OWNERS`, `_TRIG_OWNERS`, ...). The unused imports that ruff flagged after the removal are gone too. The 7 ruff findings that were already there (6 unused imports, 1 unused variable) are left.
- The 5 `@pytest.mark.original_wrong` markers and the 2 strict xfails conditioned on `HANDLERS_PACKAGE == "handlers"` are now comments that record what the old package got wrong. Under the default they were already plain passes.
- `conftest.py` keeps only `default_xfail`. The `handlers` and `original_wrong` markers and the leak check against `satrefine.handlers.*` imports are gone.

## Test counts (each suite in its own process, PYTHONHASHSEED=0, `-n 3`)

| suite | a7f7ed8 | ri/refactor-retire | why |
|---|---|---|---|
| tests/refine | 452 passed, 47 skipped, 4 xfailed | 448 passed, 4 xfailed | −47 skipped: the tests of `handlers` internals. −4 passed: the tests that read `satrefine/handlers/*.py` sources. |
| tests/refine_v3 | 1 failed, 1,004 passed | 1 failed, 1,004 passed | unchanged; the same known failure, `test_arg_of_exp_needs_the_principal_range` |
| tests/refine_v2 | 1 failed, 160 passed | (deleted) | |
| tests/refine_identities/test_battery.py, `SATREFINE_HANDLERS=handlers_v3` | 2 failed, 2,641 passed, 152 skipped, 27 xfailed | the same | both failures are the battery cases of the same v3 failure |
| tests/refine_identities (gate suite) | 2 failed, 2,662 passed, 1,920 skipped, 29 xfailed | the same | the 2 `needs/` tests; `test_import_direction.py` passes |

## Gates

`JOBS=10 SLOTS=11 SUITE_WORKERS=4 satrefine/tools/refine_gates.sh .claude/gates/retire-8a24a5e .claude/gates/specs-merged-a7f7ed8` (712 s). Every task exited as in the baseline: suite 1 (the 2 `needs/` tests), all others 0. Differences from the baseline, ignoring time lines:

- **suite:** only the order of progress dots (xdist) and object addresses in the two `needs/` failures. Totals are identical.
- **scoreboard, generated and live:** per-family same/other/miss/quiet/extra/wrong/crash and all totals are identical: generated 1,035/41/10/620/30, live 1,036/40/10/620/30, wrong 0, crash 0. The engine line has the same numbers (1,775 = online 1,421 + offline 354). Its module list now includes `identities/compat/__init__ 3`, and `core/driver` is 172 lines (was 173). The families line is unchanged (467).
- **differential, seeds 2, 3 and 7, both modes; satassume seed 2, both modes; matrices, both modes; ext generated:** only the time line changed. The v3 (`a=`) lines are identical everywhere.
- **differential ext, live:** identities `unchanged 684 → 683`, `timeout 3 → 4`. Fired 148, unsound 0 and crash 0 are unchanged, and the v3 line is unchanged. This is the load-dependent 20 s per-case timeout described in the refactor-1, refactor-2 and tools reports. The first gate run of this branch (`retire-43f2b9e`, the same code apart from the size count) had 3 timeouts here, identical to the baseline.
- **full fixpoint and termination:** only the time line changed (3 passed, 1 skipped; 8 passed).

The first run, `retire-43f2b9e`, differed only in the engine line (2,064, with `compat/upstream` counted), which led to the size-count commit.

## Commits

4d88945 (dispatcher move), 9570e49 (`_upstream` alias), f705dfa (v3 move), 75250d5 (`handlers_v3` alias), 411038c (v3 tests and capture tool imports), 82b2530 (tests/refine pruning), c3d2c81 (delete `handlers`, `handlers_v2`, `tests/refine_v2`; docs, tool usage texts, pyproject), 43f2b9e (README), 8a24a5e (engine size count), plus this report.

## Open items

- **`satrefine/_upstream.py` alias:** it can go once `tests/refine_identities` imports `satrefine.identities.compat.upstream`. The files are `test_ablate`, `test_engine`, `test_engine_conditions`, `test_engine_integer_funcs`, `test_engine_termination`, `test_family_specs` and `test_integer_funcs`. That is step 5's directory, so I did not touch it.
- **`test_import_direction.py`** could list `satrefine.reference` with the offline packages: identities must not import it, and today nothing does. That is also step 5's file.
- **`test_battery.py`'s `_OTHER_PACKAGES`** still names `handlers` and `handlers_v2`. This is harmless: it only checks `sys.modules`.
- **Already there before this branch:** README still says `satrefine.backend.set_backend`, but the module is `satrefine.identities.compat.backend` since refactor-1. CI (`.github/workflows/test.yml`) still runs `pytest tests` in one process, which the conftests refuse (default report, section 7).
- `tests/refine/test_refine_trig_sin_cos.py`'s docstring still describes the removed `handlers` copy of `refine_sin_cos`. The tests themselves exercise the loaded package.
