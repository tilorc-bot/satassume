# `_may_be_nan` in the Rust walk (issue 323; sa-port-324, 326, 327)

Tested source 6587181 (from rust-slice e5db633; Rust and Python source as 119c084), .so 8cb9b507 (x86-64, built on
pareto1). Times UTC, 18 and 19 Nov. Scratch: orion ~/sa-rust-ids-work/sa-port-324, -326, -327; bar rows pareto0
~/sp19/sa-rust-ids-work/sa-port-326/bar/.

## What changed

Only the opt-in path (`SLICE_CONVERT=rust`). Python's `_may_be_nan` (satassume/knowledge/templates/__init__.py:142)
and its call at convert.py:304 are unchanged, and Python's walker stays the default.

- `solver_rs/src/term/dispatch.rs`: a free function `may_be_nan(a, basic, nan, specials, plant)`, the one native copy
  of `_may_be_nan`. `Dispatch::opaque` (`_applied_to_nan`) calls it, and so does the walk.
- `solver_rs/src/term/walk.rs`: `term_row` takes its F_MAYBE_NAN bit from that function. It called Python's function
  through a handle before; the handle is gone from `WalkCtx`, and `specials` is read once from
  `satassume.knowledge.templates._SPECIAL`.
- The recursion is counted by walk.rs's `Depth` (`Py_EnterRecursiveCall`). **That guard now also runs in the
  dispatch's `opaque` path**, which recursed natively without a bound before.
- convert.py: `WALK_PLANTS` gains `nan-no-specials` (746), `nan-atom-args` (747), `nan-one-level` (748). Nothing else.
- p1/bar.sh (6587181): `penv` gains the no-plant rows `walk:rust` and `both:rust`; a `convert:*` row now carries
  `SLICE_CONVERT=rust` as a workload row too.
- No new compiler warning: 18 on base and head (the "19th" line 324 counted is cargo's own summary).

## The ceiling

Before the step, with both switches on, `_may_be_nan` was 0.55% of dev samples and 0.42% of fuzz samples (317's
samples). That is all the step can remove, so S1 may not show it. S1 is reported, not a gate.

## Python calls in `templates/__init__.py`, before and after

The probe over the 20 workloads (30,753 queries), four cells: frames py/rust x convert py/rust (pareto1, tools324/
pc324.sh, pcby324.py, pccmp324.py).

| | frames py, convert py | frames rust, convert py | frames py, convert rust | frames rust, convert rust |
|---|---|---|---|---|
| before (rust-slice e5db633, .so 9acc8c3b) | 2,187,213 | 2,187,213 | 2,187,213 | 2,187,213 |
| after (8e706eb, .so 8cb9b507) | 2,187,213 | 2,187,213 | 20 | 20 |

- Before: 2,187,193 calls from the walk's `term_row` (`_may_be_nan` 1,072,885 and its two generator expressions
  781,317 and 332,991) and 20 module imports, one a process. 7.82 a query on dev, 40.78 on fuzz. No other per-query
  caller.
- After, with `SLICE_CONVERT=rust`: the 20 imports remain, 0 calls a query. With convert py: unchanged.
- No other probed file moved in any cell, 0 per-function rises, knowledge_live equal per workload.
- **The count rule** (a file counts when its per-query Python calls are 0): `templates/__init__.py` meets it with
  `SLICE_CONVERT=rust`: 20 import calls per 20 processes remain, 0 per query. On the default path (Python's walker)
  nothing changed.
- registry_count.py:141-148 rebinds `_may_be_nan` to count it and now reads 0 for the Rust walk. No test rebinds it
  to change behaviour.

## 2x2 (pareto1, 8e706eb, .so 8cb9b507)

20 of 20 references exit 0; 80 of 80 cells run 0 cmp 0: answers equal Python's on the 20 workloads in all four cells.

## The history check (orion, 8e706eb, .so 52b5e1ec, `SLICE_CONVERT=rust`, frames rust and py; 64 runs)

Compared by id with 312's, 314's and 317's rows (tools324/iv324.sh, ivcmp326.py), 48 runs a group:

| group | ids | ids whose outcome differs between any two runs |
|---|---|---|
| 3 files, python | 179 | 0 |
| 3 files, rust | 179 | 0 |
| 5 files, python | 284 | 0 |
| 5 files, rust | 284 | 0 |

- Failed: 5 files, Rust backend, the base's 2 in every column (test_transfer.py::test_models_respect_transfer,
  ::test_protocol_on_fuzz). Python backend 0.
- walk_seen on the 32 Rust-backend runs: `rust:enc,klass,term_row,walk,enc_int`, the .so from the worktree.

## Depth (326)

