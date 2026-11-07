# Step 5b, C2c: eleven Relations methods in Rust (issue 323)

Tested source 2caa559, on rust-slice 8d6cff7, pareto1, x86-64, `-n 8`, `PYTHONHASHSEED=0` unless said; `.so` sha256 a348bf35…, and every run imported `satassume` from that tree (`tree.txt`). Rows: pareto1 `~/sp19/sa-rust-ids-work/sa-port-91`, copy on orion `~/sa-rust-ids-work/sa-port-92/rows`. Base rows: C2b's, `sa-port-89/suite`. rust-slice hasn't moved since 8d6cff7, so no rebase. The landed source adds two handoffs and this report, and no code the runs execute.

## What moved
- `_add_role`, `_apply_role`, `_tsource`, `_tvar`, `_share_guard`, `_congruent`, `_engage_transfer`, `_transfer_terms`, `sync_transfer` and `_congruence_pairs` are in `relations_core.rs`, as sa-port-73's list has them, and call the Rust session directly.
- **`_xswitch` moved too**, off the list, because `sync_transfer` is its only caller. This is the same case as `_eq_infinity` in C2b.
- Rust's callbacks to `_add_role`, `_apply_role` and `_tsource` from `_trichotomy`, `_mention_number`, `_interpret` and `_link` are now direct.
- Stays Python, called back: `_adapter`, `_atom_var`, `_atom_selector`, `_note_sides`, `sympy_atom`, `_own_term`, `relation_atom`, `_number_basis`, `_number_facts`, the adapters, the transfer theory and `Session.ensure`. `_share` stays Python and calls the wrappers for `_add_role` and `_share_guard`.
- **Modules: none newly counts whole.** `relations.py` still has 39 Python functions and methods, 685 lines, listed below. That includes `process`, `_eq_links`, `_share` and `_note_sides`, so it stays partial until 5c. `compile.py` is unchanged.
- Shared files changed: `session.rs` (`base_contains_direct`, `n_slots_direct`, `block_direct`) and `session_live.py`.

## The bar
1. **Suite by id against C2b's rows:** 5,959 passed, 125 failed, 23 skipped, 18 xfailed, 6,125 ids. **No new id and no changed outcome.** Passed splits as 5,958 with no firing and 1 with a firing, `test_ci_stream_reports_only_what_replays`. S's standing: its gate is met except for the 46 named stub failures, one cause. `test_equality_sharing_is_needed_and_works` stays failing and unedited, as ruled.
2. **Fresh dev and fuzz:** answers and state MATCH, four comparisons each, including the end states of the untraced runs. The control, Python against Python, also MATCHes. The answers' sha is unchanged from C2b's runs: dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6.
3. **Planted bugs:** table below. Every moved method has a plant that a workload catches. Fuzz catches all of them except `_transfer_terms`' two drop plants, and the suite catches those.
4. **Quiet handlers, suite:** 39 rows in 2 tests, the same multiset as C2b's by where, site, type and text. `test_ci_stream_reports_only_what_replays` passed: `_consistent` AttributeError, 34 `_ok` and 4 `_rb_clauses`, the named needs-internals case. `test_protocol_on_fuzz` failed: `Engine._build_context` "Already mutably borrowed" 1, the 46-stub cause, and 1 catch at the complete-check handler (`engine.py:1906`), a RuntimeError. No other firing. The `caught` rows match C2b's per id, by site, type and text: 9 tests, the others being `Uninterpreted` at the verdict. `TermFault`: 0 in the suite log. Dev and fuzz handler files: 0 rows.
5. **Known differences in answers or read state:** none.

## Plants

Each against this run's Python. `rel:plant_fired` is from each `.session.json`. A plant's count is not a count of method calls: `drop-tvar` fires once per guard, and `drop-sync` drops only predicate 0.

