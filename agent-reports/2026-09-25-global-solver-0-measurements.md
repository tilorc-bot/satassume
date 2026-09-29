# Agent report: persistent solver, stage 0, measurements

- **Date:** 2026-09-25
- **Status:** measured, no engine code. **The stage 0 stop condition is not
  met**: the active-clause ratio at the median search is 0.004, far below
  the 0.5 line, although growth passes its line (about 84 sessions' worth
  by mid-pass). **Recommendation: fund stage 1 only, as a bounded solver
  experiment, and start it after fact-lattice stage 1 has landed**, because
  both edit `solver.py` and the Pi session owns that file now. The case
  rests on one unmeasured mechanism (scoped termination), and section 5
  says what would make it fail.
- **Scope:** measurement only, on `main` at `6b935d7` (the code of
  `2069884`), locally, SymPy `ddbb536`, quiet machine. Scripts (new):
  `agent-reports/scripts/gs0_measure.py` (assumption sets, growth,
  active-clause ratio), `gs0_pollution.py` (per-query log with the cone
  path off), `gs0_search_cost.py`, `gs0_session_split.py`. Stream
  `~/.cache/satassume/stream.pkl` (13,877 queries); per-query log
  regenerated with `tools/refine_replay.py --log` on `6b935d7` (logged pass
  3.39 s, answers match).
- **Read this if:** you decide whether stage 1 of
  `2026-09-25-global-solver-evaluation-plan.md` is built

## 1. Assumption sets of consecutive queries (`gs0_measure.py`, part A)

A set is the conjuncts of the query's assumptions (`And` arguments).

| | |
|---|---:|
| queries with assumptions | 12,917 of 13,877 |
| distinct assumption sets | 540 |
| distinct conjuncts across all sets | **313** |
| conjuncts per set | median 2, max 5 |

| next query's set against the previous one | queries |
|---|---:|
| identical | 12,268 (88.4%) |
| superset | 298 |
| subset | 264 |
| overlapping | 266 |
| disjoint | 780 |

Runs of consecutive queries that share a non-empty common base: 942 runs,
median length 6, mean 14.7, max 335; 258 distinct bases. The delta beyond
the run's base is 0 conjuncts for 9,010 queries, 1 for 3,033, 2 for 537, 3
for 1,249 and 4 for 48.

What this says: one selector per distinct conjunct means 313 selectors for
the whole pass. A context API would reuse a base for about 15 queries on
average, and the extra per query is at most 4 conjuncts. Most of the reuse
is already there today: 88% of queries repeat the previous set, which the
session LRU and held levels serve.

## 2. Growth of one solver holding everything (`gs0_measure.py`, part B)

The persistent solver is modelled as the union over all sessions of their
clauses in canonical form: node literals as (node, predicate), relation
atoms as atoms, auxiliary variables named by the formula that allocated
them. So a formula or node grounded in many sessions counts once. The
replay's answers match the recording (0 differences).

| after query | sessions built so far | clauses (union) | nodes | relation atoms | variables |
|---:|---:|---:|---:|---:|---:|
| 1,388 (10%) | 45 | 1,246 | 44 | 0 | 1,468 |
| 3,470 (25%) | 208 | 3,604 | 117 | 37 | 4,060 |
| 6,939 (50%) | 640 | 9,033 | 264 | 161 | 9,650 |
| 10,408 (75%) | 1,254 | 17,268 | 534 | 161 | 18,646 |
| 13,877 (end) | 1,597 | 24,034 | 632 | 393 | 23,629 |

Plus 1,506 distinct cached unit facts (root facts in the persistent
design) and 612 rule blocks, one per distinct node.

A session holds a median of 107 clauses (mean 115). The sessions of one
pass hold 184,360 clauses in total, so the union is **7.7 times smaller
than what the sessions build**. Measured in sessions' worth, the union is
84 sessions at mid-pass and 225 at the end. In absolute terms it is small:
24,000 clauses and 24,000 variables are no memory concern. Variables are
counted as 33 per node, as today's blocks allocate them. The growth does
not level off by the end of the pass: nodes keep arriving at about the
same rate.

## 3. Active clauses per search (`gs0_measure.py`, part C)

For each of the 3,192 searches (`Solver.entails` calls), *active* is the
answering session's clause count: exact for the 1,442 searches in cone
sessions, and an upper bound, by at most three extra nodes, for the
others. *All* is the union at that moment.

| | |
|---|---:|
| active clauses per search | median 50, 90th percentile 160, max 326 |
| union at the median search | 14,988 |
| **active / all, median search** | **0.0037** |
| active / all, 90th percentile | 0.023 |
| active / all, median search in the second half of the pass | 0.0032 |

(The maximum ratio, 1.0, is the first queries of the pass.)

Rule blocks are left out on both sides of the ratio. Counting them would
add about 79 clauses per node to both.

## 4. What pollution costs today (`gs0_pollution.py`, `gs0_search_cost.py`, `gs0_session_split.py`)

Logged passes on this machine. Logged times are instrumented and slower
than the benchmark, but comparable with each other.

| engine | logged pass | answers changed |
|---|---:|---:|
| `main` (cone search on, 16 sessions kept) | 3.13 s (sum of per-query ms) | |
| cone search off | 3.55 s | 0 |
| cone search off, no eviction, no session size limit | 5.03 s | 0 |

Search cost against the searching session's variable count, top-level
searching queries, the most polluted configuration:

| variables | queries | median ms | median decisions | decisions per variable |
|---|---:|---:|---:|---:|
| 0 to 100 | 732 | 0.22 | 10 | 0.16 |
| 100 to 200 | 718 | 0.43 | 16 | 0.13 |
| 200 to 400 | 517 | 0.97 | 35 | 0.12 |
| 400 to 800 | 589 | 1.12 | 54 | 0.10 |
| 800 to 1,600 | 367 | 1.59 | 111 | 0.09 |
| 1,600 to 3,200 | 218 | 2.85 | 195 | 0.09 |
| over 3,200 | 48 | 6.20 | 330 | 0.10 |

