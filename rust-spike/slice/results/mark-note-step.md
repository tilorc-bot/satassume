# _Mark's note in term_live's Rust frames (issue 323; sa-port-317)

Tested source 46750d4 (from rust-slice 5f53735). Times UTC, 18 Nov. Scratch: orion ~/sa-rust-ids-work/sa-port-317/;
bar rows pareto0 ~/sp19/sa-rust-ids-work/sa-port-317/bar/.

## What changed

`solver_rs/src/term/live.rs` only, and only on the opt-in path (`SLICE_TERM_FRAMES=rust`). Python's tables are kept.

- `note` asked each table for `native` and `stamp` with `attr_or`, which builds and drops an AttributeError on every
  miss (a plain dict misses both, a `memos.Table` misses `native`). It now calls the builtin
  `getattr(t, name, default)`, as Python's `_note` does; the builtin builds no exception on a miss. pyo3's
  `getattr_opt` would not do: on Python 3.12 it also builds and drops one.
- `reversed` and `collections.defaultdict` are read once in `TermFrames::new` (they were imported per noted table).
- `attr_or` stays for `current_in`'s `stack` probe, which hits.
- No site moved, so no new plant row (planner, 18 Nov). Plants 740-745 are unchanged.

## S1 (pareto1 quiet lease 3cbffb0b, CPU 2, 12 interleaved rounds; bench .so 5b1d96f b18cc160, 46750d4 45f63fdf)

5b1d96f is source-equal to rust-slice 5f53735. `+frames` = SLICE_TERM_FRAMES=rust, `+rust` = SLICE_CONVERT=rust.
144 rows, 0 digest mismatches; every `+frames` row recorded `TermFrames`, every other row `py`.

| arm | dev median s (min-max, 12) | fuzz median s (min-max, 12) |
|---|---|---|
| 5b1d96f+frames | 0.781 (0.776-0.793) | 6.405 (6.335-6.714) |
| 46750d4+frames | 0.769 (0.757-0.776) | 6.382 (6.301-6.451) |
| 5b1d96f+rust+frames | 0.670 (0.664-0.677) | 5.929 (5.906-6.009) |
| 46750d4+rust+frames | 0.652 (0.647-0.659) | 5.901 (5.849-5.931) |
| 46750d4 (frames off) | 0.763 (0.753-0.778) | 6.427 (6.337-6.704) |
| 46750d4+rust (frames off) | 0.651 (0.646-0.661) | 5.960 (5.890-6.326) |

| paired per round | dev median (min to max; rounds faster) | fuzz median (min to max; rounds faster) |
|---|---|---|
| 5b1d96f+frames -> 46750d4+frames | -1.96% (-3.69 to -0.76; 12 of 12) | -0.56% (-4.80 to +1.15; 8 of 12) |
| 5b1d96f+rust+frames -> 46750d4+rust+frames | -2.76% (-3.99 to -1.53; 12 of 12) | -0.71% (-1.87 to +0.29; 10 of 12) |
| 46750d4 -> 46750d4+frames (the switch) | +0.39% (-2.10 to +1.97; 3 of 12) | -0.53% (-4.66 to +0.15; 10 of 12) |
| 46750d4+rust -> 46750d4+rust+frames (the switch) | -0.06% (-1.81 to +1.30; 6 of 12) | -1.09% (-6.37 to -0.13; 12 of 12) |

- Frames-on dev wall is no worse than 5f53735's frames-on: faster in 12 of 12 rounds under both walkers, a gain beyond
  the spread. Fuzz: the median is down, the spread crosses zero.
- The frames' landed dev +3% (frames off to on) is now within spread of zero.

### _Mark's inclusive time (pysampler, same lease, 30 dev and 6 fuzz runs an arm, two interleaved passes)

A sample counts when `TermFrames::mark`, `note` or `add_in` is on its stack (callees included). ms = share x the run's
wall. Per run: median (min-max).

