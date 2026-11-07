Rust run: 6124 tests; Python run: 6124 tests.

| | tests |
|---|---:|
| Ran on Rust and passed | 5960 |
| of those, made a Rust solver inside the test | 2822 |
| of those, none made inside the test (no solver, or a fixture shared across tests) | 3138 |
| Kept on Python, needs internals | 77 |
| Failed on Rust: re-entry | 46 |
| Failed on Rust: other, failing the same way on pure Python | 0 |
| Failed on Rust: other, passing on Python | 0 |
| Python solvers made in the Rust run | 0 |
| Rust skipped | 23 |
| Rust xfailed | 18 |
| Rust xpassed | 0 |

Python baseline: {'passed': 6083, 'skipped': 23, 'xfailed': 18} 

Tests whose outcome differs between the backends, other than a Rust failure counted above:
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

### Passed after writing a private attribute the crate doesn't have (the write did nothing)
