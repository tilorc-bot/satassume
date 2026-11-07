# Handoff, sa-port-88: component 5, step 5b, C2b. Code written and pushed; landing bar not run

Head: `port/c2b` 35d23df plus this file, on `rust-slice` 3f9ae3a. **Not landed.** Handed off at the context note (151k), no blocker.

## Done
- `_interpret`, `_guard`, `_link`, `_bound`, `_fresh`, `selectors_of` are in `relations_core.rs` and call the Rust session directly. C2a's `_fresh` and `_guard` callbacks became direct.
- `_eq_infinity` moved too, because `_interpret` was its only caller. **C1's plan is deleted:** `term_live.py`, `term/py.rs`, `term/relations.rs`. `_eq_links`' plan stays: its caller is `process`, which is 5c.
- **Term to node is still not needed.** Every C2b method holds objects, including `_eq_infinity`. It arrives with `_eq_links`' derived ids, so 5c.
- Stays Python, called back: `_adapter`, `_atom_var`, `_atom_selector`, `_add_role`, `_apply_role`, `_note_sides`, `_tsource`, `sympy_atom`, `_own_term`, `relation_atom`, the adapters, `Session.ensure`.
- New counters: `rel:fresh|interpret|guard|bound|link|selectors_of|eq_infinity`, `link:calls`, `link:cross_current|cross_hash|cross_term_id`.
- New runtime plants, by `SLICE_SESSION_PLANT`: `drop-interpret`, `drop-guard`, `drop-bound`, `drop-link`, `drop-selector`, `drop-eq-infinity`, `fresh-not-inert`, `fresh-skew`.

## What has run
Only `test_relations_core.py` and `test_term_ids.py`, on orion, aarch64, at 35d23df: 126 passed. **No suite, no fresh dev or fuzz, no plant on a workload.** Nothing here meets any item of the bar yet.

## Not done, in order
1. **Owed tests:**
   - `_bound` direct case. No test query reaches it, and Python's own `_bound` didn't fire either on 8 probe queries with `pi`, `sqrt(2)`, `E`, `sin(2)`: constants went into the coefficient field. So `drop-bound` isn't in the parametrized test, and `bound` isn't in `test_each_method_ran`. Call `_guard` with a number term directly, Rust against `PY_REL`.
   - `_eq_infinity`'s three paths with `is_` forced. I deleted `test_eq_infinity_paths_match_python` and took `_eq_infinity` out of `relations_direct.py`, since both drove the plan's `__wrapped__`. Their forced answers (decided, undecided, symbolic) are **not yet replaced**: the new `eq-oo-*` queries use the real `is_`, and I didn't check they reach all three. Fresh dev made 0 of these plans in earlier steps, so this was its main evidence. Restore it, and say so in the report.
2. **The bar's runs on pareto1,** recipe below: suite by id, fresh dev and fuzz, plants.
3. **Link counts with crossings** on dev, fuzz, suite. See "The link" below.
4. Report and land. Report text is `results/port-c2b.md`.

## The link
Test corpus only: `link:hit` 145, `link:resolved` 102, `link:no_node` 52. Workload numbers don't exist yet.
A memo hit costs, by reading and **not measured**, 3 Python frames: `term_live.current()`, `stack()`, `Basic.__hash__`, plus attribute reads of `q.kept` and `q.table`.
sa-port-86's timing was reported at journal 639abd6 and I haven't read it: `agent journal -v --session sa-port-86`. Read it first, as the planner's go says.
If the share is large, a small fix on the Rust side: key the memo on the object's pointer (the memo holds the object, so it can't alias; no hash, and no session serial needed, since `term_id` depends only on the query and the object), and mirror the current table in a thread-local that `term_live`'s stack push and pop set. Untried. `q.kept` is assigned at `term_live.py:85`; check nothing changes it mid-query.

