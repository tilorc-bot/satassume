# Baseline: satassume 9bafaa5 (main), 2026-11-03

Evaluator: sa-eval-1. Harness: branch `evalbench` of tilorc-bot/satassume, directory `evalbench/`.
HOWTO-WORKERS.md covers how to measure and submit.

**Caveat for every readout:** the stream is satassume's home ground. Its corpus was recorded
from the same SymPy test runs as the stream, and the battery stream repeats 92% of the
stream's (proposition, assumptions) pairs. The held-out *sets* are new to the workers, but
the *kind* of query is not. The fuzz workload (random linear relations and sign facts over
two reals) is the only workload that isn't drawn from SymPy's tests.

## Data and environment

* Queries: `~/dev/rete-impl/data/{stream,battery-stream,corpus}.pkl`, lists of
  (proposition, assumptions, recorded answer). The recorded answers are not satassume's and
  are never used as truth. 1,066 of the stream's recorded answers differ from 9bafaa5's
  (mostly recorded None where satassume is definite). The gates compare with 9bafaa5's own
  answers, recorded by `gates.py --record` (truth standard: satassume issue 247).
* SymPy: copy of `~/maintenance/sympy-pin` at 6379c4da698236f0c72dcc37910266cf56412e2f; mpmath 1.3.0.
  Python 3.12.14 on orion (gates, counters) and 3.12.15 in the timing image.
* satsimp 95c9340 (only for the fork-per-case refine battery).
* Timing: pareto1 (i5-13600T), `bench-container` image `sa-eval-bench:1`
  (sha256:95132be54a1eedc65bb9da35fa388e586909921a74dad796eeeb542ee7214c6b; python:3.12-slim + mpmath),
  CPU 2 (P-core, max 4.8 GHz, governor powersave). Everything runs inside one quiet
  whole-machine lease (`machine run pareto1 --quiet`) and one container invocation.
  Baseline and candidate alternate inside every round, each run is a cold process,
  PYTHONHASHSEED=0, 1 warm-up round plus 5 measured rounds, medians, ratios paired by round.
  Trees are byte-compiled before syncing because the container mounts them read-only.
  The timed loop starts after imports and `gc.freeze()`; GC stays enabled.

## The split (made before any candidate existed: `evalbench/make_split.py`, `split.json`)

The unit is the assumption set. The stream has 16,232 queries, 8,393 unique pairs and
513 sets; one set has 1,313 queries.

* **dev** (for workers): 83 whole sets drawn stratified by set size (strata 1-4, 5-19,
  20-79, 80-299, 300+ queries), each set capped at its first 200 queries, replayed in
  recorded order with repeats kept. That's 1,985 queries (1,235 unique). Recorded-None share
  50.8% vs the stream's 51.9%. Under 9bafaa5: 892 None, 1,093 definite. The draw used seed 0,
  the first seed meeting the size (2,000 ± 5%) and None-share (± 1.5 points) criteria.
* **ho-stream** (held out): every stream query whose set is not a dev set. 13,626 queries,
  430 sets; 6,143 None, 7,441 definite, 42 ValueError (inconsistent sets).
* **ho-battery** (held out): battery-stream queries whose pair is not in the stream and
  whose set is not a dev set. 1,101 queries (779 unique, 155 sets); 413 None, 641 definite,
  47 ValueError. The battery-stream minus these is 92% the stream's own pairs, so it is used
  only in the gates.
* **ho-fuzz** (held out): 3,000 queries from 20 seeds × 150 of reteassume's extended-real
  fuzz generator (`evalbench/fuzz.py`). The base seed is secret: `secret/fuzz_seed.txt`,
  sha256 `fdf46191d4206563518df5fb6fca5c83625d077628036c63afbf39fd04cf8166`. 2,426 None,
  402 definite, 172 ValueError. None-heavy and search-heavy.
* **corpus**: satassume's corpus, 2,863 queries. **fork-battery**: satsimp's refine battery
  `battery_v3`, every 17th case (103 cases), each case in a child forked from a parent
  with everything imported and the templates preloaded, as the assume-eval harness runs it.
  It reports the time inside satassume's `ask` (935 asks, 414 of them None) and the whole
  `refine`.

## Time at 9bafaa5 (pareto1; A/A: the baseline against an identical copy = the noise floor)

