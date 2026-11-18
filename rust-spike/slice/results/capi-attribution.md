# C API time by Rust caller (issue 323; sa-port-319, read-only)

Status of this document: **(a) is done. (b) and (c) are not done**; the last section says what is left and how.
No package code changed; this branch adds this file and `results/tools319/` only.

## Samples and method

- Two sample sets, both pysampler on pareto1 under a quiet lease, CPU 2, SLICE_CONVERT=rust and SLICE_TERM_FRAMES=rust,
  30 dev runs and 6 fuzz runs each:
  - **46750d4** (port/mark-note, the _Mark note fix, not landed when this was written): sa-port-317's
    `s1/run-46750d4+rust+frames`. The ranking below uses this set (planner condition 2).
  - **5b1d96f** (source-equal to rust-slice 5f53735, before the fix): sa-port-316's `prof/run-5b1d96f+rust+frames`,
    the set 317's top-15 table used. Shown beside it.
- `tools319/cap319.py` reads the records with 314's dec143.py and ana195.py unchanged. A sample is "C API from Rust"
  (ana195's capi<-rust) when its leaf is C code and a sa_solver.so frame comes before the first eval loop. Each such
  sample goes to the nearest frame that is this crate's own function; pyo3 wrappers and std or hashbrown code between
  it and the C call are skipped. A `#[pymethods]`/`#[pyfunction]` wrapper counts as its function (`__pymethod_NAME__`).
- "What it asks for" comes from the pyo3 wrapper when one is on the stack, else from the C function Rust called.
- Shares are of all in-loop samples. Total C API from Rust: dev 45.7% on 46750d4 (47.5% on 5b1d96f), fuzz 46.7% (46.6%).
  The counts on 5b1d96f equal 317's (9,730 dev, 16,804 fuzz).

Limits:

- libpython's symbol table here has exported names only. A PC in an unexported function is named after the exported
  symbol before it ("past end"). So **317's leading leaf "PyDict_Contains" is not dict membership**: 4.38% of dev
  samples sit past the end of `PyDict_Contains` and 0.03% inside it. By what was asked, that 4.38% is attribute
  lookup 1.52, container lookup 0.86, call of a C callable 0.83, import 0.48, method call 0.37: it is the shared dict
  lookup, reached from every kind of ask. `_PyType_Lookup` (3.07% dev) is likewise attribute lookup 1.40, C callable
  0.78 (the builtin `getattr`), method call 0.37.
- 3.3% dev and 3.1% fuzz are "unresolved": pyo3 inlined into the caller and the C frame unexported.
- Rust inlining merges a small callee into its caller, so a row can include helpers that have no symbol.
- "Rust heap or libc" (4.7% dev, 5.4% fuzz) is malloc, free and realloc called by Rust's own Vec and HashMap code. It
  is counted in capi<-rust by ana195's rule but asks Python for nothing.

## (a) Top 15 Rust functions by the C API time they cause

**dev**

capi<-rust 9115 of 19962 samples (45.7%); 5b1d96f 9730 of 20465 (47.5%)

| # | Rust function | 46750d4 | 5b1d96f | what it asks for (share of all samples) |
|---|---|---|---|---|
| 1 | `<term::walk::W>::klass_native` | 6.76% | 6.09% | call of a C callable 2.66; attribute by name 1.28; method call by name 0.90; type test 0.51 |
| 2 | `<term::live::TermFrames>::note` | 2.17% | 2.55% | attribute by name 0.78; call of a C callable 0.53; container write 0.35; type test 0.13 |
| 3 | `compile_loop::emit_pattern` | 1.63% | 1.73% | container lookup 0.55; container write 0.35; iteration 0.32; call of a C callable 0.15 |
| 4 | `<term::walk::Walk>::__pymethod_term_row__` | 1.57% | 1.44% | method call by name 0.32; type test 0.26; container write 0.23; iteration 0.20 |
| 5 | `<term::walk::W>::enc_native` | 1.15% | 1.15% | unresolved (unexported C function) 0.70; container write 0.28; type test 0.08; other 0.04 |
| 6 | `<PySolver>::__pymethod_add_internal__` | 1.09% | 1.06% | iteration 0.66; Rust heap or libc (not Python) 0.26; read of a Python value 0.09; release of a Python object 0.06 |
| 7 | `constfield::read_limits::{closure#0}` | 0.84% | 0.96% | attribute by name 0.52; read of a Python value 0.16; new Python object 0.10; Rust heap or libc (not Python) 0.06 |
| 8 | `<term::walk::W>::walk_native` | 0.81% | 0.79% | unresolved (unexported C function) 0.33; method call by name 0.27; attribute by name 0.14; container write 0.03 |
| 9 | `entry::__pyfunction_ent_ask` | 0.81% | 0.75% | Rust heap or libc (not Python) 0.35; release of a Python object 0.21; unresolved (unexported C function) 0.09; other 0.06 |
| 10 | `<term::live::TermFrames>::__pymethod_mark__` | 0.68% | 0.70% | attribute by name 0.32; iteration 0.09; container lookup 0.09; method call by name 0.08 |
| 11 | `term::py::req::<alloc[12e961f32105355]::vec::Vec<i64>>` | 0.65% | 0.71% | iteration 0.35; read of a Python value 0.15; container lookup 0.06; new Python object 0.05 |
| 12 | `compile_loop::split` | 0.64% | 0.72% | read of a Python value 0.16; container write 0.12; iteration 0.12; container lookup 0.11 |
| 13 | `relkeys::rk_key` | 0.61% | 0.47% | unresolved (unexported C function) 0.28; container lookup 0.15; container write 0.09; attribute by name 0.04 |
| 14 | `compile_loop::compile_patterns` | 0.60% | 0.52% | iteration 0.23; method call by name 0.11; attribute by name 0.08; Rust heap or libc (not Python) 0.05 |
| 15 | `discovery::__pyfunction_ses_ensure` | 0.56% | 0.49% | import by name 0.23; method call by name 0.15; iteration 0.07; attribute by name 0.04 |

Kinds, all functions: attribute by name 8.36 (9.92); method call by name 4.75 (4.40); Rust heap or libc (not Python) 4.67 (4.94); call of a C callable 4.38 (3.80); iteration 4.38 (4.52); unresolved (unexported C function) 3.26 (3.44); container write 3.09 (2.84); container lookup 3.05 (3.13); new Python object 2.88 (2.99); import by name 2.04 (2.82); type test 1.08 (1.17); hash or compare 0.96 (0.77); release of a Python object 0.95 (0.88); read of a Python value 0.84 (0.99); other 0.62 (0.52); thread-local read (libc, not Python) 0.35 (0.40)

**fuzz**

capi<-rust 16885 of 36118 samples (46.7%); 5b1d96f 16804 of 36046 (46.6%)

| # | Rust function | 46750d4 | 5b1d96f | what it asks for (share of all samples) |
|---|---|---|---|---|
| 1 | `<term::walk::W>::klass_native` | 2.08% | 2.08% | call of a C callable 0.86; attribute by name 0.36; method call by name 0.23; container write 0.22 |
| 2 | `compile_loop::emit_pattern` | 1.58% | 1.66% | container lookup 0.52; iteration 0.26; container write 0.26; call of a C callable 0.19 |
| 3 | `constfield::read_limits::{closure#0}` | 1.53% | 1.54% | attribute by name 0.97; read of a Python value 0.29; new Python object 0.18; Rust heap or libc (not Python) 0.09 |
| 4 | `relkeys::rk_key` | 1.47% | 1.45% | unresolved (unexported C function) 0.61; container lookup 0.44; container write 0.14; method call by name 0.11 |
| 5 | `entry::__pyfunction_ent_ask` | 1.02% | 0.92% | Rust heap or libc (not Python) 0.42; release of a Python object 0.39; call of a C callable 0.08; unresolved (unexported C function) 0.06 |
| 6 | `<PySolver>::__pymethod_add_internal__` | 1.00% | 1.10% | iteration 0.60; Rust heap or libc (not Python) 0.23; read of a Python value 0.08; release of a Python object 0.05 |
| 7 | `<term::live::TermFrames>::term_id_in` | 0.99% | 0.98% | method call by name 0.51; attribute by name 0.33; unresolved (unexported C function) 0.09; container lookup 0.03 |
| 8 | `discovery::__pyfunction_ses_ensure` | 0.98% | 0.91% | import by name 0.45; method call by name 0.24; iteration 0.14; container lookup 0.06 |
| 9 | `<formula_py::PyP>::__pymethod___hash____` | 0.89% | 0.87% | hash or compare 0.64; new Python object 0.13; unresolved (unexported C function) 0.10; release of a Python object 0.01 |
| 10 | `<adapters::LraAdapter>::memoized` | 0.86% | 0.83% | attribute by name 0.40; release of a Python object 0.23; Rust heap or libc (not Python) 0.16; container lookup 0.04 |
| 11 | `<term::walk::Walk>::__pymethod_term_row__` | 0.81% | 0.80% | method call by name 0.18; type test 0.14; container write 0.11; iteration 0.09 |
| 12 | `<session_glue::GuardMethod>::__pymethod___call____` | 0.76% | 0.60% | attribute by name 0.34; call of a C callable 0.24; container lookup 0.08; type test 0.03 |
| 13 | `<term::live::TermFrames>::note` | 0.70% | 0.68% | attribute by name 0.29; call of a C callable 0.16; container write 0.10; type test 0.03 |
| 14 | `<PySolver>::__pymethod_add_clause__` | 0.68% | 0.64% | iteration 0.51; Rust heap or libc (not Python) 0.09; new Python object 0.03; release of a Python object 0.03 |
| 15 | `<term::walk::W>::enc_native` | 0.68% | 0.68% | unresolved (unexported C function) 0.38; container write 0.18; type test 0.05; attribute by name 0.03 |

Kinds, all functions: attribute by name 8.11 (8.63); method call by name 5.72 (5.87); Rust heap or libc (not Python) 5.41 (4.97); iteration 4.73 (4.67); container lookup 3.93 (4.00); new Python object 3.70 (3.71); unresolved (unexported C function) 3.13 (3.08); container write 2.59 (2.45); call of a C callable 2.53 (2.24); import by name 1.71 (2.03); hash or compare 1.35 (1.36); release of a Python object 1.26 (1.12); read of a Python value 0.93 (0.88); type test 0.56 (0.56); thread-local read (libc, not Python) 0.55 (0.49); other 0.54 (0.56)

By module (46750d4, share of all samples): dev `term::walk` 11.9, `term::live` 4.5, `compile_loop` 4.1,
`relations_core` 3.1, `entry` 1.8, `session` 1.8, `PySolver` 1.7, `session_glue` 1.7, `constfield` 1.3, `term::py` 1.3;
fuzz `relations_core` 6.3, `term::walk` 5.0, `compile_loop` 3.7, `term::live` 3.7, `adapters` 3.4, `session` 2.8,
`constfield` 2.2, `PySolver` 2.1, `relkeys` 1.8, `session_glue` 1.7.

What the table says:

- **The time is spread thin.** The top 15 functions hold about 21% of dev's 45.7% and 16% of fuzz's 46.7%. No single
  function past `klass_native` is above 2.2%. The kinds are more concentrated than the functions.
- **`W::klass_native` is the largest caller: 6.76% dev, 2.08% fuzz.** It builds one class row per class per query
  (`term/walk.rs:499`): attribute reads on the class for each flag and operator (2.06% dev is the builtin `getattr`
  with a default, called through `PyObject_Vectorcall`), `ordering.index(name)`, subclass tests, `class_key()` and
  the template lookup. The row is computed from the class, not from the query.
- **Attribute by name is the largest kind: 8.4% dev, 8.1% fuzz**, then method call by name (4.8%, 5.7%) and
  iteration over Python lists (4.4%, 4.7%).
- **Import by name is 2.0% dev and 1.7% fuzz**, from about 50 functions that import a module on each call, 12 of
  them above 0.05% on dev
  (`discovery::ses_ensure` 0.23 dev / 0.45 fuzz, `entry::noncommutative_term`, `rel_default_spec`, `relevance::keys_rel`,
  `context::method_of`, `context::konst`, `entry::epoch`, `compile_loop::visit`, `context::patched`).
- **Rust calls Rust through Python.** `PySolver.add_internal` (1.09% dev, 1.00% fuzz) and `PySolver.add_clause`
  (0.68% fuzz) are reached by a method call by name and then iterate a Python list of literals; `PyP.__hash__` is
  0.89% fuzz; `session::core_of` is 0.56% fuzz of attribute reads.
- `constfield::read_limits` (0.84% dev, 1.53% fuzz) reads attributes by a `&str` name, which builds a Python string
  for each read.
- **_Mark's note** (planner condition 2): on 46750d4 `TermFrames::note` is still second on dev at 2.17% (2.55% before
  the fix) and 0.70% on fuzz. `term::live::attr_or` was a row of its own on 5b1d96f (2.25% dev, 0.93% fuzz) and has
  none on 46750d4; its one remaining use is inside `TermFrames::current_in` (0.55% fuzz, 0.17% before).
