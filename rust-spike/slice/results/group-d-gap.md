# Group D gap: why D's adapters-cost fix and C2 left Group D flat (issue 323, sa-port-292, read-only)

Read-only: no source changes, no package changes. This file is the only change on report/group-d-gap (from rust-slice 15c62a7).

## Method (the same for both trees)
- Trees: 1401d1f (146's tree; .so sha256 9ac1e109e685..., identical to 146's) and 15c62a7 (landed rust-slice head; .so b5a4ac6201df...).
  Staged by `git archive` from sa-port-24 and built per tree in sa-cy-build:1 (job195.sh).
- Samples: 285's harness unchanged (pysampler, 1 ms CPU time, `--cpus 1`, sa-eval-bench:1), under a **shared** pareto1 lease for
  each tree (2215096b, 58c5b1fb). There were 6 fuzz runs per tree (285 used 3): 40,270 samples on 1401d1f and 38,879 on 15c62a7.
  Dev ran 3 runs per tree.
- Timing: pinned, both trees interleaved, 7 rounds, dev and fuzz, bench-container BENCH_CPU=2, under a **quiet** pareto1 lease
  (a9cd438c, 19:16-19:18Z 11 Nov). That is 28 rows, **0 digest mismatches**.
- Seconds = sample share x the tree's pinned Rust median, as in 285/286. Group D = the ana195 category `capi<-rust`.
- Per function (new tool prof292.py, same records and the same ana195 classify):
  - **incl**: the function is anywhere on the stack.
  - **self**: the leaf PC.
  - **self+C**: the innermost Rust frame on rust/glue/capi samples. This is the function's own code plus the C API it calls directly.
  - **D**: the capi<-rust part of self+C. This is exactly 286's fdiff `rfun` key.
- The same tool was run on 288's (50f1421 -> 42fd78e) and 289's (6a461f2 -> d25b1a7) existing samples, for the step checks.
- **Answers are equal between trees**: dev digest 31cd0945c07f02a6 and fuzz digest 173502b6ef285ad6 on both trees, in Rust and in
  py mode, with 0 refusals.
- **Method gap (sa-port-285): 0.015 s dev.** 146's own number was 0.158 s; 285 measured 0.173 s the same way. Today it measures
  0.165 s.
- Sampling SE on Group D is about 0.015 s per tree on fuzz, so about 0.021 s on a difference.
- Quiet catches (engine.py's `except Exception`): not counted; this step only profiled. Equal digests and 0 refusals show no
  answer was lost in either tree.
- Limit: libpython's nm table holds only 1,734 exported symbols. C-level names are therefore approximate (`c:PyUnicode_DecodeASCII`
  "inclusive" is a static function that sits after that export), so the findings use only Rust and Python names.

## Totals (fuzz, pinned)
| | 1401d1f (146) | 15c62a7 (head) | change |
|---|---|---|---|
| Rust median s | 6.688 (6.667-6.740) | 6.404 (6.370-6.442) | **-0.284** |
| Group D s (share) | 1.950 (29.1%) | 2.198 (34.3%) | +0.248 |
| rust / glue | 0.746 / 0.396 | 0.990 / 0.519 | +0.244 / +0.123 |
| python / callback | 1.542 / 1.705 | 0.027 / 2.266 | -1.516 / +0.561 |
| sympy<-rust | 0.327 | 0.381 | +0.054 |

Dev: 0.751 -> 0.758 s median; Group D 0.165 -> 0.185 s.

