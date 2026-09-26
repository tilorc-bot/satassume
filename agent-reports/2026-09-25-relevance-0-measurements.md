# Agent report: relevance (next-steps item 3), stage 0, measurements

- **Date:** 2026-09-25
- **Status:** measured, no engine code. **Estimated saving 9.5% of the
  replay time** (stream order, on the Pi, including the whole-set
  consistency check and the cost of splitting the assumptions), **9.1%**
  with a complete SAT check instead of propagation. This clears the 5% line
  to build and the 3% line to land. **Recommendation: build it** (stage 1),
  keyed as below.
- **Scope:** branch `stage0-relevance` = `stage-constants` (`997e723`: constant
  propositions answered without the assumptions) plus the script
  `agent-reports/scripts/rel0_measure.py`. Timings on the Pi 5 (exclusive
  use, `/work/.mamba/envs/sympy/bin/python`, SymPy `/work/src/sympy-pin`,
  stream `/work/src/bench/stream.pkl`, md5 `de9b34aa…`, 13,877 queries).
  Structural counts are the same locally and on the Pi.
- **Read this if:** you design or review the relevance stage 1.

## 1. Numbers

### 1.1 Headline: stream-order replay, fresh process per pass, 10 passes base / check, 5 for the rest

| mode | median s | vs base |
|---|---:|---:|
| `base`: `ask(p, a)` as on `stage-constants` | 2.606 | |
| `comp`: key memo and sessions by the query's component, no consistency check | 2.286 | **-12.3%** |
| `check`: `comp` + whole-set check (propagation), memoized per set | 2.357 | **-9.5%** |
| `fullcheck`: `comp` + whole-set check (propagation + `Solver.solve`) | 2.368 | -9.1% |
| `emptyonly`: only an *empty* component drops the assumptions (check on) | 2.586 | -0.7% (vs its own base, 2.603) |
| `nonempty`: only a *non-empty* smaller component replaces the set (check on) | 2.523 | -3.1% |

Spread per mode is 1-2% (base 2.595-2.647, check 2.345-2.374). The two
halves add up to much less than the whole: the saving comes from queries
that become *the same query* once keyed by the component. Engine counters
over one pass:

| | base | check |
|---|---:|---:|
| engine queries (answer-memo misses reaching `Engine`) | 6,311 | 4,472 (-29%) |
| searches | 3,185 | 2,166 |
| cone searches | 698 | 444 |
| escalations | 1,682 | 1,381 |
| sessions built (check: incl. 353 check sessions) | 1,594 | 1,773 |

Answers: `base` differs from the recording (made on `main`) in 443 queries,
all None -> definite (the `stage-constants` commit). `check` differs in the
same 443 plus 3 more, also None -> definite, no definite answer changed, no
error gained or lost (the stream has no inconsistent sets). The 3
(`5718, 5720, 5768`): `Q.positive(x)`, `Q.negative(x)`, `Q.zero(x)` under
`Q.positive(x) & Q.gt(t, -pi/2) & Q.lt(t, pi/2)`; today None because the
relations over `pi` are uninterpreted (item 2), with the component
`Q.positive(x)` they answer True, False, False. That changes the
`uninterpreted="none"` policy for conjuncts disconnected from the query:
owner's call (the check session raises `Uninterpreted` already, so the old
policy can be kept for free).

### 1.2 Consistency check

| | |
|---|---:|
| distinct assumption sets (queries reaching an engine session) | 539 |
| distinct sets used by a query whose component is strictly smaller (checks made) | 353 |
| check time, propagation (fresh session, `assume_formula`, `implied`) | 64 ms per pass (2.4% of base) |
| check time, + `Solver.solve` | 71 ms (2.7%) |
| whole-set session size, distinct sets | 1.9 nodes, 8.3 clauses on average |

The check is the main cost of the design (it takes 2.8 points off the
12.3%). It can likely be cheaper: with disjoint keys the whole set is
consistent iff each component and each keyless conjunct is, and component
sessions are built anyway; not measured.

### 1.3 Per-query log (`refine_replay.py --log`, logged pass 2.77 s)

