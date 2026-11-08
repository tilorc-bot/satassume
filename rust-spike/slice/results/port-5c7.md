# Step 5c7: `Engine._union` and `Engine._within_budget` on Rust (issue 323)

## What moved
- **Two rows, `Engine._union` and `Engine._within_budget`** (sa-port-148, -151, -154, -158), in
  `solver_rs/src/budget.rs` (`union` :48, `within_budget` :105; pyfunctions `bud_union` :189, `bud_within_budget` :199).
  `session_live.py` `_install_budget` (:742) wires them over `Engine` (`_BUDGET_METHODS` :728), and `SLICE_BUDGET=py`
  puts Python's methods back. A budget that isn't an int (Python accepts any value) runs Python's own copies
  (`bud:py_fallback`, 0 on every workload).
- **The cone rows stay Python and are called back by name:** `_query_cone` (`bud:cb_query_cone`), `_cone_info`
  (`bud:cb_cone_info`), `_struct` (`bud:cb_struct`), and the module globals `atoms_of`, `under_of`, `zero_twin`, `_kid`
  read from `satassume.engine` at the call (`bud:cb_global`). Rust makes every read and call Python makes, in the same
  order, so state is Python's by construction.
- **`_over_budget` and `_note_budget` are on Python at 5c7.** Their Rust code (`bud_over_budget` :216, `bud_note_budget`
  :236) is in budget.rs, unwired unless `SLICE_BUDGET_FLAGS=rust` (not a landing configuration). They go to 5c10d under
  the inventory ruling (8 Nov ~06:22), because they write `last_budget_limited` and `stats`.
- **Counters** (session.rs): `bud:union` .. `bud:py_fallback` 156-164, and the branch counters `bud:union_cone_none`,
  `bud:union_over`, `bud:union_partial`, `bud:within_partial`, `bud:within_false` 165-169 (NAMES/COUNTS 170). Slot 155 is
  adapters C2's `cf:pi_laurent`. It was held as "rsv:155" until C2 landed and was replaced on the rebase.
- **Plants** (relations_core.rs, after C2's 111-113): `union-skip-overlap` 114, `within-no-link` 115,
  `over-budget-no-flag` 116 and `note-budget-keep-flag` 117. The last two are in unwired code and weren't run.
- **The budget plants were unarmed before 1649e9b.** `session_live.from_env` never passed `_BUDGET_PLANTS` to
  `rel_plant`, so both budget plants were void on every run before that commit, sa-port-151's plant runs included.
  Fixed at session_live.py :910.
- **Budget workload** (`budget_wl.py`, `live.py budget`, 28 queries), owed by this bar because `over_budget` is 0 on dev.
  It's built from `_within_budget`'s branches: `_over` (q0-13), overlap sums on integer/real/finite (q14-23), and
  `_sum_over` on Q.integer with 0, about 100 and about 200 set objects outside the proposition's cone (q24-27; the last is
  budget-limited). Earlier drafts were slow because of live.py's `--check entry`, which takes a full state digest after
  each outermost solver call (q14 made 15,022 entries in one session). The warm engine wasn't the cause.

## SHAs
Tested **b355db2** (port/5c7 on rust-slice 30f3309, 6g(c1)). Rows on pareto1 at
`~/sp19/sa-rust-ids-work/sa-port-158/bar-5c7b/` (`sum.txt`, `commands.txt`, `config.txt`), `.so` sha256 4a01b7bc…. Base
suite rows: 6g(c1)'s (`sa-port-157/suite`). The landed SHA is the commit carrying this file. Between it and b355db2 there
is only this report, which no run executes.

