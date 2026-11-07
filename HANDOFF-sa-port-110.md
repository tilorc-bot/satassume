# Handoff: sa-port-110 to the next 6f session (functions, special, rootof, nodes, physics, stats; issue 323)

**State (7 Nov 23:47 UTC):** port/6f on rust-slice 2540ca7. Done: the trace (scope item 1) and a workload that
reaches every item. No Rust yet. Handed off at about 130k context to leave room for the port.

## Done
- `rust-spike/slice/f6_trace.py`: per-qualname call counts for the six modules, import vs runtime. `python f6_trace.py WL OUT`
  (dev, fuzz, value, rootof, core, f6), or `pytest -p f6_trace` with F6_TRACE_OUT=dir (suite: not run yet; run it on pareto1
  with the bar's suite, or alone, for the report's suite column).
- `rust-spike/slice/knowledge_f6_wl.py` (+ `knowledge_fresh.py f6`): AccumBounds, Idx, Quantity, RandomSymbol, asin/acos of
  constants, cosh(r + I*pi*c*s), sin/cos(pi*c), re/im of floor/ceiling, cancelling-Add shifts, n-ary rows.
- `results/port-6f-trace.md`: the classification and the call table (read it; it's the evidence for scope item 1).
  Import time is `<module>` alone. fuzz reaches none of the six; dev reaches functions.py only. `special._register` is dead
  (no caller). `_value_units` offline by ruling. Factories (`_unary`, `nary`, `_pi_trig`, `_exp_ipi`, `_cosh_shift`,
  `_genocchi_half`, `_in_unit_interval_units`) run once per class per process: propose Python shells, inner parts swapped.

## Map (file:line)
- Python: functions.py `_unary` :41 (template :49), `shifted` :84, `_exp_ipi` :100, `_parts_of_round_rules` :143,
  `parts_of_round_templates` :150, `_pi_trig_rules` :177, `_pi_trig` :214, `_in_unit_interval_units` :247, `_cosh_shift_rules`
  :280, `_cosh_shift_split` :302, `_cosh_shift` :322, `nary` :354, `_value_units` :398, `_genocchi_half` :412. special.py
  `_doubled` :56, `_multigamma_rules` :66, `multigamma_templates` :88. rootof.py `_coefficients` :22, `_facts` :31,
  `crootof_units` :45. nodes.py `_accum` :22, `accumbounds_templates` :30, `idx_units` :37. physics.py :22. stats.py :22.
  wiring.py :124-148 builds the templates (imports the factories by value inside the function, so swap `functions.*` before
  a class's first build, or swap the module globals the templates call: `_pi_trig_rules`, `_cosh_shift_rules`,
  `_cosh_shift_split`, `shifted`, `_parts_of_round_rules` are looked up as globals at call time; `_genocchi_half.half` is a
  closure and isn't).
- The model, 6e: `knowledge_core_live.py` install :60, `query` :68, `ids_of` :79, `obj` (scaffold) :97, `call` :100,
  `fallback` (named callbacks, loud) :110, `rules` wrapper :238, `swap` :423, module patching :440; `_hit` plants :42.
  Wired from `knowledge_live.py` (install :193; `rust_value_units` :244; `rust_root`/realroots :327, `_bind_realroots` :152,
  `ROOT_FACTS_CALLER` :50). Rust: `term/tcore.rs` (Rule :23), `term/py.rs` core_* pyfunctions :740-900, registration :900.
  `term_live.py` `current` :112, `term_id` :269, `scaffold` :307. `sa_solver.realroots_root_facts` exists (realroots.rs:282).

## Proposed port (decide by running, not more reading)
1. Rule builders as pure Rust over small ints/rationals, swapped with 6e's `rules` wrapper: `_pi_trig_rules` (cos_, c p/q,
   has_s), `_cosh_shift_rules` (c parity, has_s), `_parts_of_round_rules`, `nodes._accum`, `_multigamma_rules(p)`'s build,
   `_genocchi_half`'s two rules (move them into a module-level function first, or swap the factory before wiring builds).
2. Splits over the query's table: `_cosh_shift_split` (per term `core_pi_split(imag=True)`, the #184 rebuild check),
   `shifted` (Rust add with the same guard; scaffold the SymPy object, counted), `_doubled`. The templates (`_unary`, `nary`,
   `_pi_trig`, `_exp_ipi`, `_cosh_shift`, `parts_of_round`, `multigamma`, `accumbounds`) become shells: the arity check, const
   flags and slot ids from Rust, keys by `const_key` and `facts` stay Python (6d). Name every `_common` helper used: so far
   `facts`, `units`, `const_key`, `pattern_key`, `consts_of`, `Rules` (all stay for 6d; none needed porting yet).
3. Units: `_in_unit_interval_units` on p/q in Rust; Float a named callback with the reason (planner's default for Floats).
   `idx_units`/`quantity_units`: Rust constants under `units`. `randomsymbol_units` reads declared symbol facts and
   `pspace.is_real`: input reading, propose as conversion. `crootof_units`: `_coefficients` is the input read (conversion);
   `_facts` on `realroots_root_facts`, which reaches realroots' Rust side on the rootof wl (the realroots footnote: show a
   realroots plant fires and is caught there). `multigamma`'s `expr.func(x, p)`: a named SymPy-semantics callback; its
   `value_units` call reaches atoms' Rust `value_units` (the value_units footnote: count it on the value wl under install).
4. Plants: one per moved function (Rust mutants in `mutate_knowledge.py`, Python `_hit` plants), caught by plain vs install
   on dev/value/rootof/core/f6; crafted shape tests for any the workloads miss, as test_knowledge_core_shapes.py.

## Ownership counts (for the report)
Before (port-ownership.tsv on 2540ca7): 27 rows: functions 14 (13 `port` + `_value_units` offline), nodes 3, physics 1,
rootof 3, special 4, stats 1; 26 `port`, all Python, owned by 6f. Proposed reclass: `special._register` not port (dead),
`randomsymbol_units` and `rootof._coefficients` conversion (ask the planner in the report).