| method | plant | dev fired | dev | fuzz fired | fuzz |
|---|---|--:|---|--:|---|
| `_add_role` | `drop-add-role` | 1,298 | DIFFER | 31,620 | DIFFER |
| `_apply_role` | `drop-apply-role` | 548 | DIFFER | 12,810 | DIFFER |
| `_apply_role` | `drop-candidacy` | 50 | DIFFER | 1,770 | DIFFER |
| `_tsource` | `drop-tsource` | 102 | DIFFER | 6,038 | DIFFER |
| `_tvar` | `drop-tvar` | 690 | DIFFER | 24,126 | DIFFER |
| `_tvar` | `drop-tvar-mc` | 0 | **MATCH, void** | 418 | DIFFER |
| `_share_guard` | `share-guard-one` | 276 | DIFFER | 4,890 | DIFFER |
| `_congruent` | `congruent-never` | 0 | **MATCH, void** | 597 | DIFFER |
| `_engage_transfer` | `drop-engage` | 35 | DIFFER | 911 | DIFFER |
| `_transfer_terms` | `drop-fixed` | 46 | DIFFER | 992 | DIFFER |
| `_transfer_terms` | `drop-terms` | 0 | **MATCH, void** | 0 | **MATCH, void** |
| `_transfer_terms` | `drop-terms-side` | 0 | **MATCH, void** | 0 | **MATCH, void** |
| `sync_transfer` | `drop-sync` | 50 | DIFFER | 1,923 | DIFFER |
| `sync_transfer` | `drop-sync-polar` | 40 | DIFFER | 1,590 | DIFFER |
| `_xswitch` | `drop-xswitch` | 136 | DIFFER | 6,904 | DIFFER |
| `_congruence_pairs` | `drop-congruence` | 0 | **MATCH, void** | 109 | DIFFER |

C2a's and C2b's plants were rerun and fire exactly as in `port-c2b.md`: the same counts and the same verdicts, `drop-bound` and `drop-eq-infinity` void on both, `drop-trichotomy` void on dev. The one exception is `link-none`, which fires 2,571 times on dev and 81,134 on fuzz, against 1,756 and 47,134, and MATCHes on both as the ruling needs. It fires once per link call, and C2c's code calls the link more, as the hash section says.

**The void ones, and what stands in for them:**
- **`drop-terms` and `drop-terms-side`** fire 0 on dev and fuzz, though `rel:transfer_terms` ticks 67 and 1,722 times there. On the suite each fired and changed ids, passed to failed:
  - `drop-terms` fired 818 times and changed 4 ids: `test_history.py::test_ci_profiles_at_both_levels[transfer-2-SPEC]`, `test_scope.py::test_zero_twins_are_in_the_scope`, and `test_zero_glue.py::test_zero_in_the_set_is_an_equality[G5-default]` and `[G5-whole]`.
  - `drop-terms-side` fired 1,562 times and changed 6 ids: two in `test_ref_fuzz.py::test_known_differences`, `test_set_verdict.py::test_unknown_verdict_does_not_raise`, `test_transfer.py::test_transfer_answers[Q.real(x)|Q.eq(x, pi/2)]`, and two in `test_unrelated_relation.py::test_known_sets_padded`.
  - Neither changed the handler multiset. `drop-fixed` reaches the same method on dev and fuzz.
- **`drop-tvar-mc`, `congruent-never` and `drop-congruence` on dev:** dev never reaches those exits. Fuzz does and catches each one.
- **All 16 C2c plants also fire and are seen in `test_relations_core.py`,** on the corpus (`test_dropped_clause_is_seen`) and on the direct Python-against-Rust comparison (`test_direct_sees_its_plants`). So no moved method rests on a workload alone.

## Direct tests
`test_relations_core.py` and `test_term_ids.py`: 167 passed on pareto1 at 2caa559. `test_session_limits.py`, which isn't in the suite: 242 passed. `relations_direct.py 300 0`: exit 0. What `_direct_c2c` compares, Python against Rust on forged state with maps in insertion order:
- `_add_role`, and `_apply_role` with each kind by each atom shape, twins and terms on and off, plus two KeyError cases.
- `_tsource`, and `_tvar` for each kind, with MC before, between and after SD and EN.
- `_share_guard`, `_congruent` (16 exits), `_congruence_pairs` (9) and `_engage_transfer` (3).
- `_transfer_terms`, `sync_transfer` and `_xswitch` over a really engaged session, with `set_fixed` and `switch` recorded.

Python against Rust can't see both of them taking the same wrong exit, so the answers are also written down in `test_c2c_answers_are_the_ones_written_down`. `test_rust_kinds_are_pythons` pins `SD, EN, MC, IE, IL`, which are hardcoded in the crate, to Python's.