| arm | dev _Mark pooled | dev per run | dev ms | fuzz _Mark pooled | fuzz per run | fuzz ms |
|---|---|---|---|---|---|---|
| 5b1d96f+frames | 1,927 = 8.01% | 7.94% (6.69-10.29) | 63.8 (53.3-82.5) | 1,009 = 2.58% | 2.66% (2.20-2.99) | 173.8 (143.7-195.8) |
| 46750d4+frames | 1,447 = 6.16% | 6.11% (4.65-7.52) | 48.2 (36.2-59.3) | 722 = 1.85% | 1.81% (1.67-2.15) | 117.7 (108.5-141.3) |
| 5b1d96f+rust+frames | 1,932 = 9.42% | 9.31% (6.41-11.21) | 64.2 (44.3-77.4) | 954 = 2.63% | 2.61% (2.46-2.77) | 158.7 (150.4-168.7) |
| 46750d4+rust+frames | 1,348 = 6.75% | 6.81% (4.06-8.98) | 45.8 (27.1-60.4) | 753 = 2.08% | 2.02% (1.99-2.35) | 121.9 (120.5-142.6) |

| `note` alone, pooled | dev | fuzz |
|---|---|---|
| 5b1d96f+frames -> 46750d4+frames | 1,086 (4.51%) -> 609 (2.59%) | 547 (1.40%) -> 314 (0.81%) |
| 5b1d96f+rust+frames -> 46750d4+rust+frames | 1,102 (5.37%) -> 528 (2.65%) | 550 (1.52%) -> 322 (0.89%) |

- `attr_or` under `note`: 513 / 565 dev and 334 / 336 fuzz samples before, 0 after.
- Fuzz: the per-run ranges before and after do not overlap in any of the four comparisons.
- Dev: a run has about 700 samples and about 60 in _Mark, so single runs overlap (6.41-11.21% against 4.06-8.98%).
  The 30-run pooled count is the steadier measure: three measurements of the old code gave 1,918 (316's lease),
  1,927 and 1,932; the new code 1,447 and 1,348, down 25% and 30%. Read as down beyond spread on that basis; the
  per-run overlap on dev is stated here so the planner can read it otherwise.
- Python's own frames spent 3.64% of dev in _Mark (316's profile); the Rust frames now 6.2-6.8%, from 8.0-9.4%.

## The history check (planner addition 5; orion, 46750d4, frames on)

iv317.sh = 314's iv314.sh with the Rust frames on only: 32 runs (fwd/rev, 3 and 5 files, cache on/off, backends rust
and python, 2 each), compared by id with 312's rows (c229014) and 314's (5b1d96f, frames py and rust).

- Ids whose outcome differs between any two runs of a group: 0 in all four groups (179 ids for 3 files, 284 for 5).
- Failed: 5 files, Rust backend, the base's 2 in every column (test_transfer.py::test_models_respect_transfer,
  ::test_protocol_on_fuzz). Python backend 0.
- frames_seen: the 16 Rust-backend runs had `TermFrames installed=True`.

## Other checks (orion, 46750d4, .so a188b7fa)

- test_term_frames.py 18 passed; test_term_live.py 20 passed, 1 skipped.
- Discard run (fresh.py dev rust --term terms --lra --discard, frames on): OUT byte-equal to 314's.
- dev, both switches on, against Python: MATCH (answers_sha 31cd0945c07f02a6).

## Where the time is: top 15 by inclusive share (planner item 3)

From sa-port-316's samples (pareto1 quiet lease, staged 5b1d96f = rust-slice 5f53735, SLICE_CONVERT=rust and
SLICE_TERM_FRAMES=rust), through 314's prof292.py. A function counts once per sample when it is anywhere on the stack.

- Listed: this project's functions (sa_solver Rust and Python frames). Left out: libpython and libc frames, pyo3's
  generic frames. A pyo3 entry wrapper is folded into its function, marked (entry).
- Own = the function is the innermost sa_solver frame with no eval loop below it (its code plus the C API it calls
  directly); for a Python function, it is the leaf.
