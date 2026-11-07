# Component 4, slice C1: term work through ids (issue 323)

**Tested source `6533bdb`, on `rust-slice` db697fc (slice D), on pareto1 (x86-64). Landed as the commit that adds this report, whose only change from the tested source is this file.** Output: `pareto1:~/sa-rust-ids-work/sa-port-74/l3`. Base column: db697fc, in the same job.

**Modules that now run whole because of this: 0 of 32. Slice C moves term work; it makes no module whole.** `relations.py`, `euf_adapter.py` and `scope.py` are all partial. Item 6 (`relations.py:777-1921`, about 1,100 lines in 36 methods) didn't fit and isn't here. It can't make `relations.py` whole either while `Session` is Python: `P`, `And`, `Args`, the session and every `s.var` key hold SymPy objects until component 5, so a "clause over ids" is a plan Python runs. The architect has decided that C2 goes with component 5, as 5b.

**One bug found and fixed on the way, in code already on `rust-slice`: see "A discard left entries in Python".**

## What moved

- `relation_atom`'s order relations (lt, le, gt, ge), `_ext_atoms`, `_eq_infinity`, and `_eq_links`' clauses as plans.
- `_is_number`, `scope.affine_pair`, `_under_apps`, `zero_twin`, and EUF's `structural`, `interned` and `_structural_subterms`.
- The glue's term work (`glue_objects`), on ids. Its difference goes through scaffolding, counted below.
- `mul`: a rational coefficient on a single factor whose class has its own `as_base_exp`.

**What this split changes from the planner's list:** C became C1 (items 1-5) and C2 (item 6, moved to 5b).

**Shared files touched:** `term_discard.py` (`emptied` counted apart), `fresh.py` (`--term-check`), `convert.py` and the crate's `term/py.rs`, `term/table.rs`, `term/algebra.rs`, `term/relations.rs`. `satassume/`, `knowledge_live.py`, `lra_live.py` and `_rows_runtime.py` aren't touched, **so the rows-kept guard ruling doesn't apply.**

## The bar

| # | What | Result |
|---|---|---|
| 1 | Suite by id, Rust, `-n 6` | **5,960 / 77 / 46, plus the 1 failure from 1b.** 124 failed, 23 skipped, 18 xfailed. 6,125 ids, none added or gone, **0 outcomes changed** against the base. Same with `SLICE_TERM_CHECK=1` |
| 2 | Fresh dev 1,985 and fuzz 3,000 | **MATCH.** Python against Rust with terms: 0 answers, 0 digests. Same with `--lra` (C and D together), check mode, and the discard run. Live: 16 `MATCH` lines, 0 `DIFFER` |
| 3 | Planted bugs through that comparison | **Caught**, below. `termwise-true` is caught at budget 5 and 2 |
| 4 | Quiet firings on Rust, that suite run | **39 rows, 2 tests, both already named.** 0 findings |
| 5 | Known differences | None in answers or read state on these comparisons. One difference in calls, under "Limits" |

**The 3 numbers:** `suite_report.py` ran with no Python rows, so "failing the same way on pure Python 0" isn't evidence, and the 1 stays named by id from `port-4a.md`: `test_lra_exhaustion.py::test_split_beyond_the_certificate_bound_counts_as_exhausted`.

**S's standing:** S's gate is met except for the 46 named stub failures, one cause. They stay listed in number 3, and the crate is unchanged for them. The `_n_conflicts` view in `rust_plugin.py` isn't a port: it's a test-plugin shim, with the 64 tests it moved.

**Passed, split per the planner's rule: 5,959 with no firing, 1 with a firing on Rust,** of 5,960. Python's counter wasn't run on this source, so "doesn't fire on Python" for that 1 comes from earlier reports.

**What differs between the suite columns:** head runs `-p discard_real`, because base has no such file. That plugin only reads counts. Neither sets `SLICE_KNOWLEDGE=atoms`, so atoms are off on both. D's mode is on in both, by `rust_plugin.py`'s default.

## What C1 was tested on, and the incoming diff

