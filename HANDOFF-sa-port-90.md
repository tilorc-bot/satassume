# Handoff, sa-port-90: component 5, step 5b, C2c. First version written and pushed; landing bar not run

Head: `port/c2c` 12a980d plus this file, on `rust-slice` 8d6cff7. **Not landed.** Handed off at the context note, no blocker.

## Done
- `_add_role`, `_apply_role`, `_tsource`, `_tvar`, `_share_guard`, `_congruent`, `_engage_transfer`, `_transfer_terms`, `sync_transfer`, `_congruence_pairs` are in `relations_core.rs`, each calling the Rust session directly. The Python line numbers on sa-port-73's list were still right.
- **`_xswitch` moved too**, off the list, because `sync_transfer` is its only caller. Same case as `_eq_infinity` in C2b. Say so in the report.
- Rust's callbacks to `_add_role`, `_apply_role` and `_tsource` from `_trichotomy`, `_mention_number`, `_interpret` and `_link` are now direct.
- Stays Python, called back: `_adapter`, `_atom_var`, `_atom_selector`, `_note_sides`, `sympy_atom`, `_own_term`, `relation_atom`, `_number_basis`, `_number_facts`, the adapters, the transfer theory, `Session.ensure`. `_share` stays Python and calls the wrappers for `_add_role` and `_share_guard`.
- New counters: `rel:add_role|apply_role|tsource|tvar|share_guard|congruent|engage_transfer|transfer_terms|sync_transfer|xswitch|congruence_pairs`.
- New runtime plants, by `SLICE_SESSION_PLANT`, all in `_REL_PLANTS`: `drop-add-role`, `drop-apply-role`, `drop-candidacy`, `drop-tsource`, `drop-tvar`, `drop-tvar-mc`, `drop-engage`, `drop-terms`, `drop-terms-side`, `drop-fixed`, `drop-sync`, `drop-sync-polar`, `drop-xswitch`, `drop-congruence`, `congruent-never`, `share-guard-one`. **None has been run.**

## What has run
Only `test_relations_core.py` and `test_term_ids.py`, unchanged, on orion, aarch64, at 12a980d: 132 passed, `~/sa-rust-ids-work/sa-port-90/rel-tests-first.txt`.
**That shows little for C2c.** Those tests don't assert the new counters or use the new plants, and I didn't check how far their queries reach these methods. No suite, no fresh dev or fuzz, no plant on a workload. Nothing here meets any item of the bar yet.

## Not done, in order
1. **Tests in `test_relations_core.py`:**
   - Add the new names to `test_each_method_ran`, and add queries to `_queries` that reach congruence, for example `f(x)`, `f(y)` with `x = y`, and a rational side.
   - Add the plants to `test_dropped_clause_is_seen` where the corpus fires them.
   - Extend `_direct` to `_add_role` (a repeat role, role before and after interpretation), `_apply_role` (each kind, with and without twins), `_tsource`, `_tvar` (each kind, MC before and after SD and EN) and `_share_guard`, Python against Rust. A plant that fires 0 on a workload needs this as its evidence.
   - Assert Rust's `SD, EN, MC, IE, IL` equal `relations._SD` and so on. Rust hardcodes them at `relations_core.rs:836`.
2. **The bar's runs on pareto1,** recipe below: suite by id, fresh dev and fuzz, each plant on both, and on the suite for any plant that fires 0 on both.
3. **The items the go asks for,** in "Also say" below.
4. Report `rust-spike/slice/results/port-c2c.md`, in the form of `port-c2b.md`. Rebase, land without force, `agent report`.

## Also say, as the go asks
- **`link-none` once on the suite, by id.** Any moved id is a finding. Join and worker-history account stays "not shown".
- **Set iterations in moved code.** My reading, checked by rg on `satassume/relations.py`, not by a run:
  - `_xcand`, `_xpart`, `_xpairs` and `_xcounted` are only added to and asked `in`, in Python and Rust alike. Nothing iterates them.
  - `_xheads.values()`, `grown` and `_xside` are dicts in insertion order. `grown` stays a real Python dict in Rust, so `==` joins the same way.
  - `specs` is a list. `_tsrc` values, `_xheads` values, `_roles` values, `_xpend`, `lterms`, `eterms` and `twins` are lists. `atom.expr` and `args` are tuples.
  - `_number_basis` returns a tuple sorted from a set, so that set's order doesn't reach here.
  - No `PySet` is made in moved code, and `s.ensure(e)` passes no set in `_transfer_terms`.
  - **Not read:** what `th.switch` and `ad.terms_since` return on the Rust backends, which `backend.install_euf` and `install_transfer` replace. Python's `th.switch` returns a list (`transfer.py:158-172`). Check both. If nothing can differ, no seed run is needed; if an order can differ, run dev and fuzz at a seed where it does.
