# State step, part 1: lra_live `_memoized` on the Rust adapter (issue 323)

## What moved
The planner's go (forward-chain-3b, 9 Nov ~03:12): the state step's first part, lra_live `_memoized`, with the atom's term ids
and the query table on the Rust adapter (ruling of 8 Nov ~09:40, item 1: "At 165k crossings on fuzz it's the largest single
crossing left"). Work by sa-port-195 (WIP d1d9728, handoff 2d41d9d); fuzz quick runs read, plant table, group-D AFTER,
readers and report draft by sa-port-197; rebase, bar, the TermRefuse fix and landing by sa-port-198.
- **adapters.rs `LraAdapter.memoized`** (:105-170) answers `_memoized(key, read, arg)` from the adapter's own per-query slot,
  `LraQuery`: the query's table, ids and objects (from term_live's stack top, `top_query` :258) and the results, keyed by
  kind (interpret / order_sides / integer_form), the argument's identity and `GENERIC_CONSTANTS`. The slot is replaced when
  the stack top changes and dies with the adapter. `Reader` (:300-440) is lra_live's `interpret`/`order_sides`/`integer_form`
  line for line, calling the table's `lra_*` readers natively (term/py.rs `lra_interpret`/`lra_order_sides`/
  `lra_integer_form` made pub(crate), `n_input_rows`).
- **Callbacks into Python left, counted by reason:** `ad:cbm_off` (lra_live not installed: the pure-Python path),
  `ad:cbm_check` (live.py `--check`), `ad:cbm_patched` (a patched `_memoized` or reader is called, not bypassed),
  `ad:cbm_noquery` (no converted query on the stack: kept queries), `ad:cbm_noid` (a side with no input row: Python reads it).
  `ad:cb_memoized` is their sum. **Inside the slot, Python entered directly:** `relation` (`ad:lra_relation`), term_live's
  `term_id` for a term with no input row of its own class (`ad:lra_term_id_py`), `scaffold` for a derived term
  (`ad:lra_scaffold`), `_fault`.
- `sa_solver.ad_lra_live(cfg|None)`: registered by lra_live `_install`, cleared by its undo. **Test-only snapshot export:**
  `sa_solver.ad_lra_export(on)`, every slot entry as stored.
- **Counters** (session.rs): 327-336 (`ad:lra_native`, `ad:lra_hit`, `ad:lra_relation`, `ad:lra_term_id_py`,
  `ad:lra_scaffold`, `ad:cbm_noquery`, `ad:cbm_noid`, `ad:cbm_check`, `ad:cbm_patched`, `ad:cbm_off`); NAMES is 337.
  **Plants** (relations_core.rs): 251-255, `_LRA_SLOT_PLANTS` (session_live.py); the u8 plant space is now full.
- **New test:** test_lra_slot.py: cert_wl's queries plus integer-form and closed-constant cases, Python against Rust, each mode
  in its own process; every exported slot entry against lra_live's own function on the same query; the digest of the slot's
  results against lra_live's (the switch digest); the flag guard and the patch guard directly. 6 passed, 1 skipped
  (`ad-lra-slot-stale`, void by construction, named in `ELSEWHERE`).
- **pycalls.py** takes `PYCALLS_FILE` (any file in the clone) and files each call under the query it ran under, read from
  term_live's stack top as `top_query` reads it (`by_state`, `by_name_state`).
- Python's `_memoized` (lra_adapter.py :439) is unchanged: the pure-Python path and the callback above.

