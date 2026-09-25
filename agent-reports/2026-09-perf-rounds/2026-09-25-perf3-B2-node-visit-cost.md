# Agent report: perf round 3, item B2, the cost of a node visit

- **Date:** 2026-09-25
- **Status:** measured, implementation after A2 (A2 removes the rule-block
  part measured here; the rest is what B2 would work on).
- **Scope:** measurement only; `Session.node`, `_compile_patterns`,
  `_emit_pattern`, `VarTable.node_base`. Script
  `agent-reports/2026-09-perf-rounds/scripts/cone_node_split.py`, modes `b2` and `b2x`. Pi,
  `main` at `9e8c3eb` (satassume code of `895a6c2`), unwrapped cold pass
  3.63 s (the share denominator); two runs each, both given where they
  differ.
- **Read this if:** you implement B2, or want to know what a node visit
  costs besides the rule block

## Measurement

`b2` replaces `Session.node` with a copy of itself with a timer per step
(answers checked; instrumented pass 3.75 to 3.83 s). 8,895 new nodes are
visited on the stream (8,260 with a rule block, 635 complete constants
without; 8,237 have cached facts to assert; none has formula templates;
template memo 8,293 hits, 602 misses), and 11,375 revisits.

| step of a new node visit | all sessions | share | per node | cone sessions only | share |
|---|---:|---:|---:|---:|---:|
| **whole visit** | 1,231 to 1,268 ms | **33.9 to 34.9%** | 140 us | 558 to 574 ms | 15.4 to 15.8% |
| rule block (`add_pattern`), gone with A2 | 450 to 467 ms | 12.4 to 12.9% | 51 us | 250 to 258 ms | 6.9 to 7.1% |
| template clauses (`_compile_patterns`) | 454 to 467 ms | 12.5 to 12.9% | 51 us | 229 to 235 ms | 6.3 to 6.5% |
| own variable block (`VarTable.node_base`) | 163 to 166 ms | 4.5 to 4.6% | 18 us | 38 ms | 1.1% |
| cached facts (unit clauses) | 66 to 68 ms | 1.8 to 1.9% | 7.5 us | 19 to 20 ms | 0.5% |
| SymPy: template lookup, memo miss (602) | 45 to 46 ms | 1.2 to 1.3% | 75 us | 0 | 0 |
| SymPy: template lookup, memo hit | 11 ms | 0.3% | 1.3 us | 4.5 ms | 0.1% |
| SymPy: `base.get(node)` | 3 ms | 0.1% | 0.3 us | 1 ms | 0.0% |
| extension node facts, formula templates | 2.5 ms | 0.1% | | 1 ms | 0.0% |
| revisits (parked clauses of a demanded node) | 43 to 44 ms | 1.2% | 3.8 us | 7.5 ms | 0.2% |
| `escalate` (overlaps the rows above: it visits nodes) | 167 to 172 ms | 4.6 to 4.7% | | 61 to 63 ms | 1.7% |

"Cone sessions" are the sessions a cone query builds after its first
attempt (the census's 12.2% "visiting the proposition's cone" plus the
assumptions' own nodes in those sessions).

`b2x` splits template clause emission and block allocation further, over
every caller (`_emit_pattern` is also called by `escalate` and
`_compile_pending`: 14,352 calls, 171,376 clauses):

| part | ms | share |
|---|---:|---:|
| shifting pattern clauses to the session's variables (the list comprehension in `_emit_pattern`) | 279 to 288 | 7.7 to 7.9% |
| `Solver.add_internal` of the shifted clauses | 191 to 194 | 5.3% |
| slot bases and child block allocation in `_compile_patterns` | 86 | 2.4% |
| the demand filter (`c[1] & want`, parking the rest) | 73 to 77 | 2.0 to 2.1% |
| demand / frontier bookkeeping | 15 | 0.4% |
| every new variable block, any caller (8,900 blocks) | 169 to 172 | 4.6 to 4.7% |

A variable block costs 19 us because `VarTable.node_base` creates 33 `P`
atoms per node (`atom_of.extend(P(p, node) for p in PREDICATES)`), and
`P` is a frozen dataclass (each `__init__` goes through
`object.__setattr__` twice). The atoms are read only by `Session.writeback` (root literals) and
`VarTable.lit_name`; `len(atom_of)` is the variable counter, so a lazy form
must keep the length.

## Reading: what is left for B2 after A2

After A2 a node visit loses its rule block (12.4 to 12.9%). What remains,
as shares of today's pass:

- **Template clause emission, about 13 to 15% over all callers**: the
  shift (7.7%) and `add_internal` (5.3%). Candidates: pre-shifted clause
  lists memoized per (pattern, slot bases) across sessions (hits only
  where two sessions number a node the same way, e.g. repeated cone
  rebuilds under the same assumptions; hit rate unmeasured), or a cheaper
  shift (patterns stored as flat lists of (slot, offset) pairs per clause
  are already that; a per-pattern precompiled lambda or bulk add of the
  unshifted pattern with a per-slot base table in the solver would remove
  the per-literal Python arithmetic).
- **Variable blocks, 4.7%**: create the 33 `P` atoms lazily (store the node
  per block and build `P(PREDICATES[i], node)` on read in `writeback` /
  `lit_name`), or make `P` a plain class with `__slots__`. Either is about
  ten lines in `compile.py` / `formula.py`; the saving is most of the 4.7%.
- **Demand filter, 2%**: precompute per pattern the partition of its
  clauses by the predicate-index mask, keyed by `want` (a frozenset from a
  small memo), instead of two list comprehensions per pattern per visit.
- **SymPy work is small**: template memo misses 1.2%, hits and node
  lookups 0.4%. Cached facts 1.8%.

## Decision

Measured; no implementation (after A2, per the plan). Bound for B2 after
A2, from today's numbers: about 13 to 15% emission plus 4.7% allocation
plus 2% filtering, about 20% of the pass is in the parts B2 could touch;
realistic savings depend on the form (the lazy atoms are the cheapest
candidate, 4.7% bound, ten lines). Re-run `b2`/`b2x` on top of A2 first:
propagation of template clauses and `add_internal` may shift once the rule
clauses are out of the watch lists.

## Risks for review

None (no code). `b2`/`b2x` copy `Session.node` and `_compile_patterns` of
`9e8c3eb`; re-copy them if those change before a re-run.