| outcome | queries | ms | share |
|---|---:|---:|---:|
| None | 6,932 | 2,266 | **81.9%** |
| definite | 6,945 | 500 | 18.1% |

| component of the query | queries (non-memo / memo) | ms | share |
|---|---:|---:|---:|
| constant proposition (no assumptions used) | 1,501 / 1,030 | 32 | 1.1% |
| no assumptions | 204 / 535 | 162 | 5.9% |
| whole set | 3,504 / 3,265 | 1,770 | 64.0% |
| strictly smaller, non-empty | 2,027 / 590 | 518 | 18.7% |
| strictly smaller, empty (no conjunct touches the query) | 670 / 551 | 285 | 10.3% |

Queries with a strictly smaller component: 3,838, 29.0% of logged time
(23.5% in those ending None, 5.6% definite; 13.1% in those that built a
session).

### 1.4 Structure (`rel0_measure.py struct`)

| | |
|---|---:|
| queries | 13,877 |
| constant propositions / no assumptions / with assumptions | 2,531 / 739 / 10,607 |
| components per set, by query: 1 / 2 / 3 | 7,379 / 2,910 / 318 |
| **component strictly smaller** | **3,838 (36.2% of queries with assumptions)**, of them empty 1,221 |
| distinct session keys: whole set / component | 539 / 498 |

Sizes of a fresh session with the assumptions only (queries whose session
builds, 9,476 / 3,755):

| | all: whole | all: component | strictly smaller: whole | strictly smaller: component |
|---|---:|---:|---:|---:|
| nodes (mean / median) | 1.6 / 1 | 1.1 / 1 | 1.9 / 2 | 0.7 / 1 |
| solver variables | 54.7 / 40 | 39.3 / 34 | 63.0 / 67 | 24.0 / 34 |
| clauses | 6.0 / 2 | 5.1 / 1 | 3.4 / 2 | 1.0 / 1 |

The assumption sessions are tiny; the saving is not from smaller sessions
but from sharing answers and sessions across sets.

### 1.5 Cold per-query (`rel0_measure.py cold`)

The 2,697 distinct (p, a) pairs with a strictly smaller component, each
asked in a fresh `Engine` (median of 3): whole set 1.32 s, component
0.96 s, **-27%** per query. Applied to the 29.0% of logged time in these
queries that gives about 7.8%, consistent with the stream-order 9.5% (which
adds memo sharing and subtracts the check).

## 2. Method

- **Keys** of an expression: its free symbols plus the classes of its
  undefined function applications (`f(1)` and `f(x)` share `f`, EUF
  congruence can connect them); numbers connect nothing. Conjuncts (`And`
  arguments of the assumptions) are merged transitively when their keys
  meet (`Q.eq(x, y)`, `x < y` connect `x` and `y`). The query's component
  is the union of components whose keys meet the query's keys; conjuncts
  without keys belong to none; a query without keys has an empty component.
  Constant propositions keep the `stage-constants` path.
- **`replay` modes** model the design outside the engine: a memo on
  `(p, a)` first; on a miss, split `a` (memoized per assumption object),
  check the whole set once if the component is strictly smaller, then
  `sympy_api.ask(p, component)` (True if empty), so the engine's answer
  memo and contextual sessions are keyed by the component. All of it is
  inside the timed loop. One fresh process per pass, modes interleaved,
  10 rounds for base and check.
- **Log split**: `tools/refine_replay.py STREAM 1 --log` on the Pi, joined
  on the stream index with the `struct` rows. `refine_replay.py` exits 1
  on this branch because of the 443 expected answer changes; the log is
  written before that.
- Not done: an implementation (session and memo keyed by component inside
  `sympy_api`/`Engine`); the per-component consistency check; the second
  gate stream.

## 3. Verdict

9.5% (9.1% with a complete check) against the lines of 5% to build and 3%
to land: **build it**. Stage 1 should: key the answer memo and the
contextual session by the component (the memo sharing is most of the win);
keep the whole-set check memoized per set, and try the per-component check;
decide with the owner whether a disconnected uninterpreted conjunct keeps
answering None (3 queries on this stream); re-measure against `base` on
the Pi with `rel0_measure.py replay` and the real code.
