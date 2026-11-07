# Step 5b: the id-to-term link and C2a (issue 323)

Tested source b455018, rust-slice bfac870 underneath, pareto1, x86-64, `-n 8`, `PYTHONHASHSEED=0`. Rows: pareto1 `~/sp19/sa-rust-ids-work/sa-port-87`, suite copy on orion `~/sa-rust-ids-work/sa-port-87/suite-rows`. Landed source adds one test case and this report, no code the runs execute.

## What moved
- **The link**, `relations_core.rs` `term_of`: object to the current query's term id. It resolves the object passed through `term_live.term_id`, creates no node, ticks no `join`, reads no row. The memo is on the query's table, key `(session serial, node)`, hit only if it holds that same object, positive answers only. None goes to Python's own function.
- **C2a**, all six methods: `_closed_extended_real`, `_order_sides`, `_order_infinite`, `_trichotomy`, `_mention_number`, `_link_integer`. `Session.ensure`, discovery, `_atom_var`, `_note_sides`, `_atom_selector`, `_add_role`, `_fresh`, `_guard` and `_tsource` stay Python and are called back.
- **No plan deleted.** `_eq_links` and `_eq_infinity` are called from `process` and `_interpret`, and neither moved. Term to node isn't needed until C2b.
- **Modules:** none newly counts whole. `relations.py` stays partial until C2b, C2c and 5c. `compile.py` is unchanged and can't count whole yet.

## The bar
1. **Suite by id against the base:** 5,960 passed, 124 failed, 23 skipped, 18 xfailed, 6,125 ids, no new id, 0 changed outcomes. Passed splits as 5,959 with no firing and 1 with a firing. S's standing: its gate is met except for the 46 named stub failures, one cause.
2. **Fresh dev and fuzz:** answers and state MATCH, four comparisons each, including the end states of the untraced runs. Python against Python is the control, also MATCH.
3. **Planted bugs**, each against this run's Python:

| plant | workload | fired | result |
|---|---|--:|---|
| `drop-order-sides` | dev | 300 | DIFFER, caught |
| `drop-order-infinite` | dev | 257 | DIFFER, caught |
| `drop-trichotomy` | fuzz | 72 | DIFFER, caught |
| `drop-trichotomy` | dev | 0 | MATCH, void: dev never reaches this clause |
| `link-none` | dev | 1,168 | MATCH, as the ruling needs |
| `link-none` | fuzz | 37,836 | MATCH, as the ruling needs |

4. **Quiet handlers, suite:** 39 rows in 2 tests, the same multiset as sa-port-84's rows by test, site, type and text. `test_ci_stream_reports_only_what_replays` passed: `_consistent` AttributeError, `_ok` 34, `_rb_clauses` 4, the named needs-internals case. `test_protocol_on_fuzz` failed: `Engine._build_context` "Already mutably borrowed" 1, the 46-stub cause. That is the 1 catch at the complete-check handler. No other firing. `TermFault`: 0 on the suite.
5. **Known differences in answers or read state:** none on dev and fuzz.

Dev and fuzz handler files: dev: 1 file(s), 0 rows;fuzz: 1 file(s), 0 rows.

## The first suite run failed, and why
The first run, 66734ec, had 54 new failures, all `TermFault: 'VarTable' object has no attribute 'core'`. `satassume/ref.py:219` keeps Python's `VarTable` under `Relations`, and my install sent those sessions to Rust. Fixed by dispatching on `isinstance(table, TableView)`, as `_rust_call` already does for the compiler; `test_relations_core.py` pins it. So the reference still runs Python's methods. None of the 54 was quiet, which also shows the fault path fires.

## Reach
| counter | dev | fuzz | suite |
|---|--:|--:|--:|
| `link:resolved` | 548 | 13,513 | 56,047 |
| `link:hit` | 620 | 24,323 | 70,385 |
| `link:no_node` | 191 | 6,230 | 23,072 |
| `link:no_table` | 0 | 0 | 20,263 |
| `link:second` | 0 | 0 | 105 |
| `link:none` | 0 | 0 | 0 |
| `rel:closed_extended_real` | 548 | 11,092 | 49,283 |
| `rel:order_sides` | 274 | 5,546 | 24,659 |
| `rel:order_infinite` | 427 | 16,651 | 67,995 |
| `rel:trichotomy` | 975 | 23,664 | 180,620 |
| `rel:mention_number` | 112 | 342 | 2,265 |
| `rel:link_integer` | 375 | 9,405 | 76,925 |

**What these comparisons don't reach:**
- **`link:none` never fires naturally on dev, fuzz or the suite.** The None path runs only under the `link-none` plant and in the unit tests. In particular, a join's other-class object reaching the link happens only in `test_join_second_object_resolves_on_its_own`.
- **The `Undecided` return** in `_order_infinite` has no counter, so its reach on the workloads is unknown. It's pinned by one case in `test_relations_core.py`, with `sign` forced to raise, run on orion only.
- **`_closed_extended_real`, `_mention_number` and `_link_integer` have no clause-drop plant.** Their evidence is the MATCH and the counters above.
- **Neither dev nor fuzz reaches `compile`'s `Or` arm**, carried from 5a. Not measured again.

## Joins, carried from the first item
1,041 joins in 19 tests, all `f(x)` shape, on one run (`port-5b-joins.md`). This suite run had 187, and the count follows what a worker ran earlier; that is stated, not fully explained. The link resolves the object passed, so a join's first object can't decide what it reads: the test pins this in both visit orders, with the other class answering None.

## Changes worth a reader's attention
- A Rational side now reaches `term_id` where Python's method stopped at `is_Rational`, so it may add a number row to the table. Nothing moved on dev or fuzz.
- `_closed_extended_real` is one Python frame less on the way to `Engine.is_`, so the recursion limit falls a frame later on that path. `test_session_limits.py`, 242 passed on orion at 66734ec; `session.rs` hasn't changed since.
- **Plants bypassed:** `var-off` lives on Python's `_var`, and `is-number-false` and `SLICE_TERM_CHECK` on `term_live`'s `_is_number`. The moved methods' direct reads go past them. Anyone rerunning those mutants needs to know.
- Shared files changed: `session.rs`, `term/py.rs` (the memo and four reads), `lib.rs`, `session_live.py`. `SLICE_REL=py` keeps the six methods on Python over the same core.

## Not run
Moved to "before any backend PR", none quoted as met: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control, the boundary rescore and suite column, the final drop score and its lost rows, the suite split with Python's counter, `order:_rows`' evidence (not caught meanwhile), the `_forms` guard test, history and seed reruns, forced moves, the native path, timing.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run.
- `term_discard.py` wasn't rerun. None of the moved methods is among its sites.
- `link-none` wasn't run on the suite. The ruling's test is dev and fuzz.
- **Speed not measured.** Every link call crosses to Python for `current()` and hashes the object for its node, even on a memo hit, so the memo saves `term_id` only. If the core's crossing cost matters, this is the first place to look.
- The public-API `test_incremental_matches_fresh` family is still owed, due by 5c.
- Fuzz history for PR 328 and the censuses on the base stay open, so section 8's limits still stand.
- The `_n_conflicts` view in `rust_plugin.py` isn't a port: a test-plugin shim, with the 64 tests it moved.