- **Tested on:** `6533bdb` on db697fc. That's the rebased source, so slice D is underneath it.
- **Incoming diff:** ce19962..db697fc, slice D, 19 files. It changes code the run executes, including `convert.py`, `term_live.py` and the crate, so **the planner's rule needed a full rerun, and this is that rerun.**
- **Conflicts:** `convert.py`, `fresh.py`, `term/py.rs`, `term/table.rs`. **One was semantic:** both slices had taken flag bit `1 << 16`. D keeps its values, and C's `PLAIN_ATOMS` moved to `1 << 19` in both Rust and Python. The rest kept both sides.
- **Earlier runs:** `l1` is on a858030 (before the fix). `l2` is on a44fac2 (the fix on ce19962).
- **`l2` is partly void, my error:** I started `l3` while `l2` was running, and they share clones, so `l3`'s setup rebuilt under `l2`. I stopped `l2` and marked it `VOID`. Only its suite line and its two discard runs are used here. They finished before `l3`'s setup started, by the times on their files, which have minute resolution.

## A discard left entries in Python

The planner asked for the state check on real refusals, because C changes what a discard must undo. On a858030, with rollback on, it reported 10 of 19 `left-something`, where zero was expected. There were two causes.

**1. A real gap: `_Mark` didn't undo growth inside `_INTERPRETED`.** That table is a `defaultdict(dict)`. Once its key exists, the run's entries go inside the value, and the outer length doesn't move. **This isn't from C: base ce19962 reproduces it the same way.**

- **Why planted refusals never showed it:** `fresh --discard` clears memos before each query, so the outer key is created during the run and popped whole. That's why slice B's 0 left of 4,985 didn't catch it.
- **What it can do:** an entry left there holds a `_CONSTANTS` index the rollback frees. With a hand-called rollback, `ask(x > log(5)/2, x < 1)` answers **False where the truth is open**, because the index now means `log(37)`.
- **What I didn't show: a wrong answer through a real refusal.** The refused query's second run re-registers the same constants straight away, which hides it. 32 shapes built from the suite's refusals (4 refused, 1 left entries) and 36 two-constant orders (all refused, 0 stale entries) all matched Python. That's a small search, so read it as "not reached", not "unreachable".
- **Fix:** `_Mark._note` also notes the values of a `defaultdict(dict)` table. It's the only such module-level table in the package.
- **Test:** `test_a_discard_leaves_nothing_inside_a_nested_memo`. With the old `_note` restored, it fails on this source with 20 entries where 10 are expected.

**2. Not a leak: `_KEYS`, `_FORMULAS` and `_CONST` emptied.** This is `_Mark`'s documented path: a table restamped or cleared during the run is emptied, which costs only recomputation for a memo. `check` now counts these as `emptied`, apart from `left-something`. I didn't look into why these tables restamp during those runs.

| Real refusals | Checked | Left something | Emptied | No-rollback control: left something |
|---|---:|---:|---:|---:|
| a858030, before the fix, 8 tests | 19 | **10** | counted as left | 16, with `_INTERPRETED` |
| a44fac2, the fix, C without D, 8 tests | 19 | **0** | 32 | 16, with `_INTERPRETED` 5 |
| **6533bdb, landing, C and D, 21 tests** | **345** | **0** | 52 | 342, without `_INTERPRETED` |

**Limit: the landing row doesn't exercise this fix.** With D on, `_INTERPRETED` shows no entries even with no rollback, because D's per-query memo takes its place on that path. The fix's evidence is the a44fac2 row and the test. It still matters with `SLICE_LRA_TERM=py`, and in anything that reaches Python's `_memoized` first. Planted refusals on the landing source: dev 1,985 and fuzz 3,000 refused, all clean, 0 answers, 0 digests.

**Slice D's report should be read with this in mind:** its "0 left" also comes from planted refusals, on the path with D's memo. I didn't rerun D's `lra` workload.

## Quiet firings

| Handler | Test | Type | Rows | Status |
|---|---|---|---:|---|
| `_consistent` | `test_invariants.py::test_ci_stream_reports_only_what_replays` | AttributeError, `_ok` 34 and `_rb_clauses` 4 | 38 | Named needs-internals case, passed |
| `Engine._build_context` | `test_transfer.py::test_protocol_on_fuzz` | RuntimeError, "Already mutably borrowed" | 1 | Named 46-stub cause, `tests/theory_harness.py:242`, failed |