## Map, at 35d23df, under `rust-spike/slice/`
- `solver_rs/src/relations_core.rs`: `term_of` :102, `fresh` :453, `bound` :481, `guard` :510, `eq_infinity` :554, `rel_interpret` :596, `rel_link` :689, `rel_selectors_of` :751, plants' consts up to :49.
- `solver_rs/src/session.rs`: counters :58-68, `node_quiet` :305, `aux_direct` :443.
- `session_live.py`: wrappers from :294, each dispatching on `TableView` for `ref.py`; `_REL_METHODS` :342, `_REL_PLANTS` :350.
- `term_live.py`: `_run_plan` :745, `_eq_links` :761, both remain.
- `test_relations_core.py`: `_queries` :28, `test_each_method_ran` :230, `test_fresh_not_inert_fires` :254, `test_link_crossings_add_up` :259.
- Python's source, `satassume/relations.py`: `_fresh` :980, `_interpret` :998, `_guard` :1082, `_eq_infinity` :1127, `_bound` :1463, `_link` :1480, `selectors_of` :1527.

## Traps
- **`_link`'s three-element set.** `ensure` iterates what it's given, and `PySet::new` inserts in literal order. CPython compiles a 3+ constant set through a frozenset constant, and marshal may sort it when loaded from a `.pyc`, so a hash collision could order it differently from Python's. Not checked. `Session.ensure` loops over it at `engine.py:781`. Compare `list(...)` across hash seeds; if it can differ, put it on the backend PR list or match it.
- **`fresh-not-inert`** can't show in a clause stream; only the fresh digests can see it. If it MATCHes, say what that means: the digest may not cover inertness, or inertness may not move an answer. `fresh-skew` is the plant that must DIFFER.
- **Plants bypassed, for the backend PR list:** Python wrappers on the moved methods no longer see Rust-to-Rust calls. `rel_interpret` calls `rel_order_sides`, `rel_trichotomy`, `rel_order_infinite` and `rel_link_integer` directly, and `SLICE_REL` is checked only at install.
- **Frames:** `_interpret`, `_link` and `_guard` are Python frames fewer on the way to `Session.ensure` and `Engine.is_`, so the recursion limit falls later on those paths. `test_session_limits.py` runs in the suite; look at it.
- `rel_selectors_of` looks up with `get_item` once where Python does `in` then `[]`. Same result unless a hash has effects.
- `term_discard.py` wasn't rerun. None of the moved methods is in its list; `_eq_links` is and hasn't moved.

## Machines
- sa-port-87's recipe on pareto1: `~/sp19/job87.sh` (environment) and `~/sp19/land87.sh` (build, suite, `run_live.sh`, plants against this run's Python). Copy both to `job88`/`land88` with this session's name, its tree, `port/c2b`, and the plant list below. Run: `setsid nohup machine run pareto1 --shared --wait 4h -r WHY -- bash -lc 'cd ~/sp19 && bash job88.sh ~/sp19/land88.sh'`.
- Plants, each on dev and fuzz: `drop-interpret`, `drop-guard`, `drop-bound`, `drop-link`, `drop-selector`, `drop-eq-infinity`, `fresh-not-inert`, `fresh-skew`, and `link-none`, which must MATCH. Read `rel:plant_fired` from each `.session.json`: **fired 0 makes that MATCH void, so say so.** sa-port-87's plant loop ran them all at once in the background, fine on an idle pareto1 at `--shared`.
- Base rows for by-id: orion `~/sa-rust-ids-work/sa-port-87/suite-rows`, pareto1 `~/sp19/sa-rust-ids-work/sa-port-87/suite`. 5b's numbers: 5,960 passed, 124 failed, 23 skipped, 18 xfailed, 6,125 ids.

## Module count
No module newly counts whole, as far as the code goes: `relations.py` keeps `process`, `_eq_links`, discovery glue and all of C2c, so it stays partial until C2c and 5c. `compile.py` is unchanged. Restate this in the report.