| workload | metric | median s | A/A speedup (median of paired rounds) | A/A per-round ratio range |
|---|---|---|---|---|
| dev (1,985) | total | 0.527 | 1.001x | 0.994..1.005 |
| | None (892) | 0.312 | 1.002x | 0.995..1.004 |
| | definite (1,093) | 0.214 | 1.001x | 0.993..1.006 |
| ho-stream (13,626) | total | 2.974 | 1.000x | 0.995..1.033 |
| | None (6,143) | 1.921 | 1.001x | 0.998..1.033 |
| | definite (7,441) | 1.039 | 0.997x | 0.987..1.034 |
| ho-battery (1,101) | total | 0.627 | 1.000x | 0.949..1.002 |
| | None (413) | 0.438 | 1.000x | 0.950..1.004 |
| ho-fuzz (3,000) | total | 7.880 | 1.008x | 0.984..1.011 |
| | None (2,426) | 6.621 | 1.009x | 0.984..1.010 |
| corpus (2,863) | total | 0.532 | 0.997x | 0.938..1.010 |
| fork-battery (103 cases) | ask | 0.767 | 0.994x | 0.961..1.050 |
| | ask, None answers | 0.495 | 0.995x | 0.952..1.061 |
| | refine | 1.229 | 0.995x | 0.976..1.034 |

None answers cost more per query than definite ones: 350 vs 196 µs on dev, 313 vs 140 µs on
ho-stream, and 2.7 ms vs 2.6 ms on the fuzz. The None share of the time is 59% on dev, 65%
on ho-stream, 84% on the fuzz and 65% inside `ask` on the fork battery.

**Reading a candidate's numbers:** A/A medians land within 1% and single rounds within
about ±6%. A speedup counts as real when its median is at least 1.02x and every round's
ratio is below 1 on that workload. Smaller effects can be checked with more rounds.

## Counters at 9bafaa5 (deterministic; `evalbench/baseline-counters-9bafaa5.json`)

| counter | dev | ho-stream | ho-battery | ho-fuzz | corpus |
|---|---|---|---|---|---|
| queries (Engine.ask/is_ calls) | 883 | 4,311 | 587 | 3,035 | 1,798 |
| cache_hits (answer memo and engine caches) | 1,248 | 10,198 | 939 | 685 | 918 |
| sessions | 918 | 4,334 | 558 | 3,149 | 1,816 |
| context_builds (= set_checks) | 833 | 3,885 | 503 | 2,938 | 1,061 |
| relevant (split to the connected part) | 583 | 2,695 | 213 | 1,238 | 569 |
| consistency_checks | 64 | 150 | 43 | 324 | 78 |
| escalations | 315 | 1,786 | 214 | 2,606 | 678 |
| searches | 475 | 2,604 | 328 | 2,649 | 709 |
| solver_conflicts | 257 | 1,695 | 203 | 7,720 | 87 |
| solver_decisions | 7,738 | 43,668 | 5,327 | 106,578 | 12,906 |
| solver_propagations | 53,418 | 318,857 | 56,695 | 790,907 | 54,680 |
| solver_clauses | 51,769 | 308,011 | 51,477 | 663,082 | 59,098 |

Phase split (exclusive time, instrumented run on orion, share of the loop):

| workload | build (set session + complete check) | prepare | search | engine (rest) | escalate | front | propagate |
|---|---|---|---|---|---|---|---|
| dev | 34% | 18% | 13% | 17% | 7% | 6% | 4% |
| ho-stream | 41% | 20% | 15% | 9% | 6% | 5% | 4% |
| ho-fuzz | 32% | 29% | 22% | 9% | 3% | 3% | 2% |
| corpus | 22% | 12% | 9% | 28% | 12% | 12% | 4% |

Every contextual query rebuilds its set's session and runs the set's complete check
(issue 97 design: build, answer, discard). On ho-stream that is 3,885 builds for 430 sets.

## Gates at 9bafaa5 (`evalbench/gates.py`)

* Answers recorded on the stream, the battery, the corpus, ho-fuzz and the fork battery
  (refine output). 42 ValueErrors on the stream.
* History independence holds at 9bafaa5. The unique stream (8,393) in a fixed shuffled order
  and in a fresh process per query (forked from a parent that has only imported) gives the
  in-order answers, 0 differences each.
* Test suite: 6,083 passed, 23 skipped, 18 xfailed. Eleven tests that start a subprocess
  fail when SymPy is only on PYTHONPATH; the harness venv has SymPy on its path (a .pth file)
  to avoid that. A candidate is checked with its own suite and with 9bafaa5's suite run
  against its package.
* Sanity check (partial, 2026-11-03 08:00 UTC): a mutant that turns every 997th True answer
  into None, history-dependently (worktree `cands/mutant-test`, never pushed), changes the
  answer digests of stream, battery, corpus, stream-unique and stream-shuffled. ho-fuzz and
  fork-battery are unchanged, as expected for so sparse a mutant, and so is the fresh-process
  run. 3 of its own tests fail. The comparison step of `gates.py` (FAIL lines, per-query
  diffs) had not finished yet: see HANDOFF-sa-eval-1.md.