- **Borrow-once is not among the top C API callers.** Thread-local reads called directly from Rust are 0.35% dev and
  0.55% fuzz. `__tls_get_addr` as a leaf is 2.05% and 2.25%, but most of it is inside libpython calls (its own
  thread-state reads). So by the planner's rule it stays queued and does not fold into this proposal.

## (b) Facts built against facts read, and (c) proposals: not done

Not measured. What is known for the next session:

- `context::fresh` (`context.rs:247`) is `_fresh_session(scope)` plus `assume_formula(assumptions)`;
  `build_context` (`context.rs:256`) calls it once, and a second time on the fallback path (`:296`).
- "Built" can be counted with no package change: `PySolver.stats()` (`lib.rs:554`) gives `vars` and `clauses`.
- "Read by the solve" has no counter. It needs a count build: a per-clause and per-variable mark set where
  `Solver::propagate` (`solver.rs:1057`) and conflict analysis (`solver.rs:1666`) read them, cleared when the query's
  solve starts. That is a scratch patch, built on pareto1 and never committed to the package; whether that is inside
  "don't change the package" is the planner's call.

Candidates for (c) that (a) already supports, without numbers for what each removes beyond the shares above:
module and constant handles read once per process (import by name, 2.0% / 1.7%); the class row (6.8% / 2.1%), which
needs an exactness argument because class attributes can change between queries; direct Rust calls where Rust
reaches `PySolver` through a Python method call.
