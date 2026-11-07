# Handoff: sa-port-45, component 6, `_common` next (issue 323)

`atoms.py` landing is in `rust-spike/slice/results/port-6b.md`. What's left is `_common.py`. The Rust half is written and builds, on its own branch, and has never run.

## Next steps

1. Rebase `origin/port/6b-common` (e330f28: Rust only, nothing calls it) on `origin/rust-slice`, and work on `port/6c`.
2. Wire it in `knowledge_live.install()`: replace the globals `_common.resolve` and `_common.Pattern`. `facts()` and `units()` call both through module globals (`_common.py:332`, `:386`), so no template changes and every template in the engine goes through Rust. `facts`, `units` and `_CACHE` stay Python.
3. Wrappers, as designed and not yet written:
   - `resolve(rules, consts)`: `slots = [k for k, c in consts.items() if c is not None]`, `read = lambda k, p: const_value(consts[k], p)`, `r = kn.resolve(rules, slots, read)`. `None` means raise `ValueError("template asserts a contradiction")`. `TermRefuse` becomes `KnowledgeFault`. Anything the read raises passes through as itself, which is parity.
   - `Pattern(rules, node, nobjs=1)`: `Pattern.__new__`, set `rules` (the object passed), `node`, `nobjs`, `complete=False`, then `clauses, used, child_preds, wide_idx = kn.build_pattern(rules, node, _common.MAX_EXPAND)`, and `wide = [rules[i] for i in wide_idx]`. Read `MAX_EXPAND` at call time.
   - `gen()` may return a non-list: materialize it before the shadow runs Python's `resolve` as well.
   - `_wrap` holds the `Pattern` class by name from import, so it survives the swap. `undo` must restore both globals.
4. Test: `test_knowledge_common.py`, seeded random rules against Python's `resolve` and `Pattern` by field, plus hand cases: contradiction, undecidable constant literal, repeated premise, wide at and past `MAX_EXPAND`, empty clause, unknown predicate (`KeyError`).
5. Plants, in `mutate_knowledge.py`: subsumption dropped, contrapositive sign, wide limit off by one, sort order of a clause. These should finally show on dev and fuzz, because every template goes through them.
6. Landing as in `~/sa-rust-ids-work/sa-port-45/jobs/`: `setup45.sh`, `fresh45.sh TAG [plants]`, `suite45.sh TAG`.

## Not `_common`'s first step

`lits`, `Rules`, `ge2_alternatives`, `consts_of`, `pattern_key`, `const_key` feed Python templates and move with them. `instantiate` and `Compiled.formulas` build SymPy formulas and move with the engine. Don't count `_common` until these are done or ruled out.

## For `functions.py`'s unary port (planner's answer to report 9e46d2b)

The offline table lands there, with no closure swap in `knowledge_live`. `_unary` captures `units` when wiring loads (`functions.py:41`, `wiring.py:144`). Rust doesn't parse the file's `value_units` section yet. `test_knowledge_value_units.py::test_offline_table_holds_what_value_units_computes` already holds the table to today's `_value_units`. Keep the workload `knowledge_value_wl.py` (`knowledge_fresh.py value`) with that port.

## File:line map

| Topic | Where |
|---|---|
| Wiring | `rust-spike/slice/knowledge_live.py`: `install`, `rust_compiled`, `_bind_value_units`, `_wrap` |
| Rust, on `port/6b-common` | `solver_rs/src/term/knowledge.rs`: `resolve`, `unsubsumed_clauses`, `Rules::expand_clause`, `Rules::build_pattern`. `py.rs`: `PyKnowledge.resolve`, `.build_pattern`, `extract_rules` |
| Python being ported | `_common.py`: `_resolve_lit:104`, `resolve:121`, `_unsubsumed:185`, `Pattern.__init__:236`, `facts:325`, `units:340`; `rules.py`: `cnf_of:207`, `expand_clause:270` |
| Direct users of the Python names | `tests/test_rows_nary.py:21`, `tests/test_wide_derived.py:134`: they hold Python's by import, which is fine |
| Fresh, plants | `knowledge_fresh.py WL OUT --mode plain/atoms/shadow/discard`, WL includes `value`; `mutate_knowledge.py` |
| Suite | `SLICE_KNOWLEDGE=atoms bash run_suite.sh WORK rust -p knowledge_suite tests`; by-id compare against `~/sa-rust-ids-work/sa-port-45/atoms1/suite/rust` |
| Offline file | `offline_data.json` holds one JSON document per line, so `json.load` fails on it |
