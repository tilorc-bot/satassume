# What is computed against what is read, on both paths (issue 323, sa-port-367)

Measurement only: no source change, no removal, no port, nothing landed. Every number is from rust-slice **966268c**.

**Result.** On neither path do the files that carry 80% of own time hold a large result that nothing reads, beyond the
two already known on the Rust path (the formula skeleton and the per-term construction level). The default path's
time is in results that are read: the SAT solver alone owns 38 to 61% of the pass. What is unread there is counters
and one model copy, estimated under 1% of the pass. The counters have limits that matter for this conclusion (entries
of containers are not counted one by one); they are in "Limits" and "What is not done".

## The two paths, the trees, the runs

- **default**: the package alone, no SLICE_ switch in the environment (what SymPy runs). The witness check is off
  (its default). `SLICE_DIR` is set: it is the driver's variable for where budget_wl.py and knowledge_wiring_wl.py are.
- **rust-nat**: SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust SLICE_WITNESS=1 SLICE_WITNESS_CAP=32 SLICE_WITNESS_RUST=1.
- **Profile**: pareto1, quiet lease 9194a3e6 (7 minutes, load at most 1.07), sa-eval-bench:1, Python 3.12.15, CPU 2
  pinned. x86-64 .so **8b8041d3fe6223c2** (sa-port-359's build of 00535462; the crate of 966268c is equal, checked by
  goprof367.sh). Method: sa-port-356's (tools342/qt342.py for wall time, 5 rounds, the two paths alternating in one
  bench-container invocation; sa-port-143's pysampler.so, SIGPROF every 1 ms, through sa-port-195's classifier), with
  the default path as the second arm. Sampler runs per path: dev and budget 30, fuzz 6, wiring 8.
- **Counts**: orion (aarch64, Python 3.12.14), .so **4d8921d9c510e99f** built from 966268c by build_solver.sh. Counts
  only, nothing there is a time.
- Tools: results/tools367. Full tables: tools367/tab-default.txt and tab-rust-nat.txt (every function and every stored
  field of the marked files, with call sites, writers and readers as file:line).
- Answers' digests are the reference ones in every timed, sampled and counted cell used here: dev 31cd0945c07f02a6,
  fuzz 173502b6ef285ad6, budget 35bc2c4a937bebc0, wiring a0df9fd43e5180c1.
- rust-slice did not move while this ran: 966268c at the first fetch and at the fetch before this was committed.