## SHAs
**Tested: d21abb6** (port/state-memoized on rust-slice 2742b66). Bar run 2, 06:45Z-07:16Z on pareto1 under a shared lease
(every phase exit 0 but seed1, not run; machine run released the lease exit 0), rows
`~/sp19/sa-rust-ids-work/sa-port-198/bar-state-memoized-r2/` (summary copied to `~/sa-rust-ids-work/sa-port-198/bar/sum-r2.txt`);
`.so` sha256 b21fbb30…. Base suite rows: the 6g c6-c9 stack's landing bar (`sa-port-194/bar-6g-c6c9/suite`).
**Incoming diff before the bar:** the branch was cut from 9529850 and rebased onto 2742b66 (the 6g c6-c9 stack: rows_tpl.rs,
term/py.rs, knowledge_core_live.py, knowledge_common_live.py, templates/functions.py and wiring.py, offline_data.json,
test_knowledge_core_shapes.py, results/). The rebase applied cleanly; both bars ran on the rebased source, so it is covered.
**Bar run 1 (b2339d0, `bar-state-memoized/`, 06:10Z-06:40Z) found a bug; see "The bar's finding" below.** Its rows are kept and
not used for landing.
**Landed:** the commit carrying this file, on rust-slice 2742b66. **Incoming diff at landing: none** (2742b66..2742b66, rust-slice unchanged since the bar started). Between d21abb6 and the
landed commit there is only this report, port-ownership.md/.tsv and HANDOFF-sa-port-197.md moved into results/ (doc only);
the landing guard saw no source difference. Week reading before the push: 87%.