- **`engine.py:1906`: 1 catch on the suite, that same stub row.** All catch rows are identical to the base's, by test, type and text. The other `caught` rows are `Uninterpreted`, which is re-raised and not quiet.
- **Fresh dev and fuzz recorded 0 at any handler on Rust**, with and without `--lra`. The one plant that fires it (`is-number-false`, 3 rows on fuzz) shows a firing would be seen.
- **The counters fire:** `quiet_fire.py` and `lazy_fire.py` exit 0 on this source.
- **`handler_count` still covers 2 of the 7 handlers.**
- **The handoff said slice C added no new handler site. That was wrong: it added one,** at `glue_objects` in `term_live.py`, over ids, for Python's `relations.py:2018`. It now counts as `caught:glue_objects:TYPE`: **0 on the suite and on fresh dev and fuzz.** `test_the_glue_handler_counts_what_it_catches` shows it fires on a planted `ValueError` and that a `TermRefuse` passes it.
- `_guarded` raises `TermFault`, a BaseException, so its wraps aren't quiet: `fault` is 0 on the suite.

## Planted bugs

Fresh, Python against Rust, answers / digests:

| Plant | Dev | Fuzz | Note |
|---|---|---|---|
| `le-swap` | 82 / 93 | 572 / 2,055 | Same through `--lra` |
| `no-ext` | 27 / 93 | 123 / 2,055 | |
| `is-number-false` | 0 / 169 | 13 / 2,947 | |
| `plan-drop` | 0 / 15 | 2 / 754 | |
| `plan-pred` | 0 / 15 | 2 / 754 | |
| `interned-reversed` | 0 / 5 | **0 / 0** | Reached on fuzz, no effect there. Why wasn't looked into |
| `affine-false` | **0 / 0** | 0 / 2 | Void on dev on the earlier tree: `affine_pair:True` 0 |

**In the direct comparison only, void on both fresh workloads:** `under-empty` (442 differs; on the earlier tree `under_apps:nonempty` was 0 on dev and fuzz) and `twin-one` (1,167). `linked-drop` was void on both on the earlier tree, because the engine never reads `linked_terms`. It wasn't rerun.

**Direct comparison:** `relations_direct.py`, seeds 1 and 2, about 3,900 cases each: 0 differs. All 9 plants were caught.

### `termwise-true`, on C's bar

| Budget | Dev | Fuzz, answers / digests | Reach on fuzz: `glue:termwise` (False) |
|---|---|---|---|
| 5 | 0 / 0 | **7 / 74** | 1,576 (1,476) |
| 2 | 0 / 0 | **0 / 3** | 1,516 (1,424) |

**Caught at both budgets, as the planner read it:** a wrong True changes cone weight, which matters near the budget. **Dev is void:** all 30 of its glue calls are True already, so the plant changes nothing there. Unplanted runs at these budgets: 0 answers, 0 digests on both workloads.

## Reach

Suite, on this source: `plan:_eq_links` 16,186, `plan:_eq_infinity` 1,167, `is_:_eq_infinity` 19, `under_apps:nonempty` 8,244, `zero_twin` 607, `affine_pair:True` 1,521, `glue:termwise` 2,744 (438 False), `term:rust:relation_atom` 379,812, `term:rust:_is_number` 1,126,309, `term:rust:structural` 677,642, `term:rust:interned` 139,592.

**The suite's MATCH says something about `_under_apps`,** which fresh dev and fuzz never reached with a nonempty result on the earlier tree.

## The `mul` line

**SymPy read:** the earlier note was half right. `core/expr.py:243` `__neg__` is a raw `Mul._from_args((-1, self))`, but `core/add.py:366` `Add.flatten` rebuilds through `Mul(c, s)`. So a correct `neg` alone wouldn't do, and `mul` did change.

| Refused with this reason | Base | Head |
|---|---:|---:|
| Suite, `class has its own as_base_exp` | **22 on 8 distinct queries** | **3 on 2** |
| Suite, all reasons | 363 | 345 |

