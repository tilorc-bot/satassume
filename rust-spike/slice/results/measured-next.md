# The next port chosen by measured time (issue 323) — (1) the profile, (2) the target, (3) the port, (4) the gate, (5) S1, (6) the ruling, the pre-bar checks, the bar started, (7) the bar read and the landing

Planner's ruling for sa-port-356, items 1 and 2. No source of the package, the slice or the crate is changed by these
two items: Python stays the default and the reference, no switch is added yet, the probe count stays 21 of 32.

## (1) Profile, sa-port-356: de88d9b9, quiet lease on pareto1

- Tree: rust-slice de88d9b9 (crate, satassume and slice sources equal to b7302f83's, checked by goprof356.sh).
  .so: pareto1 x86-64 0b6f073f5c5a600b (sa-port-354's build of b7302f83). Image sa-eval-bench:1, Python 3.12.15,
  CPU 2 pinned, quiet lease 20fa32a4, 06:48Z to 06:52Z 20 Nov, load at most 0.98.
- Configuration **rust-nat**, the fastest: SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust SLICE_WITNESS=1 SLICE_WITNESS_RUST=1
  (cap 32). Reference row **py-on32**: the package alone with SLICE_WITNESS=1.
- Tools: tools356. Wall time by tools342/qt342.py (S1's driver), 5 rounds, the two arms alternating in one
  bench-container invocation. Shares by sa-port-143's pysampler.so (SIGPROF every 1 ms, native stack plus Python frames)
  through sa-port-195's classifier, read by ana356.py: dev and budget 30 runs, fuzz 6, wiring 8. Calls by prof356.py
  (cProfile, prof350.py's cprof kind over the whole pass). Tables: tools356/tab-p1.txt, convert-split-p1.txt.
- **Method against 350's**: 350 timed one function with two clock reads and used cProfile for the split below it. Over
  the whole pass that does not work: cProfile is call-weighted and charges Rust entered through a slot to the calling
  Python file (sympy_api.py read 42% own in the orion trial), and a Python-level signal handler charges Rust time to
  the next callback. So the shares are the C sampler's (the tool S1's per-function inclusive times come from) and
  cProfile gives only the call counts. A share times the median pass is seconds, comparable with 350's shares of `s`.

Wall time, 5 rounds (answers' digests equal in both arms on all four):

| workload | rust-nat median s | iqr/median | py-on32 median s | iqr/median |
|---|---|---|---|---|
| dev | 0.6145 | 0.6% | 0.5206 | 4.5% |
| fuzz | 4.1414 | 0.6% | 5.3998 | 0.6% |
| budget | 0.3240 | 0.5% | 0.4832 | 0.5% |
| wiring | 3.3688 | 1.5% | 2.9831 | 0.7% |

Where the time is, share of in-loop samples (ana195's categories; "Rust side" = rust + glue + capi<-rust, sa_solver's
own code and the C API it calls directly; "Python side" = the rest, charged to the innermost Python frame's file):

| workload | samples | Rust side | of it C API under Rust | Python side | of it SymPy's own code |
|---|---|---|---|---|---|
| dev | 18,785 | 68.7% | 44.0% | 31.1% | 9.2% |
| fuzz | 25,251 | 73.3% | 42.3% | 26.4% | 10.3% |
| budget | 9,779 | 63.2% | 39.1% | 36.4% | 24.2% |
| wiring | 27,293 | 66.8% | 44.1% | 33.0% | 11.2% |

Own (bytecode plus the C a file's bytecode calls directly) and inclusive share per remaining Python file, ranked by own
summed over the four workloads (the full table with the bytecode/C split and calls: tools356/tab-p1.txt):

| file | dev own / incl | fuzz own / incl | budget own / incl | wiring own / incl | own summed |
|---|---|---|---|---|---|
| (SymPy's own code, not a file to port) | 9.18 / 9.3 | 10.31 / 10.6 | 24.15 / 24.8 | 11.16 / 11.2 | 54.80 |
| **slice/convert.py** | 5.50 / 31.1 | 2.92 / 18.1 | 2.79 / 35.6 | 6.33 / 38.4 | **17.54** |
| satassume/knowledge/domain.py | 1.80 / 2.0 | 1.45 / 1.5 | 4.47 / 4.6 | 3.66 / 3.7 | 11.38 |
| slice/term_live.py | 2.87 / 98.5 | 2.61 / 99.3 | 0.19 / 99.8 | 2.64 / 98.9 | 8.32 |
| satassume/sympy_api.py | 2.47 / 99.3 | 1.36 / 99.6 | 0.62 / 99.8 | 2.31 / 99.5 | 6.76 |
| satassume/state/memos.py | 2.54 / 2.9 | 0.91 / 1.0 | 0.12 / 0.1 | 2.47 / 2.7 | 6.05 |
| slice/session_live.py | 0.92 / 18.6 | 0.82 / 37.9 | 0.25 / 7.3 | 0.96 / 7.0 | 2.95 |
| satassume/theories/euf/euf_adapter.py | 1.02 / 1.2 | 0.62 / 1.1 | 0.02 / 0.0 | 0.84 / 0.8 | 2.50 |
| satassume/sat/formula.py | 0.12 / 0.3 | 0.23 / 0.4 | 2.00 / 2.4 | 0.13 / 0.4 | 2.48 |
| slice/lra_backend.py | 0.52 / 3.1 | 1.56 / 5.7 | 0.00 / 0.0 | 0.00 / 0.0 | 2.08 |
| satassume/witness.py | 0.42 / 4.6 | 0.61 / 8.4 | 0.01 / 3.9 | 0.21 / 4.4 | 1.25 |
| slice/witness_live.py | 0.38 / 4.5 | 0.23 / 7.8 | 0.06 / 3.9 | 0.36 / 4.3 | 1.03 |
| satassume/engine.py | 0.25 / 0.4 | 0.14 / 0.3 | 0.16 / 0.2 | 0.20 / 0.3 | 0.75 |
| satassume/theories/lra/lra_adapter.py | 0.13 / 0.3 | 0.41 / 0.7 | 0.01 / 0.0 | 0.00 / 0.0 | 0.55 |

Calls are not time: the ruling's count put term_live.py (1.13M calls) second and wiring.py (613k) fifth; by time
term_live.py is third among the repository's files and wiring.py is at most 0.2 points summed. The repository's Python files together own 16 to 22% of dev,
fuzz and wiring; SymPy's own code is the largest single Python cost, and convert.py is the file that reaches most of it
(SymPy and stdlib time with convert.py the nearest repository frame: dev 5.71%, fuzz 4.73%, budget 20.70%, wiring
8.62%; sympy_api.py 2.0 to 3.8%). That SymPy time is reading the input and does not move with a port.

## (2) The target: slice/convert.py

**Chosen: slice/convert.py**, the largest own share among the repository's files on every count the ruling names:
17.54 points summed, first on dev (5.50%), fuzz (2.92%) and wiring (6.33%). It is not offline, and it is not a P1 guard. It is the
run-time conversion of the input, not the input: the SymPy objects coming in stay as they are, and a Rust walker
already exists behind SLICE_CONVERT=rust. Stop rule: 5.50% on dev against 2 x 0.6% and 6.33% on wiring against
2 x 1.5% (this run's spreads; 354's 12-round spreads were 0.6% and 0.8%), so it does not trigger.

What the own time is (share of in-loop samples; tools356/convert-split-p1.txt):

| part of convert.py | dev | fuzz | budget | wiring |
|---|---|---|---|---|
| per-query entry: `convert`, `formula`, `default_engine_settings`, `_Walk.__init__`, `power_rows` | 3.08 | 1.41 | 0.53 | 3.66 |
| per-class callbacks from Rust's `klass`: `_template_name`, `_structural_class` | 1.38 | 0.46 | 0.07 | 1.34 |
| walk trampolines (Rust `walk` to the Python lambdas :428-:432 and back into Rust) | 0.42 | 0.30 | 0.36 | 0.77 |
| read dispatch, OWED [156](a): `read`, `_read_*`, the three property lambdas, `enc`'s lambda | 0.59 | 0.76 | 1.82 | 0.54 |
| convert.py own, all | 5.50 | 2.92 | 2.79 | 6.33 |

**For Tilo's open question 7** (can the converter itself move): [156]'s read dispatch is 11% of convert.py's own time
on dev, 26% on fuzz, 65% on budget and 9% on wiring. The walker's own remainder is 89%, 74%, 35% and 91%: it is the
per-query entry and the per-class callbacks, both plain reads of classes and of the engine's settings that Rust can do
itself. So on dev and wiring the converter's cost is not the dispatch, and the remainder can move.

Each result read by something (the port lesson), by reading the code:

| result of `convert` | read by |
|---|---|
| `tables` (strings, classes, terms, powers, settings, formula, the three counts) | `sa_solver.TermTable(c.tables)`, term_live.py:93; table.rs |
| `tables['reads']` (`_Walk.read`) | table.rs's lazy reads, at run time |
| `ids` | `q.ids.get`, term_live.py:327, :444, :513; the native witness check's boundary lookups |
| `objects` | term_live.py:94; `read` and `power_rows` index it |
| `classes` | `same_class`, term_live.py:416 |
| `counts`, `raised` | only `_note_query`'s report counters, term_live.py:300-303 |
| `Kept(reason)` | term_live.py:89 |

Open for the port: `counts` and `raised` are read by the reports alone (`_note_query` owns 0.42% of dev). They are
diagnostics, so whether a port keeps them is the planner's call; I did not trace which report rows use them.
Nothing else computed by `convert` is unread. `_template_name` and `_structural_class` return into the class rows that table.rs reads.

What a port can gain: the bytecode part of convert.py's own time (dev 2.22%, fuzz 1.15%, budget 0.99%, wiring 2.50%)
goes; the C part (3.28%, 1.77%, 1.80%, 3.83%) is reads of SymPy classes and objects, which Rust still makes through the
C API, with fewer of them where a trampoline or a second lookup disappears. An honest expectation is 2 to 4% on dev and
wiring and about 1% on fuzz and budget, against spreads of 0.6% and 1.5%. Item 5's rule (faster beyond the spread on two
of four) is reachable on dev and wiring and not certain.

The second file by own time, satassume/knowledge/domain.py (11.38 points summed; `constructed_noncommutative` alone is
1.2% of dev and 3.0% of wiring), is reached from the converter too: `term_row` calls it once per term (convert.py:305,
walk.rs:166). It is a separate file and stays out of this target; it is the measured candidate after convert.py.

## (3) The port of convert.py, sa-port-357 and sa-port-358: written and tested on orion, NOT gated

Item 3 of the planner's ruling. Items 4 (the per-query gate), 5 (S1) and 6 (bar, landing) are not started, so nothing
here says the port is equal to Python on the workloads or faster: no workload ran, nothing ran on a pareto or on a
lease, and no x86-64 .so of this tree exists. The correction to (2): `counts` and `raised` are read by kept tests as
well as by `_note_query` (the planner's trace: test_lazy_reads.py:74, :90, :342-343, :379-381), so they are ported, not
removed.

- Tree: the commit that adds this section (parent 7c376cc, from rust-slice de88d9b9). The .so the runs below used:
  aarch64 4d8921d9c510e99f (orion, built from this source, untracked). Base for comparison: de88d9b9, .so e0365239348de148.
- Switch: `SLICE_CONVERT=rust`, the converter's existing switch; no new switch, and no separate off-switch for the new
  items (an item can still be named alone, `SLICE_CONVERT=read,entry`, as before). Python's `_Walk` and the body of
  `convert` stay the default and the reference.

### What moved
Four new items of `convert.RUST_ITEMS` (solver_rs/src/term/walk.rs), after the five that landed with the convert step:

| item | what it answers in Rust |
|---|---|
| `klass_calls` | `_template_name` and `_structural_class`, per class, inside Rust's `klass` |
| `power_rows` | `_Walk.power_rows` |
| `read` | `_Walk.read` and the `_read_*` it dispatches to |
| `entry` | `convert`'s body, `default_engine_settings`, `formula`, `_rel`, and the state `_Walk.__init__` makes (`sa_solver.WalkEntry`) |

With every item on, no Python walker object exists for the query: Rust makes the state, and `tables['reads']` is the
bound method `Walk.read_own`. `counts` and `raised` are the same dict and list, filled by Rust.

### What of convert.py still runs as Python under SLICE_CONVERT=rust
- `convert`'s first lines: the dispatch on `WALK[0]` (kept because tests and tools replace `convert.convert` and `WALK[0]`).
- `_read_own_base`'s `Mul(2, t)`: the reference's existing construction left where it is, not new construction at
  query time by the native path (counter 745).
- `Kept.__init__` and `Converted.__init__`, called as classes.
- The fallbacks below, and any definition a test or an instrument replaced.

### Fallbacks and counters (740-746, `sa_solver.walk_counts()`)
| counter | meaning | fired by (kept test, test_convert_walk.py) |
|---|---|---|
| 740 cv:entry, 741 cv:formula, 742 cv:read | native conversions, `formula` calls, reads | test_the_entry_runs_in_rust_and_its_counters_fire |
| 743 cv:fallback:depth | `formula` nested past 100 connectives goes to Python's `formula` from the top | test_a_deep_formula_is_pythons[101], [130], [700] |
| 744 cv:fallback:name | a template whose class has its own metaclass goes to Python's `_template_name` | test_template_names_are_pythons |
| 745 cv:py:own_base | an `own_base` read (the Python construction above) | test_the_entry_runs_in_rust_and_its_counters_fire |
| 746 cv:patched | a conversion with an item off because its Python definition was replaced (P1) | test_a_replaced_definition_is_called |

Each fires on its planted case. Their per-workload values are item 4's; no zero is reported here.

The depth fallback reads the formula twice (Rust's try up to the bound, then Python's from the top). `formula` only
reads, and `counts`/`raised` belong to the walker made after it, so they stay Python's: the kept test compares them at
100 connectives (the last native depth) and 101 (the first that falls back), key for key in the same order, before any
read, after one read, and after every read (`diff`). They are equal; nothing had to be reset.

### Replaced definitions (P1)
`WalkEntry` compares `_Walk`'s methods and the module's ported functions with `convert._ORIGINAL` per query; a replaced
one turns its item off for that query (`term`, `s`, `__init__`: every item). The instrument lazy_reads.py
replaces `_Walk.read`, but as a script it never turns Rust's walker on (it does not call `convert.from_env()`), so 746
does not count there and its rows are byte-equal under `SLICE_CONVERT=py`, `=rust` and plant 773 (sa-port-359's
correction, tools359/lazyrun359.py). Only when something turns the walker on first is the `read` item off for every
query under it (746 = 150 of 150 on dev's first 150, rows equal to Python's).
sa-port-358 found the guard incomplete on its first run and fixed it:
- an item that is off was called through the function captured when the context was made, so a replaced `term_row`
  (or `enc`, `enc_int`, `walk`, `klass`, `power_rows`) was skipped; they are now called by name on the walker
  (walk.rs:452-482), and `_template_name` / `_structural_class` by name on the module (walk.rs:877, :919);
- two kept tests read the walker behind the reads (`c.tables['reads'].__self__`: `.raised`, and a weak reference to
  see it die with its table); Rust's `Walk` now has `raised` and takes weak references (walk.rs:315, :1382).
Effect, by test id under the suite plugin: de88d9b9's Rust walker fails 8 ids of test_lazy_reads.py that Python's
walker passes; at the head the Rust walker fails none that Python's passes (below).

### Plants 768-773 (`SLICE_CONVERT_PLANT`; bar rows `convert:NAME`, tools358/rows358.sh)
Rows over the six kept files with the suite plugin (`SLICE_CONVERT=rust SLICE_CONVERT_PLANT=NAME`, what p1/bar.sh's
penv sets for `convert:NAME`); "only under the plant" counts ids that fail there and pass without the plant.

| plant | row | ids failing only under the plant | also caught by |
|---|---|---|---|
| 768 calls-structural-not | convert:calls-structural-not | 10 | test_plant_is_caught[768] (the differential) |
| 769 power-rows-drop-last | convert:power-rows-drop-last | 3 | test_plant_is_caught[769] |
| 770 read-commutative-not | convert:read-commutative-not | 39 (1 id passes only under it: test_term_live.py::test_a_discard_leaves_nothing_inside_a_nested_memo, a row that fails without the plant on every tree) | test_plant_is_caught[770] |
| 771 entry-no-assumptions | convert:entry-no-assumptions | 11 | test_plant_is_caught[771] |
| 772 formula-and-as-or | convert:formula-and-as-or | 4 | test_plant_is_caught[772] |
| 773 entry-skip-replaced | convert:entry-skip-replaced | 11: test_a_replaced_definition_is_called, the 8 ids de88d9b9's Rust walker fails, and test_read_raised_reaches_the_top and test_read_term_missing_reaches_the_top | test_plant_773_is_caught |

773 is a kept-test catch: no workload replaces a definition of convert.py (kept tests and lazy_reads.py do), so the
differential over workloads cannot see it. The whole-suite and workload rows of these plants are the bar's (item 6).

### What was run (orion, aarch64, .so 4d8921d9c510e99f; output ~/sa-rust-ids-work/sa-port-358, summary tools358/rows358.txt)
- test_convert_walk.py standalone: 34 passed (each new item alone and all together against Python's walker, counts and
  raised included; the plants; the deep formulas; template names; the replaced definitions).
- The six kept files (test_lazy_reads, test_convert_once, test_term_live, test_term_ids, test_knowledge_lazy,
  test_convert_walk) under run_suite.sh, `-n 4`, `SLICE_TERM_FRAMES=rust`, one id deselected (next section):

| pass | result | failing ids only on this pass |
|---|---|---|
| head, SLICE_CONVERT=py | 10 failed, 308 passed, 6 skipped, 5 errors | 0 against rust |
| head, SLICE_CONVERT=rust | 10 failed, 308 passed, 6 skipped, 5 errors | 0 against py, 0 against base |
| de88d9b9, SLICE_CONVERT=rust | 18 failed, 283 passed, 6 skipped, 5 errors | 8 against the head's rust (test_lazy_reads.py: test_other_kinds_are_lazy_and_their_plant_is_caught[commutative], [finite], [power]; test_plant_restoring_the_eager_read_is_caught[complex], [key]; test_stock_term_plant_is_caught[finite-stock_finite], [power-stock_power]; test_without_the_nan_line_nan_refuses_with_a_miss) |

  The 15 ids that fail on all three passes alike (by id in tools358/rows358.txt: 5 errors in test_knowledge_lazy.py, 6
  failures in test_term_ids.py, 4 in test_term_live.py) also fail file by file. They are rows of this invocation (these
  kept files under `-p rust_plugin -p handler_count`; the bar runs them plain, p1/one_test.sh) and were not diagnosed.
- Quiet handlers (engine.py's `except Exception` round the complete check, `_consistent`): 0 rows in the three passes.
  The counter was not shown to fire in this step, so that zero is not evidence; TermFault in the logs: 0.

### The test that never returns under handler_count: not a regression of the default path
`rust-spike/slice/test_convert_walk.py::test_a_deep_formula_is_pythons[700-too-deep]` (new with the port) span for 41
minutes in sa-port-357's job, in the pass with Python's walker. Cause: an interpreter behaviour that our own instrument
handler_count triggers, not this tree. With any `sys.monitoring` EXCEPTION_HANDLED callback registered (handler_count.py
registers one), a RecursionError raised by a call made from a generator-expression frame at the recursion limit never
comes out: the interpreter stays in the frame at 100% CPU. It is not specific to one CPython: tools358/repro.py shows it
in 14 lines with no satassume and no SymPy on 3.12.14 (limits 91 and 93 do not return within 10 s, 92 returns at once;
without the callback all return), and the planner's own run of `repro.py 2 91 m` hangs on 3.13.15 and 3.14.7 as well
(rc 124 on both). `convert.formula` recurses through a generator expression and is unchanged from de88d9b9; the same
conversion with Python's walker never returns on de88d9b9 either (tools358/deep.py, deep-first.txt: 700, 520 and 500
levels do not return within 40 s under the callback on both trees; 400, 480 and 490 levels, and 700 without the
callback, answer in milliseconds). No in-process timeout can stop it (the loop is inside the interpreter). Logged as
OWED [157]; nothing is filed with CPython (Tilo's call).

Ruled for sa-port-359 and done there: the case carries a `skipif` whose condition is exact, `exception_handled_tool()`
(test_convert_walk.py): some `sys.monitoring` tool id has EXCEPTION_HANDLED in `get_events`, or in the local events of
Python's `formula` code. It reads no plugin name and no environment, and it is read at the test's setup. The reason
names OWED [157] and the repro. The id runs and passes wherever no such tool is registered (plain pytest: the bar's
tests phase, row in (4)); under run_suite.sh it reports SKIPPED. The per-job deselect and `timeout` are gone from
tools358/passes.sh.

## (4) The gate, sa-port-359 and sa-port-360: read; ONE row of the differential differs (a question, not landed)

Tested SHA 00535462 (source b580119 plus the ruled skipif). .so: x86-64 venv build 0f78ac2962f34b3a (gate, suite, iv,
differential; pareto0), x86-64 bench build 8b8041d3fe6223c2 (S1; pareto1), aarch64 4d8921d9c510e99f (orion). Base
de88d9b9: venv 37b7560e245df518, bench 0b6f073f5c5a600b, aarch64 e0365239348de148. Python's walker is the default and
the reference; the port is opt-in under `SLICE_CONVERT=rust` (no new switch, no separate off-switch for the new items).
Output: ~/sa-rust-ids-work/sa-port-359 (the jobs) and sa-port-360 (this step's checks); summaries in tools359 and
tools360. No bar has run, nothing is landed.

| check | result |
|---|---|
| per query, Python's walker against `SLICE_CONVERT=rust`, 20 workloads and fuzz seeds 0/1/2/42 (tools359/gate-perquery.txt) | 24 of 24 EQUAL: 42,753 queries, 41,354 conversions, 78,743 reads; 0 rows differ in answer, Engine.stats, last_budget_limited, counts (keys, order, numbers), raised, number of terms |
| moved ids, livecmp per workload, `SLICE_CONVERT=py` against `=rust` on the Rust backend (gate/livecmp-WL.txt) | MATCH 20 of 20: answers, sessions, Engine.stats, moved rows, their order, _SPLIT/_CACHE points (dev: 1,985 queries, 918 sessions, 198 moved rows, 80 engine points, every diff 0) |
| answers, three arms (Python backend; Rust backend with Python's walker; with Rust's) | 60 of 60 rows MATCH |
| the differential, every input converted by both walkers and every lazy read compared (convdiff/total.txt; tools360/convdiff-total-00535462.txt) | **69,476 inputs, 1 difference**, 14,258,356 reads compared, slow 2, reread 0. See below |
| suite by id on the Rust backend, 6,317 ids, cells rust, py, nat, off, base (tools360/byid-00535462.txt) | rust against py: 0 ids in one only, 0 outcomes differ. The same for nat against rust, rust against base, off against base, rust against off. Every cell: 6,149 passed, 127 failed, 23 skipped, 18 xfailed |
| iv, 64 runs with Python's walker and 64 with Rust's | 0 runs differ in failing ids or counts. Rust backend: tests/test_transfer.py::test_models_respect_transfer and ::test_protocol_on_fuzz fail in 16 of 32 runs under both walkers alike (the second is the known 46-stub row) |
| the six kept files under the suite plugins, orion (sa-port-359/k-py, k-rust, k-base) | py and rust: 10 failed, 5 errors, the same 15 ids; 0 ids only on rust. Base's Rust walker: 18 failed, 5 errors |
| R5, term_discard.py on dev, lra, fuzz with every Rust switch on (sa-port-359/disc, tools352/disctab352.py) | rollbacks checked 1,985 / 1,957 / 3,000, clean all, left-something 0 (only the exempt _CACHE rows); plain against discard: 0 answers, 0 digests differ; the no-rollback plant: 300 of 300 left-something |
| quiet handlers (engine.py's and sympy_api.py's `except Exception`) | 0 handler rows and 0 queries with `caught` on the 20 workloads, in each of the three arms (30,773 queries each); suite: 49 catches in every cell, base included. The counter fires: `SLICE_PLANT_HANDLER=complete_check` gives 661 rows on dev and 166 on scope, `=verdict` 46 on dev, with Rust's walker on (sa-port-360/hplant; aarch64) |

Fallbacks per workload under `SLICE_CONVERT=rust` (gate-perquery.txt; each counter fires in a kept test on the same
build, gate/kept.log, 34 passed, `[700-too-deep]` PASSED in plain pytest): 743 depth 0, 744 name 0, 746 patched 0 on
every workload; 745 own_base (Python's `Mul(2, t)`, the reference's own construction) 12, all on lra. Suite cells:
745 = 19, the others 0.

The suite's 127 failures are the Rust backend's standing rows (126 since 5c10b, results/port-6g.md, plus the
planted-history test, which failed in all five cells here, base and Python's walker included; [137e]'s keep-alive
check has not been run on it in this step: the bar's to do).

**The 15 ids that fail alike on py, rust and base under `-p rust_plugin -p handler_count`** (OWED [157](b), not this
step's): test_knowledge_lazy.py::test_a_baseexception_comes_through_as_itself, ::test_a_query_counts_the_reads_it_asked_for,
::test_a_read_that_raises_is_a_refusal_and_counts, ::test_a_root_is_converted_and_asked_with_no_complex_call,
::test_the_template_reads_once_per_table (5 errors); test_term_ids.py::test_a_key_plant_answers_on_python,
::test_a_plan_plant_changes_the_trace, ::test_a_scaffold_plant_answers_on_python, ::test_a_termwise_plant_moves_an_answer,
::test_the_consumer_runs_and_decides (KeyError 'term:rust:_eq_links'), ::test_undo_restores_python;
test_term_live.py::test_a_discard_leaves_nothing_inside_a_nested_memo,
::test_a_refusal_goes_past_the_handler[lra.py:461], [relations.py:1989], [relations.py:2018].

**The 8 ids of test_lazy_reads.py that base's Rust walker fails and the head passes**, with the cause read from
k-base/pytest.log: test_other_kinds_are_lazy_and_their_plant_is_caught[commutative], [finite], [power];
test_plant_restoring_the_eager_read_is_caught[complex], [key]; test_stock_term_plant_is_caught[finite-stock_finite],
[power-stock_power] (all seven: "this plant restores an eager read and the count did not see it", `assert 0 > 0`);
test_without_the_nan_line_nan_refuses_with_a_miss ("DID NOT RAISE TermRefuse"). Each plants by replacing a method of
Python's `_Walk` (`term_row` at test_lazy_reads.py:115-121, `term` at :314-319). de88d9b9's Rust walker runs
`term_row` and `term` natively and never looks at `_Walk`, so the plant does not run and the test's count stays 0. The
head looks, per query, for replaced definitions and calls them by name (P1, section (3)), so the plant runs.

### The one difference of the differential: OWED [157]'s hang, at a different call depth for each walker

Input (the suite's, tests/test_noncommutative.py:546): `Q.commutative(Trace(M*N))`, assumptions True. Python's child
answered all 72 reads (read_raised 16); Rust's child was killed at the 22nd, `complex` of term 3 (`M*N`, a MatMul),
at the read's CPU limit (30 s). The differential's suite pass runs under `-p handler_count` (p1/convert_diff.sh:21), which registers a
sys.monitoring EXCEPTION_HANDLED tool.

Read (tools360/depth360.py, no pytest; each walker's reads in the differential's order up to that one, in a forked
child, called D frames deeper; tools360/depth360-aarch64.txt):
- `is_complex` of `M*N` recurses to the recursion limit in SymPy: under both walkers the read gives None and records
  ('complex', 3, 'RecursionError'). With no monitoring tool that takes 0.007-0.026 s and is equal under both walkers at
  every depth tried (D 0-5).
- With an EXCEPTION_HANDLED tool registered, the read returns at every third depth and otherwise never does (killed at
  8 s): Python's walker returns at D = 2, 5 and hangs at 0, 1, 3, 4; Rust's returns at D = 1, 4 and hangs at 0, 2, 3, 5.
  When it returns, the value and the raised entry are the same as without the tool.
- So it is [157]'s interpreter behaviour (a RecursionError at the limit under an EXCEPTION_HANDLED callback), and which
  depths hang follows the number of Python frames under the read: Rust's `read` item calls the SymPy property with one
  Python frame fewer than `_Walk.read`, which is the port. On orion, the same test with the differential on and the
  plugin loaded stops BOTH walkers at `complex 3` (slow 1, differences 0); without the plugin: 528 reads, differences 0,
  slow 0. On pareto0 under xdist the depth happened to be one where Python's returns and Rust's does not.
- de88d9b9 could not show it: there the `read` item did not exist, both walkers read through `_Walk.read` at the same
  depth (convert step: 0 of 69,256).

The same suite pass without the plugin, nothing else changed (tools360/nohandler360.sh; pareto0, the staged tree of
00535462, .so 0f78ac2962f34b3a, `-p rust_plugin -p plant_count -n 6`; tools360/nohandler-00535462.txt): 40,163 inputs,
**0 differences**, 10,781,055 reads compared, reread 0, slow 1 (`Q.lt(x, sin(exp(exp(exp(5)))))`, where both children
stop at the same read: the known slow input of 359's pass too), exit 0. The pass's own pytest line is 132 failed
against 134 with the plugin; those two were not compared by id. depth360.py on that x86-64 build gives the same table
as on aarch64 (tools360/depth360-x86.txt: Python's returns at D = 2, 5, Rust's at D = 1, 4, plain equal at every depth).

It is a difference this step cannot remove without either adding a frame to the native read or changing a shared bar
file (p1/convert_diff.sh), and the bar's convdiff phase runs the same pass, so it would exit 1 there: Status: question.

### The planner's check on 359's base row: `term_live.current()` never gives a stale `_Query`

359's base row: the last query's `_Query`, TermTable and walker stay referenced until the next conversion, under
Python's walker and on de88d9b9 alike. The question was whether a query-time reader can reach it.
- By the source: `sympy_api._engine_ask` has three callers, all in `sympy_api._ask` (sympy_api.py:570, :598, :602).
  term_live wraps `_ask`; `current()` (term_live.py:160) reads only the thread's stack, which that wrapper pushes
  before the call and pops in its `finally` (:1101-:1111, and the second run after a refusal :1126-:1133). A query that
  is not converted still gets its own entry: a `_Query` whose `kept` is the reason, or a `_Refused`.
- By a trace on the head (tools360/current360.py; scope, dev, cls, lra, opaque, rootof, value, twin; 15,203 queries;
  both walkers, tools360/current360-nat.txt and -py.txt, identical counts): at every `_engine_ask` call, `current()`
  was this ask's own `_Query` (13,606 with a table; 31 kept: out-of-scope 25, args-eq-not-is 6) or a `_Refused` (478,
  the second run of a discarded query); STALE 0, anything else 0. After each top-level ask it was None, and at a
  direct call of `_engine_ask` outside any ask, right after a workload's last converted query, it was None (8 of 8).
So no query-time reader starting from `current()` can reach the earlier query's `_Query`: a memory-only base row, to
be OWED. No source changed for it. The holder is still not named.

## (5) S1, sa-port-359's run read by sa-port-360: the landing rule is met

Quiet lease f700c9b2 on pareto1 (24 minutes), bench-container, pinned, 10 arms alternating inside one invocation, 12
rounds; 1-minute load 0.99-1.07 for the whole lease (the pinned run itself; timing-s1/load.txt, timing-bw/load.txt).
All ten arms give one answers digest per workload. tools360/s1-med-00535462.txt (tools359/med359.py).

Rust at the head against Rust at de88d9b9, S1's configuration (`rust-nat`: SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust
SLICE_WITNESS=1 cap 32 SLICE_WITNESS_RUST=1), median wall seconds:

| workload | head | de88d9b9 | change | per-round quartiles | slower in | larger iqr | |
|---|---|---|---|---|---|---|---|
| dev | 0.5992 | 0.6190 | -3.2% | -3.8% .. -2.8% | 0 of 12 | 1.2% | faster beyond the spread |
| fuzz | 4.0875 | 4.1570 | -1.7% | -2.2% .. -1.1% | 0 of 12 | 0.6% | faster beyond the spread |
| budget | 0.3272 | 0.3302 | -0.9% | -1.2% .. -0.8% | 1 of 12 | 0.5% | faster beyond the spread |
| wiring | 3.2701 | 3.3885 | -3.5% | -3.9% .. -2.7% | 0 of 12 | 0.9% | faster beyond the spread |

The other two Rust pairs agree (rust-on32: -2.3%, -1.5%, -1.1%, -2.5%; rust-off: -2.4%, -1.6%, -1.0%, -3.1%). The Python rows, head against base, are within the spread on all four workloads in both arms (py-off: -0.2%,
-0.1%, -0.1%, -0.1%; py-on32: -0.3%, -0.0%, -0.5%, +0.3%). Rule: faster beyond the spread on at least two of four and no
worse on any, Python rows within the spread: met (four of four). Against (2)'s expectation of 2-4% on dev and wiring:
3.2% and 3.5%.

## (6) Ruling (a), the pre-bar checks, the probe count; the bar started detached (sa-port-361)

**The ruling (planner, ~13:00Z 20 Nov): option (a).** `p1/convert_diff.sh`'s suite pass no longer loads
`-p handler_count` (commit 5b20d1f2, one line removed, a comment citing OWED [157] and the row). **p1/convert_diff.sh is
a shared bar tool changed by this step.** It is guarded source, so **the tested SHA is now 5b20d1f2** (00535462 plus
that one file). The crate is unchanged (`git diff --quiet 00535462 5b20d1f2 -- rust-spike/slice/solver_rs`), so the .so
hashes stay: x86-64 venv 0f78ac2962f34b3a, bench 8b8041d3fe6223c2, aarch64 4d8921d9c510e99f. The frozen branch is
origin/bar/measured-next-5b20d1f2.

**Condition 2, nothing checked vanishes.** No reader took handler rows from the differential's pass: `p1/bar_sum.py`
reads `handlers.*.jsonl` only from the bar's suite rows (:28, :73, :161), `*.handlers` from the live rows (:107) and the
extra rows (:118), and has no reference to `convdiff`. Those rows are written by `p1/bar.sh` `suite()` (:131), which
keeps `-p rust_plugin -p handler_count -p plant_count`. `convert_diff.py` reads only the `SLICE_CONVERT_DIFF` files.

**Condition 3, the same exposure in the bar's own suite rows: head and base behave the same.**
`tests/test_noncommutative.py::test_scalar_valued_matrix_functions_stay_in_scope` (the id at :546, the suite's
`Q.commutative(Trace(M*N))`) alone under `suite()`'s exact invocation (`-p rust_plugin -p handler_count -p plant_count
-p hyp_profile --hypothesis-profile=bar -n 6`), each cell under `timeout 300`, pareto0 (tools361/pre361.sh):

| tree, .so | SLICE_CONVERT=py | SLICE_CONVERT=rust |
|---|---|---|
| head 5b20d1f2, 0f78ac2962f34b3a | rc 0, 1 passed in 1.07 s | rc 0, 1 passed in 0.95 s |
| base de88d9b9, 37b7560e245df518 | rc 0, 1 passed in 1.08 s | rc 0, 1 passed in 0.95 s |

The plugin was loaded in every cell (a `handlers.PID.jsonl` per process, 0 rows; the row file has the id, passed, on
the Rust backend). The same four cells with `-n 0` (the main process, another call depth): 1 passed in 0.08 s each. No
cell hangs, so the bar's suite rows are not exposed here; that fits the test's own ask not making the read (`is_complex` of
`M*N`) that the differential forces (not traced). Footnote, OWED [157]: the hang is reachable only where something reads every lazy
read under an EXCEPTION_HANDLED tool, which after (a) nothing in the bar does.

**Condition 4, the rerun differential, from the changed script as it stands** (pareto0, tree 5b20d1f2, N=6 P=7;
tools361/pre361.sh; output ~/sa-rust-ids-work/sa-port-361/pre-5b20d1f2/convdiff): **69,527 inputs, 0 differences**,
14,267,639 reads compared, 1,783,462 terms, `exit 0`. Of these the suite: 40,166 inputs, 0 differences, 10,779,167
reads (sa-port-360's pass without the plugin: 40,163; the pass is not under the derandomized hypothesis profile); the
20 workloads: 29,361 inputs. slow 1: `Q.lt(x, sin(exp(exp(exp(5)))))`, the known row. reread 100, all on rootof, all
`finite` of `x*CRootOf(...)`: Python's own second ask answering differently, the known row of
results/convert-step.md:129 (84, then 59 there; 0 in sa-port-359's run; it follows SymPy's assumptions shuffle), not a
difference between the walkers. The suite pass: 132 failed, 6144 passed, 23 skipped, 18 xfailed, the same line as
sa-port-360's pass without the plugin. The 20 workloads each exit 0. The answers (py, rust with Python's walker, rust
with Rust's): 57 of 57 rows MATCH when this was written, lra's three rows still running (lra takes 27.5 minutes in the
differential's first pass, as in sa-port-359's job, then 29 minutes on Python and about 20 on Rust in the answer runs: the job is about 1h40m,
not the 40 minutes its lease line says). tools361/chain361.sh starts the bar only on 60 of 60.

**The probe count stays 21 of 32; convert.py does not start to count.** tools354/pc354.sh on 5b20d1f2 and de88d9b9,
pareto1, three cells each, 20 workloads, 30,753 queries, 60 of 60 rows `ref 0 run 0 cmp 0` on each tree
(tools361/gopc361.sh, pctab361.py, pc-tab.txt):
- d0, every switch unset (the default): every probed file equal to base, 0 rows differ per workload and function.
  convert.py 14,559,922 calls on both: Python's walker is the default, so convert.py is still per-query Python there.
- w1 (`SLICE_CONVERT=rust`, with SLICE_WITNESS=1 and SLICE_TERM_FRAMES=rust): convert.py **2,272,599 -> 58,980** calls,
  per query 42.2 -> 1.2 on dev, 98.6 -> 2.0 on fuzz, 927.9 -> 2.4 on budget, 77.5 -> 2.0 on wiring, 163.9 -> 2.0 on
  lra. What is left per query is `convert` (29,361) and `Converted.__init__` (29,331); functions of convert.py called
  35 -> 16. Gone: `rust_walk`'s lambdas (838,516 and 263,354), `_structural_class` 425,137, `_template_name` 326,137,
  `formula` 90,166, `default_engine_settings` 29,361 and its generator 58,722, `_Walk.read` 36,503, `_Walk.__init__`
  and `_RustWalk.__init__` 29,337 each, `_Walk.power_rows` 29,331, `_read_key` 21,114, `_read_commutative` 14,650,
  `_rel` 10,929. nat (w1 plus SLICE_WITNESS_RUST=1): 2,429,056 -> 58,980.
- No other probed file changes in any cell (w1 and nat: 0 functions differ between base and head).

**The bar: started detached by tools361/chain361.sh, not read by this session.** `gobar361.sh 5b20d1f2
0f78ac2962f34b3a` (tools360's launcher and job with this session's paths; neither had run before): p1/bar.sh as of
5b20d1f2 on origin/bar/measured-next-5b20d1f2, pareto0, shared lease, phases `tests suite live plants extra suiteplants
fmrows convdiff sum`, rows wnative:on and the six convert:NAME rows as PLANTS and SUITE_PLANTS, CONVERT_PLANTS for the
convdiff phase, BASE sa-port-354's bar suite rows, then the kept file under no plant and each plant in plain pytest
(kept.txt). One end marker on orion for both outcomes, ~/sa-rust-ids-work/sa-port-361/gobar-end.txt: `NO-BAR reasons`
(chain361.sh:18) or `END rc ...` (gobar361.sh:19). Still owed for the landing: reading the bar, [137e]'s check when the
planted-history test shows, bar.sh land, guard, PUSH=1, rule [91].

## (7) The bar on 5b20d1f2 read: END 0; the planted-history repeat check; the landing (sa-port-362)

Land-only step: no source, test or bar tool changed. The marker ~/sa-rust-ids-work/sa-port-361/gobar-end.txt says
`END 0 END 0 2026-11-20T18:03:43Z 0f78ac29 5b20d1f2`; pre-end.txt says `answer rows 60, MATCH 60` (lra's three rows,
pending when (6) was written: MATCH). The bar ran on pareto0 under a shared lease for 3h20m, tree 5b20d1f2 from
origin/bar/measured-next-5b20d1f2, files in sa-port-361/bar. phases.txt: tests, suite, live, plants, extra,
suiteplants, fmrows, convdiff, sum, each `exit 0`. **Which .so loaded:** 0f78ac2962f34b3a (the x86-64 venv build of
00535462, whose crate is source-equal to 5b20d1f2's) in all eight phases of so-loaded.txt. launcher-env.txt: no SLICE_
variable in the launcher's environment; env-summary.txt: each suite row's processes carried its own row's variables and
no other. bar.log has no traceback, kill or timeout line.

| row | result |
|---|---|
| tests | 73 files, none with a non-zero exit (test_convert_walk.py 34 passed, test_lazy_reads.py 74 passed and 5 skipped, test_term_live.py 20 passed and 1 skipped); direct.txt `exit 0` |
| suite, Rust backend, against sa-port-354's bar suite as base | 6,317 ids: 6,149 passed, 127 failed, 23 skipped, 18 xfailed; new 0, gone 0, changed outcome 0. The 127 are the base's by id ((4)); the planted-history test is one of them (below) |
| quiet handlers, suite | 39 rows in 2 tests, the same multiset as base (34 and 4 `_consistent` AttributeError rows in tests/test_invariants.py::test_ci_stream_reports_only_what_replays, 1 `Engine._build_context` RuntimeError in tests/test_transfer.py::test_protocol_on_fuzz); ids whose caught rows differ from base: 0; TermFault 0 |
| live, dev and fuzz | 8 of 8 MATCH (py against py, py against rust, traced against untraced end states for both): answers, messages, sessions, end states, streams, lra, Engine.stats, moved rows and their order, 0 differences each; 14 handler files, 0 rows |
| extra, 15 workloads | 30 of 30 MATCH (control and py against rust for each), the same nine difference counts all 0; 15 handler files, 0 rows |
| wnative:on (SLICE_WITNESS=1 SLICE_CONVERT=rust SLICE_WITNESS_RUST=1) | answers and messages equal to Python's with the switch off on all 17 workloads; its suite row: changed outcome 0 |
| fm rows | 20 workloads, 0 differ, exit 0; both fm plants caught (4 and 3 workloads differ, exit 1) |
| the differential (convdiff phase, the suite pass without the plugin, ruling (a)) | 63,782 inputs (the suite and the bar's 15 workloads), **0 differences**, 13,468,551 reads, slow 1 (`Q.lt(x, sin(exp(exp(exp(5)))))`, the known row), reread 0, `exit 0`; answers 45 of 45 MATCH. The 20-workload run is (6)'s: 69,527 inputs, 0 differences, 60 of 60 |
| kept.txt (test_convert_walk.py in plain pytest, SLICE_CONVERT=rust, no plant and under each of the six) | 7 lines, each rc 0, 34 passed, `[700-too-deep]` PASSED |
| kept reasons | every share equal to base on all 17 workloads |

The zeros of the quiet handlers stand on (4)'s planted case (`SLICE_PLANT_HANDLER=complete_check`: 661 rows on dev).

### The plant table (P2: each caught by a check that does not read the plant's flag)

| plant | workload rows that DIFFER (of 17) | whole suite, ids changed (of 6,317) | the differential on dev and fuzz (4,219 inputs), differences | kept test (passed in the tests phase) |
|---|---|---|---|---|
| 768 calls-structural-not | 10: dev, fuzz, cert, cls, scope, transfer2, transfer, twin, value, zero | 81 passed to failed | 4,195 | test_plant_is_caught[768] |
| 769 power-rows-drop-last | 0 | 0 | 109 | test_plant_is_caught[769] |
| 770 read-commutative-not | 2: fuzz, cls (Engine.stats) | 0 | 4,195 | test_plant_is_caught[770] |
| 771 entry-no-assumptions | 0 | 0 | 4,195 | test_plant_is_caught[771] |
| 772 formula-and-as-or | 0 | 0 | 2,816 | test_plant_is_caught[772] |
| 773 entry-skip-replaced | 0 | 0 | not run (no workload replaces a definition of convert.py, (3)) | test_plant_773_is_caught |

Every plant is caught: 768 to 772 by the differential (`exit 1` each, convdiff-plants.txt), which compares the two
walkers' output and reads no flag, and by their kept tests; 773 by its kept test, which reads the replacement's own
calls. The workload rows have no `fired` counter for the walker's plants (the column says 0 for all of them, 768
included), so a MATCH there is read with the next paragraph, not as a zero of its own.

**Three plants move no workload answer and no suite id: 769, 771 and 772. The reason for 771 and 772 is that the
table's formula skeleton is not read by the engine's answer.** Checked on orion (aarch64 .so 4d8921d9c510e99f, three
queries, each plant against no plant in one process, a no-plant control equal): 771 and 772 change `tables['formula']`
and the string numbering that follows from it (`strings`, and the ids inside `terms` and `settings`); the number of
terms and of objects is unchanged, so the assumptions' terms are still walked. `tables['formula']` is read by table.rs
when the TermTable is made (:346) and from there only by `TermTable.formula()` (term/py.rs:311), whose one caller is
term_shadow.py:623 `check_formula`, a check; the engine's own formula comes from formula.rs `formula_ask`
(term_live.py:1140). So with 771 leaving the assumptions' skeleton out, the 29,216 queries of the 17 workloads answer as Python does. This is
the reference's shape, not the port's: Python's `formula` in convert.py made the same skeleton for the same readers.
It bears on "each ported result is read by something": the skeleton's readers are table.rs's constructor and the
shadow check, nothing that answers. 769 changes `powers` alone (109 of 4,219 inputs on dev and fuzz have a power row to
lose); no answer, stat or state row of the 17 workloads depends on the last power row, and which reader of `powers`
would is not traced here.

### The planted-history test shows, so a28c548's method was run ([137e])

tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence FAILED at :204 in each of
the bar's eight suite rows, as on base (changed outcome 0): `assert 0 == 2` in the plain row, wnative:on, 768 and 772,
`assert 1 == 2` in 769, 770, 771 and 773. No row flips. The check (tools362/rep362.sh and gorep362.sh, tools355's with
this step's cells; pareto0, shared lease 268d0099, the bar's own tree of 5b20d1f2 and .so 0f78ac2962f34b3a, one fresh
process a run, 20 runs a cell; tools362/rep-sum.txt; trees.txt: every run on that tree and .so, the Rust walker on in
the 80 runs that set SLICE_CONVERT=rust):

| cell | the test, passed | failures | keep-alive variant, passed |
|---|---|---|---|
| rust, every switch off | 0 of 20 | :204 `assert 0 == 2` 17, `1 == 2` 3 | 20 of 20 |
| rust, SLICE_CONVERT=rust | 0 of 20 | :204 `0 == 2` 13, `1 == 2` 7 | 20 of 20 |
| rust, wnative:on's environment | 0 of 20 | :204 `0 == 2` 19, `1 == 2` 1 | 20 of 20 |
| python, every switch off | 17 of 20 | :204 `1 == 2` 3 | 20 of 20 |

That is [137e]'s signature in every cell: :204, `assert N == 2` with N < 2, the plain test failing and sa-port-185's
keep-alive variant passing 20 of 20. Python's 3 of 20 is above 355's 1 of 20 and near the top of a28c548's base rate
(2 of 50 and 6 of 50). Reported by id as the known id()-reuse failure; the test is not edited. Footnotes with OWED
[157]: the id at tests/test_noncommutative.py:546 is not among the failed ids of any suite row here ((6) condition
3), and `[700-too-deep]` (the ruled skipif under a monitoring tool) ran and PASSED in the tests phase and in plain
pytest under no plant and each plant (kept.txt).

### The landing

`bash rust-spike/slice/p1/bar.sh land 5b20d1f2` in the worktree: origin/rust-slice is still de88d9b9, the tested SHA's
base, so the incoming diff is empty and the rebase is a no-op. Tested against landing source: only HANDOFF files and
rust-spike/slice/results differ, so the guard lists no file under satassume/ or rust-spike/slice/ outside results/.
Rule [91]: no other session's bar was running (`agent ls --all`, `machine ls`). Pushed with PUSH=1 from the commit
that holds this section.

Still owed, for the architect's list: the memory-only base row ((4), 360's `current()` check); the 15 plugin-mode ids
([157](b)), undiagnosed; and, new here, the formula skeleton of the converted tables is read only by table.rs's
constructor and term_shadow.py's check (P2: redundant code is removed or listed with an owner).