- **`Basic.__hash__` and `Integer.__hash__` on dev and fuzz,** by `sys.monitoring` as 639abd6: `~/sa-rust-ids-work/sa-port-86/tools/qt86.py`, kind `count`, and `tools/run.sh:50`. Not yet read beyond those lines. Compare with fuzz 708,603 and 207,017, dev 43,401 and 8,137. Don't trace them in this session; if they rise, say so. **A likely contributor, not measured:** `Cx::structural` goes through the link, which hashes the object, where Python's `structural` hashes nothing. `sync_transfer` asks it per pending node per call. Report `link:calls` too. Calling Python's function instead is a one-line change if the count says it's worth it.
- **What's still Python in `relations.py` after C2c, with lengths,** so 5c's list is complete. Compute it from the source with `ast`, subtracting `_REL_METHODS`.
- **Each moved method: does a plant reach it, on which workload, which MATCHes are void.**
- **Whether any module newly counts whole.** My expectation, to restate after checking: no. `relations.py` keeps `process`, `_eq_links`, `_share`, `_note_sides` and the discovery glue, so it stays partial until 5c, and `compile.py` is unchanged.

## Map, at 12a980d, under `rust-spike/slice/`
- `solver_rs/src/relations_core.rs`: plants' consts :53, `SD` and the others :836, `Cx` :873, `add_role` :899, `apply_role` :925, `tsource` :980, `tvar` :1009, `share_guard` :1059, `congruent` :1070, `engage_transfer` :1110, `transfer_terms` :1145, `xswitch` :1225, `sync_transfer` :1243, `congruence_pairs` :1333, `with_cx` :1398, the pyfunctions from :1406.
- `solver_rs/src/session.rs`: `base_contains_direct` :341, `n_slots_direct` :346, `block_direct` :351.
- `session_live.py`: new wrappers from :336, `_REL_METHODS` :408, `_REL_PLANTS` :427.
- `test_relations_core.py`: `_queries` :28, `_run` :74, `_direct` :138, `test_direct_sees_its_plants` :402, `test_each_method_ran` :408, `test_dropped_clause_is_seen` :426.
- Python's source, `satassume/relations.py`: `_add_role` :1197, `_apply_role` :1219, `_tsource` :1264, `_tvar` :1282, `_share` :1584, `_share_guard` :1600, `_congruent` :1624, `_engage_transfer` :1662, `_transfer_terms` :1691, `sync_transfer` :1750, `_xswitch` :1848, `_congruence_pairs` :1855.

## Traps
- **Tests that patch:** `tests/test_transfer.py:156-157` patches `Relations._engage_transfer` and `transfer.TransferTheory`. `process` is still Python, so the first patch is reached, and `engage_transfer` reads the class at each call, so the second is too. Not yet seen in a suite run. `tests/test_relations.py:164` patches `_share`, which stays Python. By rg, `tests/` touches none of `_tv`, `_tsrc` or the `_x*` state.
- **`test_equality_sharing_is_needed_and_works`** stays failing and unedited, on the backend list, as ruled.
- **Slots:** `sync_transfer` reads slots past `_Slots`, so a custom atom's slot no longer builds a `P`. `py:table` and `custom:own` counts should fall. Python built that atom only to see it isn't a tuple. Check that no digest reads those counters.
- **Plants that stop being reachable:** Rust-to-Rust calls bypass the wrappers, so a Python patch on a moved method does nothing. C2c widens this, for the backend PR list.
- **Frames:** more Python frames are gone on the way to `Session.ensure`, so the recursion limit falls later on these paths. Run `test_session_limits.py` separately; it isn't in the suite.
- `_guard`'s list can still be filling when `_apply_role` reads it, so `with_tail` reads `g` at each emit, as Python's `+` does. Don't cache it.
- `sync_transfer`'s `drop-sync` drops only predicate 0, and `drop-tvar` fires once per guard, so plant counts aren't method call counts.
- `term_discard.py` wasn't rerun. Check whether any moved method is among its sites.

## Machines
- sa-port-89's recipe on pareto1: `~/sp19/job89.sh` (environment) and `~/sp19/land89.sh` (build, tests, suite with handler rows, `run_live.sh`, plants against this run's Python, seed scan, suite for zero-fire plants). Copy both with this session's name, its tree and `BR=port/c2c`, and swap in the plant list above, plus `link-none` on the suite.
- Run: `setsid nohup machine run pareto1 --shared --wait 4h -r WHY -- bash -lc 'cd ~/sp19 && bash jobNN.sh ~/sp19/landNN.sh'`.
- Base rows for by-id: orion `~/sa-rust-ids-work/sa-port-89/rows`, pareto1 `~/sp19/sa-rust-ids-work/sa-port-89/suite`. C2b's numbers: 5,959 passed, 125 failed, 23 skipped, 18 xfailed, 6,125 ids. Passed splits as 5,958 with no firing and 1 with a firing.
- Handler base: 39 rows in 2 tests, as `port-c2b.md` item 4 lists. `TermFault` 0.

## Module count
No module newly counts whole, as far as the code goes. Restate this in the report after checking.
