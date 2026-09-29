# Agent report: performance round 2 (measurement-first), what landed and what was dropped

- **Date:** 2026-09-25
- **Status:** round complete up to the plan's stop condition. Three items
  landed (`5903431`, `41f2b80`, `63504aa`, plus tooling and reports), eight
  measured and dropped, one (2.3, the rule-block propagator) measured,
  designed and **waiting for the user's go-ahead**. Tracking issue #9.
- **Scope:** `satassume/engine.py`, `sympy_api.py`, `extensions.py`,
  `templates/registry.py`; `tools/ab.py`, `tools/gate2.py`,
  `tools/query_log.py`, `tools/refine_replay.py`;
  `tests/test_solver_incremental.py`, `tests/test_memos.py`; the per-item
  reports `2026-09-perf-rounds/2026-09-25-perf2-*.md` and scripts under `agent-reports/2026-09-perf-rounds/scripts/`
- **Read this if:** you want the state of the engine's speed after this
  round, what not to try again, or you are about to decide on 2.3

## 1. Result

Replay of the refine stream (`tools/refine_replay.py`, 13,877 `ask` calls),
cold pass, `tools/ab.py --rounds 2`, interleaved against an untouched
`b3d429b`:

| machine | reference `b3d429b` | `main` at `bae7b56` | change |
|---|---:|---:|---:|
| local (2 cores) | 4.248 s | 3.501 s | **-17.6%** |
| Pi container (at `63504aa`, reviewer's run) | 4.184 s | 3.623 s | **-13.4%** |

Every answer identical on both gates (`ab.py`: 13,877 recorded answers;
`gate2.py`: 2,863 of SymPy's own assumption-test queries, 0 changed). Test
suite: the baseline (1656 passed, the 2 known `test_shared_facts`
failures, 1 skipped, 4 xfailed, 1 xpassed) plus 12 new tests, 1668 passed.
Sessions built on the stream: 2,664 → 1,597.

## 2. What landed (one commit each, A/B numbers in the message)

| item | commit | what | A/B (Pi, reviewer) |
|---|---|---|---:|
| 2.5 (new, from the 0.3 log) | `63504aa` | remember assumption sets whose session construction raises `Uninterpreted`; 1,130 of 2,664 sessions were built only to fail on a relation no theory understands (63 distinct sets) | -13.4% vs reference, -10.2% on top of 3.3 |
| 3.3 | `41f2b80` | memoize `TemplateRegistry.clauses_for` per expression and `to_formula` per SymPy Boolean | -3.7% best-of-3 |
| 3.2 | `5903431` | `Extensions.version`; the answer memo compares an integer instead of snapshotting the handler dict | noise, cleanup |

Each was reviewed before landing by a separate reviewer that read the diff
for the case that breaks the correctness argument and re-ran both gates
and the suite. Risks, ordered, are in issue #9 (the failing-set memo shares
the answer memo's property: an adapter whose interpretation depended on
state other than the atom would leave stale entries).

## 3. What was measured and dropped

All by measurement against the plan's thresholds (5%; 3% for ten-line
items), none by argument. Each has a report and a re-runnable script.

