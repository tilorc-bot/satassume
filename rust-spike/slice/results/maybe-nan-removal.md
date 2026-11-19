# The F_MAYBE_NAN bit removed from `term_row` (issue 323)

sa-port-332 wrote the removal, sa-port-334 added the planner's ruling (2) on plant 753 and launched the bar, and
sa-port-335 read the bar and landed. Branch `port/maybe-nan-removal`, from rust-slice ec34788.

- **Tested SHA f4ce4b2**, x86-64 .so **c20c326f** (orion .so 09e6fa11). The landed commit is the one that holds this
  file; `bar.sh land f4ce4b2` shows it differs from f4ce4b2 only in results/ and the handoff files.
- `term_row` no longer computes the bit on either walker (convert.py `_Walk.term_row`, walk.rs `term_row_native`). Bit
  32 is reserved and written as 0. Plants 746-748 are retired.
- `dispatch::may_be_nan`'s cases and `_applied_to_nan` are unchanged: `git diff ec34788 f4ce4b2 -- satassume` is empty,
  and in dispatch.rs only the plant parameter and its three branches went, which were off for the dispatch.
- Plant 753 is `dispatch-nan-arg-on`: at `opaque`'s call `may_be_nan` is taken as True for every argument.

## The 2x2 (pareto1)

Base ec34788 (.so 8cb9b507) and head f4ce4b2 (.so c20c326f): 20 of 20 references exit 0, and 80 of 80 cells run 0
cmp 0, on each tree (tools334/pc334.sh, pccmp334.py).

## Probe

`templates/__init__.py` goes from 2,187,213 calls to 20 (the imports) in the two convert-py cells, and stays at 20 in
the two convert-rust cells. The falls are `_may_be_nan` 1,072,885 and its two generator expressions, 781,317 and
332,991. No other probed file moved, no function rose, knowledge_live is equal per workload, and the query count is
equal (30,753). **The count stays 21 of 32**: STATUS.md:19 already counted the file, with the footnote "`_may_be_nan`
called per query only by convert.py (input layer)", which no longer applies. The probe was taken on f4ce4b2, whose
source is the landed source.

## Row bytes (pareto1 for all 20 workloads; orion for the `rootof` control)

One line: **rows differ from ec34788 in bit 32 only.** Per walker cell (Python's and Rust's), over the 20 workloads,
436,059 rows on each tree; bit 32 is set in 6,035 rows on base (`opaque` 5,838, `lra` 197) and in 0 on head; head's raw
digest equals its masked digest on all 20; `shape_bad` 0; the Rust cell's rows were all written by `_RustWalk`
(436,059) and the Python cell's by `_Walk`. The masked digest is equal between the trees on 19 of 20 workloads.

The twentieth is `rootof`, and its difference is not from this change. Two runs of the same head tree differ on it in
the same way (orion, tools335/rowdump335.py, rdcmp335.py):

| pair, `rootof`, Python's walker | rows | rows differing | what differs |
|---|---|---|---|
| head, run 1 against run 2 | 112,046 | 4,784 | one integer per row, the same offset in every row |
| base against head, run 1 | 112,046 | 4,784 | one integer per row, the same offset in every row |
| base against head, run 2 | 112,046 | 4,784 | one integer per row, the same offset in every row |

Rust's walker gives the same (orion, .so 52b5e1ec base and 09e6fa11 head): base against head, 112,046 rows, 4,784
differing, one integer per row with one offset; head's Python cell against head's Rust cell likewise; and two runs of
the base tree's Python cell likewise.

The integer is a Dummy's `dummy_index`, which `term_row` writes through `_hashable_content()` (convert.py:277). SymPy
draws its base at import with `randint(10**6, 9*10**6)` (symbol.py:507), so it differs by process; the values seen
were 1,848,962, 4,188,574 and 6,076,328. No row differs in length or in any other element. The same holds for
rbcmp334.py's last line (`cpy rows == crust rows` False on both trees): the two cells are two processes. This is on
both trees and both walkers; whether a row should carry a per-process number is not this step's question, and it is
named in the report.

327 counted 5,838 `_may_be_nan` True calls on `opaque` and 0 elsewhere over the bar's 17 workloads; `lra` is not one
of them.

## The bar (pareto0, f4ce4b2, .so c20c326f): END 0 at 06:19:50Z 19 Nov

Config (tools334/job334.sh): TESTS=all, suite, live, plants, extra (15 workloads), suiteplants, fmrows, sum; N=6; no
SLICE_ variable from the launcher. PLANTS: `dispatch-nan-arg-on`, `dispatch-opaque-off`, `walk:rust`, `both:rust`.
Suite rows: plain, those four, and the five `convert:*`. Left out: the three retired `convert:nan-*` rows and the fm-*,
term:* and frames:rust plants of steps this one does not touch. Base: 326's bar (tested 6587181, .so 8cb9b507). Read
with tools318/barcmp318.py and wall318.py.

