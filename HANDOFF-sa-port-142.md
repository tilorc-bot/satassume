# Handoff sa-port-142 (step 6g(b), issue 323)

Branch port/6g, head 66615fa (WIP, pushed), on rust-slice 6526445 (6d's report). 6g(b) is part done and not at the bar;
6g(c) is not started.

## Done (66615fa)
- `rust-spike/slice/solver_rs/src/term/rows_tpl.rs` (new): `RowsTpl`, wiring's `any_arity` (with `piecewise_values` for
  Piecewise), `product`, `addition`, and what they call per node: `rows_block` (`block`), `rules_for`, `matches`,
  `expand`, `_placements`, `_allowed`, `_instances`, `_clauses`, `_wide_of`/`wide_formulas`/`_wide`. The family's
  `gen.terms/specs/schemas` are read once per class entry (`RowsTpl::from_template`). `block` calls 6d's `Common`
  (`consts_of`, `pattern_key`, `facts`) and hands `facts` a Rust `PyCFunction` closure as `gen`, so the rules are built
  only for a new pattern, mutating the same `consts` dict Python's lambda does.
- Still called back, named and counted `rows:python:<name>`: `constant_value` (through `wiring.constant_value`, the
  `_rows_runtime` swap), `const_value` (6d's named callback), `Integer(len(rest))` for `count`, and the core pieces
  (`_mul_factor_sets`, `_quotient_templates`, `_half_split`, `_half_templates`, `_bound_split`, `_bound_templates`,
  `_recip_templates`, `_imag_split`, `_imag_templates`), looked up in `wiring`'s namespace per call: 6e's shells, 6g(c).
- dispatch.rs: `ClassEntry.templates` is `(template, counter, Tpl)`; `Tpl::Rows` for a built-in template carrying
  `_satassume_rows` (counter `registry:rust:<name>`), else `Tpl::Python` (`registry:python:<name>`). A kept query, or
  Common not installed, runs the Python template (`registry:kept:<name>`). `dispatch-rows-off` is a control switch
  (every rows template back to Python), not a plant.
- common.rs: fields `kn`, `max_expand`, `const_value`, `ctors`, `plant` and methods `kept`, `fired`, `bump`, `facts`,
  `consts_of`, `pattern_key` made `pub(crate)`; `set_plant` accepts rows_tpl's PLANTS. knowledge.rs: `cnf` pub(crate).
- wiring.py: `template._satassume_rows = (family, tag, gen, piecewise, leave_out_wide)` set at import in `any_arity`
  (only when `arguments` is None or `piecewise_values`), `product` ('mul'), `addition` ('add'). Import-time only.
  offline_data.json regenerated (`gen_offline_data.py`): wiring.py's source hash only, body_sha256 unchanged 9af6963e.
- knowledge_common_live.py `PLANTS` += the 14 rows plants (rows_tpl.rs `PLANTS`, one per moved function; list there).
- Dev first 400 queries: MATCH (answers_sha 4230081d83335ca9 both). Counts there: registry:rust:add_rows_templates 18,
  mul 25; rows:block 50, rules_for 19, matches 261; Max/Min/Piecewise and wide (n > 32) not reached in those 400.

## Running when I stopped (detached, orion, not mine to wait on)
`~/sa-rust-ids-work/sa-port-142/reach1/` (`run.sh`, pid in `pid`): py vs rust, full, on dev, opaque, core, f6, then fuzz,
value, rootof. Ends with `done.txt`. Per workload: `<wl>-cmp.txt` (livecmp, MATCH/DIFFER), `<wl>-rust.knowledge.json`
(`counts`: `registry:rust:*`, `rows:*`). Script: scratchpad short.sh, copied into the NEXT brief below.
Read it to find which moved items are at 0 on every workload (likely: `rows:wide`, `rows:wide_formulas`,
`rows:piecewise_values`, `rows:clauses`, `registry:rust:Max_rows_templates`/`Min`/`Piecewise`). Those need a hidden-gap
workload (live.py:273 tuple, `knowledge_<name>_wl.py`, modelled on knowledge_opaque_wl.py).

## Left
1. 6g(b): read reach1; the `power` template (wiring.py:223-346, `pow_templates`: `_exp_arg`, `ipi_split`, `_unit_angle`,
   `const_key`, `Mul(c, a)`/`a + c` scaffolding, `ipi_rules`, `irrational_root`, `_unit_power_units`,
   `_pow_bound_templates`) as a fourth `Family::Power` in rows_tpl.rs (`matches` needs 'head' via `_exp_arg` then);
   the hidden-gap workload; run each rows plant on the workload that reaches it and show it caught; the 6d plants owed
   here (equiv-one, ge2-drop, wide-drop: say whether 6g(b)'s Rust code calls `Rules.equiv`/`ge2_alternatives`/the
   wide formulas at run time; rows_tpl.rs doesn't call `equiv` or `ge2_alternatives`); the bar; land; report.
2. 6g(c): the shells (core.py:120, :183, :392, :400; functions.py:41, :100, :150, :214, :328, :360; special.py:88;
   nodes.py:30, :37; rootof.py:45; physics.py `quantity_units`; stats.py:22), landed at the bar.
3. Module count after each part, with a call trace as port-6g.md did.

## Notes
- The Rust template returns the same shapes as Python's (`block`, a list, `()` for no args, None for Piecewise without a
  final True) and Dispatch's `split` flattens them.
- `product` with an empty `_mul_factor_sets` returns `[]` where Python's `out[0]` would raise IndexError; not seen.
