# Phase 3, track D: refactor steps 3–4 (issue #13)

Branch `ri/refactor-specs` (worktree `.claude/worktrees/ri-refactor-specs`), from 34b3dae. It is merged with `origin/refine-identities` at fdd87b8 (174fa09). It is not merged into `refine-identities`.

## Summary

- **Step 3:**
  - Every family module ends with `SPEC = Family(...)` and registers nothing.
  - `satrefine.identities.load()` registers every spec explicitly, in the old order.
  - The driver's generation hooks are replaced by one observer hook.
  - Every point where code outside `core/` plugs into `core/` is now an attribute of `core/hooks.py`.
  - `core/` names no specific SymPy function and no matrix type, and it imports nothing from `rules/` or `compat/`. The strict xfail is now a passing test.
- **Step 4:**
  - Measures are in one module, and there is one relation-predicate list.
  - `core/bounds.py` is merged into `core/prove.py` and reads the relation decider's normal form.
  - One row-table filter serves both `build/specialize` and `build/stages`.
  - Dead code is removed.
- **Behaviour is identical:**
  - Every gate section is identical apart from timings, line counts and the suite's new tests. The ext differential's timeout count is the one exception, and it depends on load (see Gates).
  - Regenerating the tables gives byte-identical output; `git diff` on `satrefine/identities/generated` is empty.
  - The three old suites give unchanged counts.
- **Engine size:** 1,842 → **1,775** counted lines (online 1,461 → 1,421, offline 381 → 354). **The target of 1,434 is not reached** without changing behaviour (see "What else would be needed").
- **Found and fixed first (2b7868b):**
  - The repo `.gitignore` line `build/` also matched `satrefine/build/`, so step 1's `verify.py`, `render.py`, `hooks.py`, `specs.py` and `__init__.py` were never committed.
  - As a result, `refine_specialize`, `test_generated` and `test_specialize` could not run at 34b3dae.
  - I rebuilt the files by replaying the step-1 agent's scripts on the committed sources. The regenerated tables were byte-identical. The coordinator cherry-picked the fix as d132bf3.
  - `.gitignore` now ignores only `/build/`.

## Spec schema (`satrefine/identities/core/spec.py`)

```
Rules(rows, *, by_binding=False)                                  -> rule_handler
Identities(rows, *, measure=None, opaque=None, splits=True)       -> identity_handler (opaque None: hooks.opaque)
Family(handlers, *, facts=(), exp_forms=(), rules=(), ranges=())  handlers: key -> part or tuple of parts (chained, in order)
chain(*handlers)                                                   (moved from rules/_tables; keeps .parts)
build(family) -> {key: handler}                                    each part object built once; a one-part key gets that handler itself
```

The classes are dataclasses with `eq=False`, so a part is identified by the object, not its content.

- **Table kinds (fixed):** the `Family` fields `facts` (identity rows, stated), `exp_forms` (exponential forms that `derive` composes with the facts), `rules` (rule rows, stated) and `ranges` (range rows for the `floor` of a bounded quantity).
- **Named tables stay:** module-level tables such as `DEFINITIONS`, `SPLITS`, `NEGATIVE_BASE`, `BOUNDED`, `MOD_FACTS` and the matrix `TRANSPOSE`… stay where they are, next to their docstrings.
  - They carry the maths, and they are the row labels in the generated tables' derivation comments (`complex_parts.SPLITS[0]`, `integer_funcs.MOD_FACTS[3]`). Renaming them would change the generated files.
  - The spec sorts them into the four kinds. For example, complex_parts has `facts=FACTS + SPLITS` and `rules=[ZERO] + RULES`; power_exp_log has `facts=FACTS + NEGATIVE_BASE`; trig has `rules=[ZERO] + RULES + BOUNDED`.
- **Covered heads:** these are the keys of `handlers`. Measures, opaque sets and `by_binding` are fields of each part.
- **`tests/refine_identities/test_family_specs.py` (new, 19 tests) checks that:**
  - importing a family module after `load()` changes neither `handlers_dict` nor `RANGES` (run in a subprocess);
  - every row a handler uses is stated in `facts`/`rules`, is in `derive(facts, exp_forms)`, or is a stated generic-head row with the key's head put in;
  - the registered handlers equal `build(SPEC)`, including which parts are shared.