Nested inputs f(e+1), f(e), sin(e) at depths 1 to 496, one proposition and one assumption object passed to both
walkers: every diff is `[]` on head and on base, for py|rust, py|py and rust|rust; full reads at 50 and 248. The
too-deep boundary did not move (f(e+1): Converted to 248, Kept too-deep from 252, both builds). 324's non-empty
diffs came from its tool, which built the proposition anew per conversion (ids and objects compare by identity).

## S1 (reported, not a gate; pareto1 quiet lease d5188d1c, CPU 2, 12 interleaved rounds; sa-port-327)

Arms: e5db633 (rust-slice) and 6587181, both with `SLICE_CONVERT=rust` and `SLICE_TERM_FRAMES=rust`. Bench .so (built
in sa-cy-build:1): e5db633 45f63fdf (the same hash as 317's 46750d4), 6587181 56b9d27b. 48 rows, 0 digest mismatches;
every row recorded Rust's walker and `TermFrames`. Load during the lease 1.03 to 2.21. Tools: results/tools327/.

| arm | dev median s (min-max, 12) | fuzz median s (min-max, 12) |
|---|---|---|
| e5db633, both switches on | 0.647 (0.644-0.653) | 5.876 (5.811-5.942) |
| 6587181, both switches on | 0.643 (0.637-0.651) | 5.848 (5.783-5.898) |

| paired per round | dev median (min to max; rounds faster) | fuzz median (min to max; rounds faster) |
|---|---|---|
| e5db633 -> 6587181 | -0.65% (-1.65 to +1.00; 11 of 12) | -0.65% (-2.32 to +1.50; 9 of 12) |

- No wall-time loss. Both medians are down by about the ceiling, and both spreads cross zero, so the wall time
  alone does not show a gain.

### Per-function inclusive samples (pysampler, same lease, 30 dev and 6 fuzz runs an arm, two interleaved passes)

A function counts once per sample when it is anywhere on the stack (prof292.py; tools327/nancmp327.py). ms = share x the
median run's wall.

| function | dev e5db633 | dev 6587181 | fuzz e5db633 | fuzz 6587181 |
|---|---|---|---|---|
| in-loop samples | 19,990 | 19,861 | 36,089 | 35,922 |
| Python `_may_be_nan` (all of templates/__init__.py) | 116 = 0.58% = 3.9 ms | 0 | 173 = 0.48% = 29.0 ms | 0 |
| native `dispatch::may_be_nan` | 2 (the dispatch's method) | 22 = 0.11% = 0.7 ms | 0 | 35 = 0.10% = 5.9 ms |
| `Walk::term_row` (entry) | 1,794 = 8.97% | 1,657 = 8.34% | 2,101 = 5.82% | 1,845 = 5.14% |
| `convert.py:rust_walk.<lambda>` | 5,109 = 25.56% | 4,859 = 24.47% | 4,247 = 11.77% | 4,018 = 11.19% |
| `term_live.py:_convert` | 6,769 = 33.86% | 6,531 = 32.88% | 5,018 = 13.90% | 4,811 = 13.39% |

- Python's `_may_be_nan` is gone from the samples (116 and 173 before, 0 after); the native function takes 22 and 35.
- `term_row`'s inclusive share is down 0.63 points on dev and 0.68 on fuzz, about what the Python frames were.

## Plants 746-748

Each is a wrong value in the native `may_be_nan` as the walk calls it (`SLICE_CONVERT_PLANT`); the dispatch always
passes no plant.

| plant | what it does | independent check | workloads (17) | suite row against this bar's plain row |
|---|---|---|---|---|
| 746 `nan-no-specials` | drops the `_SPECIAL` identity test | test_convert_walk.py::test_plant_is_caught[746]: 50 of 83 inputs differ, 0 without | 17 MATCH | 0 ids |
| 747 `nan-atom-args` | follows an atom's arguments | test_plant_is_caught[747]: 11 of 83, 0 without | 17 MATCH | 0 ids |
| 748 `nan-one-level` | no recursion below the first level | test_plant_is_caught[748]: 21 of 83, 0 without | 17 MATCH | 1 id, the planted-history test |

The check runs the script in a fresh process under the plant and compares the Rust walk's rows with Python's convert
rows (all items on Rust, and `term_row` alone); it does not read the plant. It is in the bar's tests phase
(test_convert_walk.py: 20 passed).

**Classification (P2): kept-test catch. No workload verdict and no suite id catches these plants, because nothing
reads the bit.**

- The plants are live on a workload. The differential (convert_diff.py, both walkers on every input, orion, 34cb68c,
  .so 52b5e1ec) on `opaque`: 0 of 2,546 inputs differ without a plant; 1,696 under 746, 64 under 747, 1,946 under 748,
  each as `table terms` (for example `Q.positive(Abs(oo))`, `Q.positive(Abs(i))`, `Q.positive(Abs(x + oo))`). The
  bar's `opaque` column is MATCH under all three.
- The harness is live: on dev, plant 672 `term-row-no-number` gives 612 of 1,221 inputs; 746 gives 0 there.
- Only `opaque` holds such terms. Python's `_may_be_nan` at convert.py:304, counted per workload (tools327/
  nancount327.py, nc327.sh; pareto0, 6587181, Python's walker): over 18 workloads 234,294 calls, 5,838 of them True, all in
  `opaque` (5,838 of its 13,854; `Abs(oo)`, `Subs`, `Piecewise`, nan itself); 0 True in the other 17. fuzz and lra
  were still running when this was written (rows: pareto0 ~/sp19/sa-rust-ids-work/sa-port-327/nc/). The
  other workloads cannot show a plant that turns True into False (746, 748), and 747 found no atom with a special
  argument in the four-workload run below.
- No reader: `fact::MAYBE_NAN` (solver_rs/src/term/table.rs:57) is used nowhere in the crate. Every reader of a
  row's bits masks other flags (algebra.rs:61-90, lra_read.rs:170 and :389, tcore.rs:87, relations.rs:14); py.rs:343
  hands the whole byte back to Python for `Table.row`, which term_history.py:78-83 hashes and tools read. In Python
  only convert.py:305 writes it; term_shadow.py:161 and test_convert_walk.py check it. Templates decide nan through
  `_applied_to_nan`, which is the dispatch's `opaque` and calls `may_be_nan` itself, not through the row.
- So the step moved a computation whose result no engine code reads, on either walker. **Removal candidate (P2), not
  removed here**: the F_MAYBE_NAN bit and its computation in `term_row` (convert.py:304-305 and walk.rs:730-731),
  with plants 746-748 and `nan_cases`; `dispatch::may_be_nan` stays for `opaque`. It needs the planner's word and an
  owner, since convert.py:304 is the Python reference and the brief says it stays unchanged. New OWED item.
- The 20-workload differential (tools327/cd327.sh, 324's optional cd324.sh) was stopped in its no-plant pass (19 of
  20 workloads exit 0) once the `opaque` rows had answered the question; a four-workload run (dev, cls, zero, core;
  pareto0, 6587181, .so 8cb9b507) gave 0 of 3,628 inputs under each plant.

## The bar (pareto0, 6587181, .so 8cb9b507): END 0 at 02:02:52Z 19 Nov

Config: 317's full bar (N=6, no SLICE_ variable from the launcher) plus `walk:rust`, `both:rust` and the three
`convert:nan-*` plants as workload rows and as suite rows. Base: 317's suite rows (tested 46750d4, source-equal to
rust-slice e5db633) and 317's bar for the plant columns. Read by sa-port-327 (tools318/barcmp318.py, wall318.py).

| check | result |
|---|---|
| tests (72 files, one process each) | all exit 0; test_convert_walk.py 20 passed; direct exit 0 |
| suite, plain | 126 failed / 5992 passed, 6159 ids; against base new 0, gone 0, changed 0 |
| live dev, fuzz | 8 of 8 MATCH (answers_sha 31cd0945c07f02a6, 173502b6ef285ad6) |
| 15 extra workloads | 30 of 30 MATCH |
| `walk:rust`, 17 workloads | 17 of 17 MATCH |
| `both:rust`, 17 workloads | 17 of 17 MATCH |
| `frames:rust`, 17 workloads | 17 of 17 MATCH |
| `walk:rust`, suite | 127 failed / 5991 passed; against base 1 id, the planted-history test (passed -> failed) |
| `both:rust`, suite | 126 failed / 5992 passed; against base 0 ids |
| workload plant columns of 317's bar (32 columns, 17 workloads) | verdict and fired count equal 317's in all 544 rows (413 MATCH, 131 DIFFER) |
| new workload rows (5 columns, 17 workloads) | 85 of 85 MATCH (see "Plants 746-748") |
| fm rows | plain: 20 workloads, 0 differ; the two fm plants exit 1 (4 and 3 differ) |
| kept reasons | 42 entries, all equal base |
| TermFault in suite logs | 0 in 29 rows; 86 in convert:enc-int-no-sign, as in 317's bar |

Environment (env-summary.txt): `SLICE_CONVERT=rust` in suite-walk:rust, suite-both:rust and the eight convert:* rows;
`SLICE_CONVERT_PLANT=nan-*` in its own row only; `SLICE_TERM_FRAMES=rust` in suite-both:rust, suite-frames:rust and
the six term:tl-* rows.

Suite rows by id against 317's rows, the 25 rows both bars have:

- 0 ids differ in 16: plain, convert:enc-int-no-sign, convert:klass-no-is-expr, convert:term-row-no-number,
  convert:walk-args-unreversed, fm-hand-instrument-by-name, fm-hand-patched-direct, fm-implies-swap, fm-ite-swap,
  nc-memo-true-false, same-is, sb-join-address, term:mark-leaves-entry, term:mark-skips-native,
  term:mark-wrong-pattern, term:tl-run-flip.
- Only the planted-history test differs in 6: dispatch-keeps-memo, frames:rust and term:tl-current-outer (failed in
  317's bar, passed here); term:tl-guard-quiet, term:tl-ids-reversed and term:tl-mark-skip (passed there, failed here).
- class-is: 135 failed against 133; 2 ids differ, both `test_zero_glue.py::test_zero_in_the_set_is_an_equality` G5
  (passed -> failed). The order-dependent family of 311 and 312; informational ([138b]). Twin workload DIFFER as in
  317's bar.
- convert:enc-true-as-false: 534 failed against 569; 89 ids differ. Known not to reproduce by id ([138b]). Caught
  (408 ids changed against this bar's plain row, the planted-history test included).
- term:tl-term-stale: 242 failed against 216; 51 ids differ. Informational ([141b]): the plant keeps process-wide
  state. 242 is 3 above the 216 to 239 of 318's eight runs. Caught (116 ids changed against this bar's plain row, the planted-history test
  included), and its workload columns equal 317's.

Known base rows by id: the planted-history test
(`tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`, id() reuse, see
below); test_transfer.py::test_models_respect_transfer and ::test_protocol_on_fuzz on the Rust backend in the history
check. The slice-test base failures of the siblings block (test_term_live.py 2, test_handler_count.py 2,
test_catch_count.py 3) did not show: all 72 files exit 0 under the bar's invocation.

Exceptions caught at engine.py:1906: workload rows 0 (701 handler files in live/ and extra/, all empty). Suite: 39
rows in 2 tests, the base's multiset, in the plain row and 24 others, the five new rows among them; the other five
are convert:enc-int-no-sign 1, convert:klass-no-is-expr 38, convert:term-row-no-number 42, term:tl-run-flip 42 (all
as in 317's bar) and convert:enc-true-as-false 690 (747 there; the order-dependent row). The counter is live: it
reads 39 in the plain suite row.

### The planted-history test (known id()-reuse row)

It passed in the plain suite row here and on base, but flipped in six planted rows and failed in suite-walk:rust
against base's plain row, so a28c548's repeat check was run (orion, worktree at 34cb68c, source as 6587181, .so
52b5e1ec; 20 fresh processes a cell; tools327/run1.sh, sweep.sh):

| cell | passed |
|---|---|
| Rust, the test | 0 of 20 |
| Rust, `SLICE_CONVERT=rust`, the test | 1 of 20 |
| Rust, both switches, the test | 0 of 20 |
| Rust, keep-alive variant, the three modes | 20 of 20 each |
| Python, the test, the three modes | 19, 18 and 19 of 20 |
| Python, keep-alive, the three modes | 20 of 20 each |

Every one of the 63 failures is at test_public_incremental.py:204, `assert N == 2` with N < 2 (52 with 0, 11 with
1). That is a28c548's signature: the test fails, keep-alive is clean, Python is near its base rate (4 of 60 here; 2
to 6 in 50). In the bar's 30 suite rows it passed in 7 (plain, dispatch-keeps-memo, frames:rust,
term:tl-current-outer, both:rust, convert:nan-no-specials, convert:nan-atom-args) and failed in 23.

### Wall time of this bar (OWED [139b])

4 h 49 m 50 s (21:13:02Z 18 Nov to 02:02:52Z 19 Nov). 317's bar: 4 h 21 m 28 s; this one has 5 more workload columns
and 5 more suite rows.

| phase | 317 | this bar |
|---|---|---|
| tests | 2 m 20 s | 2 m 27 s |
| suite | 1 m 54 s | 1 m 50 s |
| live | 14 m 24 s | 14 m 23 s |
| plants (dev, fuzz) | 62 m 32 s | 69 m 57 s |
| extra (15 workloads) | 133 m 23 s | 145 m 16 s |
| suiteplants | 45 m 57 s | 54 m 58 s |
| fmrows | 57 s | 57 s |

- Suite rows are 1 m 41 s to 2 m 05 s each; fm-ite-swap 4 m 39 s. The new rows: walk:rust 1 m 45 s, both:rust
  1 m 49 s, convert:nan-no-specials 1 m 47 s, convert:nan-atom-args 1 m 46 s, convert:nan-one-level 1 m 41 s.
  frames:rust and the six term:tl-* rows took 12 m 47 s, the eight convert:* rows 14 m 18 s.
- The five new workload columns added 7 m 25 s to plants and 11 m 53 s to extra.
- Three workloads make 117 m of extra's 145 m: budget 47 m 19 s, rootof 36 m 02 s, wiring 33 m 16 s.
