# Phase 3, track D: refactor steps 1–2 (issue #13)

Branch `ri/refactor` (worktree `.claude/worktrees/ri-refactor`), from 68857ff.
`origin/refine-identities` had no new commits when the gates started, so the
merge was a no-op. Not merged into `refine-identities`.

## Summary

- **Step 1 (moves only):** the layout of #13 is in place: `satrefine/identities/{core,rules,generated,compat}` plus `config.py`, and `satrefine/build/`, `satrefine/tools/` and `satrefine/testing/`. Nothing public was renamed. `SATREFINE_HANDLERS=handlers_identities` (the default) still selects the package. `handlers_identities` is now a 3-line package that calls `satrefine.identities.load()`.
- **Step 2:** `tests/refine_identities/test_import_direction.py` runs refine in a subprocess where `satrefine.build`, `satrefine.tools` and `satrefine.testing` cannot be imported. It passes in both modes. `core/` still names some specific SymPy functions. That check is a strict xfail listing them, and a second test fails if one is added.
- **Generated tables:** `python -m satrefine.tools.refine_specialize --write` regenerated all 4 tables at the fixpoint in 96 s. The output is byte-identical to the committed tables except for module paths: 3 header-docstring lines and the 2 import lines per file.
- **Gates** (`.claude/gates/refactor-c14693f` against `fixes-merged-68857ff`): no gate result changed. The only differences are timings, the engine and families line counts, the suite's 4 new tests and 1 new strict xfail, and one extra 20 s timeout in the ext differential (generated mode). That timeout depends on load: the old code at 68857ff, run again beside this branch, gives the same 4 timeouts and case-for-case identical records.
- **Suites:** tests/refine, tests/refine_v3 and tests/refine_v2, each run in its own process, give the same counts as 68857ff (table below). tests/refine_identities: 2 failed (the 2 `needs/` tests of the baseline), 2,631 passed plus the 4 new tests, 1,920 skipped, 29 xfailed plus the new strict xfail.
- **Engine size:** the scoreboard's engine count is now **1,842** code lines (online 1,461, offline 381), against 1,695 before. The rise is imports, module headers and the new hook points. Getting below the plan's 1,434 is for steps 3 and 4.

## What moved where

