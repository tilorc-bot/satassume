# D "adapters cost": timing, C3 conditions, bar (sa-port-288, tested 42fd78e)

Items C1, C3, C5 in solver_rs/src/adapters.rs (sa-port-287, 42fd78e on rust-slice 50f1421). Test-only: miss_count.py and test_miss_count.py.

## Group D, pinned (pareto1, bench-container CPU 2, quiet lease, 7 interleaved rounds per cell)
go288.sh resumed sa-port-287's chain from the post step (287's had no nm tables; copied from sa-port-285/gd/nm).
End marker "END done 0 2026-11-11T12:58:33Z"; table: gd-adapters-cost-med-r1.md (28 rows, **digest mismatches 0**).

| | dev base -> head | fuzz base -> head |
|---|---|---|
| Rust median s | 0.767 -> 0.763 | 6.536 -> 6.451 (-0.085) |
| Group D s (sampled share x median) | 0.191 -> 0.190 | 2.191 -> 2.205 |
| adapters.rs s | 0.007 -> 0.007 | 0.222 -> 0.204 |
| python / callback s | 0.357 / 0.071 -> 0.355 / 0.071 | 1.312 / 1.114 -> 1.274 / 1.042 |

The gain is in wall time, not in D's sampled share: the swallowed AttributeError (C1) and the import machinery (C5) ran
in CPython's C code, which the sampler books under python/callback, not under Rust frames.

## C3 conditions (planner's ruling, 12:54Z 11 Nov)
(a) The reused verdict (structural) and args are not keyed in a table. Each is carried in the stack entry (e, Some(kids))
of one intern_into call and dropped when that entry is popped: they live per intern call. (b) e and kids are
Bound<PyAny>, strong references held for the entry's whole lifetime, so no address can be reused. (c), (d) are moot (per
intern call, strong references, no table outlives the call). Plant 471 (stale args from the previous entry) is caught by
test_miss_count.py anyway. No fix needed.

## Why handler_count missed C1
handler_count.py counts sys.monitoring EXCEPTION_HANDLED events in two code objects only (_build_context, _consistent).
C1's raise was built and cleared in Rust: pyo3-ffi 0.30.1 src/compat/py_3_13.rs:185-203 on Python < 3.13 runs
PyObject_GetAttr then PyErr_Clear on AttributeError, so no Python frame handles it and no event fires. miss_count.py
(test-only) counts module-attribute misses; instance-attribute misses taken in Rust are still unseen (needs a C-level hook).

## Plants
| plant | site | caught by |
|---|---|---|
| 470 ad-swallow | py_class: a getattr_opt miss on every call (C1's cost back) | test_miss_count.py::test_count_sees_a_swallowed_raise: misses >= parses under the plant, 0 without (count plant; answers unchanged) |
| 471 ad-ready-args | intern_into: ready pass takes the previous entry's args (wrong value) | test_miss_count.py::test_intern_matches_python: interned terms differ from Python's _intern under the plant, equal without |
| 472 ad-module-swap | module(): first module object kept after sys.modules' entry is replaced (wrong value) | test_miss_count.py::test_module_is_sys_modules_entry: the theory class is the stale module's, not the replacing entry's |
Kept-test catches, in-process: the plants are set only by ad_cost_plant() from a test, and no workload sets them.

## Bar (pareto0, sa-port-280's config, .so 34412a6b built on pareto1; BASE = sa-port-280's suite on 7b637e2)
End marker "END 0 2026-11-11T15:20:30Z 34412a6b 42fd78ec".
- tests: 63 files, all exit 0 (test_miss_count.py 7 passed). DIRECT relations_direct.py exit 0.
- suite: 127 failed / 5991 passed, against base new 0, gone 0, **changed outcome 0**. Handler rows 39 in 2 tests, multiset
  same as base; caught rows differing 0; TermFault 0. The planted-history test fails as on base (test_public_incremental.py:204,
  assert 0 == 2): the known id()-reuse failure (a28c548).
- Live and extra rows, extra/summary.txt, fmrows/check.txt (20 workloads, 0 differ), both fmrows plant checks, suite-plants.txt
  and direct.txt are identical to sa-port-280's bar on 7b637e2. Rust handler files on live and extra: 0 rows.
- Plant suites differ from 280's only in plant fire counts and in which randomized test_verify_soundness fuzz tests a plant
  flips (dispatch-keeps-memo: test_fuzz_old_style_symbols; fm-ite-swap: old_style and plain instead of may_be_nan), and in the
  planted-history test flipping both ways.
