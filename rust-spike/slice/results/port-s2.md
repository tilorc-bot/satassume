# S2: the rule block's tables on Rust, no call into solver.py per solver (issue 323)

Worked by sa-port-208 (code, probe, bar launch) and sa-port-210 (bar reading, landing, this report).

## What moved
`Solver.set_rule_block` on Rust used to call Python's `_rule_tables` (satassume/sat/solver.py:362) once per Rust solver,
which is once per query (dev 918, fuzz 3,133). It no longer calls into solver.py at all.
- **Offline or ported: both, by case.** RULE_INTERNAL (rules.py:422) is a pure function of the static RULES (rules.py:96,
  174, 418). Every engine path passes `RULE_INTERNAL, NPRED` (engine.py:317, ref.py:218, session_glue.rs:41).
  - **The engine block is generated offline.** gen_rule_tables.py runs Python's `_rule_tables` and writes
    solver_rs/src/rule_tables_gen.rs (NVARS, CLAUSES, MODELS). test_rule_tables.py regenerates it and compares it with what
    `_rule_tables` computes today (`test_generated_file_regenerates`), as the other generated tables are checked.
  - **Any other block is ported.** Other blocks reach `set_rule_block` only through the public Solver API: tests/test_solver.py
    :565 :785 :804 :833 :843 :855 :860, tests/test_solver_incremental.py:162 (random small blocks), slice fuzz.py:424 :656
    :784 :786, check_step1.py:97-120, replay. block.rs `rule_tables` :34 checks them in `_rule_tables`' order with Python's
    messages (`check` :60) and enumerates their models (`block_models` :150, a port of `_block_models`).
- **Run-time registration.** knowledge/extensions.py's registration adds clauses or atoms and never changes the rule block, so
  it can't change the tables. A block that isn't the generated one, whatever its source, takes the ported path; nothing
  depends on the generated file being complete.
- Python's `_rule_tables` is unchanged; the pure-Python path still uses it.
- Counters `rb:generated`, `rb:built`, `rb:check_error` (420-422); plants 320-323; 345-419 padded "reserved:".