- Slice B's 19 on 6 was on an earlier base, so this table's base is db697fc's own.
- **`mul: factors share a base` is 308 on both:** that's the refusal this line must keep. It is D's mode reaching it: it wasn't in slice B's counts.
- **Direct and shadow match on these forms:** `term_ids_direct`, 0 differs. Shadow dev and fuzz, 0 bad.
- **The direct refusal columns aren't before and after:** slice C changed `term_ids_direct.py`'s generator, so head and base ran different cases. Head's `own as_base_exp, and Mul changes the factor` is 238, against base's 896, and `key: power base not an input term` under `sub` is 2,529 against 236. I'd expect some of those to be terms now passing `mul` and refusing at the key, but I can't say how many from these columns.
- **A new refusal, safe:** `scaffold: rebuilt form differs from Rust`, 5 on direct, 0 on the suite and fresh. The check did its job. I didn't look at the 5 forms.
- `lra: a callback on a derived term` is 5 on head, 4 on base and 4 in check mode. I didn't look into it. No outcome moved.

## Scaffolding, must reach zero before any backend PR

Rebuilt terms per step:

| Step | Suite, base | Suite, head | Dev | Fuzz |
|---|---:|---:|---:|---:|
| `_eq_links` | 18,968 | 18,947 | 0 | 0 |
| `glue_objects` | 0 | **5,325** | 69 | 232 |
| `relation_atom` | 8 | 17 | 0 | 100 |
| `integer_form` | 112 | 112 | 0 | 0 |
| `order_sides` | 1 | 1 | 0 | 0 |
| **Total** | **19,089** | **24,402** | **69** | **332** |

**The count goes up, because moving the glue moves its `d = p - q` onto this path.** Mismatches: 0 on the suite and fresh.

## Limits

- **Atoms and formulas stay Python's**, as above, so "clauses over ids" means a plan Python runs.
- **`_is_number` is a wide wrapper.** It reaches `scope` and `engine`, but `ref.py` keeps its own binding. Its cost per call wasn't measured.
- `is_Rational` here is the class flag, where Python's `_structural_subterms` and `interned` test `isinstance(e, Rational)`. They'd differ only on a class that sets the flag without subclassing. Not tested.
- **`_under_apps` returns a set in a different insertion order.** Consumers checked by `rg` test membership. Not every path past `glue_atoms`' `cinfo` was read.
- `_under_apps`' fallback for a class with its own `atoms` has never been seen firing, so that path is untested.
- **`_intern` stays Python's.**
- **A difference in calls, no state moved as far as read:** a plan calls `s.var` once per clause, where Python's `_eq_infinity` calls it once. `Session.var` is get-or-allocate, so numbering holds. The recording sessions log allocations only, so they can't see this.
- **`_Mark`'s other limits stand,** from `port-4a.md`: overwrites of an existing key, in-place changes, SymPy's caches and `Dummy._count`. Nothing walks for other holders of a freed `_CONSTANTS` index, and that's where this bug was.

## Flake and load

- **`test_stock_term_plant_is_caught[finite-stock_finite]`:** 1 failure on the rebased tree on orion, Python's solver, `-n 3`, under load. It passed in all 6 `-n 2` runs on Rust's solver on each of head and base on pareto1, so those don't test the same combination. **Cause not found.** Sa-port-72 saw it fail 1 in 4.
- `test_performance_smoke_300_vars` passed on head, base and check mode.

## Not run

- **Moved to before any backend PR, not run:** the mutant 2, 5, 6, 7, 9 rerun and mutlive's control, the boundary rescore and suite column, the final drop score and its lost rows, the suite split with Python's counter, `order:_rows`' evidence (not caught meanwhile), the `_forms` guard test, history and seed reruns, forced moves, the native path, and timing.
- **The public-API version of `test_incremental_matches_fresh`:** not written. It's due during the engine port at the latest.
- **Slice D's `lra` workload and registry comparison weren't rerun on this source.** `--lra` ran on dev and fuzz only, and D's own report says those miss some of its sites.
- **`SLICE_KNOWLEDGE=atoms`:** not run with slice C.
- **Mutants 2, 5, 6, 7, 9 rest on the API fuzzer alone.** 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run.

## Tests

- On this source, `test_term_ids.py`, `test_term_live.py`, `test_lazy_reads.py`: 206 passed, 6 skipped on Python's solver; 207 passed, 5 skipped on Rust's.
- `test_lra_live.py` with those on orion: 234 passed, 5 skipped on Rust.
