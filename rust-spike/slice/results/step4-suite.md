Rust run: 6124 tests; Python run: 6124 tests.

| | tests |
|---|---:|
| Ran on Rust and passed | 5949 |
| of those, made a Rust solver inside the test | 2820 |
| of those, none made inside the test (no solver, or a fixture shared across tests) | 3129 |
| Kept on Python, needs internals | 77 |
| Failed on Rust: re-entry | 46 |
| Failed on Rust: other, failing the same way on pure Python | 11 |
| Failed on Rust: other, passing on Python | 0 |
| Python solvers made in the Rust run | 0 |
| Rust skipped | 23 |
| Rust xfailed | 18 |
| Rust xpassed | 0 |

Python baseline: {'passed': 6070, 'xfailed': 18, 'skipped': 23, 'failed': 13} 

Tests whose outcome differs between the backends, other than a Rust failure counted above:
- `tests/test_solver.py::test_performance_smoke_300_vars`: Python failed, Rust passed
- `tests/test_wide_derived.py::test_wide_derived_or_against_or_is_fast[nor-or]`: Python failed, Rust passed
Only in one run: [] 

### Needs internals, by file and reason
- `test_solver`: `_held`: 3
- `test_solver`: `_lazy`: 3
- `test_solver`: `_rbc`: 1
- `test_solver`: `provenance`: 4
- `test_solver`: `subclass override of _rb_reason`: 3
- `test_solver_incremental`: `_held`: 10
- `test_solver_incremental`: `_ok`: 4
- `test_solver_incremental`: `_rb_n`: 7
- `test_solver_incremental`: `_ring_hit`: 1
- `test_solver_incremental`: `_trail_lim`: 14
- `test_transfer`: `_solve`: 1
- `test_verify_integration`: `_trail_lim`: 1  **NOT in the handoff's list**
- `test_writeback_provenance`: `_cowner`: 1  **NOT in the handoff's list**
- `test_writeback_provenance`: `provenance`: 2  **NOT in the handoff's list**
- `theory_harness`: `_trail_lim`: 5
- `theory_harness`: `_val`: 17

Handoff files with none: ['test_lra_integers']

Kept tests not passing on Python in the baseline run: []

### Re-entry, by the last test frame before the raise
- `tests/theory_harness.py:242`: 41
- `tests/test_euf_fuzz.py:555`: 1
- `tests/test_euf_fuzz.py:574`: 1
- `tests/test_lra_fuzz.py:212`: 1
- `tests/test_lra_fuzz.py:200`: 1
- `tests/test_theory_hooks.py:217`: 1

### Other failures, passing on Python

### Other failures, failing the same way on Python
- `tests/test_compiled_rows.py::test_the_compiled_rows_are_up_to_date`
- `tests/test_compiled_rows.py::test_the_compiled_rows_do_not_depend_on_the_hash_seed`
- `tests/test_layering.py::test_new_name_import_enters_the_old_name`
- `tests/test_layering.py::test_old_name_first_loads_no_second_module`
- `tests/test_layering.py::test_old_name_is_a_package_attribute[euf_adapter]`
- `tests/test_layering.py::test_old_name_is_a_package_attribute[lra_adapter]`
- `tests/test_layering.py::test_old_name_is_a_package_attribute[lra_bounds]`
- `tests/test_layering.py::test_old_name_is_a_package_attribute[templates]`
- `tests/test_memos.py::test_memo_registry_lists_every_owner`
- `tests/test_sympy_boundary.py::test_runtime_trap_corpus`
- `tests/test_trig_rows.py::test_show_rows_lists_each_row_with_its_source`

### Passed after writing a private attribute the crate doesn't have (the write did nothing)
