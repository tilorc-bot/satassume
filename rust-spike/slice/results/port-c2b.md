# Step 5b, C2b: six Relations methods in Rust (issue 323)

Tested source a62bd61, on rust-slice 3f9ae3a, pareto1, x86-64, `-n 8`, `PYTHONHASHSEED=0` unless said. Rows: pareto1 `~/sp19/sa-rust-ids-work/sa-port-89`, copy on orion `~/sa-rust-ids-work/sa-port-89/rows`. Landed source adds this report, no code the runs execute.

## What moved
- `_interpret`, `_guard`, `_link`, `_bound`, `_fresh`, `selectors_of` are in `relations_core.rs` and call the Rust session directly. C2a's `_fresh` and `_guard` callbacks became direct.
- **`_eq_infinity` moved too**, because `_interpret` was its only caller. C1's plan for it is deleted from `term_live.py`, `term/py.rs` and `term/relations.rs`.
- **`_eq_links`' plan stays:** its caller is `process`, which is 5c.
- **Term to node still isn't needed:** every C2b method holds objects. It arrives with `_eq_links`' derived ids, so 5c.
- Stays Python, called back: `_adapter`, `_atom_var`, `_atom_selector`, `_add_role`, `_apply_role`, `_note_sides`, `_tsource`, `sympy_atom`, `_own_term`, `relation_atom`, the adapters, `Session.ensure`.
- **Modules: none newly counts whole.** `relations.py` keeps `process`, `_eq_links`, the discovery glue and all of C2c, so it stays partial until C2c and 5c. `compile.py` is unchanged.

## The bar
1. **Suite by id against 5b's rows:** 5,959 passed, 125 failed, 23 skipped, 18 xfailed, 6,125 ids, no new id, **1 changed outcome**, explained below. Passed splits as 5,958 with no firing and 1 with a firing. S's standing: its gate is met except for the 46 named stub failures, one cause. This new failure is a separate cause, not one of the 46.
2. **Fresh dev and fuzz:** answers and state MATCH, four comparisons each, including the end states of the untraced runs. Python against Python is the control, also MATCH.
3. **Planted bugs:** table below. Each moved method with a plant that fires is caught, except `_bound`, which no workload reaches.
4. **Quiet handlers, suite:** 39 rows in 2 tests, the same multiset as 5b's by where, site, type and text. `test_ci_stream_reports_only_what_replays` passed: `_consistent` AttributeError, `_ok` 34, `_rb_clauses` 4, the named needs-internals case. `test_protocol_on_fuzz` failed: `Engine._build_context` "Already mutably borrowed" 1, the 46-stub cause, and the 1 catch at the complete-check handler. No other firing. `TermFault`: 0 in the suite log. Dev and fuzz handler files: 0 rows.
5. **Known differences in answers or read state:** none on dev and fuzz. See the failure below for the one thing a test can see.

## The one changed outcome
`tests/test_relations.py::test_equality_sharing_is_needed_and_works`, passed to failed: `assert True is None` at line 167.

**Cause:** the test monkeypatches `Relations._trichotomy` to turn that clause off. `rel_interpret` now calls Rust's `trichotomy` directly, so under Rust the patch reaches nothing and the clause is still emitted. No answer changes unless a test patches the method. No other test in `tests/` patches a moved method (by rg), so no other test is passing with a patch that does nothing.

| run | sharing on | sharing off |
|---|---|---|
| Python, patch after the first query, as the test does | True | None |
| Rust's core, `SLICE_REL=py`, same patch | True | None |
| Rust, same patch | True | **True**, the failure |
| Python, patch from the start | None | None |
| Rust, new plant `skip-trichotomy`, method off from the start | None | None |

So with the method really off, Rust answers as Python does. `drop-trichotomy` doesn't show this: it drops only the final clause, and keeps the `ensure`s, vars and roles, so that query still answers True. `test_a_patch_on_a_moved_method_reaches_nothing` pins all five rows.

**The test isn't edited, and it stays failing.** Under the rule that a new ruling joins the bar only if it can move an answer or hide a wrong one, this goes to the backend PR list: the test needs another way to turn the clause off, or the moved methods need to honour a patch.

## Plants

Each against this run's Python. `rel:plant_fired` is from each `.session.json`.