## SHAs
- Tested: **bb92b07** (bar `bar-s2`), stacked on sa-port-207's tested ce1092c.
- Landed: **fd367ce** = bb92b07 rebased on rust-slice cac82a9, plus sa-port-208's handoff commit and this report's commit
  (neither is under bar.sh's push guard).
- **Incoming diff** (ce1092c..cac82a9): `rust-spike/slice/results/port-state-relations.md` only, 87+/16-. bar.sh's guard
  found no source file differing between bb92b07 and fd367ce (`git diff bb92b07 fd367ce -- satassume rust-spike/slice`
  outside results/: empty). No code the bar ran changed, so no rerun (rebase rule); no rebuild was needed for an identical
  source.

## The bar (pareto1, `~/sp19/sa-rust-ids-work/sa-port-208/bar-s2` on bb92b07)
Run 14:01Z-14:54:43Z, shared lease, every phase exit 0; seed1 not run. `.so` sha256 5ee060a2…. Base suite rows: sa-port-207's
`bar-state-relations-iii1b/suite` (ce1092c). WLS: f6 value rootof opaque core scope loop zero wiring cert budget. Tests phase:
sa-port-207's list plus test_rule_tables.py and 6i(a)'s 4 knowledge tests: **746 passed, 4 skipped**, exit 0. DIRECT
`relations_direct.py 300 0`: exit 0.
1. **Suite by id:** 5,991 passed, 127 failed, 23 skipped (plus 18 xfailed), over 6,159 ids. **Against base: new 0, gone 0,
   changed outcome 0.** Passed splits into **5,990 with no handler firing and 1 with a firing**:
   `tests/test_invariants.py::test_ci_stream_reports_only_what_replays`, the named case.
2. **Fresh dev and fuzz: answers and state MATCH** (Rust against Python, traced and untraced; Python against Python as the
   control). dev answers_sha 31cd0945c07f02a6, fuzz 173502b6ef285ad6; Rust made 0 Python solvers (918 / 3,133 on Python).
   All 11 extra workloads MATCH, Rust against Python.
3. **Plants caught:** the wrong-table plant `rb-gen-model-flip` fired and was caught on all 13 workloads. Table below.
4. **Quiet handler firings on Rust: the handler multiset is the same as base.** 39 rows in 2 tests:
   - 34 × `_consistent` AttributeError `'Solver' object has no attribute '_ok'`, in test_ci_stream_reports_only_what_replays;
   - 4 × `_consistent` AttributeError `'Solver' object has no attribute '_rb_clauses'`, in the same test;
   - 1 × `Engine._build_context` RuntimeError "Already mutably borrowed", in test_protocol_on_fuzz (the named 46-stub cause).

   **engine.py:1906's catches (`ctx:caught`): 0 on all 13 workloads**, and 0 in the base bars. This step didn't re-show the
   counter firing on a planted raise; earlier steps did. TermFault in pytest.log: 0. The live and extra handler files have
   0 rows. Each session report's `so` is this bar's build.
5. **Known differences in answers or read state: none.**

## Plants
| plant | fired (bar), per workload | caught by | suite (SUITE_PLANTS `zero`) |
|---|---|---|---|
| `rb-gen-model-flip` (320) | dev 918, fuzz 3,133, f6 2,902, value 3,550, rootof 4,784, core 1,635, opaque 2,373, scope 171, loop 384, zero 667, wiring 5,818, cert 87, budget 17 | **DIFFER on all 13** (state: stream, end or lra; answers equal) | not run (fires on workloads) |
| `rb-built-model-drop` (321) | **0 on all 13: void on workloads** | test_rule_tables.py (in the bar's tests phase) | fired 15 (7 workers), **0 changed: void in the suite** |
| `rb-gen-any` (322) | every call (= `rb:generated`), MATCH on all 13: **void on workloads** | test_rule_tables.py | not run |
| `rb-check-skip` (323) | every call, MATCH on all 13: **void on workloads** | test_rule_tables.py | not run |

The three void plants are void by construction: no workload passes a block other than RULE_INTERNAL, and RULE_INTERNAL is
well formed, so skipping the checks or taking the generated tables for "any" block changes nothing there. They are caught
by `test_plant_is_caught[...]` in test_rule_tables.py, which passed inside the bar's 746. **Finding (not a landing
blocker):** the main suite builds 15 non-engine blocks under the plant and none of its tests notices a dropped model.

## Per-query calls into solver.py, before (693fef9 and 9e10f0d, identical) and after (bb92b07)
Module-wide probe (pycalls.py, PYCALLS_FILE=satassume/sat/solver.py, every function), 15 workloads, all exit 0. Before:
| workload | queries | `_rule_tables` (converted / kept) | `_block_models` | `_BlockClosure` | after |
|---|---|---|---|---|---|
| dev | 1,985 | 914 / 6 out-of-scope | 188 | 2 | **0** |
| fuzz | 3,000 | 3,135 / 0 | 188 | 2 | **0** |
| f6 | 2,902 | 2,891 / 13 refused | 188 | 2 | **0** |
| value | 3,742 | 3,537 / 15 refused | 188 | 2 | **0** |
| rootof | 5,187 | 4,786 / 0 | 188 | 2 | **0** |
| core | 1,636 | 1,637 / 0 | 188 | 2 | **0** |
| opaque | 2,546 | 2,368 / 7 refused | 188 | 2 | **0** |
| scope | 169 | 173 / 0 | 188 | 2 | **0** |
| loop | 420 | 386 / 0 | 188 | 2 | **0** |
| zero | 854 | 669 / 0 | 188 | 2 | **0** |
| wiring | 6,512 | 5,819 / 1 refused | 188 | 2 | **0** |
| cert | 61 | 89 / 0 | 188 | 2 | **0** |
| budget | 28 | 19 / 0 | 188 | 2 | **0** |
| dev-seed1, fuzz-seed1 | as dev, fuzz | as dev, fuzz | 188 | 2 | **0** |

Before, `_rule_tables` had 1 miss per process and the rest were memo hits (`_BlockClosure.__init__` once). After, the probe
is live: it still records solver.py's 6 import-time calls (`noquery`) on every workload, and nothing else.

## Module count (STATUS "Counted modules", 18 of 32)
**19 of 32: solver.py joins**, on the module-wide probe above: 0 calls per query on all 15 workloads, kept paths included.
Footnote: "solver.py: 0 calls per query on all 15 workloads (import time only); the engine's rule block is generated
offline from `_rule_tables` (test_rule_tables.py regenerates and compares); `_rule_tables` stays for the pure-Python path."
The other footnotes stand as in STATUS, including registry.py and templates/__init__.py's "pending: install order".

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
Every share equals base (sa-port-207's bar for dev, fuzz, budget, cert, loop, scope, zero; 6i(a)'s bar for the other six).
- Out-of-scope: dev 24/1,985 (1.21%); every other workload 0.
- Refused: f6 13/2,902 (0.45%: `algebra: Float` 10, `lra: a callback on a derived term` 1, `scaffold: rebuilt form differs
  from Rust` 2); value 15/3,742 (0.40%, `algebra: Float`); opaque 7/2,546 (0.27%: `algebra: infinity or nan` 5,
  `algebra: holds an infinity, nan or Float` 2); wiring 1/6,512 (0.02%, `lra: a callback on a derived term`); 0 elsewhere.

## Fallbacks to Python inside ported code (planner's fallback-reporting ruling)
From the bar's knowledge files with sa-port-204's `fbcounts.py`. **Every count equals base, by template**, on all 13
workloads (sa-port-207's bar for the 7 it ran, 6i(a)'s bar for core, f6, opaque, rootof, value, wiring). This step touches
no template.

| workload | dispatch.rs:242 `registry:python`, by template | rows_tpl.rs:413 `rows:python` | `ad:cbm_noid` |
|---|---|---|---|
| dev | 126: `_load` 68, `_unary` 31, `symbol_units` 15, `constant_units` 12 | 625 | 0 |
| fuzz | 38: `_load` 30, `constant_units` 6, `symbol_units` 2 | 378 | 0 |
| f6 | 211: `_unary` 97, `_load` 54, `nary` 49, `symbol_units` 7, `constant_units` 4 | 878 | 0 |
| value | 507: `_unary` 327, `constant_units` 150, `_load` 29, `symbol_units` 1 | 1,208 | 0 |
| rootof | 27: `_load` 26, `symbol_units` 1 | 16 | 0 |
| core | 35: `_load` 28, `symbol_units` 6, `constant_units` 1 | 2,105 | 0 |
| opaque | 101: `_unary` 59, `_load` 39, `symbol_units` 3 | 69 | 0 |
| scope | 26: `_load` 26 | 0 | 0 |
| loop | 31: `_load` 20, `symbol_units` 6, `constant_units` 5 | 161 | 0 |
| zero | 43: `_load` 29, `symbol_units` 6, `_unary` 5, `constant_units` 3 | 119 | 0 |
| wiring | 75: `symbol_units` 40, `_load` 35 | 510 | 0 |
| cert | 24: `_load` 20, `symbol_units` 3, `constant_units` 1 | 208 | 0 |
| budget | 469: `symbol_units` 450, `_load` 19 | 80 | 0 |

`rows:python` by template: `Integer` and `const_value` (the named callback) on every workload, plus the kcl shells
(`_bound_split`, `_half_split`, `_imag_split`, `_mul_factor_sets`, `_quotient_templates`, `Add`, `Mul`,
`_pow_bound_templates`, `_unit_power_units`, `ipi_split`, `constant_value`), each equal to base; full lists in
`~/sa-rust-ids-work/sa-port-210/fb.txt`. Owners as in port-6i-a.md (`_unary`/`nary`: 6i(b); `symbol_units`/
`constant_units`: atoms' input facts; `_load`: the registry load). So dispatch.rs:242 and rows_tpl.rs:413 don't yet report
0 outside named callbacks.

## State: each container this step touches
`set_rule_block`'s tables (clauses, nvars, models) go into the Rust solver as before; only their source changed. Python
never read the Rust solver's copies. The bar's live state comparison MATCHes on all 13 workloads.

## Not run
Moved to "before any backend PR", none quoted as met: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control; the boundary
rescore and suite column; the final drop score and its lost rows; the suite split with Python's counter; `order:_rows`'
evidence (not caught meanwhile); the `_forms` guard test; history and seed reruns (the bar's seed1 phase not run; the probe
ran dev-seed1 and fuzz-seed1); forced moves; the native path; timing.
Also not run: a re-shown `ctx:caught` firing on a planted raise in this step; the suite under `rb-gen-any` and
`rb-check-skip` (SUITE_PLANTS `zero` picks only plants that fired 0 on workloads).

Other notes:
- S's standing: S's gate is met except for the 46 named stub failures, one cause.
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals.
- `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`: the known id()-reuse
  failure (a28c548), unedited.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and the
  boundary suite column wasn't run.
- **Install order:** sa-port-206's harness fix has not landed, so the scope workload's MATCH here still rests on the old
  order (live.py builds the default engine before `backend.install()`).
- `test_performance_smoke_300_vars`: same outcome as base in the bar's suite (changed outcome 0 overall); not chased.
- **Speed not measured.**
