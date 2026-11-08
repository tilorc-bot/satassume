# Step 5c6: the rest of `Session` on Rust (issue 323)

## What moved
- **The eight `Session` rows** (sa-port-134, 50fb678): `Session.__init__`, `assume_formula`, `link_set`, `assumption_lits`,
  `_set_glue`, `_group_sel` and `_glue_of` are in `solver_rs/src/session_glue.rs` (init :30, assume_formula :81, link_set :134,
  assumption_lits :152, set_glue :246, group_sel :330, glue_of :388; pyfunctions `ses_*` :420-463). `session_live.py`
  `_install_glue` (:702) wires them, and `SLICE_GLUE=py` puts Python's back. The class row `Session` goes with them.
- As in 5c1-5c5, the session's containers (`_groups`, `literals`, the solver, `Relations`) stay the Python objects Python
  reads later, so state is Python's by construction. Rust makes every read and call Python makes, in the same order.
- **Direct calls:** among these seven, and from `query.rs` (:274, :308, the two `_glue_of` callbacks that were
  `call_method1` before), every call is direct Rust. Other `Session` methods (`emit`, `_ensure_atoms`, `discover`,
  `_relations`, `dvar`) are still called by name, as Python calls them. Under the default backend each one is a 5c1/5c3
  `session_live` shell into Rust.
- **Counters** `ses:init` .. `ses:glue_of` (session.rs :182-188). **Plants** (relations_core.rs :148-154): one per moved
  method.
- **Shells:** `_ses_init` falls back to Python's `__init__` when `engine.VarTable` isn't `TableView`, and the other six
  fall back when the session's table isn't a `TableView`. ref.py's `_RefSession` is untouched.

## SHAs
Tested **50fb678**: port/5c6 on rust-slice 803d073. Rows are on pareto1 at `~/sp19/sa-rust-ids-work/sa-port-134/bar-5c6/`
(`sum.txt`, `commands.txt`). The `.so`'s sha256 is c5c0e922…, and the base is scope's suite rows
(`sa-port-126/bar-scope2/suite`). The supplementary suite under `glue-of-plain` ran from
`~/sp19/sa-rust-ids-work/sa-port-135/bar-5c6-glue/` on 55c80ab. 55c80ab adds only sa-port-134's handoff note to 50fb678,
so it runs the same code. The landing source is the commit carrying this file. Between it and 50fb678 there are only docs
(this report, port-ownership.md/.tsv and the handoff note), which no run executes. The incoming diff at landing was empty: rust-slice was still 803d073.

