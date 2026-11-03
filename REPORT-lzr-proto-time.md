# REPORT sa-lzr-3: timing the lazy-links prototype (lazy-proto 5af2f7c), as is

No code was changed. I timed and counted the prototype exactly as sa-lzr-2 left it.

## Verdict

* **dev: lazy is 2.5% faster than 9bafaa5 (pinned)**, below the 5% bar. Its None
  queries are 4.3% faster and its definite ones 0.6% slower. Answers are identical
  (1985/1985, `dev.py`).
* **fuzz 424242: lazy is 16.8% faster, but 12 answers change** (7 True→None and
  5 False→None; table below). So the prototype is **not exact**: in pure-LRA queries
  it accepts a model of the negation that the full link set rules out. The 16.8% cannot
  be claimed until this is fixed.
* `SA_LAZY=0` (the same tree with the eager path) costs +0.5 to +0.7% over 9bafaa5,
  which is the prototype's overhead.

## Pinned A/B

pareto1 under a quiet lease, `bench-container run sa-eval-bench:1` on CPU 2. Cold
process per run, PYTHONHASHSEED=0. Round 0 was a warmup and is discarded. Rounds 1 to 6
are interleaved, with the order rotating (lzr1/lzr0/base, lzr0/base/lzr1, base/lzr1/lzr0).
Values are medians of 6 runs. "Paired" is the range of the per-round ratio to base.
Runner: `tools-lzr/protime.sh` + `tools-lzr/protime.py`. Sources are `git archive` of
5af2f7c and 9bafaa5. SymPy is the harness copy (`~/dev/sa-eval/ext/sympy`, same content
as pareto1's `~/sa-lzr-bench/sympy`).

| workload | variant | runs | total s | vs base | None s | vs base | definite s | vs base | range s | paired | n None | digest |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|
| dev | 9bafaa5 | 6 | 0.577 | | 0.361 | | 0.215 | | 0.575-0.578 | | 892 | 31cd0945c07f02a6 |
| dev | SA_LAZY=0 | 6 | 0.580 | +0.7% | 0.364 | +0.7% | 0.216 | +0.6% | 0.579-0.582 | 1.001-1.010 | 892 | 31cd0945c07f02a6 |
| dev | **SA_LAZY=1** | 6 | **0.562** | **-2.5%** | 0.346 | -4.3% | 0.216 | +0.6% | 0.561-0.598 | 0.970-1.036 | 892 | 31cd0945c07f02a6 |
| fuzz 424242 | 9bafaa5 | 6 | 8.065 | | 6.733 | | 1.329 | | 8.034-8.139 | | 2387 | 173502b6ef285ad6 |
| fuzz 424242 | SA_LAZY=0 | 6 | 8.106 | +0.5% | 6.770 | +0.5% | 1.333 | +0.3% | 8.060-8.127 | 0.990-1.011 | 2387 | 173502b6ef285ad6 |
| fuzz 424242 | SA_LAZY=1 | 6 | 6.713 | -16.8%\* | 5.599 | -16.8% | 1.112 | -16.3% | 6.677-6.778 | 0.820-0.844 | **2399** | **31104c5fe1549d16** |

\* Not a valid speedup: 12 answers differ.

For comparison, the no-links ceiling (REPORT-lzr.md) was -27.5% on dev and -48.7% on
fuzz. The prototype gets about a tenth of the dev ceiling and about a third of the fuzz
ceiling.

## Answers vs 9bafaa5

* dev: `dev.py ~/dev/sa-lzr --base ~/dev/sa-eval/cands/base-9bafaa5` gives
  "1985/1985 identical". The digest is 31cd0945c07f02a6 for all three variants, both
  pinned and on orion.
* fuzz 424242, all 3000 answers compared (orion and pinned agree): SA_LAZY=0 equals
  9bafaa5 exactly. SA_LAZY=1 differs on 12 queries, and in each one a definite answer
  becomes None:

| # | query | assumptions | 9bafaa5 | lazy |
|---:|---|---|---|---|
| 52 | `Q.ne(3*x + 2*y, x + 2*y + 1)` | `Q.gt(y, -1) & Q.lt(x, -1) & Q.ge(1 - y, -2*x - y)` | False | None |
| 227 | `Q.ne(-y - 1, -x + y)` | `Q.finite(x) & Q.gt(y, 1) & Q.eq(-2*x - 1, x + 1)` | True | None |
| 509 | `Q.ge(x - y + 1, x + y + 1/2)` | `Q.ge(y, 1) & Q.le(x, pi/2) & Q.extended_positive(x + 2*y)` | False | None |
| 646 | `Q.le(2*x + y - 1, -x + 2*y - 1)` | `Q.ge(y, 1/2) & Q.gt(x, 2) & Q.eq(x + 1/2, 3*x + 1)` | False | None |
| 1442 | `Q.ne(-2*x, 2*x + 2*y - 3/2)` | `Q.ge(x, pi/2) & Q.gt(x + 2*y + 2, -2*x - y + 1)` | True | None |
| 1742 | `Q.finite(-x - y)` | `Q.finite(y) & Q.le(x, -1) & Q.eq(-2*x, 2*x - y - 1)` | True | None |
| 1891 | `Q.ge(2*x + 2*y + 1, x + 2*y + 1)` | `Q.gt(y, 0) & Q.lt(x, 0) & Q.eq(-x, 3*x + 2*y + 2)` | False | None |
| 2010 | `Q.eq(2*y + 1/2, 2 - x)` | `Q.lt(y, 1/2) & Q.gt(x, pi/2) & Q.eq(3*x - y, -2*x - y)` | False | None |
| 2166 | `Q.ne(-x - y + 1, 3*x + 2*y - 3/2)` | `Q.ge(y, 1) & Q.extended_positive(x - y + 1/2)` | True | None |
| 2210 | `Q.nonzero(x + 1/2)` | `Q.gt(x, 1) & Q.lt(y, 1) & Q.le(x + y - 3/2, 1/2 - y)` | True | None |
| 2403 | `Q.finite(-x + y)` | `Q.extended_real(y) & Q.ge(x, 0) & Q.ge(y, 1/2) & Q.eq(x, -x + y)` | True | None |
| 2866 | `Q.le(-3/2, 3*x + y)` | `Q.le(y, -1) & Q.gt(x, 1/2) & Q.extended_positive(x + y - 1)` | True | None |

Regenerate the answer lists with `tools-lzr/protime.py LABEL fuzz OUT.json`. All 12 are two-variable linear
(in)equalities. Since None needs both the query and its negation to be consistent, lazy
must have accepted a SAT model with no reported disagreement that the eager link clauses
make UNSAT. The exactness argument is therefore broken somewhere: in the LRA
sign/integrality check, the scratch replay, or the unimplemented interface equalities. I
did not look for the cause because this step was not to fix anything. Dev never hit
this case.

## Counts (deterministic; `tools-lzr/protprof.py`, orion)

| | dev: sessions | links | built | fuzz: sessions | links | built |
|---|---:|---:|---:|---:|---:|---:|
| None queries | 96 | 186 | 28 (15%) | 2256 | 7364 | 1113 (15%) |
| definite | 99 | 185 | 41 (22%) | 325 | 1203 | 266 (22%) |
| set checks | 164 | 227 pending | 108 (48%) | 2919 | 5192 pending | 1929 (37%) |

* fuzz in total: 9405 links deferred and 3313 built (35%). 10271 solves, of which 2210
  are re-solves. The scratch replay ran 3005 times and was feasible 1353 times (45%).
  Build reasons: lra_sign 2261, polar 384, atom 335, lra_int 294, euf 36, euf_cong 3.
  The None/definite session counts on fuzz are lazy's own (2256/325). Eager has
  2244/337 because 12 answers move.
* dev in total: 375 deferred, 178 built, 611 solves (148 re-solves), scratch 200
  (95 feasible). These match sa-lzr-2's numbers.

## Profile split (one instrumented run each, orion, unpinned; s)

Timers wrap `Relations.unbuilt_disagree` (which includes the scratch replay),
`Relations._lra_scratch`, `Relations.build` (`_link` + `process`), `Relations._link`,
`Relations.process` (all calls, including those from `build`) and `Session._lazy`.

| | fuzz lazy | fuzz eager (SA_LAZY=0) | dev lazy | dev eager |
|---|---:|---:|---:|---:|
| wall (ask_all) | 11.06 | 12.52 | 0.783 | 0.840 |
| `unbuilt_disagree`, all | **1.615** (14.6%) | | **0.076** (9.7%) | |
| of which scratch LRA replay | **0.667** (6.0%) | | **0.039** (5.0%) | |
| of which the cheap check | 0.948 | | 0.037 | |
| `build` (lazy builds) | 1.152 | | 0.053 | |
| `_link`, all | 0.337 | 1.303 | 0.017 | 0.044 |
| `Relations.process`, all | 2.931 | 5.732 | 0.102 | 0.223 |
| `Session._lazy`, all | 5.44 | | 0.223 | |
| solves etc. inside `_lazy` (rest) | ~2.67 | | ~0.094 | |

(Calls: fuzz unbuilt_disagree 8347, scratch 3005, build 2210; dev 479 / 200 / 148.)

How to read this: lazy cuts `_link` + `process` from 7.04 to 3.27 s on fuzz (-3.8 s)
and from 0.267 to 0.119 s on dev (-0.15 s). It pays back 1.6 s (fuzz) and 0.08 s (dev)
in `unbuilt_disagree` alone, plus its re-solves. On dev, the disagreement check takes
about half of what deferring the links saves, and the scratch replay alone takes about
a quarter. This is a rough upper bound, not a measurement: if the check cost nothing,
dev would gain about another 9 to 10 points.

## Open (not done here)

1. The 12 fuzz answers lost (exactness). Any further timing of this line depends on
   fixing this first.
2. Set checks build 37 to 48% of their links (mostly lra_sign, with scratch feasible
   only 1/65 on dev). Atom is the second reason.
3. Interface equalities are not checked.
4. The test suite was not re-run (sa-lzr-2 had not run it after the scratch-LRA
   change either).
