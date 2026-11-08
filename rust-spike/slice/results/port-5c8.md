# Step 5c8: sympy_api's relevance rows on Rust (issue 323)

## What moved
- **The 16 port rows of sympy_api.py** (port-ownership.tsv 539-554; sa-port-166, -168, -170, -171), in
  `solver_rs/src/relevance.rs`: `_const_base`, `_const_free`, `_closed_keys`, `_expr_keys`, `_arg_keys`, `_keys`,
  `_keys_rel`, `_bool_keys`, `_sides_keys`, `_Split` (class, `__init__`, `part`), `_relevant`, `_vocab_blocks`,
  `_part_consistent` and `_consistent`. Pyfunctions `rv_relevant` :773, `rv_keys_rel` :778, `rv_keys` :784,
  `rv_const_free` :793, `rv_vocab_blocks` :799, `rv_part_consistent` :804, `rv_consistent` :809, and the `Split` class.
- **Wiring:** `session_live.py` `_install_relevance` sets the module names Python calls (`_RELEVANCE_NAMES`: `_relevant`,
  `_keys`, `_keys_rel`, `_const_free`, `_vocab_blocks`, `_part_consistent`, `_consistent`, `_Split`) to the Rust ones.
  `SLICE_RELEVANCE=py` puts Python's back. The engine's only Python caller is `_ask_general` (sympy_api.py :579, conversion),
  which calls `_relevant`. The other key helpers stay as module names only for Python's `_keys_rel`, which is the deep
  fallback for a Boolean deeper than relevance.rs's DEPTH (`rv:py_deep`, 0 on every workload).
- **Callbacks into conversion and other owners:** `_formula` and `_applied_category`/`_is_matrix_predicate` (conversion),
  `Engine.verdict` (5c10) and `theory_scope` (Rust). Reads of input terms are lazy conversion reads.
- **`_consistent`'s handler (5c8 ruling):** Rust catches exactly what Python's `except Exception: return False` catches,
  from the same callbacks, gives the same quiet False and counts it (`rv:consistent_caught`). A BaseException
  (`TermFault`/`KnowledgeFault`) goes up on both. `handler_count.py` :40-54 writes Rust's catches as rows under Python's
  site name (`rust_handled`), so the bar's handler item covers them.
- **Counters** (session.rs): `rv:*` 179-199 (NAMES/COUNTS 200). **Plants** (relations_core.rs): 124-139, the 16 named in
  `_RELEVANCE_PLANTS`.