Least squares over those queries: about 1.8 ms per thousand variables
(0.37 ms plus 1.83 µs per variable). Decisions grow linearly with the
session, about one per ten variables: CDCL decides until every variable
is assigned.

Where the logged time of `main` goes, by why the answering session
exists:

| session | queries | share of logged time |
|---|---:|---:|
| reused, nothing built | 5,036 | 52.9% |
| cone rebuild | 757 | 30.3% |
| first time these assumptions | 507 | 10.3% |
| context-free (`is_`, fresh by design) | 190 | 3.5% |
| rebuilt after eviction | 143 | 1.6% |
| answered without a session (memos) | 7,244 | 1.4% |
| **every query that built a session** | 1,597 | **45.7%** |

The 45.7% is the ceiling for what a persistent solver removes. It
includes each such query's own propagation and search, which remain, so
the removable part is smaller. The plan puts it at 23% certain and 37%
conditional, from the B5 profile; nothing here contradicts that.

## 5. Stop condition and recommendation

The plan's stage 0 stops if "the active-clause ratio at the median search
is above about 0.5 *and* the growth makes the persistent solver larger than
about 50 sessions' worth by mid-pass". Growth passes its line: 84
sessions' worth. The ratio does not: it is 0.004. **The condition is not
met.**

What the numbers say about the design:

- **Without scoped termination the design fails outright.** At the
  mid-pass size (9,650 variables) the measured slope gives about 18 ms
  per search. At the end of the pass (23,600 variables) it gives about
  43 ms. Today a search takes 0.6 ms. Over 3,192 searches that is one to
  two minutes per pass, against 3 s today.
- **With scoped termination the prize is real.** A search would need to
  satisfy a median of 50 clauses, fewer than today's median session of
  107. The work that goes is about 45% of the logged pass at most, and
  every assumption conjunct would be grounded once under one of 313
  selectors.
- **Scoped termination is untested in CPython.** Round 3's propagator
  delivered half its estimate because a Python hook replaces per-literal
  work rather than removing it. Scoped termination has the same risk. Two
  costs grow with the whole solver, not the active part: watch lists over
  inactive clauses satisfied by false selectors, and a branching heap over
  every variable. Stage 1's own stop condition tests exactly this: the
  mechanism must be free when unused, and the search must not cost more
  than 10% over today.
- **Theories would be attached for most of the pass.** The union gains
  its first relation atoms between queries 1,388 and 3,470, and holds
  them from then on. The fact-lattice stage 0
  measured that attaching any theory costs +14% of the pass today, mostly
  because held assumption levels are kept only without theories. A
  persistent solver needs the "inactive theory atoms" part of stage 1 plus
  that policy change. Otherwise the tax lands on every query, where today
  it lands only on sessions with relations.
- **Most reuse is already captured.** 88% of queries repeat the previous
  assumption set, and 53% of the logged time is in reused sessions, which
  a persistent solver does not make cheaper.

**Recommendation.** Fund stage 1 as specified, including its stop
conditions, as a solver-only experiment of two to three days. The
engine-level stages 2 and 3 are funded only if stage 1 shows scoped search
at or under today's cost on the unchanged workload, *and* on one synthetic
check first: a solver loaded with the whole pass's union (24,000 clauses,
about 313 selectors) must answer a sample of the stream's searches at a
cost that tracks the active clauses, not the union. Start after
fact-lattice stage 1 lands on `main`, since both change `solver.py`, and
the held-levels-with-theories question is shared: fact-lattice stage 1
has to answer it first.

## 6. Recipe

```bash
cd <checkout of main>          # here: a worktree of 6b935d7
S=/home/tilo/sympy; P=/home/tilo/satassume/agent-reports/scripts; L=/tmp/claude-1000/gs0
PY=/home/tilo/satassume/.venv/bin/python
PYTHONHASHSEED=0 PYTHONPATH=.:tools:$S $PY tools/refine_replay.py ~/.cache/satassume/stream.pkl --log $L/log-6b935d7.jsonl
PYTHONHASHSEED=0 PYTHONPATH=.:$S $PY $P/gs0_measure.py ~/.cache/satassume/stream.pkl $L/measure.json      # about 5 s
PYTHONHASHSEED=0 PYTHONPATH=.:tools:$S $PY $P/gs0_pollution.py ~/.cache/satassume/stream.pkl $L/log-nocone.jsonl
PYTHONHASHSEED=0 PYTHONPATH=.:tools:$S $PY $P/gs0_pollution.py ~/.cache/satassume/stream.pkl $L/log-nocone-keepall.jsonl keep_sessions=10**6 session_limit=10**9
python3 $P/gs0_search_cost.py $L/log-6b935d7.jsonl $L/log-nocone.jsonl $L/log-nocone-keepall.jsonl
python3 $P/gs0_session_split.py $L/log-6b935d7.jsonl
```

## 7. Limits of these measurements

- The union counts clauses, not solver work. A persistent solver's
  watch lists, heap and theory state are what cost time, and stage 1
  measures them.
- Guarded twin variables of relations are named per session, so the union
  overcounts them slightly. The cone flag of a few searches in nested
  queries may be misattributed. Neither changes the ratio's order of
  magnitude.
- Active clauses exclude the implicit rule-block clauses. With them,
  active and all both grow by about 79 per node, and the ratio stays
  under 0.01.
- One stream, the refine battery's. The sympy test-suite distribution
  (`tools/gate2.py`) was not measured.