## Per function, fuzz (s): the 14 largest Group D changes, then 286's C1/C3/C5 functions and pyo3's thread check
| Rust function | incl 146 | incl head | self 146 | self head | self+C 146 | self+C head | D 146 | D head | D change |
|---|---|---|---|---|---|---|---|---|---|
| `relkeys::rk_key` | 0.000 | 0.291 | 0.000 | 0.009 | 0.000 | 0.136 | 0.000 | 0.127 | +0.127 |
| `relations_core::rel_interpret` | 1.877 | 1.617 | 0.011 | 0.014 | 0.089 | 0.048 | 0.078 | 0.033 | -0.044 |
| `discovery::deque` | 0.036 | 0.000 | 0.000 | 0.000 | 0.036 | 0.000 | 0.035 | 0.000 | -0.035 |
| `session::core_of` | 0.000 | 0.036 | 0.000 | 0.003 | 0.000 | 0.036 | 0.000 | 0.033 | +0.033 |
| `<adapters::LraAdapter>::memoized` | 0.000 | 0.568 | 0.000 | 0.008 | 0.000 | 0.039 | 0.000 | 0.031 | +0.031 |
| `Bound<PyAny>::call_method1::<&pyo3::instance::Boun` | 3.730 | 3.614 | 0.012 | 0.007 | 0.053 | 0.018 | 0.041 | 0.012 | -0.029 |
| `compile_loop::split` | 0.039 | 0.020 | 0.002 | 0.001 | 0.038 | 0.008 | 0.035 | 0.007 | -0.028 |
| `relations_core::sympy_atom` | 0.059 | 0.051 | 0.001 | 0.001 | 0.033 | 0.007 | 0.032 | 0.006 | -0.026 |
| `<adapters::EufAdapter>::intern_into` | 0.000 | 0.084 | 0.000 | 0.002 | 0.000 | 0.024 | 0.000 | 0.022 | +0.022 |
| `<adapters::Reader>::pairs` | 0.000 | 0.033 | 0.000 | 0.003 | 0.000 | 0.025 | 0.000 | 0.022 | +0.022 |
| `theory_flags::theory_flag` | 0.000 | 0.024 | 0.000 | 0.002 | 0.000 | 0.023 | 0.000 | 0.021 | +0.021 |
| `discovery::discover_inner` | 0.463 | 0.422 | 0.004 | 0.002 | 0.025 | 0.002 | 0.021 | 0.000 | -0.021 |
| `<relations_core::Cx>::tsource` | 0.041 | 0.082 | 0.003 | 0.003 | 0.028 | 0.008 | 0.025 | 0.006 | -0.020 |
| `relations_core::rel_process` | 2.908 | 2.679 | 0.008 | 0.008 | 0.050 | 0.030 | 0.042 | 0.022 | -0.019 |
| `<adapters::EufAdapter>::build` | 0.000 | 0.007 | 0.000 | 0.000 | 0.000 | 0.003 | 0.000 | 0.003 | +0.003 |
| `<adapters::EufAdapter>::py_class` | 0.000 | 0.005 | 0.000 | 0.000 | 0.000 | 0.005 | 0.000 | 0.004 | +0.004 |
| `<pyo3::impl_::pyclass::ThreadCheckerImpl>::ensure` | 0.046 | 0.106 | 0.022 | 0.054 | 0.022 | 0.054 | 0.000 | 0.000 | +0.000 |
| `adapters::attach_to` | 0.000 | 0.024 | 0.000 | 0.000 | 0.000 | 0.017 | 0.000 | 0.016 | +0.016 |
| `adapters::module` | 0.000 | 0.005 | 0.000 | 0.000 | 0.000 | 0.002 | 0.000 | 0.002 | +0.002 |
| `std::thread::current::current` | 0.026 | 0.056 | 0.024 | 0.050 | 0.026 | 0.056 | 0.003 | 0.006 | +0.003 |

By module (med285): adapters D 0 -> 0.206, relkeys 0 -> 0.107, relations_core 0.511 -> 0.366, discovery 0.151 -> 0.063,
compile_loop 0.294 -> 0.233, session 0.115 -> 0.158.

