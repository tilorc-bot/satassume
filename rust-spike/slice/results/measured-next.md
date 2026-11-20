# The next port chosen by measured time (issue 323) — (1) the profile, (2) the target

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