**Earlier bars on this step's code:**
- **bd46e54** (port/5c7 on C2's 9c8d981): `~/sp19/sa-rust-ids-work/sa-port-158/bar-5c7/`, base C2b's suite rows. This is
  the bar that ran the suite under `within-no-link`, and it's clean on every item. 6g(c1) landed while it ran. Its diff
  (`term/{rows_tpl,common,py}.rs`, `knowledge_c*_live.py`, `knowledge_core_wl.py`, `test_knowledge_core_shapes.py`) is
  under the push guard, so the full bar reran on b355db2.
- **1649e9b** (on b838d3f, 6g(b)): `~/sp19/sa-rust-ids-work/sa-port-154/bar-5c7/`. It was clean too, but C2's diff
  (constfield.rs, lra_cert.rs, relations_core.rs, session.rs) touched guarded source.

Each rebase brought conflicts only in the plant and counter lists (relations_core.rs, session.rs) and in live.py's workload
lines. Both sides were kept, and the 5c7 code itself is unchanged.

## The bar (sa-port-158/bar-5c7b, on b355db2)
1. **Suite by id against 6g(c1)'s rows:** 5,992 passed, 126 failed, 23 skipped, 18 xfailed, 6,159 ids. New 0, gone 0,
   changed outcome 0. Passed splits as 5,991 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`).
   S's standing: S's gate is met except for the 46 named stub failures, one cause.
2. **Fresh dev and fuzz, plus zero, budget and cert:** answers and state MATCH, and every control MATCHes. Answers are
   unchanged: dev 31cd0945c07f02a6 (1,985 q), fuzz 173502b6ef285ad6 (3,000 q), zero d9ed3534a2093027 (854 q), budget
   35bc2c4a937bebc0 (28 q), cert 6a09c059eb266747 (61 q). The Rust runs made 0 Python solvers.
3. **Plants:** union-skip-overlap is caught on the budget workload (DIFFER, first q14: True -> None). within-no-link is
   void everywhere, the suite included (see below).
4. **Quiet handlers in the suite:** 39 rows in 2 tests, the same multiset as base:
   - `_consistent` AttributeError: 34 on `_ok` and 4 on `_rb_clauses` (the named needs-internals case);
   - `Engine._build_context` "Already mutably borrowed": 1, in `test_protocol_on_fuzz` (the 46-stub cause).

   The `caught` rows per id match base. **Quiet catches at engine.py:1906: 1**, in the suite, as on base. The 15 live and
   extra handler files and the 4 dev/fuzz plant handler files have 0 rows. TermFault 0.
5. **Known differences in answers or read state:** none. Tests: 512 passed (the 11 slice files plus test_cf_laurent.py),
   and `relations_direct.py` exited 0.

The bd46e54 bar gave the same numbers against C2b's rows on all five items.

## Plants (fired; D = DIFFER)
| plant | item | dev | fuzz | budget | zero | cert | suite | caught by |
|---|---|--:|--:|--:|--:|--:|--:|---|
| union-skip-overlap | `_union` | 88 | 7,236 | 65 D | 77 | 108 | not run | budget (first q14: True -> None) |
| within-no-link | `_within_budget` | 197 | 3,108 | 7 | 608 | 61 | 31,143 (0 changed) | **void everywhere** |
| over-budget-no-flag | `_over_budget` | - | - | - | - | - | - | not run (unwired, 5c10d) |
| note-budget-keep-flag | `_note_budget` | - | - | - | - | - | - | not run (unwired, 5c10d) |

The fire counts are the same on b355db2 and bd46e54. The suite column is bd46e54's.

**union-skip-overlap** makes `_union` treat a cone that adds new objects as if it overlapped completely. It fires on every
workload, but it changes a verdict only where the union crosses the budget, and only the budget workload does that.
There 7 answers DIFFER, starting at q14.

**within-no-link is void on dev, fuzz, budget, zero, cert and the suite.** It makes `_within_budget` query both cones
with `link=False` (budget.rs :145). A linked cone contains the unlinked one, so the plant can change a verdict only
where linking is what pushes a cone over the budget: the unlinked cone fits and the linked one doesn't. No query on these
workloads has that shape, and no suite test either. The suite under the plant (bd46e54's bar) fired it 31,143 times in
9 files, with 0 changed outcomes, new 0, gone 0, and the same handler multiset. Its counters do move (`bud:union` 615 ->
477 on dev, `bud:union_over` 6 -> 3 on budget), and the answers and state MATCH. **Owed:** a budget-workload query whose
cone fits unlinked and doesn't fit linked. It isn't needed to land, because union-skip-overlap meets bar item 3.

## Reached (bud:* branch counters on the Rust run, per pass)
| counter | dev | fuzz | zero | budget | cert |
|---|--:|--:|--:|--:|--:|
| `bud:union` | 615 | 8,621 | 277 | 38 | 184 |
| `bud:within_budget` | 840 | 3,127 | 724 | 37 | 61 |
| `bud:union_cone_none` | 0 | 0 | 0 | 6 | 0 |
| `bud:union_over` | 0 | 0 | 0 | 6 | 0 |
| `bud:union_partial` | 88 | 7,236 | 77 | 69 | 108 |
| `bud:within_partial` | 0 | 0 | 0 | 6 | 0 |
| `bud:within_false` | 0 | 0 | 0 | 16 | 0 |
| `bud:cb_query_cone` | 3,232 | 11,798 | 2,846 | 111 | 244 |
| `bud:cb_cone_info` | 881 | 24,130 | 852 | 1,467 | 528 |
| `bud:cb_struct` | 153 | 16,176 | 173 | 2,553 | 177 |
| `bud:cb_global` | 836 | 384 | 2,494 | 0 | 4 |
| `bud:over_budget`, `bud:note_budget`, `bud:py_fallback` | 0 | 0 | 0 | 0 | 0 |

**Both moved items are reached on every workload.** The over-budget branches (`union_cone_none`, `union_over`,
`within_partial`, `within_false`) are reached only by the budget workload, which is why it's owed here. Every bud:*
branch counter is above 0 on budget. `over_budget`, `note_budget` and `py_fallback` are 0 everywhere: the first two
are unwired at 5c7, and no workload passes a budget that isn't an int.

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
Share of all queries kept per reason, on the Rust run. Base is 6g(c1)'s bar.

| workload | queries | out-of-scope | refused | other named exceptions | base |
|---|--:|--:|--:|--:|---|
| dev | 1,985 | 24 (1.21%) | 0 | 0 | the same |
| fuzz | 3,000 | 0 | 0 | 0 | the same |
| zero | 854 | 0 | 0 | 0 | the same |
| cert | 61 | 0 | 0 | 0 | the same |
| budget | 28 | 0 | 0 | 0 | no base (new workload) |

**No share rose.**

## State: each container 5c7's rows touch (planner's state ruling and 5c7 container ruling, 8 Nov)
5c7 removes no container's last non-test Python reader (sa-port-147, INVENTORY-state.md part 1a). So **nothing moves to
Rust-native state at 5c7.** Each container is kept, with its named reader and the step it moves in:

| container | decision | named reader past 5c7 | moves in |
|---|---|---|---|
| `Engine._kids` | kept | `Engine.__init__`, `engine_memos` (5c9); `_struct`, `_drop_cones` (5c10, through the Rust view after 5c9); test write test_writeback_provenance.py :453 (needs-internals) | 5c9 |
| `Engine._cones` | kept | `Engine.is_` :2001, `Engine.is_many` :2049 (5c10); `_cone_info` (5c10) | 5c10 |
| `Engine._qcones` | kept | `Engine.__init__`, `engine_memos`, `_query_cone` (5c9) | 5c9 |
| `Engine._glue_adapters` | kept | `Engine.__init__`, `engine_memos` (5c9); relations `link_objects`/`glue_objects` take it as memo | 5c9 |
| `Engine._constructing` | kept | `Engine.is_` :1998, `is_many` :2047 (5c10); compile_loop.rs `core_visit` (Rust over the Python set) | 5c10 |
| `engine._NEIGH` | kept | `neighbourhood` (moved to 5c9 with it: it reads the registry memo), state.memos registry | 5c9 |
| `Engine.last_budget_limited` | kept | writers `_over_budget`/`_note_budget` (5c10d); readers sympy_api and public `ask` (read-only view when it moves) | 5c10d |
| `Engine.stats["budget_limited"]` | kept | `_over_budget`/`_note_budget` (5c10d); public `Engine.stats` | 5c10d |
| `Session.truncated` | kept | `_note_budget` (5c10d), `_complete_check`, `_put_result` (5c10) | 5c10 |

`_union` and `_within_budget` hold no state of their own. The TSV shows the new owners: port-ownership.tsv rows 83-84
"landed 5c7 (port-5c7.md)", Rust. `_drop_cones`, `_struct` and `_cone_info` go to 5c10, `_query_cone` and
`neighbourhood` to 5c9, and `_over_budget` and `_note_budget` to 5c10d (rows 79-82, 85, 98, 101; port-ownership.md
:46-49). The state rows are 814-818.

## Module count (count rule)
**13 of 32, unchanged** (~/dev/architect/STATUS.md "Counted modules"). engine.py counts at 5c10.

## Owed-list additions
- `within-no-link` has no catch anywhere. Owed: a budget-workload query whose cone fits unlinked and is over the budget
  linked.

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
- the suite under union-skip-overlap, which the budget workload catches (not needed);
- `over-budget-no-flag` and `note-budget-keep-flag`, which are in unwired code;
- the suite under `within-no-link` on b355db2: it ran on bd46e54, and budget.rs and the 5c7 wiring are the same in both.

Other notes:
- S's standing: S's gate is met except for the 46 named stub failures, one cause.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and
  the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals.
  This step doesn't touch it.