## `link-none` on the suite, by id (the go's item 1)
The plant fired 927,784 times, once on every link call in the suite. **One id moved:** `tests/test_verify_soundness.py::test_fuzz_old_style_symbols`, passed to failed. That makes it a finding, but not one about the link:
- It's a Hypothesis test that isn't derandomized, and each suite run has its own database. The failing case was drawn only in this run: `ask(Q.positive(k), ~(Q.positive(c) | Q.lt(c, c)) & (Q.positive(c) | Q.eq(c, c + k)))` on the shared engine, where `k` is extended-positive and `c` is finite. The test's point checker says `{k: oo, c: I}` refutes True.
- **Replayed directly on orion, the answer is True on Python, on Rust and on Rust with `link-none`,** on a fresh engine and on the shared one (scratch script `ln92.py`; `link:none` 72 of 72 calls under the plant). So `link-none` doesn't change the answer. Under Python the same case fails the same assertion.
- Whether True or the point checker is right isn't settled here. SymPy's evaluation isn't ground truth (issue 247), and the checker's reading of `Eq(I, I + oo)` is what decides it. **For the planner:** a Python-side soundness question in `test_verify_soundness.py`, found by chance, unrelated to C2c.
- The None path counts as settled by this run. The other 6,124 ids are unchanged, and so is the handler multiset.
- Natural `link:none` in the plain suite was 0 this time. C2b's runs had 5 and 88, and the plant suites here had 64 and 123. The join and worker-history account stays "not shown".

## Set order in moved code (the go's item 2)
**Nothing in moved code iterates a set, and no order Rust chooses reaches its output.** This is by reading each moved method, Python and Rust:
- `_xcand`, `_xpart`, `_xpairs` and `_xcounted` are only added to and asked `in`.
- `_xheads.values()`, `grown` and `_xside` are dicts in insertion order. `grown` is a real Python dict in Rust.
- `specs`, the values of `_tsrc`, `_xheads` and `_roles`, `_xpend`, `lterms`, `eterms` and `twins` are lists. `atom.expr` and `args` are tuples. `_number_basis` returns a tuple sorted from a set.
- `th.switch` on Rust (`transfer.rs:116`) returns a `Vec` in the fixed order full then polar, as `transfer.py:166` does. `ad.terms_since` is Python's own on both backends, because `install_euf` replaces `EUFTheory` and not `EUFAdapter`.

So the go's condition for a seed run isn't met. Dev and fuzz were run anyway at `PYTHONHASHSEED=1`, where `_link`'s set differs, and both MATCH with the same answers' sha. That is one seed, an extra, not the seed rerun.

## Callback hash counts (the go's item 3)
Counted as 639abd6 did, with sa-port-86's `qt86.py`, kind `count`, rust arm, which counts `sys.monitoring` starts called directly from Rust. Run on pareto1 under a shared lease, on the tested tree. This is a count, not a timing.

| | 639abd6 | C2c, 2caa559 | ratio |
|---|--:|--:|--:|
| fuzz `Basic.__hash__` | 708,603 | 1,563,962 | 2.21x |
| fuzz `Integer.__hash__` | 207,017 | 615,456 | 2.97x |
| dev `Basic.__hash__` | 43,401 | 73,784 | 1.70x |
| dev `Integer.__hash__` | 8,137 | 22,856 | 2.81x |
| `link:calls`, fuzz / dev | 47,134 / 1,756 at C2b | 81,134 / 2,571 | |

**They rise. Not traced in this session, as ruled.**
- The base 8d6cff7 wasn't counted, so this doesn't split the rise between C2b and C2c.
- The link isn't most of it. The link hashes at most once per call, `link:cross_hash` being 81,134 on fuzz, so its 34,000 extra calls cover at most 34,000 of fuzz's 1.26M extra hashes.
- `Cx::structural` going through the link remains one contributor, unmeasured.

## What's still Python in `relations.py` after C2c (for 5c's list)
By `ast` on the source, minus `_REL_METHODS`. The file is 2,021 lines. The 24 moved methods are 755 lines, and **39 functions and methods, 685 lines, are still Python**, plus the classes `AdapterSpec` and `Uninterpreted` (4 and 3 lines). Lengths in lines:

