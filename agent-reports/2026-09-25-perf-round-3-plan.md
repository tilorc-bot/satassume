# Agent report: plan for performance round 3 (the propagator, then the profile after it)

- **Date:** 2026-09-25
- **Status:** plan; execution starts the same day. Baseline is `main` at
  `895a6c2` (end of round 2, report `2026-09-25-perf-round-2-report.md`).
  Replay of the refine stream: 3.50 s cold locally, 3.62 s on the Pi.
- **Scope:** `satassume/solver.py`, `engine.py`, `sympy_api.py`,
  `compile.py`, `rules.py`; `tests/test_solver_incremental.py`
- **Read this if:** you run or review round 3, or want to know why these
  items and not others

## 1. Where the time is after round 2

From the round 2 measurements on this `main` (all shares of the cold pass):

- **Rule block:** 79 unary-rule clauses per node, 83% of inserted
  clauses; 10.0% to insert, 18.9% to propagate over. The largest cost.
- **Cone queries (757):** 37.4% together: visiting the proposition's own
  nodes 12.2%, the first attempt on the polluted session plus setup 9.4%,
  search 9.0%, re-grounding the assumptions 5.4%, escalation 1.4%.
- **Sessions:** 1,597 built (444 first sight at 8.2%, 143 LRU rebuilds at
  3.5%, 190 context-free at 3.4%).
- **Search:** 22% of the pass in `_propagate`, decisions median 11 and
  conflicts 0 per solve; nothing left there for search heuristics
  (round 2 dropped 1.1, 1.2, 1.3 by measurement).
- **Memo hits:** 5,971 queries answered from the answer memo; their per-hit
  cost (SymPy hashing, `_registry_state`) has not been measured.

## 2. Ground rules (unchanged from round 2)

Measure the bound before writing code; drop under 5% (3% for ten-line
items). Keep only at the same threshold in `tools/ab.py --rounds 2`
against an untouched `895a6c2`, every answer identical on both gates
(`ab.py`, `tools/gate2.py`), suite unchanged (1668 passed, the 2 known
`test_shared_facts` failures, 1 skipped, 4 xfailed, 1 xpassed, plus new
tests). One commit per kept item with the A/B numbers; a reviewer re-runs
the gates before it lands on `main`; risks go in the round's issue.

## 3. Items

### A. The rule block as a propagator (the round's main item)

Design: `2026-09-25-perf2-2.3-propagator-design.md`. Bound 28.9%,
realistic 18 to 21%. Two commits:

- **A1, solver side** (`solver.py`, tests): `set_rule_block`,
  `register_block`, the hook in `_propagate`, int-encoded reasons
  materialized in `_analyze`/`_analyze_final`; a fuzz mode comparing
  rules-as-clauses against rules-as-propagator (plain and with a theory
  attached), 4,000 seeds; direct tests with conflicts. Landable alone:
  with no `set_rule_block` call the solver behaves as today, and the
  no-block path of `_propagate` must stay within noise.
- **A2, engine side** (`engine.py`, `compile.py`): `Session.__init__`
  installs the block, `Session.node()` registers instead of
  `add_pattern(RULE_INTERNAL, ...)`. The A/B is measured here.
  `Solver.stats()["clauses"]` changes meaning; note it.

Decision: keep at 5% or more (expected far above). If A1 lands but A2
shows under 5%, revert A1 too; the hook is not free.

### B. The cone path (engine side; measure first, after A2)

- **B1, the first attempt on the polluted session (9.4%).** A cone query
  first propagates and escalates in the polluted session, then rebuilds.
  Measure: of those 9.4 points, how much is the attempt that answered
  nothing versus setup the rebuild needs anyway; and how many polluted
  sessions answer by propagation without a rebuild (those must keep the
  attempt). Sketch: when the session is polluted beyond the threshold,
  skip escalation there and go to the cone after propagation alone; or
  decide the cone before touching the polluted session when the query's
  atom is not already a variable of it. Correctness: the cone session is
  a sound session over the same clauses; answers by propagation in the
  polluted session are also derivable in the cone (same facts, fewer
  nodes) only if the cone contains every node the propagation used, so
  check answers on both gates. Keep at 5%.
- **B2, visiting the proposition's nodes (12.2%).** After A2 the rule
  block is out of node creation; what remains is template clause
  emission, node facts and SymPy work. Measure the split per node with
  the log and a profile. Sketch, depending on the split: pre-shifted
  template clause lists per (template, base) memoized across sessions;
  `add_pattern` in bulk (one `extend` per watch list); node facts read
  once. Keep at 5%.
- **B3, memo-hit and API overhead.** Cost per answer-memo hit and per
  query of `out_of_scope`/`_categories`/`to_formula` key building, as a
  share of the pass. Sketch: hoist `_registry_state` to a version check
  (3.2 did half), cheaper scope check on memo hits. Ten-line item: keep
  at 3%.

### C. The solver's hot loops after A (solver side, measure first)

After A2, profile `_propagate` and `_search` on the replay: share of the
pass, and the split between the propagator hook, template clauses, learnt
clauses and trail/heap maintenance. Sketch: the standard pure-Python
tightening (locals bound once per call, watch lists as flat lists of
(clause, other-literal) pairs so the common case skips the clause, fewer
attribute lookups in the inner loop). Keep at 5%. This is the last item
before a compiled core would be the only lever, so the report says what a
compiled core would buy on the measured profile.

## 4. Order, staffing, machines

```
A1 (solver agent, local) --> review --> A2 (engine agent, Pi) --> review
                                              |--> B1, B2, B3 (engine agent, Pi)
                                              \--> C (solver agent, local)
```

Two Opus 5.5 agents on disjoint files, one machine each, an Opus reviewer
agent per item (the user's rule for this round: all subagents are Opus),
straight to `main` after review, risks in the round's issue. The engine
agent measures B3 (independent of A) while A1 is being written, and
prepares A2's two call sites so it lands the day A1 does. Stop condition:
all items through their decision rule, then the summary report.