## The bar (sa-port-198/bar-state-memoized-r2 on d21abb6)
1. **Suite by id against the 6g c6-c9 rows:** 5,991 passed, 127 failed, 23 skipped, 18 xfailed, 6,159 ids. New 0, gone 0,
   **changed outcome 0.** Passed splits as 5,990 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`).
   `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` failed, as on base: the
   known id()-reuse test artifact (sa-port-185, report a28c548), unedited. S's standing: S's gate is met except for the 46
   named stub failures, one cause.
2. **Fresh dev and fuzz, plus loop, zero, cert, scope and budget:** answers and state MATCH, `lra_diff` 0 and `stats_diff` 0
   everywhere, every Python-Python control MATCHes, traced against untraced end states MATCH on dev and fuzz. Answers: dev
   31cd0945c07f02a6, fuzz 173502b6ef285ad6, loop 09238b2537e54383, zero d9ed3534a2093027, cert 6a09c059eb266747, scope
   12e06b0586faee40, budget 35bc2c4a937bebc0. Rust made 0 Python solvers, reentry 0.
3. **Plants:** `ad-lra-kind-key` and `ad-lra-pair-swap` caught by the live comparison on dev, fuzz, cert, scope and zero;
   `ad-lra-flag-key` and `ad-lra-patch-guard` caught by test_lra_slot.py (they fire on every workload and MATCH: no workload
   flips `GENERIC_CONSTANTS` inside a query or patches `_memoized`); `ad-lra-slot-stale` void by construction (table below).
4. **Quiet handlers in the suite:** 39 rows in 2 tests, the same multiset as base: `_consistent` AttributeError 34 (`_ok`) and
   4 (`_rb_clauses`), the named needs-internals case; `Engine._build_context` "Already mutably borrowed" 1 in
   `test_protocol_on_fuzz` (the 46-stub cause). **engine.py:1906's catches (`ctx:caught`):** 1 in the suite (that row), 0 on
   all seven workloads; caught rows per id equal base (0 ids differ). TermFault 0. Every live and extra handler file has 0
   rows; the plant runs' only rows are `ad-lra-kind-key`'s own (`_consistent` ValueError, dev 1, fuzz 315: the plant's broken
   result shape, which the live comparison also catches). Suite plants: none run (SUITE_PLANTS=`zero` and every plant fired on
   dev or fuzz).
5. **Known differences in answers or read state:** none. Tests: 686 passed, 4 skipped (5c10d's files plus test_lra_slot.py and
   test_adapters_core.py); `relations_direct.py` exited 0.

### The bar's finding (run 1, b2339d0), fixed in d21abb6
Run 1 changed **14 suite outcomes passed -> failed** (test_unevaluated_products.py's `test_repro_is_open` x8 and
`test_brute_force_definite_answers_hold`, test_ref_fuzz.py's `test_engine_agrees_with_reference[general-0, general-1,
inconsistent-1]`, test_invariants.py's `test_ci_stream_no_longer_finds_the_zero_i2_family`, test_sympy_api.py's
`test_unread_relation_is_a_free_atom[prop1-assum1]`), each a `TermFault: lra integer_form: TermRefuse: ...` (14 in
pytest.log); dev, fuzz and the five workloads all MATCHed. Smallest case: `ask(Q.eq(Mul(1/3, x, 3/x, evaluate=False), 1))`.
Cause: the table's `lra_integer_form` raises `TermRefuse` ("mul: factors share a base"). On lra_live's path `_rust`'s
`except Exception` lets it through (TermRefuse is a BaseException by design), so the query is refused and rerun on Python
(counted `refused:mul: factors share a base`). The slot's `Reader.fault` wrapped every error, TermRefuse included, into
lra_live's TermFault, so the query failed instead. **Fix:** `Reader.fault` passes non-`Exception` errors up unchanged
(adapters.rs). test_lra_slot.py gains two such queries; on the old build they fail with the bar's TermFault, and they pass on
d21abb6. Run 2's suite: 0 changed outcomes, TermFault 0. The live workloads didn't catch this because none of their queries
reaches a refusal inside `lra_integer_form` (refused 0 on all seven).

## Plants
| plant | what it breaks | caught by |
|---|---|---|
| ad-lra-kind-key (251) | memo key without the kind | bar: DIFFER on dev (1,418 fires), fuzz (41,888), cert, scope, zero; MATCH on budget (36), 0 on loop; test_lra_slot.py |
| ad-lra-slot-stale (252) | slot not replaced when the query changes | **void by construction** (below); bar: fires dev 1,135, fuzz 59,037, all MATCH |
| ad-lra-flag-key (253) | memo key without `GENERIC_CONSTANTS` | test_lra_slot.py (flag case); bar: fires everywhere (dev 5,475, fuzz 164,954) and MATCHes, since no workload flips the flag inside a query |
| ad-lra-patch-guard (254) | a patched `_memoized`/reader bypassed | test_lra_slot.py (patch case); bar: fires everywhere (dev 5,508, fuzz 164,954) and MATCHes, since no workload patches |
| ad-lra-pair-swap (255) | coefficients of the first two pairs swapped | bar: DIFFER on dev (450 fires), fuzz (47,256), cert, scope, zero; MATCH on budget (60); test_lra_slot.py |

**`ad-lra-slot-stale` is void by construction.** It fired 59,037 times on fuzz with answers and state MATCH
(`~/sa-rust-ids-work/sa-port-195/q2-stale`, d1d9728). Python's own memo (`_INTERPRETED`, lra_adapter.py :425-450) is shared
across queries and keyed by the atom and `GENERIC_CONSTANTS` only ("equal atoms linearise identically"), so the results are a
function of (atom, flag). A stale slot serves those same results, and a miss against the old table goes through `term_id` /
`ad:cbm_noid` to Python. The per-query slot is the state rule's scoping (cross-query memos under per-query ids), not an answer
path.

## Crossings and the group-D samples, before and after
`ad:cb_memoized` per pass: **dev 5,508 -> 33, fuzz 164,954 -> 0** (quick runs on orion, d1d9728; **the bar's rows at d21abb6 give the same: dev 33, fuzz 0**).
**5,508 to 33 is the first real drop in a crossing count in the state work** (planner, 9 Nov ~03:30).

Group-D C API samples on the LRA path, sa-port-146's method (sa-port-195's tools, `~/sa-rust-ids-work/sa-port-195/gd/`):
BEFORE rust-slice 9529850 (`run-9529850/SUMMARY.md`), AFTER f7ea3d3 (`run-f7ea3d3/SUMMARY.md`), both on pareto1 under a shared
lease with `--cpus 1`, dev x10 and fuzz x3. Sample totals differ between the runs (dev 10,364 / 23,460, fuzz 27,744 / 46,467:
the shared lease's load), so shares compare, not counts. **Counts and shares only, no timing.** Answer digests equal on every
row of both runs (dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6).

| | dev before | dev after | fuzz before | fuzz after |
|---|--:|--:|--:|--:|
| (a) C API from LRA Rust modules (adapters, term::py, term::lra_read) | 256 (2.5%) | 618 (2.6%) | 782 (2.8%) | 2,186 (4.7%) |
| ... of which with a `memoized` frame in the stack | 36 (0.3%) | 0 | 221 (0.8%) | 0 |
| (b) callbacks entered at `memoized` | 290 (2.8%) | 6 (0.0%) | 2,479 (8.9%) | 0 |
| (b') slot callbacks entered from adapters (`relation`, `term_id`, `scaffold`) | in (b) | 94 (0.4%) | in (b) | 495 (1.1%) |
| (c) SymPy called from Rust under `memoized` | 30 (0.3%) | 0 | 328 (1.2%) | 0 |
| (c') SymPy called from an LRA Rust module | 7 (0.1%) | 35 (0.1%) | 87 (0.3%) | 207 (0.4%) |
| **LRA path, (a)+(b)+(b')** | **5.3%** | **3.0%** | **11.7%** | **5.8%** |

The callbacks are gone; part of their cost came back as C API in adapters, mostly on fuzz (adapters 1.7% -> 3.7%: "other C"
331, unicode 228, attribute lookup 205, allocation 186, dict 179). Every slot call still does `getattr`s on the module
(`_memoized`, the reader by name, `GENERIC_CONSTANTS`) and on term_live's `_local.stack` and the query's `kept`, the guards
that keep a patch or a flag flip correct. A speed item for later (cache them per query), not a bar item.

## Readers: lra_adapter.py per query, by workload (the lra_adapter count ruling)
`pycalls.py` with `PYCALLS_FILE=satassume/theories/lra/lra_adapter.py`, Rust, f7ea3d3, orion
(`~/sa-rust-ids-work/sa-port-197/pyc/`). Calls filed by the query they ran under.

| workload | queries | converted: `relation` | converted: other | kept:out-of-scope | no query (import) |
|---|--:|--:|--:|--:|--:|
| dev | 1,985 | 3,212 | 0 | 141 | 3 |
| fuzz | 3,000 | 100,449 | 0 | 0 | 3 |
| zero | 854 | 10,868 | 0 | 0 | 3 |
| loop | 420 | 0 | 0 | 0 | 3 |
| scope | 169 | 1,530 | `integer_form` 4 | 0 | 3 |
| budget | 28 | 60 | 0 | 0 | 3 |
| cert | 61 | 1,154 | 0 | 0 | 3 |

dev's 141 kept calls, by name: `_memoized` 33, `_lin` 24, `relation` 22, `_constraint` 22, `_closed` 10, `_side` 8,
`interpret` 7, `_linear` 7, `integer_form` 4, `order_sides` 4. The import-time three are `<module>`, `_Unhandled` and
`LRAAdapter` (class bodies).

Checked and reported as the ruling asks; **nothing claimed for the count before the planner applies the count rule:**
- **Per-query reach:** outside kept paths, two lra_adapter.py functions still run per query on Rust: `relation` (every
  workload but loop) and `integer_form`, 4 on scope. Those 4 are the slot's `ad:cbm_noid` fallback: term_live.py :717 sends a
  non-eq atom to relations.py `glue_objects`, whose `link_objects` (Rust) asks the adapter's `integer_form` for a side that
  has no input row in the query's table, so `_memoized` goes back to Python and lra_live's `integer_form` runs Python's
  (`on_python`, lra_live.py :169). Every other function is at 0 per query outside kept paths on all seven workloads.
- **`relation` as conversion:** it reads only the input relation's SymPy parts: `atom.function`, `atom.arguments` (and for
  `Q.is_true` its one argument) for an `AppliedPredicate`, otherwise `type(atom)`, `atom.lhs`, `atom.rhs`. It returns
  `(name, lhs, rhs)`. Rust (`Reader.rel`, adapters.rs) takes `name` as a string and uses `lhs`/`rhs` only to look up their
  ids in the query's `ids` dict. The results are built from the table's output and the query's `objects`, so nothing
  `relation` builds is kept or later read as engine state.
- **The 33 remaining `_memoized` calls (dev):** all 33 are kept, reason **out-of-scope** (convert.py's scope check: the query
  runs on Python, so `top_query` sees `kept` set and the slot counts them `ad:cbm_noquery`). No-query in the strict sense (no
  query on the stack at all): 0. fuzz, zero, loop, scope, budget, cert: 0 `_memoized` calls into lra_adapter.py.

## Which moved items are reached, and by what
The slot's counters per workload from the bar's Rust live rows (`adcounts.py`, `~/sa-rust-ids-work/sa-port-198/bar/counts-r2.txt`):

| workload | cb_memoized | cbm_noquery | cbm_noid | lra_native | lra_hit | lra_relation | lra_term_id_py | lra_scaffold | ctx:caught |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| dev | 33 | 33 | 0 | 5,475 | 1,749 | 3,212 | 1,825 | 20 | 0 |
| fuzz | 0 | 0 | 0 | 164,954 | 47,844 | 100,449 | 64,424 | 0 | 0 |
| zero | 0 | 0 | 0 | 18,671 | 5,849 | 10,868 | 2,410 | 0 | 0 |
| cert | 0 | 0 | 0 | 2,270 | 964 | 1,154 | 460 | 0 | 0 |
| scope | 4 | 0 | 4 | 2,468 | 709 | 1,530 | 1,324 | 0 | 0 |
| budget | 0 | 0 | 0 | 72 | 0 | 60 | 60 | 0 | 0 |
| loop | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

`ad:cbm_check`, `ad:cbm_patched` and `ad:cbm_off` are 0 on every workload (no `--check`, no patch, lra_live installed); the
plants show the guards behind them fire (`ad-lra-patch-guard` 164,954 on fuzz) and test_lra_slot.py's patch and flag cases
take them. **Reached:** the slot's native read (`LraAdapter.memoized` and `Reader.interpret`/`order_sides`/`integer_form`) by
dev, fuzz, zero, cert, scope and budget, its hits by all of those but budget; `Reader.obj`'s scaffold branch by dev only (20);
the `ad:cbm_noid` fallback by scope only (4, the `link_objects` case above); the kept path (`ad:cbm_noquery`) by dev only (33).
loop reaches none of it (no LRA atom). `Reader.fault`'s TermRefuse pass-through is reached by the suite (the 14 tests above)
and test_lra_slot.py's two refused queries, not by the seven workloads (refused 0 on each).

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
Out-of-scope: dev 24/1,985 (1.21%), every other workload 0; refused 0 everywhere; no other named exception. Equal to the 6g
c6-c9 bar on dev, fuzz, loop, zero, cert, scope and budget. **No share rose.**

## Fallbacks to Python inside ported code (planner's fallback-reporting ruling, 9 Nov ~06:35)
Counted from the bar's `*-rust.knowledge.json` (`fbcounts.py`, `~/sa-rust-ids-work/sa-port-198/bar/counts-r2.txt`):
`registry:python:NAME` is dispatch.rs:242's (a template with no rows spec runs as Python; its fires are counted at :355;
`_load` is :200's registry load, listed for completeness); `rows:python:NAME` is rows_tpl.rs's fallback to the kcl shells
(`wiring_fn`, :475 at d21abb6; :413 at the time of the ruling) together with the other `rows:python:` sites (`Integer`,
`const_value`, the named SymPy callback). **Every count is equal to the 6g c6-c9 bar's on all seven workloads**: this step moves
none of them.

| workload | dispatch.rs:242, `registry:python` | rows_tpl.rs, `rows:python` |
|---|---|---|
| dev | 126: `_load` 68, `_unary.<locals>.template` 31, `symbol_units` 15, `constant_units` 12 | 625: `Integer` 256, `const_value` 256, `_mul_factor_sets` 36, `_half_split` 20, `_quotient_templates` 19, `_bound_split` 18, `_imag_split` 11, `Add` 6, `Mul` 3 |
| fuzz | 38: `_load` 30, `constant_units` 6, `symbol_units` 2 | 378: `Integer` 136, `const_value` 136, `_bound_split` 34, `_half_split` 34, `_imag_split` 34, `_mul_factor_sets` 2, `_quotient_templates` 2 |
| zero | 43: `_load` 29, `symbol_units` 6, `_unary.<locals>.template` 5, `constant_units` 3 | 119: `Integer` 36, `const_value` 36, `_bound_split` 11, `_half_split` 11, `_imag_split` 11, `_mul_factor_sets` 7, `_quotient_templates` 7 |
| loop | 31: `_load` 20, `symbol_units` 6, `constant_units` 5 | 161: `Integer` 60, `const_value` 60, `Add` 6, `_bound_split` 6, `_half_split` 6, `_imag_split` 6, `_mul_factor_sets` 6, `_quotient_templates` 5, `Mul` 3, `_pow_bound_templates` 3 |
| cert | 24: `_load` 20, `symbol_units` 3, `constant_units` 1 | 208: `Integer` 104, `const_value` 104 |
| scope | 26: `_load` 26 | 0 |
| budget | 469: `symbol_units` 450, `_load` 19 | 80: `Integer` 40, `const_value` 40 |

Also `registry:kept` (a rows template on a kept query): dev 4 (`add_rows_templates` 2, `mul_rows_templates` 2), 0 elsewhere.

## State: each container this step touches (planner's state ruling, 8 Nov)
| container | decision | Python readers past this step | inventory row |
|---|---|---|---|
| the adapter's per-query slot (adapters.rs `LraQuery`: table, ids, objects, results) | **new, Rust-native from the start**; replaces lra_live's per-call reads through Python; dropped when the query changes | none in engine or wiring; test-only export `ad_lra_export` | tsv "state: LraAdapter slot" (new) |
| lra_live's per-table memo (term/lra_read.rs, inside the table) | unchanged (Rust-native, per query) | none | as 6-series rows |
| `lra_adapter._INTERPRETED` (Python, cross-query) | **unchanged**: since lra_live a converted query neither reads nor writes it (lra_live.py :192-196); kept queries and the pure-Python path keep it | `_memoized` (kept and pure-Python paths), tests/test_invariant_repros.py :80, test_term_live.py :141, satassume/state/memos.py :201 | tsv row 768 notes |

**Switch digest:** test_lra_slot.py's export at f7ea3d3: 1,484 entries, each equal to lra_live's own function on the same
query; slot digest a2fa4c14a0805a07 equal to lra_live's (also at d1d9728), **and again at d21abb6** with the two refused
queries added (1,484 entries: a refused query leaves none). The bar's live state comparison MATCHes on all seven workloads
(`lra_diff`, `end_diff`, `stats_diff` 0).

## Owed-list additions
- The slot's per-call `getattr` guards (`_memoized`, the reader, `GENERIC_CONSTANTS`, `_local.stack`, `kept`): a speed item,
  cache them per query.
- `ad-lra-flag-key` and `ad-lra-patch-guard` are caught only by test_lra_slot.py: no workload flips the flag inside a query or
  patches `_memoized`.

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

Also not run:
- the full suite under any plant (SUITE_PLANTS was `zero`, and all five fired on dev or fuzz);
- the group-D samples on d21abb6: they are from f7ea3d3; d21abb6 differs from it only in `Reader.fault`'s error path and the
  rebase onto the 6g stack, which the LRA path doesn't run differently on dev or fuzz (refused 0, counts above equal).

Other notes:
- S's standing: S's gate is met except for the 46 named stub failures, one cause.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and
  the boundary suite column wasn't run.
- **Speed not measured.** The group-D shares above are samples, not timing.
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals.
- `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`: the known id()-reuse test
  artifact (sa-port-185, report a28c548), unedited.
- `test_lra_exhaustion.py::test_split_beyond_the_certificate_bound_counts_as_exhausted` fails on Rust, as on base (not changed).
- test_term_live.py's 2 failures (`_Mark` has no `facts`) are on base 9529850 too.
- lra_adapter.py's count: **nothing claimed**; the three checks above are for the planner's count rule.
