# Handoff: sa-port-98 to the next 6e session (`knowledge/templates/core.py`, issue 323)

**State:** port/6e head 6abc2f8 (pushed), on rust-slice de8bd3a. The Add family is on Rust under `knowledge_live.install()`.
The Mul and Pow families are not ported yet. Nothing landed. Handed off at my context budget (~110k).

## Done (sa-port-98)

- `solver_rs/src/term/tcore.rs` (new; named `tcore` so it doesn't shadow the `core` crate). Splits over ids:
  `core_coeff_term`, `core_half_split`, `core_bound_split`, `core_recip_base` (`_recip_templates`' shape test),
  `core_imag_term`, `core_imag_split`, `core_is_number` (convert's `F_NUMBER`; refuses on a skeleton node without `F_READ`).
  Rule builders in Python's order: `half_rules:228`, `bound_rules:252`, `recip_rules:274`, `imag_rules:299`,
  `imag_number_rules:324`, `not_unit_premises:332` (returns indices into `_INT_BOUNDS`, so the wrapper hands back Python's own tuples).
  `IS_MUL`/`IS_POW` are defined locally from `convert.FLAGS` (bits 1, 2); `table.rs` is untouched.
- `py.rs:669-`: `core_*` pyfunctions, registered in `register`. `core_kept_product(table, ids)` builds Rust's `mul` and
  checks it is a Mul keeping exactly those factors.
- `knowledge_core_live.py` (new): the wrappers. `install(shadow, counts, fault_cls, mismatch)` swaps names in core, `wiring`
  and `functions` (`swap = {` at :215) and returns the undo. `knowledge_live.py` gains two lines (import, and `undo_core` around
  `term_live.install()`), the only change to that shared file. Counts: `core:<name>`, `core:kept`, `core:no-query`,
  `core:derived`, `core:refuse`, `core:kept_product` (+`:unchecked`, `:mismatch`, which raises TermRefuse), `core:imag_number:python`.
  Templates `_half_templates`/`_bound_templates` stay Python's code and call the swapped Rust rule builders through core's globals;
  `_recip_templates` and `_imag_templates`' signs branch are rewritten in the wrapper over Rust's shape test.
  `_imag_templates`' all-number branch stays Python (builds `Add` of numbers: scaffolding, not yet ported).
- Plants: Python-side `SA_CORE_PLANT=core-half-parity|core-rules-drop-last`; 15 Rust source plants `('core', ...)` in
  `mutate_knowledge.py`, whose unit column now also runs `test_knowledge_core.py`. **The mutant run was not done.**
- `test_knowledge_core.py`: 6 tests, rule builders enumerated against Python (and types, since `_mismatch` compares types). Pass.

## Evidence so far (orion, short runs; not the bar)

Output: `~/sa-rust-ids-work/sa-port-98/`. Python default untouched.
- dev `--limit 400`: shadow 1,333 core compares, 0 mismatches; `core:kept_product` 41, none unchecked or mismatched;
  `core:derived` 11. plain vs atoms MATCH byte for byte.
- fuzz `--limit 300`: shadow 1,957 core compares, 0 mismatches, 0 faults.
- Plants on dev-400, atoms mode against plain: core-half-parity 211 lines differ, 265 shadow mismatches;
  core-rules-drop-last 212 lines, 484 mismatches.
- Not run: full dev/fuzz, the suite, the quiet handler count, the mutant columns, anything on pareto1.

## Left

1. **Mul:** `_mul_factor_sets:325` (calls `ipi_split`, `kept_product` at :346), `_quotient_rules:353`, `_quotient_templates:360`.
2. **Pow/exp:** `_unit_angle:380`, `ipi_split:392`, `pi_split:400`, `_pi_split:406` (kept_product :430), `ipi_rules:476` with
   `_ipi_table_rows:448`/`IPI_GUARDS:435`/`_table:575` as Rust data, `irrational_root:485` (integer_nthroot), `_unit_power_units:498`
   (as_real_imag; decide keep-with-reason or port the Rational branch: 41 suite calls), `_exp_arg:524`, `_pow_bound_templates:533`
   (calls `_bound_split`, `_not_unit_premises`). Call sites: `wiring.py:213`, `:285-335`, `:634-635`; `functions.py:114,129,214,311`.
   Add them to `knowledge_core_live.swap` the same way (functions imports `ipi_rules`, `ipi_split`, `pi_split`).
3. `_imag_templates`' all-number branch (Add of numbers) and `_half_templates`/`_bound_templates`' bodies: decide whether the
   wrapper should own them as `_recip_templates` does.
4. The bar on pareto1 (x86 .so built there): suite by id, full dev and fuzz MATCH, mutant columns (`mutate_knowledge.py --only
   core-...`), quiet handler count, then `bar.sh land` per the rebase rule. `_common` helpers used: `facts`, `const_key`,
   `consts_of` stay Python (6d); none ported.

Import-time list (sa-port-97's trace, `core_trace.py`): `<module>:1` alone, the constants. Runtime items 28; `__getattr__` not one.
Ownership counts for core: before 30 items, UNOWNED; after: not yet. The Add family touches 15 of the 28 runtime items: 6 splits in Rust
(`_half_split`, `_coeff_term`, `_bound_split`, `_imag_term`, `_imag_split`, `_recip_templates`' shape), 6 rule builders in Rust, and
`_half_templates`, `_bound_templates`, `_imag_templates`, whose Python bodies call the Rust rules (key building is conversion).