| method | plant | dev fired | dev | fuzz fired | fuzz |
|---|---|--:|---|--:|---|
| `_interpret` | `drop-interpret` | 969 | DIFFER | 24,075 | DIFFER |
| `_guard` | `drop-guard` | 588 | DIFFER | 9,294 | DIFFER |
| `_link` | `drop-link` | 375 | DIFFER | 9,405 | DIFFER |
| `selectors_of` | `drop-selector` | 38 | DIFFER | 1,006 | DIFFER |
| `_fresh` | `fresh-skew` | 2,994 | DIFFER | 74,497 | DIFFER |
| `_fresh` | `fresh-not-inert` | 1,124 | DIFFER | 28,695 | DIFFER |
| `_bound` | `drop-bound` | 0 | **MATCH, void** | 0 | **MATCH, void** |
| `_eq_infinity` | `drop-eq-infinity` | 0 | **MATCH, void** | 0 | **MATCH, void** |
| C2a `_order_sides` | `drop-order-sides` | 300 | DIFFER | 7,097 | DIFFER |
| C2a `_order_infinite` | `drop-order-infinite` | 257 | DIFFER | 13,335 | DIFFER |
| C2a `_trichotomy` | `drop-trichotomy` | 0 | **MATCH, void** | 72 | DIFFER |
| C2a `_trichotomy` | `skip-trichotomy` | 975 | MATCH, see below | 23,664 | DIFFER |
| the link | `link-none` | 1,756 | MATCH, as the ruling needs | 47,134 | MATCH, as the ruling needs |

**The void ones, and what stands in for them:**
- **`_eq_infinity`:** the plant sits on the symbolic path, and dev and fuzz don't reach that path, though `rel:eq_infinity` ticks 526 and 12,733 times on atoms with no infinite side. **On the suite it fired 1,176 times and changed 7 ids, passed to failed:** 5 in `test_extended_order.py`, 1 each in `test_ref_fuzz.py` and `test_history.py`. So it is caught there. The direct test below covers all three paths.
- **`_bound`:** `rel:bound` is **0 on dev, fuzz and the suite**, and `drop-bound` on the suite fired 0 with 0 changed ids. No workload reaches `_bound` at all. **Its only evidence is the direct test**, on Python-against-Rust clauses, where `drop-bound` fires and is seen.
- **`_trichotomy` on dev:** all 975 calls leave at the missing-reverse check, so dropping the clause fires 0, and `skip-trichotomy` firing 975 times changes nothing. That MATCH says dev never reaches the clause. Fuzz does.
- **`fresh-not-inert` DIFFERs on both,** so the digests do cover inertness.

## The two owed tests
`test_relations_core.py`, `_direct`, Python against Rust, recording clauses, `ensure` and `is_` in order:
- **`_eq_infinity`:** symbolic, decided true and false, undecided, each with the infinity on either side and `is_` forced, plus no infinite side. This replaces the forced answers of the deleted `test_eq_infinity_paths_match_python`.
- **`_guard` and `_bound`:** a constant real at the root, forced unknown, forced true and false, a symbol, a mix, the memo, a second term list with the constant already bounded, an adapter with no `register_bounds` and with it `None`, and `_bound` called alone.
- `drop-bound`, `drop-guard` and `drop-eq-infinity` each fire and change what it compares. 24 tests in the file pass, and `test_term_ids.py` with it makes 132 on pareto1. `relations_direct.py 300 0`: exit 0.

## The link: calls with crossings, including memo hits

| counter | dev | fuzz | suite |
|---|--:|--:|--:|
| `link:calls` | 1,756 | 47,134 | 314,395 |
| `link:hit` | 1,130 | 33,513 | 195,856 |
| `link:resolved` | 622 | 13,621 | 68,014 |
| `link:no_node` | 194 | 6,274 | 24,929 |
| `link:no_table` | 4 | 0 | 50,520 |
| `link:second` | 0 | 0 | 556 |
| `link:none` | 0 | 0 | 5 |
| `link:cross_current` | 1,756 | 47,134 | 314,395 |
| `link:cross_hash` | 1,752 | 47,134 | 263,875 |
| `link:cross_term_id` | 622 | 13,621 | 68,019 |
| **link crossings, all three** | **4,130** | **107,889** | **646,289** |
| all other `py:` and `rs:` | 60,599 | 979,130 | 21,365,753 |
| **link's share of all crossings** | **6.4%** | **9.9%** | **2.9%** |

**No fix made: it isn't a large share.** A memo hit is 64% to 71% of calls on dev and fuzz, and 62% on the suite. A hit costs about 470 ns from Python, on one rough run: orion, unpinned, 300,000 probes, best of 7, including the call into the probe. That is about 16 ms of fuzz's 6.59 s and 0.5 ms of dev's 0.747 s, using sa-port-86's rust-mode times. **Those whole-pass times are from bfac870, before the link existed, and C2b hasn't been timed**, so this is arithmetic, not a measured share. A memo hit still crosses to Python twice. The fix stays available if a later timing says otherwise: key the memo on the object's pointer and mirror the current table in a thread-local. Untried.