| from (68857ff) | to | notes |
|---|---|---|
| `handlers_identities/_dispatch.py` | `identities/core/driver.py` (git mv) | the driver; the termination guard is split out to `core/guard.py`, the env switches to `identities/config.py`, `tracing()`/`live_for()` to `build/hooks.py`, the Pow/exp `_eval_refine` copies to `compat/sympy_fixes.py` |
| (part of `_dispatch.py`) | `identities/core/guard.py` | limits, `RefineLoopError`, `_Call`, `strict`/`strict_loops`, `loop_events`, the *Termination* argument; `driver` re-exports these names (tests and tools read them there) |
| (parts of `_dispatch.py`, `satrefine/__init__.py`) | `identities/config.py` | `SATREFINE_HANDLERS`, `SATREFINE_IDENTITIES`, `SATREFINE_STRICT_LOOPS` read in one place (`handlers_package`, `env_mode`, `env_strict`); `SATREFINE_BACKEND` stays in `compat/backend.py` |
| `handlers_identities/_engine.py` | `identities/core/rewrite.py` (git mv) | now only orderings (`default_measure`, `size`, ...) and `identity_handler`/`rule_handler` |
| (part of `_engine.py`) | `identities/core/prove.py` | `provable`, `decide`, the order vocabulary, `_from_bounds` |
| (part of `_engine.py`) | `identities/core/match.py` | `part`, `_shape`, `_match`, `bindings`, `subst`, `REBUILD`, plus a hook point: `MATCH_HOOKS`, `NON_SCALAR`, `COMMUTATIVE`, `register()` |
| (part of `_engine.py`) | `identities/core/split.py` | `case_split`, `endpoint_split` and their helpers |
| (part of `_engine.py`) | `identities/rules/_tables.py` | `derive` |
| (matrix part of `_engine._match`) | `identities/compat/matrix_match.py` | `_bind_matrix`, the `MatrixSymbol`, `Z + R`/`HadamardProduct(Z, R)`, `c*Z` and `MatMul`-run forms; registered as a matcher hook with `MatrixExpr` non-scalar and `MatAdd`/`HadamardProduct` commutative |
| `handlers_identities/_simple.py` | `identities/rules/_simple.py` (git mv) | the `floor`/`Piecewise` handlers, `RANGES`, `floor_two_valued` |
| (part of `_simple.py`) | `identities/core/bounds.py` | `stated_bounds`, `stated_finite`, `full_bounds`, `_affine`, `_checked`, ... |
| (part of `_simple.py`) | `identities/compat/sympy_fixes.py` | the `acot`/`acoth` rebuild guard (B8), installed as the driver's `rebuild_hook` |
| `handlers_identities/_tables.py`, `_wraps.py` | `identities/rules/_tables.py`, `_wraps.py` (git mv) | `_tables` also holds `compile_table`/`compile_rule` (online; they were in `_specialize`) and re-exports the engine API the families import |
| the 8 scalar families | `identities/rules/<family>.py` (git mv) | content unchanged apart from imports; `power_exp_log` lost its `CATALOG` (below) |
| `handlers_identities/matrices.py` | `identities/compat/matrices.py` (git mv) | the matrix family (#13 puts it in compat) |
| `handlers_identities/generated/` | `identities/generated/` (git mv) | |
| `satrefine/backend.py` | `identities/compat/backend.py` (git mv) | `_upstream` imports it from there; no `satrefine.backend` alias is left |
| `handlers_identities/_specialize.py` | `build/specialize.py` (git mv) | specialisation, `identity_keys`, `generate_family`, `family_modules` |
| (part of `_specialize.py`) | `build/verify.py`, `build/render.py` | `verify`, `sample_point`, `SAMPLE`, `EDGE_POINTS`; `table_order`, `render_module`, `generated_path`, `write_family` |
| `power_exp_log.CATALOG` | `build/specs.py` (`CATALOGS`) | importing a family no longer imports offline code; `generate_family` reads it there |
| `handlers_identities/_stages.py` | `build/stages.py` (git mv) | |
| `satrefine/harness.py` | `testing/harness.py` (git mv) | |
| `tools/refine_*.py`, `tools/refine_gates.sh` (12 files) | `satrefine/tools/` (git mv) | run as `python -m satrefine.tools.<name>`; the old paths are 10-line shims (`runpy.run_path` of the new file, same arguments) |
| `pyproject.toml` | | excludes `satrefine.build*`, `satrefine.tools*`, `satrefine.testing*` from the distribution |

The families are loaded by `identities.load()` in the old order: alphabetical, with `matrices` in its place. The simple rules are installed first, then the generated tables. Registration order into `handlers_dict` is checked identical to 68857ff (keys and handler names).

## Not moved, and why

- **`satrefine/_upstream.py`** (the vendored dispatcher; #13 puts it in compat): `handlers`, `handlers_v2`, `handlers_v3`, tests and tools import `satrefine._upstream` in about 30 places. It stays until step 7 archives the old packages.
- **`handlers`, `handlers_v2`, `handlers_v3`:** untouched.
- **`satrefine/tools/lib/`:** not created. Nothing is shared yet except `refine_differential` importing `refine_fuzz`'s grammar; building the shared library is step 6. `satrefine/tools/__init__.py` holds one helper, `rerun_with` (below).
- **Family docstrings** still cite `._engine.derive`, `tools/refine_differential.py` and similar. The families were to move unchanged, and step 3 rewrites them. The shims keep the tool paths valid.

## Cycles and import-order problems, and how they were handled

1. **Driver and `_simple`** (for `rebuild`): the driver now has `rebuild_hook` and `eval_refine_copies`, and `compat/sympy_fixes.py` fills them when imported. `satrefine/identities/__init__.py` imports `compat.sympy_fixes` and `compat.matrix_match`, so the hooks are installed whenever anything under `satrefine.identities` is imported (also under `handlers_v3`, where they are inert).
2. **Matcher and matrices:** `core/match.py` asks `MATCH_HOOKS` right after the atom cases. `MatrixSymbol` is neither `is_Symbol` nor `is_Atom`, so the matching order is exactly the old one. A matrix pattern that fits none of the matrix forms still falls through to the generic forms, as before.
3. **`satrefine/__init__` imports `identities.config`.** This runs `identities/__init__`, then `compat.matrix_match`, then `core.match`, which imports `satrefine._upstream` while `satrefine` is still initialising. It works because `_upstream` is imported first. Keep that order.
4. **`core/split.py` imports `rules/_simple.floor_two_valued`** (the endpoint split is about `floor`). That is core importing rules. There is no cycle, because `_simple` imports core only lazily, apart from `core.bounds`. For step 3/4.
5. **Online imported offline:** families used `compile_table` from `_specialize`, and `power_exp_log` built its `CATALOG` from it. Fixed by moving `compile_table` online and the catalog to `build/specs.py`.
6. **`python -m satrefine.tools.X` imports `satrefine`, and so its handler package, before the tool reads its arguments.** Tools that pick the package or backend themselves (`refine_identity_scoreboard --handlers`, `refine_fuzz --handlers`, `refine_oracle --handlers/--backend`, `refine_specialize`, `refine_battery_generate`) call `satrefine.tools.rerun_with(...)`. It re-executes the tool once with the variables set, and only when what is loaded differs. Checked: `-m satrefine.tools.refine_fuzz 2 30 --handlers handlers_v3` gives v3's numbers (fired 14; identities fire 15). Workers that tools spawn (differential, ablation) still run the tool file as a script, as before.

## Notes for step 3

- **Generation hooks:** their state is still in the driver: `note()`/`_trace`, `consulted`, `live_keys`, and `_forced` with `live()`/`tables()`/`staged()`. `build/hooks.py` has only `tracing()` and `live_for()`. The observer hook replaces them. Tests use `driver.live()` and `driver.tables()` as mode switches, so keep those two, or give tests an equivalent.
- **Family registration** is still an import side effect. `EDGE_POINTS` and `SPECIALIZE` are still in the families; `CATALOGS` is already in `build/specs.py`.
- **`rules/_tables.py` re-exports the engine API** (`Row`, `identity_handler`, `rule_handler`, `part`, `principal`) so the family import lines changed one-for-one. The declarative specs can drop this.
- **Names `core` still uses** (the strict xfail): `prove`: `ceiling`, `floor` (integer refutation in `_from_bounds`); `rewrite`: `Abs`, `Piecewise`, `arg`, `floor`, `im` (the default opaque heads, the endpoint split's `floor`, `Abs` in `default_measure`, undecided `Piecewise` candidates); `split`: `Abs`, `arg`, `floor`, `im`.
- **The driver re-exports** the guard names and `MODE_ENV_VAR` for existing tests and tools. `test_engine_conditions.py` patches `rewrite.case_split`, where it is looked up. Step 5 can import from `guard` and `config` directly.
- **`test_ablate`, `test_fuzz_ext`, `test_matrix_fuzz` and `test_engine_termination`** import tools as `satrefine.tools.*`. They no longer put `tools/` on `sys.path`.

## Gates

`JOBS=10 SLOTS=11 SUITE_WORKERS=4 satrefine/tools/refine_gates.sh .claude/gates/refactor-c14693f .claude/gates/fixes-merged-68857ff` (826 s). The diff against the baseline, by section:

- **suite:** 2 failed (the same 2 `needs/` tests), 2,631 → 2,635 passed, 1,920 skipped, 29 → 30 xfailed. The extra 4 passed and 1 xfail are the new `test_import_direction.py`.
- **scoreboard, generated and live:** only the `engine` and `families` code-line lines changed (see Line counts). Per-family same/other/miss/quiet/extra/wrong/crash are identical, and so are the totals: generated 1,035/41/10/620/30, live 1,036/40/10/620/30, wrong 0, crash 0.
- **differential, seeds 2, 3 and 7, both modes; satassume backend, seed 2, both modes; matrices, both modes:** only the time line changed.
- **differential ext, seed 2, generated:** identities `unchanged 684 → 683`, `timeout 3 → 4`, and the time line. Everything else is unchanged, including fired 148, unsound 0 and crash 0. It is load, not a change: I ran the identities worker (`--worker handlers_identities --ext --seed 2 --cases 1000 --timeout 20`, generated mode) on 68857ff and on this branch at the same time. Both give 4 timeouts (cases 60, 169, 276, 392) and the same status and result for every case.
- **differential ext, live:** only the time line changed.
- **full fixpoint and termination:** only the time line changed (3 passed, 1 skipped; 8 passed).

## Suites run on their own (68857ff vs this branch, default package)

| suite | 68857ff | ri/refactor |
|---|---|---|
| tests/refine | 452 passed, 47 skipped, 4 xfailed | 452 passed, 47 skipped, 4 xfailed |
| tests/refine_v3 | 1 failed, 1,004 passed | 1 failed, 1,004 passed (same test: `test_arg_of_exp_needs_the_principal_range`) |
| tests/refine_v2 | 1 failed, 160 passed | 1 failed, 160 passed (same test: `test_relation_rules_do_not_fire_under_the_satassume_backend`) |

## Line counts (code lines: no blanks, comments or docstrings; physical lines in brackets)

| part | code | physical |
|---|---:|---:|
| **online** `satrefine/identities/` (with `handlers_identities/__init__`) | **2,259** | 4,577 |
| — `core/` (8 files) | 1,093 | 1,803 |
| — `rules/` (8 families + `_simple`, `_tables`, `_wraps`) | 598 | 1,425 |
| — `compat/` (backend 326 physical, matrices family, matcher hook, SymPy fixes) | 394 | 793 |
| — `generated/` | 121 | 407 |
| — `__init__`, `config`, `handlers_identities/__init__` | 53 | 149 |
| **offline** | **4,698** | 6,201 (+132 for `refine_gates.sh`) |
| — `build/` | 381 | 563 |
| — `tools/` (Python) | 4,093 | 5,299 |
| — `testing/` | 224 | 339 |

The scoreboard now prints the engine as one line, with online and offline totals and every module. That keeps the gate summary's `tail -12` window the same. Its "engine" is the former underscore modules at their new places (`identities/` without the families, generated tables and backend) plus `build/`: **1,842 = online 1,461 + offline 381** (was 1,695). The families line is unchanged except `power_exp_log` 64 → 61 (the `CATALOG` and its import moved to `build/specs.py`); families total 509 (was 512).

## Commits

508967f (whole-file moves), d9e6f4e (engine split), d595d25 (driver split, compat), 24dcc60 (bounds, specialize split, specs), cfca97e (tools into satrefine/tools), bc3d77d (step 2 tests), 4ba6528 (docs), c14693f (regenerated tables), plus this report.

Also updated outside the repository: the "How to run things" block and rules 13–14 in `.claude/phase3/agent-rules.md`, which now use the new module paths.