- **`load()`:** it runs `_simple.install`, then the generated tables, then each family's spec and range rows.
  - The order is sorted except that power_exp_log goes before complex_parts. That was the real old import order, because complex_parts imports its `EXP_FORMS`.
  - I compared a dump of the registration before and after (every key in order, the kinds, the rows, shared handler objects, `RANGES`). They are identical apart from `chain`'s module path.
- **Generation settings moved to `build/specs.py`:** `CATALOGS`, `EDGE_POINTS = {"integer_funcs": (S(2), S(-2))}`, and `NOT_GENERATED = {"minmax_deltas"}` (which replaces `SPECIALIZE = False`).
- **Docstrings:** the family docstrings stay with the rows. Stale paths in them are updated (`._engine.derive`, `._specialize.compile_table`, `._engine.decide`, `tools/refine_differential.py`, …), and so are the paths in `generated/__init__` and the package docstring.
- **Removed:** `compile_rule` and `compile_table`. Five tests now call `rule_handler([...])`.

## One extension mechanism (`satrefine/identities/core/hooks.py`)

Every way code outside `core` plugs into `core` is now a plain module attribute. `core` reads them at call time, and they are set once, at load. The module docstring lists them.

| attribute | set by | replaces |
|---|---|---|
| `rebuild(func, args, assumptions)` | `compat/sympy_fixes` (acot/acoth guard, B8) | `driver.rebuild_hook` |
| `eval_refine` | `compat/sympy_fixes` (Pow/exp copies, A1) | `driver.eval_refine_copies` |
| `match`, `non_scalar`, `commutative` | `compat/matrix_match` | `match.MATCH_HOOKS`, `NON_SCALAR`, `COMMUTATIVE`, `register()` |
| `fallback`, `own_args` | `rules/_simple.install` | `driver.fallback_handlers`, `own_args` |
| head roles `opaque` (floor, im, arg), `conditional` (Piecewise), `modulus` (Abs), `step` (floor), `two_valued` (`floor_two_valued`) | `rules/_simple.install` | the SymPy function classes that `core/rewrite` and `core/split` used to import |
| `observer` (a stack of `Observer(on_fire, tables)`, pushed with `driver.observing(on_fire=None, tables=None)`) | `build/` | `note()`/`_trace`, `consulted`, `live_keys`, `staged()`, `build/hooks.live_for` |

How the observer works:

- The driver calls the innermost observer's `on_fire(kind, row)` on each firing of a table row.
- When that observer has `tables`, `tables(key)` picks the generated table the driver uses for `key`, whatever the mode. The observer's `tables` also replaces `frozenset(live_keys)` in the result-cache key.
- `build/hooks.tracing()` is `observing(on_fire=...)` plus its patch of `ask`.
- `build/stages` keeps its own dict of installed tables. It no longer clears and restores `driver.generated_handlers`, and the fixpoint compares the installed handlers.
- `specialize` runs under `live()` unless an observer supplies tables.
- `driver.live()`, `driver.tables()` and `generated_handlers` stay, because tests use them as mode switches.

`live`, `tables`, `observing`, `exploring` and `strict_loops` now share one stack context manager, `guard.pushed`.

## What left `core/`

- `core/rewrite` and `core/split` no longer import `Abs`, `Piecewise`, `arg`, `floor` or `im`. They use the head roles in `hooks`.
- `core/split` no longer imports `rules._simple`. It uses `hooks.two_valued`.
- In `prove._from_bounds`, `ceiling`/`floor` are gone. The integer refutation uses SymPy's exact floor division (`hi // 1`, `-((-lo) // 1)`).
  - The design's `math.floor` was wrong. It converts to a float first, so an endpoint `1.5707963267948966 - pi/2` (about -6e-17) came out as 0, and `atan(tan(x))` under `Q.le(x, 1.5707963267948966) & Q.gt(x, -pi/2)` stopped firing. The scoreboard caught it.
- `test_import_direction.py`: `REMAINING` is empty and the strict xfail is now a plain test. A new test, `test_core_imports_no_rules_or_compat`, is an AST scan that also catches lazy imports.

## Duplicates merged