| check | result |
|---|---|
| tests (72 files, one process each) | all exit 0; direct exit 0 |
| suite, plain | 127 failed / 5991 passed, 6159 ids; against base new 0, gone 0, changed 1: the planted-history test |
| live dev, fuzz | 8 of 8 MATCH (answers_sha 31cd0945c07f02a6, 173502b6ef285ad6, as in 326's bar) |
| 15 extra workloads | 30 of 30 MATCH |
| `walk:rust`, `both:rust`, 17 workloads each | 34 of 34 MATCH |
| `dispatch-opaque-off`, 17 workloads | `opaque` fired 274, DIFFER; fired 0 and MATCH on the other 16, as in 326's bar |
| plant 753 `dispatch-nan-arg-on`, 17 workloads | 10 DIFFER, 7 MATCH (table below) |
| workload plant rows both bars have (51) | fired count and verdict equal 326's in all 51 |
| fm rows | plain: 20 workloads, 0 differ, exit 0; the two fm plants exit 1 (4 and 3 differ) |
| kept reasons | 42 entries, all equal base |
| .so the workload runs loaded | c20c326f in all 174 reports |

Environment (env-summary.txt): `SLICE_CONVERT=rust` in suite-walk:rust, suite-both:rust and the five convert:* rows;
`SLICE_TERM_FRAMES=rust` in suite-both:rust only; `SLICE_CONVERT_PLANT` and `SLICE_SESSION_PLANT` each in its own row
only; the plain row has none.

### Plant 753, `dispatch-nan-arg-on`

Caught by workload answers and by suite ids.

| workload | fired | verdict |
|---|---|---|
| opaque | 61 | DIFFER (first difference is an answer, query 0) |
| dev | 36 | DIFFER |
| core | 160 | DIFFER (an answer, query 5) |
| f6 | 340 | DIFFER |
| value | 339 | DIFFER |
| wiring | 33 | DIFFER |
| zero | 22 | DIFFER |
| transfer:7:60 | 16 | DIFFER |
| transfer2:3:40 | 15 | DIFFER |
| loop | 4 | DIFFER |
| cls | 9 | MATCH |
| twin | 4 | MATCH |
| fuzz, budget, cert, rootof, scope | 0 | MATCH |

Suite row: 402 failed / 5716 passed; 277 ids changed against this bar's plain row. On orion before the bar (334, .so
09e6fa11, `opaque`): fired 61, DIFFER, answers True 179 -> 18 and False 169 -> 23.

`dispatch-opaque-off`, suite row: 178 failed / 5940 passed; 51 ids changed against the plain row.

The suite's own "plant fired" line reads 0 in every row, the rows with hundreds of changed ids included, so it says
nothing here; the fired counts above are the workload reports'.

### Suite rows by id against 326's rows (the 8 rows both bars have)

