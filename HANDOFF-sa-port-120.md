# Handoff sa-port-120 (step 6g, issue 323)

Branch port/6g on origin/rust-slice 7e2ece0 (6f). No code changed yet; this file is the only commit.

## Done so far
- Step 0, count rule, reported (journal 592d001, Status: progress): core.py fails (4 per-node Python shells:
  `_half_templates` core.py:120 and `_bound_templates` core.py:183 called per Add node from wiring.py:668, :671;
  `ipi_split`/`pi_split` core.py:392, :400 called from wiring.py:133, :292 and functions.py:114, :317). So 9 of 32 on the
  brief's reading. Applied to physics and stats too (`quantity_units` physics.py, `randomsymbol_units` stats.py:22, each a
  per-class template calling Python `_common.units` _common.py:340, which no live file swaps), 7 of 32. Recommended 7.
- `_rows_runtime` field: decided, no extension, so no planner question. Fire counts on 6f's bar rows (pareto1
  `~/sp19/sa-rust-ids-work/sa-port-116/{live,extra}/*-rust.knowledge.json`): `rows:value:python:Pow:I` and `:-I` fire 1
  each per process on every workload (dev, fuzz, f6, value, rootof, core): read once when Pow's generator is built
  (knowledge_live.py:405-417, rows.rs:418-432), not per query. `rows:constant_value:python` 0 on dev and fuzz, 1 on the
  core wl (`Zero:1/number`); Float 0 on dev, fuzz and the four workloads. I is algebraic (I**2 = -1); rows' `Num::E`
  (rows.rs:275) and constfield's `Poly` treat constants as independent generators, so I isn't exact there without a
  reduction step: not small. Floats stay on Python by the planner's default (SymPy precision). Report both as "kept on
  Python with reason".

## The per-node path today (what 6g moves)
- engine.py:577-578 `_visit`: `engine.clause_templates(node)` per node, Python. Set at engine.py:1318-1346 to
  `registry.clauses_for`, wrapped by `relations.with_closed_units` (relations.py:423, 5c5's file: don't edit it; if 6g
  changes what it wraps, name it) when lra is on.
- registry.py:226 `clauses_for`: memo `_clauses_cache` by expr; `opaque` = `_applied_to_nan` (__init__.py:162, with
  `_may_be_nan` :142 and `_SPECIAL` :139); `templates_for(type(expr))` registry.py:194 (per-class memo, `_redefines`
  :62 is conversion); each template's result split by `_split` registry.py:265 (Compiled, plus `wide_formulas` when
  `pattern.wide`, plus plain formulas). `_adopt_memo` registry.py:281-282.
- Templates mostly end in `_common.facts(key, gen, consts, objs, node)` _common.py:325 or `units(key, gen, obj)` :340,
  over `consts_of` :399 and `const_key` :50 (6d's; port only what 6g's path needs and say which). `Compiled`
  _common.py:287 has slots `objs`, `pattern`; its consumer is engine.py after :578.
- wiring.py families: `power` :223 (template :275, ipi_split :292, `_pow_bound_templates` :335), `any_arity` :539 /
  `rows_block` :565 / `rules_for` :596 / `_wide_of` :558 / `wide_formulas` :489, `product` :620, `addition` :650
  (half/bound/recip/imag at :656-:671), `piecewise_values` :349, `expand` :381, `_placements` :417, `_allowed` :440,
  `_instances` :453, `_declared` :176, `_attributed` :186, `matches` :196. Ownership rows: port-ownership.tsv 243-306.
- Atoms' no-query path: knowledge_live.py:209-215 (`term_live.current()` None, `py:no-query`, tests calling Engine
  directly: 6e's `core:no-query` suite 49,237, 6f's `f6:no-query` 3,305). Also `py:kept` :216 (kept queries stay Python by
  ruling). term_live.py:73-98 is the per-query table (`table`, `ids`, `objects`, `kept`).
- Shells to finish: core's 4 above; 6f's 9: functions.py:41 `_unary`, :100 `_exp_ipi`, :150 `parts_of_round_templates`,
  :214 `_pi_trig`, :328 `_cosh_shift`, :360 `nary`; special.py:88 `multigamma_templates`; nodes.py:30
  `accumbounds_templates`; rootof.py:45 `crootof_units`; plus the per-class `units(...)` wrappers physics.py
  `quantity_units`, stats.py:22, nodes.py:37 `idx_units`.
- Install points: knowledge_live.py:196 `install` (atoms swap :452-461, core :464, f6 :466); knowledge_core_live.py:423-448
  (swap dict, `undo`); knowledge_f6_live.py:107 (swap :305, meta_path hook :353-361). Rust: term/py.rs:570-606
  (`Knowledge.symbol_units`, `constant_units`, `units`, `resolve`), term/knowledge.rs:178, :303, term/tcore.rs, term/tf6.rs.

## Proposed design (not started; check by running, not reading)
1. A Rust `Knowledge.clauses_for` that the engine calls directly (`engine.clause_templates` set to the bound pyo3 method,
   so no Python wrapper in registry/wiring runs per node). It finds the node's id in the current query's table, runs the
   opaque check on the term tree, dispatches by class to Rust templates, and builds `Compiled` objects without running
   `Compiled.__init__` in Python. Per-class template lists are handed to Rust once at install (registration stays Python,
   import-time). A class with any unported template calls back the Python template, named and counted
   (`registry:python:<name>`).
2. Order: opaque + dispatch + atoms (incl. no-query, by converting the lone atom into a one-off table) first, then the rows
   families (any_arity/product/addition/power), then the core and 6f shells. Land in parts if the bar allows; each part
   with its own plants.
3. Bar per port-6f.md; the extra workloads in live.py; a hidden-gap workload for any moved item at 0.
