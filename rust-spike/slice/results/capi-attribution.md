# C API time by Rust caller (issue 323; sa-port-319, read-only)

Status of this document: **(a), (b) and (c) are done** (sa-port-319 for (a); sa-port-320 and sa-port-321 for the rest).
No package code changed; this branch adds this file, `capi-attribution-counts.md` and `results/tools319/` only.

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

## (b) Facts built against facts read

**Top lines.** Counts of facts, from one count run per workload; no time is measured here.

- Of the clauses `build_context` adds, the query phase (everything after `build_context` returns) visits 56.2% on
  dev and 71.0% on fuzz, uses 30.0% and 33.2% as a reason or conflict, and has 4.9% and 2.6% in a proof. The complete check visits 82.6% and 88.0%.
  In any phase 91.7% and 91.9% are visited; 1,060 (8.3%) and 18,619 (8.1%) never are.
- So 43.8% (dev) and 29.0% (fuzz) of `build_context`'s clauses are never visited by a query. Most of those are
  visited by the complete check, whose verdict is part of the answer (207 of the 3,000 fuzz queries raise ValueError, which is how its
  INCONSISTENT verdict surfaces).
- At the size a lazy builder could defer, a relation row, nothing is unread: every row that emitted something is
  visited on dev (2,004 of 2,004) and 99.4% on fuzz (259 of 47,013 are not). 93.8% and 93.1% are a reason somewhere.
- The query phase adds more than `build_context` does: 35,620 clauses against 12,838 on dev, 409,391 against
  229,988 on fuzz.
- **Built-but-unread is an upper bound in hindsight, not a saving** (planner ruling (3)).

### How it was counted

- `tools319/count320.patch` is a scratch patch against 46750d4's `solver_rs/src` (solver.rs, context.rs,
  relations_core.rs). It was applied to a copy of sa-port-317's `bench-46750d4` in sa-port-321's own directory on
  pareto1 (`tools319/job321.sh`, under a shared lease), built there, and **never committed to the package** and
  never copied into 317's tree. The count build's `.so` has a sha256 starting `0bdac11ab5199038`; 317's starts `45f63fdfb8e8523c`.
- One run of dev and one of fuzz with 317's `qt195.py`, SLICE_CONVERT=rust and SLICE_TERM_FRAMES=rust (the
  +rust+frames arm the samples used). Answers are unchanged by the marks: the digests equal 317's on that arm
  (dev `31cd0945c07f02a6`, fuzz `173502b6ef285ad6`). `ctx:caught` and `ctx:fallback` are 0 on both workloads.
- dev is 1,985 queries (892 None, 557 False, 536 True) over 833 `build_context` calls; fuzz is 3,000 queries
  (2,387 None, 207 raise ValueError, 204 False, 202 True) over 2,952.
