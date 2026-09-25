# Agent report: perf round 3, item B1, the first attempt on the polluted session

- **Date:** 2026-09-25
- **Status:** measured, implementation after A2 (A2 makes node creation
  cheaper, and the attempt is mostly node visits, so every number here
  shrinks and must be re-measured on top of A2 before any code).
- **Scope:** measurement only; `Engine.ask` (the cone block). Script
  `agent-reports/scripts/cone_node_split.py`, modes `b1`, `b1oracle`,
  `p0`/`p1`/`p2`. Pi, `main` at `9e8c3eb` (satassume code of `895a6c2`),
  unwrapped cold pass 3.63 to 3.64 s (the share denominator).
- **Read this if:** you implement B1, or change when `Engine.ask` goes to
  the cone

## Measurement

`b1` replaces `Engine.ask` by a copy of itself with timers (logic
unchanged, answers checked, instrumented pass 3.64 to 3.70 s). Every
contextual query that meets a polluted reused session (more than
`cone_threshold` nodes beyond the assumptions') first runs in that
session: `_literal`, propagation, maybe escalation and a second
propagation. Those queries, by outcome of that first attempt and by
whether all the proposition's nodes were already visited in the polluted
session ("seen") or not ("new"):

| first attempt | queries | attempt time | share of pass |
|---|---:|---:|---:|
| answered, new nodes, by propagation | 260 | 79.8 ms | 2.20% |
| answered, new nodes, after escalation | 45 | 27.4 ms | 0.75% |
| answered, seen, by propagation | 437 | 31.7 ms | 0.87% |
| answered, seen, after escalation | 1 | 0.1 ms | 0.00% |
| **answered: must keep the attempt** | **743** | **139 ms** | **3.8%** |
| nothing, new nodes, escalated, then cone | 264 | 196.6 ms | 5.42% |
| nothing, seen, escalated, then cone | 113 | 20.9 ms | 0.58% |
| nothing, seen, propagation only, then cone | 380 | 19.1 ms | 0.53% |
| **nothing: attempt wasted** | **757** | **237 ms** | **6.5%** |

(1,500 polluted queries, 5.5 extra nodes on average. No query with new
nodes goes to the cone without escalating.) Of the 376 ms of attempts,
188 ms is `_literal` (visiting the proposition's nodes in the polluted
session) and 37 ms escalation.

The cone itself, for the 757 cone queries: re-grounding the assumptions
152 ms (4.2%), `_literal` 508 ms (14.0%), escalation 59 ms (1.6%), search
329 ms (9.1%), swap 3 ms; 1,051 ms together (29.0%). Answers: None 747,
False 9, True 1.

**Is any of the wasted attempt setup the rebuild needs?** No. `b1oracle`
reads the 757 indices from a `b1` run and lets exactly those queries skip
the first attempt and build the cone at once. Interleaved against `b1`
(same instrumentation):

| run | `b1` | `b1oracle` |
|---|---:|---:|
| 1 | 3.676 s | 3.378 s |
| 2 | 3.704 s | 3.395 s |

**-8.2%, answers identical.** The cone did not need anything the attempt
wrote back: the cone's `_literal` got *faster* without the attempt
(508 → 404 ms), its assumptions re-grounding 6 ms slower. So the oracle
bound for B1 is about 8%: the 6.5% wasted attempt plus about 2% that is
not in the timed sections (allocation and GC churn of the nodes the
attempt creates in a session that is then thrown away, by elimination).

**The two sketches of the plan**, as policies in a copy of `Engine.ask`
(`p0` the copy unchanged; interleaved runs, pass time):

| policy | run 1 | run 2 | change | answers |
|---|---:|---:|---:|---|
| `p0` control | 3.644 s | 3.682 s | | identical |
| `p1`: polluted session, propagation failed → cone at once, no escalation there | 3.577 s | 3.622 s | -1.7% | identical (762 cones instead of 757) |
| `p2`: polluted session and a new node in the proposition → cone before touching the polluted session | 3.508 s | 3.519 s | -4.1% | **2 changed** |

`p2` changes two answers to None (stream 12,144 `ask(Q.zero(k - n + 1),
...)` recorded False, 12,149 `ask(Q.negative(-k + n), ...)` recorded
True, both under `Q.integer(k) & Q.integer(n) & Q.nonnegative(n) &
Q.positive(k - n)`): the polluted session held nodes of earlier queries
(`k - n`) whose clauses the proof needs and the cone of the new query does
not reach. This is the plan's warning ("only if the cone contains every
node the propagation used") happening on the stream. `p2` sends 435
queries to an early cone, 209 of which then search.

## Reading

- The waste is concentrated: 264 "new nodes, escalated, nothing" queries
  are 5.4% of the 6.5%. What distinguishes them from the 305 "new nodes"
  queries that the polluted session answers is not visible before the
  attempt (`p2` shows the naive predictor both mispredicts 305 queries into
  a more expensive path and loses answers).
- `p1` keeps every answer but is only 1.7%: escalation in the polluted
  session is cheap (37 ms); the cost is the node visits of `_literal`.
- A policy reaching the oracle's 8% needs to know, before visiting the
  proposition's nodes in the polluted session, that propagation there will
  fail. Candidates for after A2: the answer being None in a previous cone of
  the same proposition shape; or `p2` with the polluted session's
  propagation as a fallback only when the early cone says None *and* the
  polluted session holds nodes the cone does not (the two changed answers),
  which costs the attempt back for most of the 435.

## Decision

Measured; no implementation (after A2, per the plan). Current bounds:
oracle 8.2%, `p1` 1.7% (under 5%), `p2` 4.1% with two changed answers (not
keepable). After A2 the attempt's node visits lose their rule-block
insertion (about 45% of a node visit, see the B2 report), so re-measure
`b1`/`b1oracle`/`p1` on top of A2 before deciding; `p1` is likely to fall
further under 5%.

## Risks for review

None (no code). The `b1` and policy modes copy `Engine.ask` of `9e8c3eb`;
re-copy it if `Engine.ask` changes before they are re-run.