| row | failed / passed | ids differing from 326's row | changed against this bar's plain |
|---|---|---|---|
| plain | 127 / 5991 | 1: the planted-history test, passed -> failed | |
| both:rust | 127 / 5991 | 1: the planted-history test, passed -> failed | 0 |
| walk:rust | 126 / 5992 | 1: the planted-history test, failed -> passed | 1, that test |
| convert:klass-no-is-expr | 295 / 5804 | 1: the planted-history test, failed -> passed | 189 |
| convert:term-row-no-number | 133 / 5986 | 1: the planted-history test, failed -> passed | 8 |
| convert:walk-args-unreversed | 127 / 5991 | 0 | 0 (caught by the differential, convert-step.md:184) |
| convert:enc-int-no-sign | 247 / 5870 | 1: `tests/test_s7_trig.py::test_numbers_sound[cos]`, passed -> failed | 121 |
| convert:enc-true-as-false | 594 / 5526 | 108 (534 failed in 326's; the order-dependent row, [138b]) | 467 |

Known base rows by id: the planted-history test
(`tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`, id() reuse, below).
The slice-test base failures of the siblings block (test_term_live.py 2, test_handler_count.py 2, test_catch_count.py
3) did not show: all 72 files exit 0 under the bar's invocation.

Exceptions caught at engine.py:1906: workload rows 0 (140 handler files in live/ and extra/, all empty). Suite: 39
rows in 2 tests, the base's multiset, in the plain row and in suite-both:rust, suite-walk:rust,
suite-dispatch-nan-arg-on, suite-dispatch-opaque-off and suite-convert:walk-args-unreversed. The counter is live: it
reads 39 in the plain row and changes under convert:enc-int-no-sign (1), klass-no-is-expr (38), term-row-no-number
(42) and enc-true-as-false (748 in 111 tests). TermFault in suite logs: 0 in 9 rows, 86 in convert:enc-int-no-sign, as
in 326's and 317's bars.

### The planted-history test (the plain row's one differing id; first gate, case (a))

In the bar it failed at test_public_incremental.py:204 with `assert 1 == 2`; it passed in 326's plain row. a28c548's
repeat check on the tested source (orion, 332's worktree, .so 09e6fa11; 20 fresh processes a cell; tools335/run1.sh,
sweep.sh):

| cell | passed |
|---|---|
| Rust, the test | 0 of 20 |
| Rust, `SLICE_CONVERT=rust`, the test | 0 of 20 |
| Rust, both switches, the test | 0 of 20 |
| Rust, keep-alive variant, the three modes | 20 of 20 each |
| Python, the test, the three modes | 20, 20 and 19 of 20 |
| Python, keep-alive, the three modes | 20 of 20 each |

Every one of the 61 failures is at test_public_incremental.py:204, `assert N == 2` with N < 2 (48 with 0, 13 with 1).
That is a28c548's signature as [137e] words it: the test fails, keep-alive is clean, and Python is near its base rate
(1 of 60 here; 4 of 60 on 6587181). On 6587181 the same check gave Rust 0, 1 and 0 of 20. In this bar's 10 suite rows
the test passed in 4 (walk:rust, dispatch-nan-arg-on, convert:klass-no-is-expr, convert:term-row-no-number) and
failed in 6.

### `test_s7_trig.py::test_numbers_sound[cos]` in the convert:enc-int-no-sign row

A planted row, and the plant is caught either way (121 ids changed against the plain row). The id failed here
(InconsistentAssumptions) and passed in 326's row, and it is not a hypothesis test, so it was read: it depends on the
tests that ran before it in its xdist worker, and base and head agree under each order.

| run under `SLICE_CONVERT_PLANT=enc-int-no-sign`, `SLICE_CONVERT=rust` (orion) | base tree (ec34788, .so 52b5e1ec) | head tree (f4ce4b2 source, .so 09e6fa11) |
|---|---|---|
| the id alone, and its file alone (46 tests) | passed | passed |
| this bar's worker order up to the id (1,030 tests, one process) | failed; 14 failed ids | failed; the same 14 failed ids |
| 326's bar's worker order up to the id (1,100 tests, one process) | passed; 13 failed ids | passed; the same 13 failed ids |

The two workers' lists differ (250 ids before it here that 326's worker did not run before it, 320 the other way).
Each replay ran its list in order (ran.txt `in_order True`) with the bar's plugins and hypothesis profile, and the
plant was on: the first failure is the bar worker's, test 36, `TermFault: conversion: tables refused`. Tools:
tools335/s7.sh, replay335.sh, order335.py. So this is a second order-dependent planted row, like
convert:enc-true-as-false ([138b]), and no difference between base and head.

### Wall time of this bar

1 h 28 m 41 s (04:51:09Z to 06:19:50Z 19 Nov). Phases: tests 2 m 20 s, suite 1 m 50 s, live 14 m 24 s, plants 11 m
18 s, extra 41 m 52 s, suiteplants 15 m 59 s, fmrows 57 s. Suite rows: 1 m 43 s to 1 m 51 s each (plain 1 m 50 s,
dispatch-nan-arg-on 1 m 44 s, dispatch-opaque-off 1 m 47 s, walk:rust 1 m 46 s, both:rust 1 m 46 s). Longest extra
workloads: budget 14 m 10 s, rootof 9 m 47 s, wiring 9 m 27 s, value 2 m 17 s. No timing was measured for this step;
these are the bar's wall times on a shared lease.

## Where the rows are

- Bar: pareto0 ~/sp19/sa-rust-ids-work/sa-port-334/bar; base ~/sp19/sa-rust-ids-work/sa-port-326/bar.
- 2x2 and row bytes: pareto1 ~/sp19/sa-rust-ids-work/sa-port-334/ (pc-base, pc-head, rb-base, rb-head, rbcmp.txt).
- Repeat check, `rootof` control, the s7 runs and the order replays: orion ~/sa-rust-ids-work/sa-port-335/ (runs/,
  rd/, s7/, order/); the bar comparison and wall times as read: bar/barcmp.txt, bar/wall.txt there.
- Tools: results/tools334 (334's), results/tools335 (this reading), results/tools318 (barcmp318.py, wall318.py).
