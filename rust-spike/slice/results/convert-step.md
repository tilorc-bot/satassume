# The convert step: `_Walk`'s enc, klass, term_row, walk and enc_int in Rust (issue 323)

State at sa-port-301's handoff (12 Nov, ~10:00Z). Not landed. The Python `_Walk` is the default and the reference;
`SLICE_CONVERT=rust` turns the Rust walker on.

## Item 0 (8c72dd0, results/convert-item0.md)

Conversion is 39.4% of in-loop samples on dev and 16.3% on fuzz. Of its own samples: bytecode 25.8% / 21.6%, C straight
from convert.py 43.7% / 42.6%, SymPy/satassume Python callees 27.2% / 33.4%, Rust 3.4% / 2.5%; lazy reads 1.6% / 4.1% of
N. Expected gain: dev 11% to 19% of loop time (0.085 to 0.145 s of 0.760), fuzz 6% to 9% (0.37 to 0.60 s of 6.420).

## Items 1-5, one commit each (cut from the WIP commit d4af871; the last one's files equal d4af871's)

| item | commit | identity check (test_convert_walk.py: the item alone and the items so far, against Python's `_Walk` on 51 inputs, 0 differences) | plant, caught by that comparison |
|---|---|---|---|
| 1 enc | 682e141 | 4 passed | 670 enc-true-as-false, test_plant_is_caught[670] |
| 2 klass | 87f86ca | 6 passed | 671 klass-no-is-expr, [671] |
| 3 term_row | e204e5a | 8 passed | 672 term-row-no-number, [672] |
| 4 walk | 8363e8a | 10 passed | 673 walk-args-unreversed, [673] |
| 5 enc_int | eb10c7d | 12 passed | 674 enc-int-no-sign, [674] |

Each commit on its own, pareto1 (cut301.sh: build, test_convert_walk.py, the suite as the bar runs it, with
SLICE_CONVERT=py and =rust): all five build; the suite's failed set equals the base's (bar298's suite, 127 failed, 5991
passed) in the seven runs read (682e141, 87f86ca, e204e5a with both walkers, 8363e8a with Python's), except that
tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence (the known id()-reuse
test) passed in two of them. 8363e8a with the Rust walker and eb10c7d's two runs ended after that read: rows in pareto1
~/sp19/sa-rust-ids-work/sa-port-301/cut/rows.txt, not read yet.

Plants 670-674 used, next free 675. Counters: none used (706-719 free).

## Item 6, the differential (4784f4e; p1/convert_diff.sh; bar phase `convdiff` 9cdbb4f)

Both walkers on every input of a run, every lazy read of every term compared. Run on pareto1 on 4784f4e
(~/sp19/sa-rust-ids-work/sa-port-301/diff-4784f4e, end marker end.txt there), NOT FINISHED at the handoff: the 20th
workload (lra) was still running; the suite, the answers (livecmp) and the plant runs come after it.

Partial sum at 09:56Z, 19 workloads complete plus lra so far: **29168 inputs, 39 differences** (430936 terms; 29138
converted, 6 args-eq-not-is, 24 out-of-scope). The ten examples kept are all of one shape, in rootof:
`Q.positive(x*CRootOf(...))` under `Q.positive(x)`, differing in `read finite 2` and `counts`: the lazy read of
`finite` of the CRootOf term answers differently under the two walkers, tables, ids, objects and classes being equal.
**Control (SLICE_CONVERT_DIFF_CONTROL=1: Python's walker against Python's walker), rootof on orion, partial at 10:17Z:
14 differences in 2184 inputs, the same shape (`read finite 2`, `counts`); Rust against Python beside it: 13 in 1850.**
So these are not the Rust walker's: the second conversion to ask `finite` of a CRootOf term gets another answer than
the first, whichever walkers they are (SymPy's own state after the first evaluation; compare the known
test_lazy_reads.py stock_finite flake). The comparison has to be made independent of who asks first before its count
can be the bar's zero: see HANDOFF-sa-port-301.md. (~/sa-rust-ids-work/sa-port-301/ctl/out.txt when it ends.)
Dev alone on orion before that: 1221 inputs, 0 differences, answers MATCH under SLICE_CONVERT=py and =rust.

The bar needs 0. barq301.sh starts the bar only on `exit 0` and 60 MATCH rows, so the bar has not started.

## Item 6, continued (sa-port-302: 5c7db78 fresh-state reads, bfac1a4 the read limit)

**Gate (a), the cause, pure SymPy (finite_history_repro.py, no satassume code).** The term is the rootof workload's
`m = x*r`, `x` positive, `r = ComplexRootOf._new(reducible poly, i)`. `m.is_finite` (what `_Walk._read_finite` reads)
raises KeyError (`_reals_cache[self.poly]` in `ComplexRootOf._eval_is_real` / `_eval_is_imaginary`: `_new` keeps a poly
`rootof` would factor, which is never a key of that cache) or answers True, by the order `_ask` shuffles the
prerequisite facts into; each raise leaves facts settled in `_assumptions`, so a later ask of the same object can answer
where an earlier one raised. 40 shuffle seeds, three asks each: the first ask raised in 31, the second differed from
the first in 6, the third from the second in 7. With `rootof(...)`'s own object (`--rootof`): 0, 0, 0. So the read's
VALUE differs (a raise, which Rust refuses on, against True), not only its count or position, and it comes from
SymPy's state (the shuffle's RNG and each object's `_assumptions`), not from `_Walk`'s memo and not from the walk order.

**Gate (b).** Fresh state makes the differences vanish: rootof in a whole run, 4784 inputs, 39 differences under the
old comparison (4784f4e), 0 under the fresh-state one (5c7db78), Rust against Python. On orion, the 399
`Q.positive(x*r)` inputs each converted alone (~/sa-rust-ids-work/sa-port-302/b): 0 differences fresh-state, Python
against Python and Rust against Python; the old comparison also gave 0 there, so the 39 need the state a whole run
leaves; Python's own second ask of `finite` differed on 63 of the 399. "PROCESS.clear() plus SymPy's cache cleared"
would not be enough: the input object itself keeps its `_assumptions`, and the shuffle's RNG isn't reset by either.
Answers: the answer rows (livecmp, 60) are part of the run that was going at the handoff; not read yet.

**Gate (c), the comparison (convert_diff.py).** Tables, ids, objects and classes as before. Then each walker's lazy
reads in its own forked child of the state the two conversions left: both ask first, of the same objects in the same
state; values, counts and `raised` are all compared. `reread`: inputs where Python's second ask, in its child,
answers differently (pure-Python history dependence, listed, not a walker difference). `slow`: a read gets 30 s of its
child's CPU; both children stopping at the same read lists the input and compares the reads before it; stopping at
different reads is a difference. `reads`: the number of reads compared.

**First fresh-state run, 5c7db78, pareto1 (~/sp19/sa-rust-ids-work/sa-port-302/diff-5c7db78; stopped before its answer
rows and plants, superseded by bfac1a4): 69245 inputs (20 workloads 29361, suite 39884), 1780845 terms; workloads 0
differences (rootof 0, was 39); suite 1: `Q.lt(x, sin(exp(exp(exp(5))))) | Q.positive(x)`, both children killed at the
ten-minute cap in `complex(sin(exp(exp(exp(5)))))`, which doesn't end (the 4784f4e run sat in the same read for 90
minutes and never finished its suite). bfac1a4's read limit turns that into a `slow` row. `reread`: 84 inputs, all in
rootof, all `finite`.** The suite under that differential: 130 failed, base's 127 plus
test_lra_constants.py::test_constants_evalf_cannot_bound_rigorously_are_not_read (the input above, ten minutes in it)
and test_wide_derived.py::test_wide_derived_or_against_or_is_fast[or-nor] and [or-or] (wall-clock asserts, run while
the differential forks twice per input). The plain suite is the bar's.

**Gate (d), owed as its own spec item, not convert's:** a lazy read whose value depends on who asked first and on the
assumptions shuffle, in pure Python, on the rootof workload's `ComplexRootOf._new` inputs (84 inputs of the 20
workloads, none in the suite). Same family as the stock_finite flake (OWED [131]).