Wall time, median of 5 pinned rounds (iqr/median on dev / fuzz / budget: default 1.7 / 1.6 / 3.0%, rust-nat 0.7 / 0.6 /
2.8%; wiring's spread, min and max are in tab-*.txt):

| workload | default s | rust-nat s |
|---|---|---|
| dev | 0.5275 | 0.6022 |
| fuzz 424242 | 8.0545 | 4.0756 |
| budget | 0.4754 | 0.3267 |
| wiring | 2.7374 | 3.2607 |

(fuzz on the default path is 8.05 s here against 5.40 s for 356's `py-on32` row, which had the witness check on. That
row is from another lease and from de88d9b9, so it is an observation, not a controlled comparison.)

### What of the slice loads or runs on the default path

mods367.py, one pass per workload in the profile's container (run/WL-py-mods.json): **no slice module is loaded on dev
and fuzz; on budget and wiring only the workload's own query list** (budget_wl.py, knowledge_wiring_wl.py), which
runs nothing inside the loop (0 function starts under rust-spike/slice in the loop on all four). sa_solver is not
loaded. The only SLICE_ variable in the environment is SLICE_DIR. So the default profile is satassume and SymPy, with
no slice glue, and there is no slice row to report on that path.

## The files that carry 80% of own time

Own share of in-loop samples per file (bytecode plus the C its bytecode calls directly); the cumulative column is over
the repository's files, own summed over the four workloads.

**default** (repository files own 85.8 / 82.0 / 85.9 / 94.3% of the pass; SymPy's own code 7.2 / 8.4 / 8.8 / 3.1):

| file | dev | fuzz | budget | wiring | summed | cumulative |
|---|---|---|---|---|---|---|
| satassume/sat/solver.py | 38.52 | 38.70 | 38.09 | 61.17 | 176.48 | 50.7% |
| satassume/engine.py | 14.23 | 9.40 | 9.73 | 17.77 | 51.14 | 65.4% |
| satassume/knowledge/compile.py | 1.27 | 0.76 | 12.04 | 5.08 | 19.15 | 70.9% |
| satassume/relations.py | 6.45 | 10.82 | 0.28 | 0.89 | 18.43 | 76.2% |
| satassume/knowledge/templates/_common.py | 3.31 | 0.13 | 10.87 | 1.36 | 15.66 | 80.7% |
| next: theories/lra/lra.py 15.43, sympy_api.py 12.26, knowledge/rules.py 8.91, sat/formula.py 6.09 | | | | | | 93.0% |

**rust-nat** (repository files own 14.8 / 11.2 / 8.7 / 14.5%; SymPy's own code 9.6 / 11.1 / 24.3 / 11.7; the Rust side
is the rest):

| file | dev | fuzz | budget | wiring | summed | cumulative |
|---|---|---|---|---|---|---|
| satassume/knowledge/domain.py | 2.26 | 1.52 | 4.39 | 3.80 | 11.97 | 24.3% |
| slice/term_live.py | 2.85 | 2.38 | 0.16 | 2.59 | 7.98 | 40.6% |
| satassume/sympy_api.py | 2.60 | 1.46 | 0.73 | 2.47 | 7.26 | 55.4% |
| satassume/state/memos.py | 2.48 | 1.02 | 0.12 | 2.48 | 6.10 | 67.8% |
| slice/session_live.py | 0.84 | 0.90 | 0.14 | 1.03 | 2.91 | 73.7% |
| slice/convert.py | 0.53 | 0.37 | 0.61 | 0.90 | 2.41 | 78.6% |
| satassume/sat/formula.py | 0.12 | 0.16 | 1.96 | 0.08 | 2.33 | 83.3% |
| next: slice/lra_backend.py 2.15, witness.py 1.38, slice/witness_live.py 1.01, engine.py 0.78 | | | | | | 94.2% |

The ruling named 356's profile (measured-next.md (1), de88d9b9) for this path. It is from before convert.py's port:
convert.py owned 17.54 points summed there and owns 2.41 here. The lease took both paths at once, so the table above
is the head's; 356's set (convert.py, domain.py, term_live.py, sympy_api.py, memos.py, session_live.py) is the same
six files plus sat/formula.py.

## The ranked table: time recoverable, default path first, then the Rust path

Classes: **read 0** = computed and never read (removal candidate); **minority** = read on fewer than half of the
computes (compute-on-first-read candidate, exact); **read** = a port candidate. Counts are dev / fuzz / budget /
wiring per pass. "Not separable" means the sampler's unit is the function and the result is one statement inside a
larger one; the estimate beside it is from the count, not a measurement.

| # | path | result | class | computed | read | time it carries | readers (excluded readers apart) |
|---|---|---|---|---|---|---|---|
| 1 | default | the solver's counters `Solver._n_props`, `_n_decisions`, `_n_restarts`, `_n_conflicts`, `_n_learned`, `_n_late`, `_n_late_written`, `_n_ring_hits`, `_n_tdecisions`, `_rb_blocks` (solver.py:1731, :2393, :2492, :2110, :2117, :1368, :1383, :2464, :2079, :1162), `VarTable.naux` (compile.py:125), `Engine.stats` (engine.py:1416, :1424, :1940, :2233 and others) | read 0 | about 38.5k / 442k / 61k / 520k updates summed | 0 | not separable; at an assumed 50 ns per update about 0.4 / 0.3 / 0.6 / 0.9% of the pass (an estimate) | none in the pass. Apart: the solver's own statistics method (solver.py:2828-2836), tools/query_log.py:216, tests (tests/test_lazy_atoms.py:47, tests/test_p3_review.py:62, ...); `naux` also session_live.py:161 and session.rs:2347 on the Rust path |
| 2 | default | `Solver._mvals`, the model copied on every satisfiable answer (solver.py:2499, :2462, in `_solve` :2432) | read 0 | 1,864 / 7,848 / 26 / 13,446 | 0 | not separable from `_solve`'s own 0.97 / 0.38 / 0.04 / 1.22% (one list slice per answer; the same slice is `_witness`, row 3, so removing `_mvals` alone saves a store, not the slice) | `Solver.model` (solver.py:2543-2550) is its only reader, and nothing in the pass calls it. Apart: tests/test_solver.py:77, tests/test_solver_incremental.py:474, tests/theory_harness.py:131, tools/totality.py:79, slice/check_step1.py:23 |
| 3 | default | `Solver._witness`, the same model copy kept for the next query's shortcut | minority | 841 / 2,765 / 18 / 6,006 results | 344 / 115 / 9 / 2,503 | as row 2 | `Solver._witness_satisfies`, solver.py:2651 |
| 4 | default | the status returned by `Solver.add_clause` (:680), `add_internal` (:917), `register_block` (:1080), `register_atom` (:1876) | read 0 (the returned flag only) | 13,877 / 316,135 / 37,174 / 106,564 for add_clause; 3,298 / 33,176 / 290 / 15,126 for add_internal | 0: dropped at every call site (engine.py:543, :661, :599; lra_adapter.py:486; relations.py:1852; euf_adapter.py:153) | none: the flag is a by-product; the clauses these functions store are read by the solver | - |
| 5 | default | stores of an argument that are read later on some queries only: `Session.assumption_formula` (engine.py:939; read engine.py:980 on 32 / 14 / 0 / 0 of 559 / 2,563 / 12 / 3,429), `Session.scope` (engine.py:310; read relations.py:875), `Session.literals`, `Relations._user_eq`, `_xextra`, `_xsides_n`; never read: `Relations.scope` (relations.py:875), `VarTable._preds` (compile.py:86), `Solver._conflict` (solver.py:2259; reader solver.py:2647, not called in the pass) | minority / read 0 | see tab-default.txt (C) | | none: each stores a value that exists already | as listed |
| 6 | default | everything else the five files compute: 294 functions, the returned value taken at every call site but for `Session.node` (dropped on 3,079 of 7,950 calls on dev: called for its side effect at those sites) and `Session._ensure_twins` | read | tab-default.txt (B) | | **63.8 / 59.8 / 71.0 / 86.3% of the pass = 0.336 / 4.817 / 0.338 / 2.362 s** | tab-default.txt (B), call sites per function |
| 7 | rust-nat | KNOWN, not re-measured: the per-term construction level (`constructed_noncommutative`, domain.py:58, called from walk.rs; sa-port-364: computed 4,515 / 28,853 / 7,472 / 63,184, read 0; removal queued as sa-port-366) | read 0 | 364's | 0 | at the head, own of `constructed_noncommutative` 1.71 / 1.39 / 2.55 / 3.07% = 0.010 / 0.057 / 0.008 / 0.100 s, plus its part of `_fixed_noncommutative` (0.32 / 0.08 / 1.11 / 0.60% whole); 364's split at de88d9b9: 1.43 / 1.38 / 3.51 / 3.54% | apart: term_shadow.py:167 |
| 8 | rust-nat | KNOWN, not re-measured: the formula skeleton (sa-port-363/365's removal) | read 0 | - | 0 | 363's S1 | apart: term_shadow.py:623 |
| 9 | rust-nat | `TableView.base_of`, `.slots`, `.base_view`, `.atom` and the objects `_BaseOf`, `_Slots`, `_Base` made for every session (session_live.py:132-135) | read 0 as fields | 746 / 1,897 / 17 / 5,603 sessions | 0 | at most 0.02% (own of the four `__init__`s) | none through the field in the pass; the names are also read in session.rs:1200, :1256 and engine.py:622, relations.py:861, :1806 on other objects: not checked which of these reach a TableView. Apart: test_session_limits.py:80, :81 |
| 10 | rust-nat | `TableView.custom`, `.var` (session_live.py:132, :133) | minority | 623 / 1,776 / 17 / 3,263 results | 101 / 1,401 / 0 / 0 | at most 0.01% | session_live.py:616 (through getattr) |
| 11 | rust-nat | `_Query.classes` (term_live.py:92: the converter's `c.classes` kept on the query) | read 0 as a field | 1,197 / 2,998 / 28 / 6,512 | 0 | within `_Query.__init__`'s own 0.19 / 0.06 / 0.00 / 0.14% | none through the field in the pass. Whether the crate reads the same table from its own side (dispatch.rs:209, :222, :350 name `classes`) is not checked. Apart: test_discard_exempt.py:118, test_cbm_noid.py:8, convert_diff.py:142 |
| 12 | rust-nat | everything else the seven files compute: 112 functions, no returned value dropped at any call site | read | tab-rust-nat.txt (B) | | marked files' own less row 7: about **10.0 / 6.4 / 5.6 / 10.3% of the pass = 0.060 / 0.262 / 0.018 / 0.335 s** | tab-rust-nat.txt (B) |

### Time per class and path (share of the pass; seconds)

| path | read 0 | minority | read |
|---|---|---|---|
| default | counters, estimated 0.4 / 0.3 / 0.6 / 0.9% (0.002 / 0.022 / 0.003 / 0.026 s); `_mvals`: no time of its own | `_witness`: within `_solve`'s own 0.97 / 0.38 / 0.04 / 1.22%, not separable | 63.8 / 59.8 / 71.0 / 86.3% (0.336 / 4.817 / 0.338 / 2.362 s) |
| rust-nat | the level, known: 1.7 / 1.4 / 2.6 / 3.1% (0.010 / 0.057 / 0.008 / 0.100 s) plus part of `_fixed_noncommutative`; rows 9 and 11: at most 0.2% together | row 10: at most 0.01% | about 10.0 / 6.4 / 5.6 / 10.3% (0.060 / 0.262 / 0.018 / 0.335 s) |

Where the read time is, for choosing a port (own share, dev / fuzz / budget / wiring):

- default: `Solver._propagate` 7.42 / 7.41 / 6.91 / 14.49, `Solver._add_lits` 4.18 / 3.79 / 7.73 / 6.28,
  `Solver._grow` 2.98 / 3.11 / 5.14 / 6.21, `Solver._internal_lits` 2.51 / 3.06 / 4.79 / 2.77,
  `Session._emit_pattern` 2.31 / 1.24 / 3.63 / 2.35 (inclusive 11.2 / 6.2 / 11.6 / 17.9), `Solver.add_internal`
  2.46 / 1.76 / 2.22 / 2.39, `Solver.register_block` 1.71 / 0.86 / 0.93 / 4.36, `compile._or_cnf` 0 / 0 / 6.46 / 0.89
  (inclusive 28.1 on budget), `_common._unsubsumed` 1.02 / 0.05 / 5.43 / 0.50.
- rust-nat: `memos._path` 1.22 / 0.52 / 0.06 / 1.14 and `Memos.items` 0.91 / 0.34 / 0.05 / 1.03,
  `convert.convert` 0.51 / 0.36 / 0.61 / 0.89 (SymPy and stdlib under it 5.7 / 4.6 / 14.5 / 9.1: reading the input),
  `sympy_api._engine_ask` 0.40 / 0.28 / 0.54 / 0.52, `term_live._ask_once` 0.59 / 0.21 / 0.04 / 0.58.

## The read-counting method, so it can be checked

tools367/cnt367.py, installed from outside after the imports (no source change), one cold pass per workload and path:

- **Functions.** sys.monitoring PY_START on every code object of the files named: calls ("computed") and the call
  site. PY_RETURN: the returned value is counted as dropped when the caller's next instruction is POP_TOP. `returns`
  says whether the function has any `return` of a value at all.
- **Stored fields.** Each attribute a class of those files stores (its `__slots__`, `self.X = ...`, annotated class
  fields; found by ast) gets a counting data descriptor in front of the slot or the instance dict. A write of None, a
  bool, a number or an empty container is `trivial` (an initial value). A read is classed from the reader's source
  position: `mut` (the container is filled in place: `self.f[k] = v`, `self.f.append(v)`, ...), `aug` (`self.f += v`)
  or `use` (anything else, and every read that is not a LOAD_ATTR of that name: getattr(), a native reader). A result
  is computed when a clean field gets a non-trivial write, a fill or a self-update (`epochs`), and read when a `use`
  finds it so (`epochs_read`). The class is read 0 for epochs_read = 0 and minority for 2 x epochs_read < epochs,
  summed over the four workloads.
- **Readers** are file:line for every read; tab367.py prints the first four per field and the first three call sites
  per function, the JSON rows hold 40.
- **Excluded readers.** The counted cells install no shadow check, instrument or test, so none reads anything in the
  counts; for the rows of the table their readers were found by rg and are listed after "Apart".

**Proof that each counter fires** (after each pass, outside the counted window; `plant` in every WL-PATH.line):
per file a planted function called once as a statement and once assigned gives exactly 2 calls and 1 dropped return;
per field with a live object one planted LOAD_ATTR read and one `operator.attrgetter` read (PyObject_GetAttr, the call
Rust's getattr makes) each move `reads` by exactly 1 and both count as `use`; a planted class shows one read of each
kind classed as expected. `plant.failed` is empty in all 16 cells. Fields shown to fire: default 245 / 242 / 170 / 184
of 274 (dev / fuzz / budget / wiring); rust-nat 48 / 43 / 43 / 43 of 66. The rest had no object written in that pass:
their rows read "-" (not computed), not "read 0".

**Which cells are used.** Default: every satassume module instrumented (274 fields), digests equal to the reference
in all four. Rust path: with every satassume and slice module instrumented the digests of **dev and fuzz change**
(87c8bba93cdafb96, dbcf7b7b9e3f33d8), so those cells are **not used**; with the seven marked files alone all four
digests are the reference ones, and those are the cells in cntR and in tab-rust-nat.txt. Which module's descriptors
move the answers was not found.

## Limits

- Entries of a dict, list or set held in a field are not counted one by one. A column that is filled for every term
  and of which only some entries are read shows as `read`. This is the form the level and the skeleton had, and the
  form "don't construct as many facts unless they're needed" most likely takes on the default path (clauses emitted
  by `Session._emit_pattern` into the solver, `VarTable.new_nodes`): it is not measured here.
- A value returned to Rust and kept in a Rust table counts as read (the call's value is taken). Whether the crate
  reads it is not answered by these counters.
- A returned tuple of which the caller uses some items counts as read.
- Module-level memo dicts are not wrapped, because a Rust reader holds the dict object itself.
- Times are per function. A result that is one statement of a larger function has no time of its own here; the
  estimates above say so.
- The quiet catches at engine.py:1906 were not counted in these runs.

## What is not done

- Per-entry reads for the default path's containers (first item of "Limits"): the solver's clauses and the VarTable's
  nodes, emitted against used. It needs a counter inside the solver's own lists and is the open half of this audit.
- The crate side of rows 9 and 11, and of every Python value handed to Rust.
- The files after the 80% set (lra.py, sympy_api.py on the default path; lra_backend.py, witness.py on the Rust
  path): counted on the default path (cntB holds every satassume module) but not tabled.
- The cause of the changed answers under full instrumentation on the Rust path.