- Three kinds of read, each kept per phase: **visited** (propagation's watch scan reached the clause, or the
  variable's literal was dequeued), **reason** (the clause or block implied a literal, or was the conflict),
  **proof** (read by conflict analysis, minimisation or the final analysis, or in the reason cone of an entailed
  literal or of a root conflict). Phases: 1 inside `build_context`, 2 inside its complete check, 0 otherwise, which
  is the query. A clause's row is the phase that added it.
- A relation row is one unit of work in `rel_process`: a user eq atom, a queued atom interpreted, a top entry or a
  pending link. It is read when any clause, variable, unit or theory atom it emitted is marked.
- `tools319/plant320.py` shows each counter firing on a planted case first: 39 rows pass and none fails, on orion and
  on the pareto1 build. `tools319/sum320.py` makes the tables; `capi-attribution-counts.md` has its full output
  (clauses, variables, units, blocks and rows by phase and kind).

### The tables

"query" columns are phase 0, "check" columns phase 2, "any" every phase. Percentages are of the built column.

| built, per workload | dev | fuzz |
|---|---:|---:|
| solvers (born in build_context / in the query) | 840 / 78 | 2955 / 178 |
| variables: build_context / its check / the query | 22489 / 0 / 18725 | 183402 / 0 / 181955 |
| clauses: build_context / its check / the query | 12838 / 3311 / 35620 | 229988 / 34905 / 409391 |
| clauses: learnt / other (theory, explanations) | 657 / 15 | 37724 / 640 |
| unit clauses: build_context / its check / the query | 169 / 1397 / 1435 | 389 / 8276 / 2444 |
| rule blocks: build_context / its check / the query | 1238 / 0 / 1180 | 7446 / 0 / 9047 |
| relation rows made: user eq / queued atom / top entry / pending link | 38 / 1501 / 396 / 375 | 888 / 36397 / 5236 / 9405 |
| relation rows that emitted something, same kinds | 35 / 1507 / 87 / 375 | 888 / 36398 / 322 / 9405 |

**dev**, read by the query (phase 0), by the complete check (phase 2) and in any phase:

| dev | built | query: visited | query: reason | query: proof | check: visited | check: reason | check: proof [p] | any: visited | any: reason | any: proof | never visited |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| build_context's clauses | 12838 | 7219 (56.2%) | 3852 (30.0%) | 633 (4.9%) | 10607 (82.6%) | 5819 (45.3%) | 205 (1.6%) | 11778 (91.7%) | 7135 (55.6%) | 815 (6.3%) | 1060 |
| build_context's variables | 22489 | 10162 (45.2%) | 8735 (38.8%) | 1015 (4.5%) | 12039 (53.5%) | 8744 (38.9%) | 596 (2.7%) | 16352 (72.7%) | 12633 (56.2%) | 1467 (6.5%) | 6137 |
| the check's own clauses | 3311 | 1336 (40.4%) | 349 (10.5%) | 4 (0.1%) | 1823 (55.1%) | 297 (9.0%) | 0 (0.0%) | 2219 (67.0%) | 447 (13.5%) | 4 (0.1%) | 1092 |
| the query's own clauses | 35620 | 26378 (74.1%) | 8773 (24.6%) | 330 (0.9%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 26378 (74.1%) | 8773 (24.6%) | 330 (0.9%) | 9242 |
| rule blocks, all phases | 2418 | 2068 (85.5%) | 1868 (77.3%) | 131 (5.4%) | 1234 (51.0%) | 556 (23.0%) | 49 (2.0%) | 2417 (100.0%) | 2069 (85.6%) | 168 (6.9%) | 1 |
| relation rows that emitted, all kinds | 2004 | 1671 (83.4%) | 1605 (80.1%) | 296 (14.8%) | 1281 (63.9%) | 1158 (57.8%) | 268 (13.4%) | 2004 (100.0%) | 1880 (93.8%) | 510 (25.4%) | 0 |
| of them, pending links | 375 | 330 (88.0%) | 328 (87.5%) | 65 (17.3%) | 227 (60.5%) | 227 (60.5%) | 56 (14.9%) | 375 (100.0%) | 375 (100.0%) | 119 (31.7%) | 0 |

**fuzz**, read by the query (phase 0), by the complete check (phase 2) and in any phase:

| fuzz | built | query: visited | query: reason | query: proof | check: visited | check: reason | check: proof [p] | any: visited | any: reason | any: proof | never visited |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| build_context's clauses | 229988 | 163315 (71.0%) | 76400 (33.2%) | 5946 (2.6%) | 202490 (88.0%) | 87226 (37.9%) | 6819 (3.0%) | 211369 (91.9%) | 110520 (48.1%) | 12323 (5.4%) | 18619 |
| build_context's variables | 183402 | 132079 (72.0%) | 118787 (64.8%) | 14665 (8.0%) | 146633 (80.0%) | 122983 (67.1%) | 16970 (9.3%) | 163824 (89.3%) | 143637 (78.3%) | 28116 (15.3%) | 19578 |
| the check's own clauses | 34905 | 23171 (66.4%) | 7886 (22.6%) | 261 (0.7%) | 24539 (70.3%) | 6560 (18.8%) | 149 (0.4%) | 27826 (79.7%) | 9793 (28.1%) | 400 (1.1%) | 7079 |
| the query's own clauses | 409391 | 345735 (84.5%) | 130776 (31.9%) | 4379 (1.1%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 345735 (84.5%) | 130776 (31.9%) | 4379 (1.1%) | 63656 |
| rule blocks, all phases | 16493 | 15184 (92.1%) | 14866 (90.1%) | 1429 (8.7%) | 7324 (44.4%) | 6991 (42.4%) | 1238 (7.5%) | 16376 (99.3%) | 15971 (96.8%) | 2449 (14.8%) | 117 |
| relation rows that emitted, all kinds | 47013 | 42656 (90.7%) | 40174 (85.5%) | 10529 (22.4%) | 26250 (55.8%) | 23596 (50.2%) | 6569 (14.0%) | 46754 (99.4%) | 43756 (93.1%) | 15676 (33.3%) | 259 |
| of them, pending links | 9405 | 8633 (91.8%) | 8632 (91.8%) | 2036 (21.6%) | 5192 (55.2%) | 5038 (53.6%) | 1505 (16.0%) | 9405 (100.0%) | 9251 (98.4%) | 3398 (36.1%) | 0 |

**[p] The check's proof column is a lower bound, not a zero where it is small.** The complete check
(`context.rs:357`) can reach INCONSISTENT in three places: `propagate()` returns false (a root conflict, marked;
0 on both workloads), `implied()` returns None, or `solve()` returns false (marked through the final analysis).
`implied()` is `assume`: a conflict there is found at an assumption level, no analysis runs, and the patch walks no
cone, so that refutation has **no proof mark**; the reason column bounds it. Planted: `x > 1 & x < 0 & y > x` is
refuted there (entries: 0 solve_int, 1 assume, 1 propagate; 15 clauses as reasons, proof unmarked), while four
clauses over `positive(x)`, `positive(y)` reach `solve()` and all 4 are in the proof. On the workloads 6 (dev) and 94
(fuzz) solvers born in `build_context` never ran `solve_int`, which bounds how many checks ended there. A consistent check ends in a model, which has no
proof either: its proof marks come only from conflicts its search met on the way.

### What the tables say

- **Query against check.** The check reads more of the context than the queries do, at every level except proof on
  dev. Of `build_context`'s clauses, 4,559 on dev (35.5%) and 48,054 on fuzz (20.9%) are visited in some phase but
  never by a query. The check also adds its own: 3,311 clauses and 1,397 units on dev, 34,905 and 8,276 on fuzz,
  of which queries later visit 40.4% and 66.4%.
- **Proof level is small everywhere**: 6.3% (dev) and 5.4% (fuzz) of `build_context`'s clauses in any phase. But a
  proof exists only where something is refuted. 44.9% of dev answers and 79.6% of fuzz answers are None, where
  both of the query's solves end in a model; a model is a statement about every clause.
- **Pending links.** The 375 (dev) and 9,405 (fuzz) pending-link rows are the same counts as the deferred links in
  the main-package lazy-links reports. Here all of them are built. In some phase 375 of 375 and 9,251 of 9,405
  (98.4%) are a reason, which is what option A found from the other side (it built 374 of 375 and 96%). The
  query's proofs touch 17.3% and 21.6% of them; sign repair got builds down to 94 of 375 (25%) and 2,004 of 9,405
  (21%). These are different builds (Python main package there, the Rust slice here), so this is an agreement in
  shape, not a derivation.
- **Variables** are read less than clauses: 27.3% of `build_context`'s on dev (6,137) and 10.7% on fuzz (19,578)
  are never dequeued.

### What is not marked

- `implied()` returns the whole trail to Python, so no cone is walked for it; and a refutation inside it has no
  proof mark ([p] above).
- `clause_ok`, `witness_satisfies` and `ring_hit` read clauses against stored models without a mark.
- Unit clauses have no reason mark ("n/m" in the full tables). Theory and explanation clauses are not in watch
  lists, so "visited" is 0 for them by construction.
- Rule blocks are not tagged with rows, and their marks are not split by the phase that built them. `discover`,
  `_share` and the transfer calls run untagged, so what they emit belongs to no row.
- "Rows made" is a process-wide counter, not split by phase; "emitted" is counted per solver, so it can pass
  "made" (dev queued atoms: 1,507 against 1,501).
- A solver still alive when the process ends reports its state at its last `solve_int` or `assume`.
- Reads by Python or by theory code outside the solver's own propagation and analysis.
- Cost. A fact's count says nothing about what it took to build.

## (c) Proposals

**1. From (a): module and constant handles read once per process.** About 50 Rust functions import a module by
name on each call. That is 2.0% of dev samples and 1.7% of fuzz samples, which is the most this step can remove.
Nothing is skipped: the handle kept is the module object, and every attribute is still read from it at each use, so
a patched method or a changed constant is seen as today (ruling P1). The acceptance check is the bar's (digests on
dev and fuzz identical, the suite, the plant table including the patched-method kept tests), plus a gain beyond the
spread on S1. That last part is in doubt: 317's twelve pinned rounds on this arm span 1.8% on dev (0.647 to 0.659 s)
and 1.4% on fuzz, so the ceiling is about one spread wide, and rk_key's read-once caches were dropped for exactly
that reason. Shares are of samples, not wall time.