The per-commit suites' three unread rows (8363e8a rust, eb10c7d py and rust): 127 failed each, the same set as base
(10 of 10 runs read). Plants 670-674 under the new comparison: caught by test_convert_walk.py (14 passed, orion and
pareto1); under the whole-run differential on dev and fuzz: part of the bfac1a4 run.

## S1 (pareto0, one quiet lease e8402a95, 7 interleaved rounds, pinned CPU 2; ~/sa-rust-ids-work/sa-port-301/gd)

Arms: 146 (1401d1f), base 899d354, 4784f4e with SLICE_CONVERT=py (the default) and with SLICE_CONVERT=rust. 56 rows,
digest mismatches 0 (med-r1.md).

| arm | dev wall s, median (min-max) | fuzz wall s, median (min-max) | convert inclusive, samples (share of N), dev / fuzz | Python self samples in convert.py (bytecode, convert + read), dev / fuzz |
|---|---|---|---|---|
| 146 1401d1f | 0.756 (0.749-0.757) | 6.683 (6.618-6.713) | | |
| base 899d354 | 0.761 (0.759-0.763) | 6.372 (6.334-6.439) | 923 (39.7% of 2327) / 6397 (16.5% of 38791) | 259 / 1836 |
| 4784f4e, py | 0.760 (0.751-0.792) | 6.364 (6.330-6.393) | 927 (39.8% of 2329) / 6382 (16.4% of 38823) | 230 / 1838 |
| 4784f4e, rust | 0.646 (0.641-0.650) | 5.908 (5.860-5.928) | 593 (30.0% of 1978) / 4466 (12.5% of 35791) | 39 / 277 |

Rust walker against the default on the same tree: dev -0.114 s (-15.0%), fuzz -0.456 s (-7.2%). Item 0 expected dev
0.085 to 0.145 s (11% to 19%) and fuzz 0.37 to 0.60 s (6% to 9%): both inside. Against 146: dev -14.6%, fuzz -11.6%.
The default arm equals base within spread. Under the Rust walker 78.2% (dev) and 84.4% (fuzz) of convert's samples have
a sa_solver frame below the innermost convert.py frame (SymPy calls made from Rust included); lazy reads fall from
4.1% to 1.8% of N on fuzz. Split by tools300/split300.py on the lease's samples: gd/split-ARM/tab.txt.

## Not done (at sa-port-302's handoff)

The full differential on bfac1a4 was running (pareto1, ~/sp19/sa-rust-ids-work/sa-port-302/diff-bfac1a4: all/total.txt,
all/answers.txt, plants.txt, end.txt): its counts, the 60 answer rows and the five plant rows are not read. The bar
(bar302.sh on pareto0) starts by itself from barq302.sh only if that run is clean; landing and the probe follow it.