- The first nine rows are the call chain from the driver to the engine entry, so the rows below them and the own-cost
  lists are where a target shows.

**dev** (20,465 in-loop samples, 30 runs)

| # | function | inclusive | own |
|---|---|---|---|
| 1 | `qt195.py:<module>` | 99.93% | 0.15% |
| 2 | `sympy_api.py:ask` | 99.46% | 0.21% |
| 3 | `term_live.py:_ask_once` | 98.67% | 0.05% |
| 4 | `formula::formula_ask (entry)` | 98.59% | 0.03% |
| 5 | `term_live.py:_ask` | 97.40% | 0.13% |
| 6 | `sympy_api.py:_ask` | 54.64% | 0.07% |
| 7 | `sympy_api.py:_ask_general` | 53.18% | 0.11% |
| 8 | `sympy_api.py:_engine_ask` | 50.67% | 0.09% |
| 9 | `entry::ent_ask (entry)` | 48.90% | 0.17% |
| 10 | `session_glue::GuardMethod::__call__ (entry)` | 33.31% | 0.14% |
| 11 | `term_live.py:_convert` | 32.78% | 0.06% |
| 12 | `convert.py:convert` | 29.37% | 0.44% |
| 13 | `convert.py:rust_walk.<lambda>` | 24.29% | 0.20% |
| 14 | `context::build_memoized` | 24.10% | 0.08% |
| 15 | `context::context_session_from` | 23.96% | 0.00% |

Rows 16-40 (dev): `context::context_session` 23.9; `context::build_context` 23.7; `context::fresh` 17.7; `query::ses_relations (entry)` 16.2; `entry::ask_inner` 15.8; `relations_core::rel_process (entry)` 15.8; `session_live.py:_rel_process` 15.8; `relations_core::rel_process` 15.8; `session_glue::ses_assume_formula (entry)` 14.6; `term::walk::W::klass_native` 12.9; `query::ses_prepare_query (entry)` 9.9; `relations_core::rel_interpret` 9.7; `term::live::TermFrames::mark (entry)` 9.4; `term::walk::Walk::term_row (entry)` 8.9; `discovery::ses_ensure (entry)` 8.0; `term::walk::Walk::klass (entry)` 7.8; `context::call_from::<bool, budget::within_from::{closure#0}, budget::within_fr` 7.5; `budget::within` 7.4; `budget::within_from` 7.3; `discovery::discover_inner` 7.1; `budget::query_cone` 6.8; `term::walk::Walk::walk (entry)` 6.7; `term::walk::W::walk_native` 6.7; `session::SessionCore::visit_id` 6.6; `compile_loop::visit` 6.1.

Own cost, top 10 Rust (dev): `term::walk::W::klass_native` 6.43; `term::live::TermFrames::note` 2.74; `compile_loop::emit_pattern` 2.72; `term::live::attr_or` 2.28; `term::walk::W::enc_native` 1.61; `<alloc[12e961f32105355]::raw_vec::RawVecInner>::finish_grow` 1.59; `constfield::read_limits::{closure#0}` 1.00; `term::walk::W::walk_native` 0.85; `entry::query_literal` 0.77; `compile_loop::split` 0.75.
C leaf, top 6 (dev): `PyDict_Contains` 6.86; `_PyType_Lookup` 5.17; `_PyObject_GenericGetAttrWithDict` 3.51; `PyObject_Malloc` 2.86; `__tls_get_addr@@GLIBC_2.3` 2.82; `__default_morecore@GLIBC_2.2.5` 2.11.
Categories (dev): capi<-rust 47.5%, callback 19.9%, rust 13.2%, sympy<-rust 9.5%, glue 8.4%, python 1.3%, unattributed 0.2%.

**fuzz** (36,046 in-loop samples, 6 runs)