## Top three differences, with a cause each
1. **adapters: Group D 0 -> 0.206 s.** The largest items are LraAdapter::memoized 0.031, intern_into 0.022, Reader::pairs 0.022 and
   attach_to 0.016. Cause: the Python adapters moved into Rust (96be463, adapters part B; state part 1's Reader). Their C API calls
   on Python-held objects are now counted as Group D. Before, the same work was in the python and callback categories. Inclusive
   time went down overall: the Python adapter files took 1.416 s on 146 (lra_adapter.py 1.165, euf_adapter.py 0.251). On the head,
   Rust `adapters` takes 1.140 s and the Python remainder 0.143 s, about 0.13 s less. So this is moved time, not added time.
2. **relkeys::rk_key: Group D 0 -> 0.127 s** (inclusive 0.291, own code 0.009). Cause: Relations' nine sets became Rust-native
   (181c161, RDict/RSet). Every get, set and contains computes a key, and rk_key re-reads the query from Python on each call:
   `term_live.current()`, `.kept`, is_basic/is_joinable isinstance checks, then term_of. Its Group D time is attribute lookup
   0.026 s (GenericGetAttr, _PyType_Lookup), PyDict_Contains 0.014 s and PyObject_IsSubclass 0.006 s. Callers: rd_get 0.037 s,
   rd_set 0.014 s, rs_contains 0.008 s. Python dict/set operations did this in one hash. relations.py took 0.359 s inclusive on
   146; relkeys takes 0.401 s on the head. This is the one difference that is real new overhead rather than moved time.
3. **relations_core: Group D 0.511 -> 0.366 s.** rel_interpret -0.044, sympy_atom -0.026, tsource -0.020 and rel_process -0.019.
   Cause: rel_interpret now calls the Rust adapters directly (C2) and reads relations once per query (state part 1). Its inclusive
   time fell 1.877 -> 1.617 s (-0.260 s), and callback inside it fell -0.469 s. But its Group D grew +0.068 s and its rust part
   +0.084 s, because work that was Python callbacks is now Rust calling the C API.

Also outside Group D: pyo3's unsendable-pyclass thread check (ThreadCheckerImpl::ensure plus std::thread::current) grew from 0.048
to 0.110 s. That is spread over every pyclass borrow (RDict::get_item, PyTermTable::try_borrow, add_clause, ...) and is booked as
`rust`.

## The 0.12 s: candidates (1)-(3)
286 predicted C1 0.034 + C2 0.039 + C3 0.027 + C5 0.025 = 0.125 s. Those were Group D (`rfun`) deltas at the adapters step.
Checked step by step:
| item | 286 (D) | landed step, D change of that function | its inclusive change | where the rest went |
|---|---|---|---|---|
| C1 py_class | 0.034 | -0.025 (0.029 -> 0.003) | **-0.063** (0.066 -> 0.003) | 0.035 s of it ran in `_compat._add_renamed.<locals>.__getattr__` (Python module `__getattr__` on a miss), booked as callback |
| C2 rel_interpret | 0.039 | -0.030 (0.060 -> 0.030) | -0.037; rel_process -0.080 | +0.016 reappears under register/interned (now called directly, so their C API calls count against them); trampolines show in glue -0.029 |
| C3 intern_into | 0.027 | +0.002 | -0.006 | the landed C3 (second visit only, per the 12:54Z ruling) is narrower than 286's proposal |
| C5 module/build/attach_to | 0.025 | ~0 | ~0 | attach_to (0.015 of the 0.025) was not part of the landed C5; module() was 0.009 inclusive and stayed there |
Wall time did fall. On fuzz, 288's step went 6.536 -> 6.451 s (-0.085) and 289's 6.463 -> 6.402 s (-0.061), together -0.146 s. In
categories, 288's step cut callback -0.073 and python -0.037 while Group D went +0.013. 289's step cut callback -0.043 and glue
-0.029 while Group D went -0.006.

**Verdict.**
- **(3), mainly.** The savings landed: about 0.15 s of wall time over the two steps. They landed in callback, python and glue, not
  in Group D.
- **(1), partly.** 286's figures were Group D alone (innermost Rust frame on capi samples), not inclusive time. For C1 this
  understated the cost: 0.034 in D against 0.066 inclusive, half of it in a Python `__getattr__`. For C3 and C5 it overstated
  what the landed fixes could remove, because those fixes were narrower than 286's proposals.
- **(2), yes, as a property of the metric.** Group D is one category's share. It cannot show savings booked in other categories.
  It moves when code changes callee or inlining: ses_ensure's import moved to `PyModule::import` at 42fd78e, +0.022 there. And
  each step's change of about 0.03 s is at its sampling SE.

So Group D should not be the yardstick for speed fixes. Use pinned wall time and per-function inclusive time.

Head vs 146: fuzz is 0.284 s faster, while Group D is +0.248 s. The Group D growth is moved time (differences 1 and 3) plus one
real new overhead, rk_key (difference 2).

## Files
Scratch on orion: ~/sa-rust-ids-work/sa-port-292/gd/.
- go292.sh: the driver.
- run-{1401d1f,15c62a7}/: samples and SUMMARY.md.
- med-r1.md and timing-r1/: pinned timing.
- prof-fuzz-*.json and old/prof-fuzz-{50f1421,42fd78e,6a461f2,d25b1a7}.json: profiles.
- tools/{prof292,cmp292,tab292,icat292}.py: the new analysis.
- table-fuzz.md: the table above.
