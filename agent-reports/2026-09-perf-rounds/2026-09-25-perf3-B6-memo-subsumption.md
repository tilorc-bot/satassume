# Agent report: perf round 3, item B6, monotone answer-memo subsumption

- **Date:** 2026-09-25
- **Status:** measured offline; no implementation (as asked). Bound
  **7.2% of the logged pass without the consistency check** (a semantic
  change), **about 3% with it** (proxy estimate). Script
  `agent-reports/2026-09-perf-rounds/scripts/memo_subsumption.py`, run on the Pi over the
  stream and `log-747fb0e.jsonl` (logged pass 3,310 ms; shares below are
  of that sum, which includes the log's overhead of about 6%).
- **Scope:** measurement only (`sympy_api.ask`'s answer memo)
- **Read this if:** you consider answering `ask(P, A')` from an earlier
  definite answer to `ask(P, A)` with `A ⊆ A'`

## Measurement

Assumptions as sets of conjuncts (`True` = empty set, an `And` its
arguments, anything else a singleton; SymPy's `And` is flattened and
sorted, so this is the memo key's equality lifted to sets). Over the
7,906 queries that miss the memo, in stream order:

| class | queries | ms logged | share |
|---|---:|---:|---:|
| **earlier definite answer for the same proposition under a subset** | 1,900 | 243.1 | 7.34% |
| of these: the engine gives the same answer | 1,648 | 238.1 | **7.19%** |
|   by path: propagation only | 1,613 | 229.5 | 6.93% |
|   by path: propagation>escalation>propagation | 17 | 8.5 | 0.26% |
|   by path: none (trivial or out of scope) | 18 | 0.1 | 0.00% |
| of these: the engine says None (the memo would change the answer) | 251 | 4.9 | 0.15% |
|   because the assumptions hold an uninterpreted relation | 241 | 4.8 | |
|   because the query is out of scope (`via none`) | 10 | 0.1 | |
| of these: earlier answers conflict (True under one subset, False under another) | 1 | 0.0 | |
| of these: the engine gives the opposite answer | 0 | | |
| of these: the query raises ValueError (outcome "error") | 0 | | |

None of the subsumed queries searches: every one is answered by
propagation (or never reaches the engine). Sessions: 1,458 reused, 147
first sight, 25 evicted, 18 none.

**The reverse, for None (information only, not sound):** an earlier None
for the same proposition under a superset of conjuncts would have
predicted 705 queries: right for 643 (435.9 ms, 13.2%), wrong for 62 (36
were False, 26 True). A None memo by subsumption would change 62 answers.

## The caveat, measured

A subsumption hit skips everything the engine does for `A'`, including
two things that decide the answer besides monotonicity:

1. **Uninterpreted relations.** `ask` returns None when the assumptions
   hold a relation no theory interprets (by design: out of scope). 241 of
   the 1,900 candidates are such queries; the memo would answer them True
   or False. A monotone memo must first know `A'` is interpretable (the
   2.5 failure memo knows it only for sets whose session was already
   built), and out-of-scope queries (10) must stay None.
2. **Inconsistent assumptions.** No candidate is inconsistent per the log
   (0 "error" outcomes), but the one conflicting case shows the hole:
   `ask(Q.positive(x), Q.positive(x) & Q.zero(x) & Q.gt(t, -pi/2) &
   Q.lt(t, pi/2) & Q.nonzero(x*tan(t)))`. Its assumptions are
   inconsistent (`positive(x)` and `zero(x)`), earlier queries gave
   True under `{Q.positive(x)}` and False under `{Q.zero(x)}`, and the
   engine answers None here only because the relations are
   uninterpreted. A subsumption memo would return True or False where
   `sympy.ask` semantics require ValueError (or, as today, None).

**With the consistency check kept** (the only way to keep ValueError on
inconsistent `A'`), a hit still needs the contextual session and
`implied(A')`, which is most of what a propagation-only query costs. A
proxy: charging each of the 1,648 hits the median propagation-only query
of its session kind (reused 0.067 ms, first 0.27 ms, evicted 0.21 ms)
leaves **96 ms, about 2.9%**. The proxy includes visiting the
proposition's nodes in the check, which a hit would skip, so the true
figure is somewhere between 2.9% and 7.2%, nearer the lower end: the
reused-session hits (1,458) are the cheap ones.

## Decision

Measured, not implemented. The 7.2% needs a semantic change of the kind
2.4 and issue #8 describe: answering without re-checking the consistency
of the assumptions, plus a scope/interpretability check. That is the
orchestrator's decision, not a free speedup. With the check kept the
bound is about 3%, and the memo would need a per-proposition index of
conjunct sets with subset tests on every miss, which costs part of that.

## Risks for review

None (no code). The conjunct normalization is the memo key's equality on
the `And`'s arguments; a nested or reordered `And` normalizes the same way
in SymPy, but an equivalent assumption written differently (`~Q.negative`
vs `Q.nonnegative`) does not match, as with the memo itself.