**sa-port-86's timing:** the session core's net is 2.6% on dev and 2.7% on fuzz at bfac870, not large, so under the planner's go no timing was added at 3f9ae3a.

**`link:none` now fires naturally on the suite,** where 5b reported 0: 5 here, all in `test_scope.py::test_zero_twins_are_in_the_scope`, and 88 on this session's earlier run at bceaacf. `join` moved the same way, 24 here and 289 there. 5b already noted that joins follow what a worker ran earlier, so this looks like the same effect, but that is not shown. `link-none` forcing None everywhere MATCHes on dev and fuzz, and that test passes on both runs.

## `_link`'s three-element set
The handoff's trap is real, and doesn't reach any answer.
- **Order differs:** Python's order comes from the constant frozenset in the loaded code, and Rust's `PySet::new` inserts in literal order. Against the real constant in `_link`'s code, they differ on **10 of 41 seeds** on pareto1, though not on seed 0. Python doesn't agree with itself either: a fresh compile and a marshal round trip differ on 90 of 300 seeds on orion, so there's no single order to match.
- **Why it doesn't reach anything, by reading:** `Session.ensure` uses the set only in `d.update(BASIS_OF[p])` (`engine.py:781`) and `frozenset(demanded)` (`want_of`), and neither depends on order.
- **By running:** dev and fuzz at seed 1, where the orders differ: Python against Rust MATCH on answers and state. No code change. This is one seed, not the seed rerun below.

## What these comparisons don't reach
- `_bound` on any workload, as above.
- `_eq_infinity`'s decided and undecided paths on any workload's plant: the plant sits on the symbolic path, and the direct test is their evidence.
- **The `Undecided` return** in `_order_infinite` has no counter, carried from 5b.
- **`_closed_extended_real`, `_mention_number` and `_link_integer` have no clause-drop plant.** Carried from 5b. Their evidence is the MATCH and the counters.
- **Neither dev nor fuzz reaches `compile`'s `Or` arm**, carried from 5a. Not measured again.

## Changes worth a reader's attention
- `_interpret`, `_link` and `_guard` are Python frames fewer on the way to `Session.ensure` and `Engine.is_`, so the recursion limit falls later on those paths. `rust-spike/slice/test_session_limits.py` isn't in the suite, whatever the handoff said: run separately, 242 passed on orion, aarch64, at a62bd61. It tests the session's own limits and doesn't measure where the limit now falls on these paths. The suite's recursion tests have no changed outcome.
- `rel_selectors_of` looks up once with `get_item` where Python does `in` then `[]`. Same result unless a hash has effects.
- Shared files changed: `session.rs`, `term/py.rs`, `term/relations.rs`, `term_live.py`, `session_live.py`, `relations_direct.py`, `test_term_ids.py`. `SLICE_REL=py` keeps the moved methods on Python over the same core.

## For the backend PR list
- **Plants the moved methods bypass:** `rel_interpret` calls `rel_order_sides`, `rel_trichotomy`, `rel_order_infinite` and `rel_link_integer` directly, so Python wrappers don't see those calls, and `SLICE_REL` is read only at install. Anyone rerunning those mutants needs to know.
- **A patch on a moved method does nothing,** as the failure above shows. Re-point the test or honour the patch.
- The planner's list from 338b606's limits stands: the three methods with no drop plant, and the three older plants the moved methods' direct reads bypass, `var-off`, `is-number-false` and `SLICE_TERM_CHECK`. Each needs re-pointing or a note.
- Re-entering the solver from a hook is allowed on Python and raises on Rust; through `_build_context` it would be a quiet unknown. Name it in the backend's contract.

## Not run
Moved to "before any backend PR", none quoted as met: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control, the boundary rescore and suite column, the final drop score and its lost rows, the suite split with Python's counter, `order:_rows`' evidence (not caught meanwhile), the `_forms` guard test, history and seed reruns, forced moves, the native path, timing.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run.
- `term_discard.py` wasn't rerun. None of the moved methods is among its sites; `_eq_links` is, and hasn't moved.
- `link-none` wasn't run on the suite. The ruling's test is dev and fuzz.
- **Speed not measured.** See the link above.
- The public-API `test_incremental_matches_fresh` family is still owed, due by 5c.
- Fuzz history for PR 328 and the censuses on the base stay open, so section 8's limits still stand.
- The `_n_conflicts` view in `rust_plugin.py` isn't a port: a test-plugin shim, with the 64 tests it moved.
- `tests/test_solver.py::test_performance_smoke_300_vars` passed on pareto1, no changed outcome.