- **Test fix after the first bar:** `test_relevance_core.py` installed Rust at import, so collecting it left Rust installed
  for the other files in the same pytest process (the first bar's tests phase: 8 failed). 256e294 moves the install into a
  module-scoped fixture that undoes it.

## SHAs
**Tested: fece4c7 for the suite, live, plants and extra phases; 256e294 for build, tests and sum.** Both are port/5c8 on
origin/port/stack-c2-elemnew **f1e4a74** (the stack's tested source, per the landing order). Between fece4c7 and 256e294
the only guarded file is `rust-spike/slice/test_relevance_core.py`, which the suite, live, plants and extra phases don't
run, so under the rebase rule those phases stand. The rest of that diff is results/ and handoffs.
Rows on pareto1: `~/sp19/sa-rust-ids-work/sa-port-170/bar-5c8/` (fece4c7, all phases) and
`~/sp19/sa-rust-ids-work/sa-port-171/bar-5c8t/` (256e294: build, tests, sum; the fece4c7 rows copied in, with
`sum-fece4c7.txt` and `tests-fece4c7.txt` kept). `.so` sha256 on fece4c7: da93a769…. Base suite rows: 5c7b's
(`sa-port-158/bar-5c7b/suite`), and S1's (`sa-port-167/bar-S1/suite`, the stack's f1e4a74) in `bar-5c8t/sum-vs-S1.txt`,
so the stack's own changes aren't counted as 5c8's.
**Landed:** the commit carrying this file, on rust-slice a2dc947 (the stack, landed from tested f1e4a74 unchanged). Between
256e294 and it there is only this report and the rebased results. **Incoming diff** (f1e4a74..a2dc947): HANDOFF-sa-port-167.md,
results/port-6g.md, results/port-elemnew.md, and one line each in results/port-ownership.md and .tsv (Element._new's
owner text). None of it is guarded source, so the bar stands on the landing source.

## The bar (sa-port-170/bar-5c8 on fece4c7, tests rerun on 256e294)
1. **Suite by id against 5c7b's rows and against S1's (f1e4a74):** 5,992 passed, 126 failed, 23 skipped, 18 xfailed,
   6,159 ids. New 0, gone 0, changed outcome 0 against each. Passed splits as 5,991 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`).
   S's standing: S's gate is met except for the 46 named stub failures, one cause.
2. **Fresh dev and fuzz, plus loop, zero and cert:** answers and state MATCH, and every control MATCHes. Answers are
   unchanged: dev 31cd0945c07f02a6 (1,985 q), fuzz 173502b6ef285ad6 (3,000 q), loop 09238b2537e54383 (420 q), zero
   d9ed3534a2093027 (854 q), cert 6a09c059eb266747 (61 q). The Rust runs made 0 Python solvers.
3. **Plants:** 11 of the 15 run are caught by the comparison (table below), and the raising plant `consistent-fault`
   comes out loud.
4. **Quiet handlers in the suite:** 39 rows in 2 tests, the same multiset as 5c7b's and as S1's:
   - `_consistent` AttributeError: 34 on `_ok` and 4 on `_rb_clauses` (the named needs-internals case);
   - `Engine._build_context` "Already mutably borrowed": 1, in `test_protocol_on_fuzz` (the 46-stub cause).

   The `caught` rows per id match base. **Quiet catches at engine.py:1906: 1**, in the suite, as on base. The 15 live and
   extra handler files and the 30 plant handler files have 0 rows. TermFault 0 in the suite log.
5. **Known differences in answers or read state:** none. Tests on 256e294: 574 passed, 0 failed (the 12 files of 5c7's list, test_elem_pyclass.py and
   test_relevance_core.py; on fece4c7 it was 8 failed, 566 passed, from the import-time install). The .so's sha256 is the
   same on both SHAs (da93a769…). `relations_direct.py` exited 0.

### `_consistent`'s firings, Rust next to Python (5c8 ruling)
| rows | `_ok` AttributeError | `_rb_clauses` AttributeError | other |
|---|--:|--:|--:|
| Python's `_consistent`, 5c7b's suite rows (base) | 34 | 4 | 0 |
| Rust's `_consistent`, this bar's suite rows | 34 | 4 | 0 |
| Same test alone on orion, `SLICE_RELEVANCE=py` / `rust` (`~/sa-rust-ids-work/sa-port-171/hc/`) | 34 / 34 | 4 / 4 | 0 / 0 |

All in `tests/test_invariants.py::test_ci_stream_reports_only_what_replays`. Live and extra: 0 on both
(`rv:consistent_caught` 0 on every workload).

**Handler conditions:**
- **Same catches as Python:** `test_relevance_core.py::test_same_catches` (4 cases): an Exception raised by `Engine.verdict` or
  `_formula` gives False on both, and Rust counts `rv:consistent_caught` once. A BaseException goes up on both. Pass.
- **Rust faults stay loud:** the `consistent-fault` plant raises a TermFault inside relevance.rs's `_consistent` body.
  **It doesn't come back as a quiet answer:** `test_fault_plant_is_loud` gets the TermFault from a direct call, and on
  live.py (sa-port-168 `pl/`) the TermFault comes up through `_ask_general` and stops the run on dev (q5), fuzz and zero.
  It isn't in the bar's PLANTS because it ends the run.
- **Firing counts:** the table above.

## Plants (fired; D = DIFFER on answers or state; the bar's plants and extra phases, fece4c7)
| plant | row | dev | fuzz | loop | zero | cert | caught by |
|---|---|--:|--:|--:|--:|--:|---|
| const-base-no-pow | `_const_base` | 1 | 0 | 0 | 0 | 0 | **void** |
| const-free-no-mul | `_const_free` | 6 | 1 D | 0 | 1 | 11 | fuzz (state: session count, end, stream) |
| closed-keys-no-undef | `_closed_keys` | 0 | 0 | 0 | 13 D | 0 | zero (msg) |
| expr-keys-closed-skip | `_expr_keys` | 579 | 11,093 | 1 | 185 D | 10 | zero (state) |
| arg-keys-no-closed | `_arg_keys` | 13 D | 0 | 0 | 2 D | 0 | dev, zero |
| keys-empty | `_keys` | 0 | 0 | 0 | 0 | 0 | **void** |
| keys-rel-no-flag | `_keys_rel` | 53 | 2,744 | 0 | 28 | 82 | **void** |
| bool-keys-opaque-in | `_bool_keys` | 6 D | 0 | 0 | 0 | 0 | dev (state: session count) |
| sides-keys-first-only | `_sides_keys` | 53 D | 2,744 D | 0 | 28 | 82 | dev, fuzz |
| split-no-merge | `_Split.__init__` | 169 D | 3,419 D | 3 | 252 D | 30 | dev, fuzz, zero |
| split-part-first | `_Split.part` | 36 D | 44 D | 0 | 13 D | 0 | dev, fuzz, zero (answers) |
| relevant-assume-consistent | `_relevant` | 60 D | 315 D | 0 | 23 D | 0 | dev, fuzz, zero |
| vocab-no-derived | `_vocab_blocks` | 0 | 0 | 230 | 0 | 0 | **void** |
| part-consistent-true | `_part_consistent` | 104 D | 0 | 0 | 25 D | 0 | dev, zero (state) |
| consistent-ignore-verdict | `_consistent` | 64 | 315 D | 0 | 25 D | 0 | fuzz (answers), zero |
| **consistent-fault** | `_consistent` (raises inside the ported body) | **loud** | **loud** | - | **loud** | - | **TermFault, never a quiet answer** |

**Void, with reasons:**
- **keys-empty:** `rv_keys` has test-only callers (test_memos.py :137/:143, test_relevance.py :312,
  test_relevance_core.py). The engine never calls it, so no workload can fire it.
- **keys-rel-no-flag:** `rel` feeds `_Split.relational`. Under the default `RELATIONAL = "components"` (sympy_api :1070)
  it only picks whole-set `_consistent` against per-component checks, and `prel` is read only by the "whole" ablation
  (:960). Components share no key, and the glue case goes to the whole set anyway (:987), so the verdicts agree.
- **vocab-no-derived:** it skips `_DERIVED_CLASSES` (Add/Mul/Pow). It changes an answer only if a vocabulary class is
  registered for one of those, or a base of one, while no subterm is an instance. loop registers none like that.
- **const-base-no-pow:** fires once on dev and changes nothing. **Owed:** a workload query shaped like
  `ask(Q.positive(x), Q.gt(x, sqrt(2)) & Q.gt(y, sqrt(2)))`, where the plant makes sqrt(2) a key and merges components.

## Reached (rv:* counters on the Rust run, one pass each, sa-port-168 `wl/`, --check plain)
| counter | dev | fuzz | loop | scope | zero | cert | budget |
|---|--:|--:|--:|--:|--:|--:|--:|
| `rv:relevant` | 989 | 2,938 | 244 | 166 | 740 | 61 | 19 |
| `rv:split_new` | 83 | 1,766 | 10 | 27 | 63 | 31 | 14 |
| `rv:keys_rel` | 1,180 | 7,222 | 13 | 39 | 933 | 117 | 93 |
| `rv:keys_miss` | 454 | 3,431 | 12 | 25 | 97 | 84 | 61 |
| `rv:const_free_miss` | 10 | 1 | 0 | 0 | 3 | 26 | 0 |
| `rv:vocab_blocks` | **0** | **0** | 10 | 0 | 0 | 0 | 0 |
| `rv:part_consistent` | 104 | 0 | 0 | 0 | 25 | 0 | 0 |
| `rv:consistent` | 64 | 315 | 0 | 0 | 25 | 0 | 0 |
| `rv:consistent_caught` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `rv:br_verdict` / `br_parts` | 2 / 58 | 315 / 0 | 0 | 0 | 11 / 12 | 0 | 0 |
| `rv:br_glue`, `br_unsupported`, `py_deep` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `rv:cb_formula` / `cb_verdict` | 122 / 64 | 315 / 315 | 0 | 0 | 37 / 25 | 0 | 0 |
| `rv:cb_theory_scope` / `cb_ext` | 58 / 0 | 0 | 0 / 10 | 0 | 12 / 0 | 0 | 0 |
| `rv:cb_category` / `cb_memo` | 400 / 2,552 | 687 / 11,934 | 12 / 267 | 21 / 232 | 94 / 1,786 | 2 / 290 | 77 / 126 |

Answers in that run equal 5c7's hashes on all seven (scope 12e06b0586faee40, budget 35bc2c4a937bebc0), with 0 Python
solvers made.

**Reach per moved item:**
- `_relevant`, `_Split`, `_Split.__init__`, `_Split.part`, `_keys_rel` and, through `keys_rel`'s misses, `_const_base`,
  `_closed_keys`, `_expr_keys`, `_arg_keys`, `_bool_keys` and `_sides_keys`: reached on every workload.
- `_const_free`: dev, fuzz, zero and cert.
- `_part_consistent`: dev and zero.
- `_consistent`: dev, fuzz and zero. Its handler path (`consistent_caught`): the suite only (38 rows, above) and
  test_relevance_core.
- `_vocab_blocks`: **loop only** (0 on dev and fuzz). That's why loop is in this bar's extra phase.
- `_keys`: **tests only** (test-only entry). No workload reaches it.

**Python calls per query into sympy_api.py (5c8 count ruling, condition 2):** `pycalls.py` (sys.monitoring PY_START on
sympy_api.py's code objects, classed by PORT-INVENTORY's sympy_api lists), fece4c7, Rust, `~/sa-rust-ids-work/sa-port-170/pyc/`
(orion). Outside the ruled-conversion rows there are only `<module>` 1 and the `_Split` class body 1, both at import, so
**0 per query** on dev, fuzz, zero, loop, scope, budget and cert. Conversion calls per query: dev 13.3, fuzz 29.8, zero
22.5, loop 14.6, scope 19.0, budget 51.5, cert 26.7.

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
Share of all queries kept per reason, on the Rust run. Base is 5c7b's bar; S1's gives the same (S1 has loop, not cert).

| workload | queries | out-of-scope | refused | other named exceptions | base |
|---|--:|--:|--:|--:|---|
| dev | 1,985 | 24 (1.21%) | 0 | 0 | the same |
| fuzz | 3,000 | 0 | 0 | 0 | the same |
| zero | 854 | 0 | 0 | 0 | the same |
| cert | 61 | 0 | 0 | 0 | the same |
| loop | 420 | 0 | 0 | 0 | not in 5c7b's extra phase; S1's: the same |

**No share rose.**

## State: each container 5c8's rows touch (planner's state ruling, 8 Nov)
5c8 removes no container's last non-test Python reader (sa-port-147, INVENTORY-state.md). So **nothing moves to
Rust-native state at 5c8, and no digest switch is owed.**

| container | decision | named readers past 5c8 | moves in | inventory row |
|---|---|---|---|---|
| `Engine.splits` | kept | relevance.rs through its methods (Rust over the Python memo); `_drop_set_memos`/`_settings_changed` (5c9); term_live `_Mark` | 5c9 | port-ownership.tsv 821; INVENTORY-state.md :193 |
| `Engine.stats` | kept | relevance.rs `_consistent` increments it as Python does; sympy_api `_ask_general` and public `ask` write it | never by a planned step (view plus a write path, or with the conversion pass) | tsv 822; INVENTORY-state.md :199 |
| `sympy_api._KEYS` | kept | relevance.rs `keys_rel` through its table methods; Python `_keys_rel` deep fallback; state/memos PROCESS registry (5c9); term_live `_Mark`; tests test_memos.py :136-143, test_relevance.py :35, test_term_live.py :324; tools/relevance_fuzz.py :181 | stays | tsv 823; INVENTORY-state.md :169 |
| `sympy_api._CONST` | kept | as `_KEYS` (relevance.rs `const_free`) | stays | tsv 824 |

The relevance memo stays with its listed step: sa-port-147's inventory doesn't put its last engine reader in 5c8. The TSV
shows the 16 rows as "landed 5c8 (port-5c8.md)", Rust (539-554), and port-ownership.md :99 is updated.

## Module count (5c8 count ruling)
**14 of 32.** All three conditions of the 5c8 count ruling hold: the bar is clean (above), condition 2 holds (0 Python
calls per query into sympy_api.py outside the ruled-conversion rows, on all seven workloads), and the 5c8 handler
conditions hold (same catches, the raising plant loud, `_consistent`'s firings Rust 34 + 4 next to Python's 34 + 4).

Footnote, word for word from the ruling: 'sympy_api.py: port rows done (relevance layer). The entry, `to_formula`, the
answer memo and the scope check are the input layer, which stays Python by Tilo's design and runs per query.'

In STATUS's named list: sympy_api.py, 'split module, port part complete'.

## Owed-list additions
- `const-base-no-pow` has no catch: a workload query shaped like `ask(Q.positive(x), Q.gt(x, sqrt(2)) & Q.gt(y, sqrt(2)))`.
- `vocab-no-derived` has no catch: a vocabulary class registered for Add/Mul/Pow (or a base of one) with no subterm that is
  an instance.
- `keys-rel-no-flag` can only be caught under the "whole" ablation (`RELATIONAL`), which isn't a landing configuration.
- `rv_keys` (`_keys`) is reached only by tests.

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
- the suite under any 5c8 plant (SUITE_PLANTS empty);
- `consistent-fault` in the bar's plants phase: it ends the run by design (loud), shown in test_relevance_core and sa-port-168's `pl/`;
- the scope and budget workloads in this bar's extra phase: their answers equal 5c7's hashes in sa-port-168's reach run, but
  they weren't compared Python against Rust here;
- the suite, live, plants and extra phases on 256e294: its only guarded change is test_relevance_core.py, which none of them run.

Other notes:
- S's standing: S's gate is met except for the 46 named stub failures, one cause.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and
  the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals.
  This step doesn't touch it.
