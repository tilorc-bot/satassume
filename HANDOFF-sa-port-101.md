# Handoff: sa-port-101 to the next 6e session (`knowledge/templates/core.py`, issue 323)

**State:** port/6e head 22db265 (pushed) + this handoff commit, on rust-slice de8bd3a. All of core's runtime items now run on Rust
under `knowledge_live.install()` except the named Python fallbacks below. Nothing landed. Handed off at ~145k context, 10 minutes
of work in; the bar is what's left.

## Done (sa-port-101)

- `solver_rs/src/term/tcore.rs:356-` (Mul and Pow families): `core_pi_split:373`, `core_mul_factor_sets:405` (derived sets before
  `kept_product`), `core_quotient_shape:424`, `core_unit_angle:446`, `core_exp_arg:461` (exp is `Kind::Function` with class name
  `exp`), `core_irrational_root:474` (exact BigInt roots, `exact_root`), `core_pow_bound_shape:488`, `core_unit_power_units:498`
  (Rational exponent only), free fns `unit_power_units`, `quotient_rules`, `pow_bound_rules`, and `IPI_TABLE:569` (Rust data,
  slots S/N, guards `CWhen`) with `ipi_rules:597`.
- `py.rs:770-` (`core_rest`, `core_pq`, 11 pyfunctions from `core_pi_split:798`), registered in `register`.
- `knowledge_core_live.py`: wrappers `pi_split_:240` ... `pow_bound_templates:353`, added to `swap` at :399. `_pi_split` is swapped
  in core, so `ipi_split`/`pi_split` (Python one-liners) and `functions._pi_trig`'s default `split_=pi_split` reach Rust.
  `ids_of:65` now gives a derived Add/Mul a row through `term_live.term_id` (`core:derived:id`), and results map back through
  `term_live.scaffold` (`obj`). Per-function fallback counts `core:derived:<name>`. `pure:49`: shadow reference = Python's code over
  Python's own helpers (copies of core's functions over a copied globals dict), used for `_mul_factor_sets`.
  Python-side plants added: `SA_CORE_PLANT=core-pi-coeff|core-mul-drop-ipi` (`core-rules-drop-last` also covers `ipi_rules`).
- `knowledge_core_wl.py` (new, 1,572 queries, `knowledge_fresh.py core`): reaches `ipi_rules` and `_unit_power_units`, which
  dev-400 and fuzz-300 never reach. `mutate_knowledge.py`: 15 new Rust plants (`core-pi-split-second-i` at :90 onward); its `off`
  column scores `core` when `PLAIN/core-plain.tsv` exists. `test_knowledge_core.py`: `test_mulpow_rule_builders` (7 pass).

## Evidence so far (orion, short runs, shadow mode; not the bar). Output: `~/sa-rust-ids-work/sa-port-101/`

- dev-400: 0 mismatches, `shadow:core` 1,844; `core:derived` 0, `core:derived:id` 103; Mul/Pow wrappers fire (mul_factor_sets 366,
  pow_bound 47, irrational_root 45, exp_arg/unit_angle 47, _pi_split 4).
- fuzz-300: 0 mismatches, 0 faults, `shadow:core` 2,587.
- core wl: 0 mismatches; ipi_rules 708, _unit_power_units 90 (Rust), `core:unit_power:python` 75, _pi_split 1,092, irrational_root
  171, pow_bound 644, quotient 2,699, `core:kept_product` 1,343 (scaffolding, checked against Rust's `mul`).
- Not run: atoms-vs-plain MATCH on anything, the Python plants, the mutant columns, the suite, quiet handlers, full dev/fuzz, pareto1.

## Kept on Python, named (counted)

- `_unit_power_units` for a non-Rational exponent (`core:unit_power:python`): needs SymPy's `as_real_imag` of a closed number
  (`I`, `1+I`, `pi`, `sqrt(2)`); keep with reason, or port the `c*I`/`r + c*I` forms if the planner wants.
- `_imag_templates`' all-number branch (`core:imag_number:python`): builds an `Add` of numbers. Proposed: keep with reason.
- Derived Adds whose args have no row (`core:derived:_half_split|_bound_split|_imag_split`, 78 each on the core wl).
- `_half_templates`/`_bound_templates` bodies stay Python and call Rust's rules (key building is conversion).
- `facts`, `const_key`, `consts_of` (`_common`, 6d's): none ported. `table.expand`/`Row`: no longer called by core at runtime on
  the Rust path (IPI_TABLE is Rust data), only by the shadow and the fallback.

## Left

1. Plain and atoms on dev-400 and core wl on orion, byte compare (MATCH); Python plants `core-pi-coeff`, `core-mul-drop-ipi` caught.
2. On pareto1 (build the x86 .so there, `~/sp19/p1_job.sh`): suite by id (three numbers, handler_count on), full dev and fuzz atoms
   vs plain MATCH, `mutate_knowledge.py WORK PLAIN --only core-...` (needs dev/fuzz/value/core-plain.tsv in PLAIN; report void
   plants with a direct test standing in), quiet handler count with a planted raise shown firing.
3. Rebase on origin/rust-slice per the rebase rule (check whether the wiring step landed; then dev/fuzz MATCH on the default Rust
   backend and the `rows_kept` guard rules apply), `bar.sh land` (on origin/port/5c 1b97a5a until 5c1 lands; `git show` it), report.
4. Ownership after: core's 30 items: 28 runtime (sa-port-97's trace), all ported except the fallbacks above; `<module>` import-time;
   `__getattr__` not runtime; `_table`/`_ipi_table_rows`/`IPI_GUARDS` moved as Rust data.