**2. From (b): none.** No skip-building step can be argued from this count, so (b) stands as a measurement.

- A step that skips building needs an exact decider that runs while the query runs. The two shapes available are
  "build a fact when propagation would touch it" and "check each model against the unbuilt facts".
- The first builds what the "visited" column shows: 91.7% and 91.9% of `build_context`'s clauses, and every
  relation row on dev and 99.4% on fuzz. The second is option A, and the "reason" column agrees with its result:
  100% and 98.4% of the pending links are a reason in some phase.
- The small column, proof, cannot decide anything in advance. It is known only after a refutation, and most answers
  (None, and every consistent check) end in a model instead.
- The clauses a query never visits are mostly there for the complete check, which cannot be dropped: its verdict
  is the difference between an answer and a raised error.
- The one exact mechanism that did cut builds, sign repair, chooses the model; it does not predict reads. Its
  acceptance check (answers identical on dev and fuzz, the suite) is the one any port of it would carry. Porting it
  is the main-package lazy-links line's step, not a new proposal from this count.

Not proposed, for the planner to weigh: Rust adds clauses to its own solver through a Python method call by name
(`PySolver.add_internal` 1.09% dev and 1.00% fuzz, `add_clause` 0.68% fuzz); the solvers took 51,769 problem
clauses on dev and 674,284 on fuzz by every path together. A direct call when the object is exactly the Rust type would be speed-only, with the same thin
ceiling as proposal 1. Borrow-once stays queued (thread-local reads from Rust are 0.35% dev, 0.55% fuzz).