## The bar (sa-port-134/bar-5c6)
1. **Suite by id against scope's rows:** 5,958 passed, 126 failed, 23 skipped, 18 xfailed, 6,125 ids. New 0, gone 0,
   changed outcome 0. Passed splits as 5,957 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`).
   S's standing: S's gate is met except for the 46 named stub failures, one cause.
2. **Fresh dev and fuzz, plus loop and scope:** answers and state MATCH, and every control MATCHes. Answers are unchanged:
   dev 31cd0945c07f02a6 (1,985 q), fuzz 173502b6ef285ad6 (3,000 q), loop 09238b2537e54383 (420 q), scope 12e06b0586faee40
   (169 q). The Rust runs made 0 Python solvers.
3. **Plants:** see the table below. 6 of 7 are caught on dev and fuzz. `glue-of-plain` fires and MATCHes on every
   workload, and the suite catches it (36 changed outcomes). None is void.
4. **Quiet handlers in the suite:** 39 rows in 2 tests, the same multiset as base:
   - `_consistent` AttributeError: 34 on `_ok` and 4 on `_rb_clauses` (the named needs-internals case);
   - `Engine._build_context` "Already mutably borrowed": 1, in `test_protocol_on_fuzz` (the 46-stub cause).

   The `caught` rows per id match base. **Quiet catches at engine.py:1906: 1**, in the suite, as on base. Dev, fuzz, loop
   and scope have 0: their 14 handler files have 0 rows, and so do all 14 dev/fuzz plant handler files. TermFault 0. The
   counter fires: the suite's own rows show it.
5. **Known differences in answers or read state:** none. Tests: 510 passed (the 11 slice files), and
   `relations_direct.py` exited 0.

## Plants (fired; D = DIFFER)
| plant | item | dev | fuzz | loop | scope | caught by |
|---|---|--:|--:|--:|--:|---|
| init-no-relations | `__init__` | 198 D | 3,018 D | 0 | 135 D | dev, fuzz, scope |
| af-drop-relations | assume_formula | 196 D | 2,950 D | 0 | 133 D | dev, fuzz, scope |
| link-set-skip | link_set | 32 D | 14 D | 0 | 8 D | dev, fuzz, scope |
| al-drop-delta | assumption_lits | 197 D | 2,631 D | 0 | 36 D | dev, fuzz, scope |
| set-glue-no-emit | _set_glue | 334 D | 6,025 D | 0 | 5 D | dev, fuzz, scope |
| group-sel-no-impl | _group_sel | 45 D | 15 D | 0 | 13 D | dev, fuzz, scope |
| glue-of-plain | _glue_of | 2,201 | 13,797 | 488 | 737 | suite (36 changed) |

**glue-of-plain** returns `atoms` unchanged at every call, so it "fires" 2,201 times on dev. It changes the result only
when the session has zero atoms (`_a_zs`) or `atoms` holds a `zero` atom, and `glue_atoms` then adds twins. 5c5 found
that neither dev nor fuzz reaches `glue_atoms`' twin case (`glue-no-twins` was 0 there and caught only by the suite, with
43 changed). So the plant is void on all four workloads in effect, though its fire count isn't 0. `SUITE_PLANTS=zero`
didn't select it for that reason, and I ran the suite under it separately (bar-5c6-glue, phases build, suite, suiteplants and sum). The plain suite there reproduces bar 1 exactly (5,958/126/23/18, 0 changed, same handler multiset). Under the plant: 5,922 passed and 162 failed, with **36 ids passed -> failed**, new 0 and gone 0. Those are 25 in test_zero_glue.py, 4 in test_ref.py's `test_zero_under_an_application_is_an_equality`, 3 in test_history.py's transfer repros, 2 in test_p7_review's I5 zero-as-eq repros, `test_scope.py::test_zero_twins_are_in_the_scope` and `test_invariants.py::test_ci_stream_no_longer_finds_the_zero_i2_family`. The handler multiset is the same as base, and the plant fired 146,490 times in the suite. **Caught by the suite**, and by no live workload.

## Reached (and by which workload)
Calls per pass, from the bar's Rust session reports (dev, fuzz), and from a caller probe on orion
(`~/sa-rust-ids-work/sa-port-135/caller_probe.py`, output in `trace/`, answers equal to the bar's on all four workloads).
The probe wraps each installed method with a counter keyed by its Python caller, so calls Rust makes directly don't pass
through it. Its `ses:*` counts equal the bar's on dev and fuzz.

| method | dev | fuzz | loop | scope | Python callers (dev) | Rust direct |
|---|--:|--:|--:|--:|---|---|
| `__init__` | 918 | 3,133 | 384 | 171 | `Engine._fresh_session` 918 | 0 |
| assume_formula | 833 | 2,952 | 244 | 166 | `Engine._build_context` 833 | 0 |
| link_set | 833 | 2,758 | 244 | 166 | `Engine._build_context` 833 | 0 |
| assumption_lits | 1,611 | 5,602 | 488 | 334 | `_build_context` 833, `Engine._ask` 776, `Engine._is_custom` 2 | 0 |
| _set_glue | 327 | 5,451 | 0 | 10 | none | all (from assumption_lits) |
| _group_sel | 32 | 14 | 0 | 31 | none | all (from assumption_lits) |
| _glue_of | 2,201 | 13,797 | 488 | 737 | none | all (assumption_lits, query.rs) |

On fuzz the Python callers are `_fresh_session` 3,133, `_build_context` 2,952/2,952/2,758, `_ask` 2,605 and `_is_custom` 45.
**All seven moved items are reached on dev and on fuzz, and each plant fires there.** No REACHED-CODE workload is owed
for the methods. The exception is `_glue_of`'s twin branch (`_a_zs` or a `zero` atom present), which dev and fuzz don't
reach. The suite reaches it (36 tests change under `glue-of-plain`). Loop reaches neither `_set_glue` nor `_group_sel`.

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
Share of queries kept per reason, out of the queries the engine converts or keeps (`converted` plus every `kept:*`). Base
is scope's bar (`sa-port-126/bar-scope2`, live and extra knowledge.json).

| workload | queries at conversion | out-of-scope | refused | other named exceptions | base |
|---|--:|--:|--:|--:|---|
| dev | 1,221 | 24 (1.97%) | 0 | 0 | the same: 24 of 1,221, refused 0 |
| fuzz | 2,998 | 0 | 0 | 0 | the same |
| loop | 384 | 0 | 0 | 0 | the same |
| scope | 169 | 0 | 0 | 0 | the same |

**No share rose.** `refused` is absent from all four files, which means 0 (term_live.py:913). `const_value`'s fire count
isn't counted on this branch, because its counter comes with 6d.

## Module count (count rule)
**engine.py doesn't count. It counts at 5c10.** The eight Session rows are Rust, but under the count rule a shell is Python
running per query. What still runs as Python per query for `Session`:
- **the seven 5c6 shells** in `session_live.py` (`_ses_init`, `_ses_assumption_lits` and the `_g` wrappers): each one is an
  `isinstance` check and a call into Rust. They're called from Python's `Engine._fresh_session`, `_build_context`, `_ask`
  and `_is_custom`. They go when those callers move to Rust (5c9, 5c10) and call `session_glue` directly;
- **the 5c1/5c3 shells** that Rust still calls by name (`emit`, `_ensure_atoms`, `discover`, `_relations`, `dvar`, and the
  `table`/`base` properties). Rust calls a Python shell, which calls Rust again. These can become direct calls once nothing
  outside the session can replace them, which is 5c10 at the latest.

So `Session` has no Python body left that runs per query, apart from those shells. The module count is unchanged by this
step. **engine.py's per-query Python left for 5c7-5c10** (port-ownership.md :35, :36, :42, :43, and sympy_api.py :90):
- **5c7:** `Engine._drop_cones`, `_struct`, `_cone_info`, `_query_cone`, `_union`, `_within_budget`, `_over_budget`,
  `_note_budget`, `neighbourhood` (the budget and cone).
- **5c8 (sympy_api.py, relevance):** `_const_base`, `_const_free`, `_closed_keys`, `_expr_keys`, `_arg_keys`, `_keys_rel`,
  `_bool_keys`, `_sides_keys`, `_Split` (with `__init__` and `part`), `_relevant`, `_part_consistent`, `_consistent`.
- **5c9:** `engine_memos`, `DictCache` (`sync`, `facts`, `put`), `AnswerMemo.put`, `Engine._fresh_session`, the settings
  properties read per query (`extensions`, `relation_specs`, `transfer`, `uninterpreted`, `relevance`), `_check_version`,
  `_settings_fingerprint`; and state/ (`epoch.bump`, `memos.Table`/`Memos`).
- **5c10:** `Engine.ask`, `_ask`, `is_many`, `_decide`, `_is_custom`, `_build_context`, `_build_context_memoized`,
  `_context_session`, `_complete_check`, `verdict`, `_put_result`, `_noncommutative`, `_noncommutative_atoms`, `_kid`,
  `_check_writeback`, `_check_uninterpreted`, `_gave_up`, `_exhausted`, with `Engine.is_` (called back) and the removal of
  the shells above.

The ownership rows are updated: port-ownership.md :41 and the TSV's rows 19-20, 43-47 and 50 now read "landed 5c6
(port-5c6.md)", Rust. TSV totals for "today" after this step: Rust 478 (was 470), Python 313 (was 321), called back 19,
kept as type 2.

## Owed-list additions
- `_glue_of`'s twin branch has no live catch. A live.py workload with zero atoms under applications, in the set or in the
  proposition, would reach it. It's the same workload 5c5 owes for `glue_atoms`' twins and `zero_twins`, and 5c4 owes for
  `drop-prep-twins`. One workload covers all four. The suite catches it meanwhile.

## Not run
Moved to "before any backend PR", and none quoted as met:
- the mutant 2, 5, 6, 7, 9 rerun and mutlive's control;
- the boundary rescore and suite column;
- the final drop score and its lost rows;
- the suite split with Python's counter;
- `order:_rows`' evidence (not caught meanwhile);
- the `_forms` guard test;
- history and seed reruns (seed1 not run);
- forced moves;
- the native path;
- timing.

Also not run: the suite under the six plants that dev and fuzz catch (not needed; `zero` doesn't select them).

Other notes:
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and
  the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- The public-API `test_incremental_matches_fresh` family is still owed, as a test-only step before 5c7 (pure Python first,
  adds only, and a Python failure is a finding against main).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals. This
  step doesn't touch it.