`Relations.__init__` 86, `Relations.process` 79, `_number_basis` 52, `Relations._eq_links` 48, `_affine_strip` 30, `relation_atom` 29, `glue_objects` 28, `zero_twins` 27, `closed_units` 26, `_under_apps` 22, `link_objects` 22, `_structural_subterms` 20, `default_specs` 19, `_termwise` 17, `Relations._share` 15, `glue_atoms` 12, `sympy_atom` 11, `_terms_of` 11, `_guarded_adapters` 11, `_own_term` 10, `zero_twin` 10, `zero_args` 10, `with_closed_units` 10, `Relations.wants_transfer` 10, `under_of` 9, `_ext_atoms` 7, `Relations._note_sides` 7, `Relations._atom_selector` 7, `Relations._adapter` 5, `Relations.note_formula` 5, `Relations._link_later` 4, `_number_facts` 4, `_constant_term` 4, `_missing` 4, `Relations._atom_var` 4, `relational_name` 3, `_key` 3, `Relations.enqueue` 2, `_is_number` 2.

Several module-level ones, such as `relation_atom`, `_is_number`, `_under_apps`, `_structural_subterms`, `_termwise`, `_ext_atoms` and `glue_objects`, already have Rust counterparts in the term layer (`term:rust:*` counters). Their Python source stays as the reference and the fallback.

## Other checks
- **`py:table` and `custom:own` fell,** as expected once `sync_transfer` reads slots past `_Slots`. On the suite they went from 8,943,939 to 7,672,719 and from 220,941 to 162,438. Only `session.rs` names them, and no digest or test reads them.
- **`term_discard.py`:** none of the moved methods is among its sites. `_eq_links` is, and hasn't moved.
- **Patches:** `tests/test_transfer.py:156-157` (`test_protocol_on_fuzz`) patches `Relations._engage_transfer`, a moved method, and `transfer.TransferTheory`. Both are reached. `_engage_transfer`'s only callers are Python (`relations.py:866` in `note_formula` and `:946` in `process`), with no Rust-to-Rust call, and Rust's `engage_transfer` reads the class at each call. That test fails on base and on C2c alike, from the 46-stub cause, so its outcome shows nothing about the patch. By rg, the only other test in `tests/` that patches a moved method is `test_relations.py:166`, the ruled failure.

## What these comparisons don't reach
- `_bound` on any workload, carried from C2b. `_eq_infinity`'s decided and undecided paths on a workload plant, also carried.
- `_transfer_terms`' two drop plants on dev and fuzz. They're caught on the suite and in the direct test.
- The `Undecided` return in `_order_infinite` has no counter, carried from 5b. `_closed_extended_real`, `_mention_number` and `_link_integer` have no clause-drop plant, also carried.
- Neither dev nor fuzz reaches `compile`'s `Or` arm, carried from 5a.

## For the backend PR list
- **More plants are now bypassed:** Rust-to-Rust calls skip the Python wrappers, so a patch on any of the eleven moved methods reaches nothing. `test_equality_sharing_is_needed_and_works` is still the only test that shows it. `_engage_transfer`'s patch in `test_protocol_on_fuzz` works only because no Rust code calls that method. Re-point the tests or honour the patch.
- **Frames:** more Python frames are gone on the way to `Session.ensure`, so the recursion limit falls later on these paths. `test_session_limits.py` passes, but it doesn't measure where the limit now falls.
- **The hash rise above:** trace it, as the planner's check asks, now that it's shown rising.
- C2b's items stand: the three methods with no drop plant, the three older plants the direct reads bypass, and re-entering the solver from a hook (raises on Rust, and becomes a quiet unknown through `_build_context`).

## Not run
Moved to "before any backend PR", none quoted as met: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control, the boundary rescore and suite column, the final drop score and its lost rows, the suite split with Python's counter, `order:_rows`' evidence (not caught meanwhile), the `_forms` guard test, history and seed reruns, forced moves, the native path, timing.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run.
- **Speed not measured,** and no timing claim made. The hash counts are counts.
- The public-API `test_incremental_matches_fresh` family is still owed, due by 5c.
- Fuzz history for PR 328 and the censuses on the base stay open, so section 8's limits still stand.
- The `_n_conflicts` view in `rust_plugin.py` isn't a port: a test-plugin shim, with the 64 tests it moved.
- `tests/test_solver.py::test_performance_smoke_300_vars` passed on pareto1, no changed outcome.
- No evaluator was asked for.
