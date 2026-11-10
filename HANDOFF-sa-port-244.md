# HANDOFF sa-port-244: formula step (issue 323), fourth part

Branch `port/formula`, head = this commit, on rust-slice 0192b35. **Unbarred, unlanded.** Handed off at the context
budget, **between gate items**: item 1 is done as far as it can be before state part 3 lands; items 2 to 5 are not started.

## Done (details: rust-spike/slice/results/cbm-noid-cause.md, last section)
1. Gate 1 (b): test_term_live.py, test_handler_count.py, test_catch_count.py, test_cf_diff.py fail the same way, same
   ids, on the base build 0192b35. Base failures; no owner yet.
2. Gate 1 (c), ruling Q1:
   - (a) rule named; plant 662 `ad-lra-atom-object` fires and is caught by test_cbm_noid.py.
   - (b) wiring.py `matches` 'same' and the Pow key compare by `==` (**reference change**); rows_tpl.rs `same_term` the
     same rule; counter 672 `same:eq`; offline_data.json regenerated (header hash only). **0 answers changed**: 16
     workloads Python base against new, and 0 probe events in `tests` on both backends. Plant 663 `same-is` is **void by
     R12** (such queries are kept, so wiring.py answers them under Rust too); the reference with `is` fails the new test.
   - (c) cache-store key test passes on both backends, **but through `is_(u, 'extended_real')`; relations.py:1116 itself
     was not reached by any crafted query**. Footnotes for engine.py:1722 and relations.py:1657 written.
3. Gate 1 (d): workload `cls` (cls_wl.py, `live.py cls`) reaches `cls:eq` 174 and MATCHes. **Plants 660, 661, 662 fire on
   it and livecmp still MATCHes**: seen only by `ad:cbm_noid` (0 to 264) and by test_cbm_noid.py. Footnote written;
   whether a nonzero `ad:cbm_noid` on `cls` becomes a bar verdict is a question for the planner.

## Not done
- Gate 1 (a): `twin_row` / plant 409 / `rk:twin` removal and the three tests, after state part 3 lands and this branch
  rebases. Known failures until then: test_rs_core.py::test_two_equal_function_classes_key_as_one,
  ::test_class_split_plant_is_caught, test_relations_core.py::test_join_second_object_resolves_on_its_own.
- A query reaching relations.py:1116, or a footnote ruling for it.
- Gate 2 (`_CACHE` fix), 3 (the entry converts once; `fm:nosession` is 159 on `cls`), 4 (term_live fallback cause),
  5 (D, E; plant 602; plants 604/605). The bar, after state part 3.
- Not run at this head: dev, fuzz and the other workloads on Rust (only `cls`); the 50 slice files one by one (7 near
  the change pass: test_formula_nodes, test_knowledge_rows, test_knowledge_core_shapes, test_knowledge_wire,
  test_lra_slot, test_cbm_noid; `gen_offline_data.py --check` same); the Rust suite's failed ids against the base's rows
  (count 127 equals the base bar's).

## File:line map (at this head)
- formula.rs: counters `NAMES` :61 (630-644, 670-672), plants `PLANTS` :98 (601-606, 660-663), `plant_set` :142,
  `atom_object_set` :147, `same_eq_met` :158, `class_is_planted` :164, `same_class` :173, `class_is_plant` :205,
  `formula_plant` :537. The rest of the file is HANDOFF-sa-port-243's map plus about 30 lines after :130.
- rows_tpl.rs: `same_term` :761, `same_value` :775 (not edited), 'same' shape :788, Pow key :934; the other `same_class`
  sites about 18 lines below HANDOFF-sa-port-243's numbers.
- adapters.rs: plant 662's copy of the rows :152, `Reader.id` :321, the plant's swap :328-331.
- wiring.py (satassume/knowledge/templates): 'same' :222-225, Pow key :325. convert.py R12 :214-215.
- test_cbm_noid.py: `_not_first` :149, plant 662 test :174, `_twins` :193, `_same_base` :213, `==` test :227, plant 663
  void test :240, cache-store test :255. cls_wl.py; live.py `cls` :276. same_eq_probe.py (pytest `-p same_eq_probe`, or
  `SAME_EQ_OUT`).
- Items 2 to 4: the brief's map is unchanged (knowledge_live.py rust_compiled :258-295, _common.py:345, common.rs:404-444,
  scope_core.rs :259/:291, budget.rs :61/:373/:465-466, session.rs lines as in HANDOFF-sa-port-234.md).

## Watch
- Runs: `~/sa-rust-ids-work/sa-port-244/` (`q1/wl/summary*.txt`, `q1/suite-python`, `q1/suite-rust`, `cls/`,
  `base-slice/`, `slice-head/`; `q1job.sh`, `q1job2.sh`). **Nothing is running detached.**
- Two worktrees of this clone hold builds: `~/sa-rust-ids-work/sa-port-244/base` (0192b35) and `.../q1tree` (17241af).
  `git worktree remove` them when not needed.
- A wiring.py edit needs `gen_offline_data.py` rerun, or Rust refuses the offline file at load.
- test_formula_nodes.py fails with "knowledge_live is already installed" if run under run_suite.sh's plugin; run it plain.
- Plants 664-669, 607-629 and counters 673-679, 645-659 are free.
