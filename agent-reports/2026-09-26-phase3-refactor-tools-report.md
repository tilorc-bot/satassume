# Phase 3, track D: refactor step 6, the tools (issue #13)

Branch `ri/refactor-tools` (worktree `.claude/worktrees/ri-refactor-tools`), from 34b3dae.
`origin/refine-identities` had no new commits when the gates started, so the
merge was a no-op. Not merged into `refine-identities`.

## Summary

- **`satrefine/tools/lib/`** (12 modules) holds what the tools share: case generation, assumption sampling, sample points, numeric checks, the matrix family, battery loading and classification, size counting, the backend-suite runner, worker plumbing and package/backend selection.
- **Thin tools:** `refine_fuzz` goes from 1,155 to 228 code lines, `refine_differential` from 429 to 196, `refine_ablate` from 338 to 274. `refine_differential` no longer imports `refine_fuzz`.
- **One scoreboard entry point:** `python -m satrefine.tools.scoreboard {battery|lines|suite}`. `battery` is the default. `refine_identity_scoreboard` (= `battery`) and `refine_scoreboard` (= `suite`) are now 12-line shims with the same options and output. The gates call `scoreboard battery`.
- **`refine_oracle`:** its nested time limits, forked task pool and table printer are in lib. Mode A output is identical. Mode B was broken before this branch (fixed here, see "Behaviour changes").
- **Random streams unchanged:** the existing digest test passes. A new test pins the sample points of all three families and the extended stream, with digests taken from the code before the move. A wider digest (scalar cases with points and `refine_fuzz`'s check, the extended stream with points, matrices with points, 120 cases each) was identical before and after.
- **Every tool answers `--help`** under `python -m`, and every old `tools/refine_*` command still works. `tools/refine_fuzz.py` can be imported again. `tools/ask_fuzz.py` (satassume's tool) imports it; it had been broken since the step-1 shim.
- **Gates** (`.claude/gates/tools-afb7883` against `refactor-c14693f`, 848 s): no gate result changed. The scoreboard sections are identical in both modes, including the size lines. The suite has 6 more passed tests (the new ones). The differential sections differ only in the time line, except for the load-dependent 20 s timeouts in the ext differential. There, v3 and identities ran on old and new code at the same time and gave identical records, case for case.
- **Found, not mine:** `refine-identities` (34b3dae) lacks `satrefine/build/{__init__,hooks,render,specs,verify}.py`. The repository's `.gitignore` has `build/`, so step 1 never committed them. `refine_specialize`, the fixpoint tests and anything that imports `satrefine.build.stages` fail on a clean checkout. `ri/refactor-specs` restores them in 2b7868b. For my runs and the gates I put those five files into my worktree as untracked (ignored) files. They are not in my commits.

## lib modules

| module | holds | code lines |
|---|---|---:|
| `select` | `rerun_with` (moved from `tools/__init__`, which re-exports it), `select(handlers, backend)`: the "re-exec under `python -m` if something else is loaded, then set the variables" pattern five tools had, `backend_from_env()` | 30 |
| `assumptions` | the predicate vocabulary with numeric definitions (`PREDS`, `EXT_PREDS`, `c_*`), combos, the samplers `draw`/`draw_ext`, `relations`/`ext_relations`, the relation deciders `rel_holds`/`rel_holds_ext`, `conjunction` | 146 |
| `grammar` | the scalar grammar (`atom`, `inner`, `OUTER`), `scalar_case(rng)`/`generate(seed, case)` (was written twice, in `refine_fuzz.main` and `refine_differential.generate`), the extended grammar and `ext_generate` | 137 |
| `points` | edge and branch-cut points, `check_points` (scalar), `ext_points`/`ext_satisfiable` (extended). The cut pre-image code, the candidate filter and the product-or-each point builder were written twice; now there is one of each | 141 |
| `numeric` | `numeric`, `agree`, `compare`, `refine_fuzz`'s own `check`, `fmt`, and the extended values and SymPy-convention classification (`ext_value`, `ext_compare`, `ext_convention`) | 202 |
| `matrices` | the matrix family: predicates, explicit sample matrices, `mat_generate`, `mat_points`, `mat_value`, `mat_compare`, `MatrixRowCoverage` | 423 |
| `battery` | `load_battery`, `KEYS`/`SHORT`/`UNCHECKED`, `family_of`, `same`, `known_oracle_limit`, and `classify` (one case into one of the 7 categories plus an unchecked flag). The scoreboard and `refine_ablate` had separate copies of this | 83 |
| `sizes` | rows per family, `code_lines`, `engine_paths`, `family_paths` (the scoreboard's size lines) | 47 |
| `suite` | running a pytest suite under a backend and parsing its junit file (the old `refine_scoreboard`) | 51 |
| `report` | `table()`: two column formats, the old scoreboard's and the oracle's | 11 |
| `workers` | `run_json_worker` (a `python -m` worker that writes JSON; the differential and ablation had separate copies), `refine_case` (refine one case under a per-case alarm, check it, return a JSON record; the differential's worker and ablation's soundness gate had separate copies), `CaseTimeout`/`NO_SWALLOW`, the oracle's nested `timed`/`attempt`/`Timeout`, `run_forked`, `load_srepr` | 177 |

## Tools before and after (lines: physical / code, i.e. no blanks, comments or docstrings)

| file | before | after |
|---|---:|---:|
| `refine_fuzz.py` | 1,472 / 1,155 | 269 / 228 |
| `refine_differential.py` | 557 / 429 | 282 / 196 |
| `refine_ablate.py` | 453 / 338 | 387 / 274 |
| `refine_oracle.py` | 1,698 / 1,346 | 1,578 / 1,256 |
| `refine_identity_scoreboard.py` | 276 / 211 | 12 / 4 (shim) |
| `refine_scoreboard.py` | 227 / 163 | 12 / 4 (shim) |
| `scoreboard.py` (new) | – | 327 / 231 |
| `refine_battery_generate.py` | 299 / 242 | 303 / 244 |
| `refine_battery_capture.py` | 114 / 77 | 119 / 81 |
| `refine_specialize.py` | 93 / 63 | 92 / 61 |
| `refine_record.py`, `refine_replay.py` | 74 / 49 | 79 / 54 |
| `__init__.py` | 36 / 20 | 6 / 1 |
| `lib/` (12 files) | – | 2,104 / 1,448 |
| **total `satrefine/tools/*.py`** | **5,299 / 4,093** | **5,570 / 4,082** |

The total barely moves. What was removed as duplication (the second scalar generator, the second edge/cut-point code, the second battery classifier, the second worker record, the second worker runner, the `fz()` import dance, the `sys.argv` hacks) is roughly offset by module headers and docstrings in `lib/`. It also leaves room for the extra subcommand routing and `--help` handling. The 1,256 code lines left in `refine_oracle` are its own logic: templates, the old-system candidate search, the explicit 2x2 matrix instances and mode B's AST replay. Nothing else uses them.

## The merged scoreboard

```
python -m satrefine.tools.scoreboard [battery] [--handlers P] [--battery FILE] [--family F]... [--show] [--fuzz [SEED CASES]] [--lines]
python -m satrefine.tools.scoreboard lines                 # = battery --lines
python -m satrefine.tools.scoreboard suite [--backends sympy,satassume,combined] [--suite tests/refine] [--handlers P]
                                           [--junit-dir D] [--reuse D] [--show-failures B] [-- pytest args]
```

With no subcommand (or with options only), `battery` runs. So `python -m satrefine.tools.scoreboard` prints what `refine_identity_scoreboard` printed. `refine_identity_scoreboard ARGS` runs `scoreboard battery ARGS`, and `refine_scoreboard ARGS` runs `scoreboard suite ARGS`. The output of both halves is byte-identical to before, apart from timings. Checked: `--family trig --family minmax_deltas --show`, `--lines`, `--handlers handlers_v3 --family inverse --fuzz 2 40`, and `suite --backends sympy,satassume -- -k abs`.

## How behaviour was kept

- Before touching anything, 15 short runs of the tools on 34b3dae went to a scratch directory: fuzz scalar, v3, ext and matrices; differential scalar, ext and matrices, and the shim; scoreboard battery, lines, v3 plus fuzz, and suite; oracle mode A; ablation with and without soundness. After the changes each run's output was identical except for timings.
- Stream digests (scalar cases with points and `check`, the extended stream with points, matrix points) were identical before and after. The new test `test_sample_points_and_ext_stream_unchanged` pins them from the old code.
- `NO_SWALLOW` is now always `(CaseTimeout,)`. Before, the differential's worker set it to its own timeout class in `--ext` mode only. Only the extended checkers consult it, and `CaseTimeout` is raised only by the per-case alarm, so nothing else changes.
- The differential's and ablation's workers now run as `python -m satrefine.tools.<tool> --worker` with `SATREFINE_HANDLERS` in the environment. Before, they ran the tool file as a script, which set the variable before importing `satrefine`. The repository root is added to the worker's `PYTHONPATH`.

## Behaviour changes (deliberate)

- **`refine_oracle --mode b` works again.** It read the SymPy test modules from a hard-coded `/home/tilo/sympy`, so every module raised in its forked child. The error record (mode A's shape) then crashed the report with `KeyError: 'module'`, the same way on 34b3dae. It now reads the modules next to the imported `sympy` package, and a module whose replay raises is counted as `unreplayable`. First run, 26 modules: e.g. `test_complexes.py` 50 found, 38 match, 3 equivalent form, 5 gap, 4 trivial, 0 unsound.
- **`--help`** now works for `refine_battery_generate`, `refine_record` and `refine_replay`, which read `sys.argv` by hand. Before, `refine_record --help` ran the whole battery and wrote a pickle named `--help`. `refine_battery_capture` is a pytest plugin; run as a command it prints its docstring.
- `tools/refine_fuzz.py`, imported as a module, provides the lib's vocabulary, grammar and numeric check. Before, importing it ran a 3,000-case fuzz as `__main__`, which broke `tools/ask_fuzz.py`.

## Gates

`JOBS=10 SLOTS=11 SUITE_WORKERS=4 satrefine/tools/refine_gates.sh .claude/gates/tools-afb7883 .claude/gates/refactor-c14693f` (848 s, 1-minute load 5 to 10 from other work). The baseline is the one in `.claude/phase3/BASELINE`. The diff against it, by section:

- **suite:** 2 failed (the same 2 `needs/` tests), 2,635 → 2,641 passed (the 5 tests of `test_tools_lib.py` and the new pinned-points test), 1,920 skipped, 30 xfailed.
- **scoreboard, generated and live:** no change at all. The gates now run `scoreboard battery`.
- **differential, seeds 2, 3 and 7, both modes; satassume backend, seed 2, both modes; matrices, both modes:** only the time line changed.
- **differential ext, seed 2:** generated: v3 `unchanged 688 → 687`, `timeout 2 → 4`, `fired 136 → 135`, `checked 121 → 120`, 1 fewer case with an infinite point checked, and `same result 107 → 106`. Live: v3 `timeout 2 → 3`, identities `timeout 3 → 4` (`unchanged 684 → 683`). Unsound, crash and fired for identities are unchanged: 148 fired, 0 unsound, 0 crash. These are per-case 20 s timeouts under load. I ran the ext worker (`--worker P --ext --seed 2 --cases 1000 --timeout 20`) on 34b3dae and on this branch at the same time, for v3 (generated) and identities (live). The old and new records are identical for all 835 cases of each, including the timeouts (v3: cases 60 and 169; identities: 60, 169, 276, 392).
- **full fixpoint and termination:** only the time line changed (3 passed, 1 skipped; 8 passed).

The run used the five `satrefine/build` files of 2b7868b as untracked files (see Summary). The baseline worktree had them too.

## Tests

- New: `tests/refine_identities/test_tools_lib.py`. It covers the scoreboard's subcommand routing, `battery.classify`, the statuses of `workers.refine_case` and its unsound record, the `srepr` round trip, and `table`. `test_fuzz_ext.py` has the new pinned-points test.
- `test_fuzz_ext.py` and `test_matrix_fuzz.py` import from `satrefine.tools.lib`. `test_ablate.py` is unchanged and passes. `test_engine_termination.py` still imports `generate` from `satrefine.tools.refine_differential`, which re-exports it from lib. I left it alone because it is an engine test.

## Notes for others

- **Coordinator:** once this branch is merged, the "How to run things" line in `.claude/phase3/agent-rules.md` can say `python -m satrefine.tools.scoreboard [--family F] [--show]`. The old name keeps working for phase 3. I did not edit it, because the new command does not exist on `refine-identities` yet.
- **ri/refactor-specs:** `lib.matrices.MatrixRowCoverage` reads the matrix family's tables by name (`satrefine.identities.compat.matrices.DETERMINANT`, `HADAMARD`, `INVERSE`, `MATADD`, `MATMUL`, `MATRIXELEMENT`, `TRACE`, `TRANSPOSE`) and builds single-row handlers with `satrefine.identities.core.rewrite.rule_handler`. `lib.sizes` uses `satrefine.identities.families`/`family_module_name` and the family attributes `FACTS`, `EXP_FORMS`, `RULES`, `SIMPLE_RULES`, `RANGES`, `SPLITS`, `NEGATIVE_BASE` and `BOUNDED`. `refine_ablate` finds a family's keys from its literal `handlers_dict['key'] =` lines and its tables through the handlers' `rows`/`parts`. If the family specs change any of these, those three places need the new names. The tools only read `satrefine.build` through `stages` (as `refine_specialize` did before).
- `refine_battery_generate` keeps its own `srepr` loader and namespace. `lib.workers.load_srepr` has a slightly larger namespace, and without the capture files I could not check that it regenerates `battery_v3.py` byte for byte.

## Commits

2d9b07c (lib: generation, points, numeric, matrices, workers; fuzz and differential thin), 0a801a0 (one scoreboard; battery, sizes, suite, report; ablate and oracle over lib; `--help` everywhere), 1742433 (gates call `scoreboard battery`; lib tests), afb7883 (oracle mode B), plus this report.