- **Measures:** `core/measure.py` holds `size`, `_is_negation`, `_provably_positive`, `default_measure` and `node_measure`, which share one `_structure` helper; each returns the same tuple as before.
  - `count_measure((exp,))` replaces `exp_node_measure`.
  - `negative_number_base_measure` is Pow-specific and moved into power_exp_log, next to minmax_deltas' own measure.
- **Relation predicates:** `prove._RELATIONS` is the only list. `_ask_cost` and the bounds read it.
- **Bounds:** they are merged into `core/prove.py`.
  - `_stated_relations` puts each conjunct through `_RELATIONS`, and a sign fact counts as its relation against 0.
  - `stated_bounds` returns `(lo, hi, lo_open, hi_open, finite)`; `stated_finite` and `_stated` are folded into it.
  - B1–B9 hold as before:
    - a sign fact makes the quantity finite, and a relation does not;
    - a bound proves only `extended_real` and the extended signs unless infinity is excluded;
    - an empty interval proves nothing (`_checked`, in `stated_bounds`, `full_bounds` and `_merged`).
  - **Design point that did not hold:** the design's `d = v - u` found more bounds than before (`b - a` under `Q.lt(a, b)`, 22 calls), because `_affine` matches by structure. `d` therefore stays the stated difference, first argument minus second.
  - The new bounds were compared call by call with the old `bounds.py` over both battery modes and the full suite: about 38,000 calls, 0 differences.
- **Table filter:** `build/specialize.row_tables(module)` is now used by both `identity_keys` and `stages.row_labels`. The 189 labels are identical and in the same order.

## Dead code removed (each checked dead first)

- **`rules/_simple.refine_floor`:** integer_funcs always overrides `floor`/`ceiling`. A snapshot of the handlers after loading confirms it. `floor` and `ceiling` are vendored keys, so the key order is unchanged. The fallback is now `floor_of_bounded` itself, and the `simple_floor` wrapper and the `SIMPLE_RULES`/`FALLBACK_RULES` dicts went with it.
- **`build/render.write_family`:** grep found no caller.
- **The driver's path for non-SymPy results** (`non_basic_returns`, `sympify`): every handler is a table handler or one of `_simple`'s, and all return SymPy objects. The baselines report `non-SymPy=0`. The scoreboard's import of it already has an `ImportError` fallback.
- **Unused `__all__` lists** in rewrite, specialize and stages. `_tables.__all__` is kept because it declares that module's re-exports.
- **The driver's `MODE_ENV_VAR` re-export:** two tests now import it from `config`.
- **trig's unused `S` and `true`:** `ruff F401` is clean on `satrefine/identities` and `satrefine/build`.

## Tools (allowed by the coordinator for the spec API)

- `refine_ablate.family_keys` reads the keys of the module's `SPEC.handlers` instead of the `handlers_dict[...] =` lines. The unused `re` import is removed.
- `lib/sizes.family_rows` counts rows from each family's `SPEC` kinds. It counts only rows the module states in its own public tables, so the shared `ZERO` row and complex_parts' borrowed `EXP_FORMS` are left out.
  - `stage0` per family is unchanged, total 180.
  - Two columns move: complex_parts facts 5 → 6 and power_exp_log facts 4 → 6 (`SPLITS` and `NEGATIVE_BASE` are facts), and trig rules 13 → 14 (`BOUNDED`).
- `lib/matrices` coverage reads one rule table per key from `SPEC.handlers`, in the same order.
- The `refine_specialize` docstring now points at `build.specs.EDGE_POINTS`.

## Line counts (the scoreboard's counted code lines)

| module | 34b3dae (+ restored build) | now |
|---|---:|---:|
| identities/__init__ | 28 | 33 |
| config | 22 | 22 |
| core/driver | 223 | 173 |
| core/guard | 47 | 49 |
| core/hooks | – | 22 |
| core/match | 246 | 228 |
| core/measure | – | 53 |
| core/prove | 140 | 251 (bounds merged in) |
| core/bounds | 136 | – |
| core/rewrite | 144 | 121 |
| core/spec | – | 48 |
| core/split | 157 | 147 |
| rules/_simple | 105 | 95 |
| rules/_tables | 58 | 22 |
| rules/_wraps | 14 | 14 |
| compat/matrix_match | 81 | 83 |
| compat/sympy_fixes | 60 | 60 |
| **online** | **1,461** | **1,421** |
| build/hooks | 30 | 20 |
| build/render | 52 | 44 |
| build/specialize | 120 | 116 |
| build/specs | 9 | 19 |
| build/stages | 125 | 110 |
| build/verify | 45 | 45 |
| **offline** | **381** | **354** |
| **engine** | **1,842** | **1,775** |
| families | 509 | 467 |