| item | bound | why | report |
|---|---:|---|---|
| 1.1 witness reuse | 4.8% | a ring of 4 models hits 22% of solves, but those are the cheap ones (18% of solve time); Nones of a session do not share a model | `2026-09-perf-rounds/2026-09-25-perf2-1.1-witness-reuse.md` |
| 1.2 component-restricted search | <1% | the query variable's component is 0.88 of the session (0.83 in cone rebuilds): templates link every node to its subexpressions and nodes share symbols. The cone machinery stays. | `2026-09-perf-rounds/2026-09-25-perf2-1.2-component-search.md` |
| 1.3 phase heuristic | ≤4.9% ceiling, ~2.7% real | median 11 decisions and 0 conflicts per solve | `2026-09-perf-rounds/2026-09-25-perf2-1.3-phase-heuristic.md` |
| 2.2 base-session clone | 1.6% net (5.4% with a free clone) | the base session is small (~50 vars, 130 clauses); a cone query's time is visiting its own nodes (12.2%) and searching (9.0%), not re-grounding the assumptions | `2026-09-perf-rounds/2026-09-25-perf2-2.2-base-session-clone.md`, census in `2026-09-perf-rounds/2026-09-25-perf2-2.1-session-census.md` |
| 2.4 atomic fast path | 0.9% | only the literal-in-assumptions part keeps answers; the other 5% would skip the consistency check and change 399 answers | `2026-09-perf-rounds/2026-09-25-perf2-2.4-atomic-fast-path.md` |
| 3.1 `implied` misses | 2.7% + 0.6% | theory sessions could hold levels for 2.7%; the "root units" are node facts emitted at node creation, not `writeback()`, nothing to batch | `2026-09-perf-rounds/2026-09-25-perf2-3.1-implied-misses.md` |
| 2.1 `keep_sessions` retest | 0.4% (32), 0.7% (64) | after 2.5 only 143 sessions are LRU rebuilds | `2026-09-perf-rounds/2026-09-25-perf2-2.1-session-census.md` |

The plan's headline bet, that `None` is expensive because of search
(phase 1), did not survive measurement: search is 22% of the pass and its
decisions are mostly conflict-free single assignments of isolated
variables. The cost that measurement found instead was structural: doomed
session builds (landed as 2.5) and the rule block.

## 4. The one lever left: 2.3, the rule block as a propagator

`Session.node()` instantiates 79 rule clauses per node (`RULE_INTERNAL`,
the unary predicate implications). On this `main` they are 83% of inserted
clauses, **10.0% of the cold pass to insert and 18.9% to propagate over
(83% of watch-list visits): 28.9% combined**, realistic saving 18 to 21%.
Design in `2026-09-perf-rounds/2026-09-25-perf2-2.3-propagator-design.md`: one lookup per
processed literal in `_propagate` over a shared per-rule table, reasons
encoded as ints and materialized only in `_analyze`; no change to the
theory interface, held levels or the propagation cache; engine side is six
lines. Gate: a rules-as-clauses versus rules-as-propagator fuzz mode plus
both replay gates. Estimate: about 90 solver lines, 120 test lines, one
agent-day. **Not started**: the brief's default was to stop and ask before
2.3.

## 5. Tooling that stays

- `tools/ab.py`: interleaved A/B of two checkouts, same embedded loop on
  both sides, noise floor about 1%. Use it for every speed claim.
- `tools/gate2.py`: second query distribution (SymPy's assumption tests,
  recorded with `tools/record_queries.py` on the Pi), frozen answers in
  `~/.cache/satassume/gate2-frozen.jsonl`; 2 s. It also settled issue #8's
  open question: caching `None` answers changes nothing on it.
- `tools/refine_replay.py --log PATH [--log-models]` and
  `tools/query_log.py`: the per-query log every measurement above read
  off. Logs of `d166940` (= `b3d429b`) and `eae6070` (after 2.5) are in
  `~/.cache/satassume/`.
- `tests/test_solver_incremental.py`: the solver differential fuzz as a
  test, 500 seeds in CI (12 s), `SOLVER_FUZZ_SEEDS` for more; extensible
  operation mix.

## 6. How the round ran

Two agents on disjoint files and separate machines (engine agent on the
Pi, solver agent local), the orchestrator landing one item at a time
after a reviewer fork re-ran the gates; measurements in `agent-reports/`
as they happened. About five hours wall clock. What worked: the shared
A/B script and the fixed log format removed last round's confusion about
numbers; per-item reports meant nothing was lost when an agent's context
filled. What to change: reviews serialized the agents (a reviewer needs
the item's machine, so its agent idles); with a third machine the reviews
could overlap the next measurement.

Remaining levers beyond this plan, unchanged from the previous report: a
compiled core for the solver's hot loops, and asking fewer questions on
the refine side.