| # | function | inclusive | own |
|---|---|---|---|
| 1 | `qt195.py:<module>` | 99.88% | 0.04% |
| 2 | `sympy_api.py:ask` | 99.67% | 0.06% |
| 3 | `term_live.py:_ask_once` | 99.38% | 0.01% |
| 4 | `formula::formula_ask (entry)` | 99.35% | 0.00% |
| 5 | `term_live.py:_ask` | 99.18% | 0.07% |
| 6 | `sympy_api.py:_ask` | 82.31% | 0.01% |
| 7 | `sympy_api.py:_ask_general` | 81.95% | 0.04% |
| 8 | `sympy_api.py:_engine_ask` | 77.99% | 0.05% |
| 9 | `entry::ent_ask (entry)` | 75.62% | 0.08% |
| 10 | `session_glue::GuardMethod::__call__ (entry)` | 59.86% | 0.24% |
| 11 | `query::ses_relations (entry)` | 44.22% | 0.02% |
| 12 | `session_live.py:_rel_process` | 43.81% | 0.09% |
| 13 | `relations_core::rel_process (entry)` | 43.73% | 0.01% |
| 14 | `relations_core::rel_process` | 43.71% | 1.49% |
| 15 | `context::build_memoized` | 32.81% | 0.03% |

Rows 16-40 (fuzz): `context::build_context` 32.6; `entry::ask_inner` 32.1; `context::context_session_from` 30.8; `context::context_session` 30.7; `context::fresh` 27.1; `relations_core::rel_interpret` 26.9; `session_glue::ses_assume_formula (entry)` 25.2; `query::ses_prepare_query (entry)` 23.4; `query::ses_literal_of (entry)` 20.1; `term_live.py:_convert` 13.8; `convert.py:convert` 12.6; `convert.py:rust_walk.<lambda>` 11.6; `context::call_from::<bool, budget::within_from::{closure#0}, budget::within_fr` 11.5; `budget::within` 11.4; `budget::query_cone` 11.4; `budget::within_from` 11.1; `adapters::LraAdapter::memoized` 8.8; `discovery::ses_ensure (entry)` 8.4; `relations_core::rel_link_objects` 8.0; `budget::union` 7.7; `budget::cone_info` 7.5; `relations_core::rel_link` 7.5; `relations_core::rel_link_objects::{closure#0}` 7.4; `budget::struct_` 7.1; `solver::Solver<PyTheory>::solve_int` 6.8.

Own cost, top 10 Rust (fuzz): `compile_loop::emit_pattern` 2.68; `relkeys::rk_key` 2.32; `term::walk::W::klass_native` 2.21; `<alloc[12e961f32105355]::raw_vec::RawVecInner>::finish_grow` 1.76; `constfield::read_limits::{closure#0}` 1.59; `relations_core::rel_process` 1.49; `relations_core::ensure` 1.33; `session::SessionCore::emit` 1.22; `relations_core::rel_interpret` 1.20; `term::live::TermFrames::term_id_in` 1.07.
C leaf, top 6 (fuzz): `PyDict_Contains` 5.29; `_PyType_Lookup` 4.54; `_PyObject_GenericGetAttrWithDict` 3.43; `__tls_get_addr@@GLIBC_2.3` 2.62; `PyObject_Malloc` 2.53; `__default_morecore@GLIBC_2.2.5` 2.21.
Categories (fuzz): capi<-rust 46.6%, rust 18.3%, callback 14.3%, glue 10.3%, sympy<-rust 9.8%, python 0.5%, unattributed 0.3%.

What the tables say about a next target:

- dev: conversion is a third of the time (`term_live.py:_convert` 32.8%), and `term::walk::W::klass_native` alone is
  6.4% own cost, the largest single Rust function. Building the context session is 24%.
- fuzz: `relations_core::rel_process` is 43.7% inclusive (`rel_interpret` 26.9%), the context session 32.8%,
  conversion 13.8%.
- Both: about 47% of samples are C API called directly from Rust, with `PyDict_Contains`, `_PyType_Lookup` and
  generic getattr as the top C leaves.

## 2x2, the bar and the probe count

(Filled in when the bar is read: see HANDOFF-sa-port-317.md.)