Of the 1,775 counted lines, 65 are attribute docstrings: a string after an assignment, which the counter counts as code. I left them as they are. Counting them as docstrings would be a change to the counter in `tools/lib/sizes.code_lines`.

## What else would be needed to reach 1,434 (341 more lines)

I found nothing else worth more than a line or two that keeps behaviour identical. Every remaining option changes behaviour:

- **Drop the generated-table mode:** the mode switch, `generated_handlers`, the observer's `tables`, and `build/`. That is about 30 online and 354 offline lines. The fast path goes, and live becomes the only mode.
- **Drop the case and endpoint splits:** `core/split` (147 lines) and their uses in rewrite (about 15). Rows whose bookkeeping collapses only through a sign split would stop firing.
- **Move the matrix matcher out of the engine count:** `compat/matrix_match` is 83 lines. It could be counted with the matrix family, or dropped with it.
- **Drop the `_eval_refine` copies** in `compat/sympy_fixes` (about 40 lines), once SymPy routes them through the backend.

The phase-3 fixes added about 260 engine lines before this refactor (1,434 → 1,695). Step 1's moves then added 147 (→ 1,842), and steps 3–4 removed 67 net, including the new `spec`, `hooks` and `measure` modules.

## Gates

Run as `JOBS=10 SLOTS=11 SUITE_WORKERS=4 satrefine/tools/refine_gates.sh .claude/gates/specs-174fa09 .claude/gates/tools-merged-fdd87b8`. Results by section:

- **suite:**
  - Before: 2 failed, 2,641 passed, 1,920 skipped, 30 xfailed. Now: 2 failed, 2,662 passed, 1,920 skipped, 29 xfailed.
  - The 2 failures are the same 2 `needs/` tests.
  - The 21 extra passes are the 19 `test_family_specs` tests, the new core-imports test and the former strict xfail.
- **scoreboard, both modes:** only the `engine` and `families` line counts changed. The per-family table and the totals are identical.
- **differential:** seeds 2, 3 and 7 in both modes, the satassume backend in both modes, the matrices runs and the ext live run changed only in their time lines.
- **differential ext, generated:** this is the one exception to "only timings changed". The identities side went `unchanged 683 → 684`, `timeout 4 → 3`; v3 on the same run went `unchanged 687 → 688`, `timeout 3 → 2`. Fired 148, unsound 0 and crash 0 are unchanged. This is the known load-dependent 20 s timeout: refactor-1 measured 3 and the fdd87b8 baseline 4.
- **full fixpoint and termination tests:** only the time lines changed (3 passed and 1 skipped; 8 passed).

**Suites run on their own** (`-n 4`), counts unchanged from 34b3dae:
- tests/refine: 452 passed, 47 skipped, 4 xfailed.
- tests/refine_v3: 1 failed, 1,004 passed. The failure is the same test as before, `test_arg_of_exp_needs_the_principal_range`.
- tests/refine_v2: 1 failed, 160 passed. The failure is the same test as before, `test_relation_rules_do_not_fire_under_the_satassume_backend`.

**Speed:** the full battery was timed pinned to cores 10 and 11, with the cores swapped between runs, at a load of about 2–3.
- Step 3A against 2b7868b: 85.6 s against 86.0 s, and 86.4 s against 88.6 s.
- Step 4 against 2ba1873: generated mode 82.0 and 82.9 s against 82.8 and 81.9 s; live mode 81.7 and 83.0 s against 82.9 and 82.7 s.

It is not slower.

## Commits

2b7868b (restore of build/), 926cd93 and 4fb9d22 (hooks, core names-free), d7f34f3 and 2ba1873 (specs), 494502b (measure), b2da413 (bounds into prove), 36cde60 (table filter), 97f3964 (dead code), 57ff5e3, 4a79f8f, bed29ec, 25cdb4e and 88d75ba (simplifications), 174fa09 (merge of fdd87b8 and the tools' spec API), plus this report.
