# Witness bounds: the engine's exits first, and a bound on the check's work (issue 323) — IN PROGRESS, NOTHING LANDED

sa-port-346, branch port/witness-bounds from bfceccc9 (the tree sa-port-345 lands). Items (1), (2) and (3) are
committed; the gate (4), S1 (5) and the bar (6) are not started. SLICE_WITNESS stays off by default and the
unchanged path is the default. No SymPy construction or evaluation at query time. No Rust change: orion .so
a956b03496066671, the same as sa-port-344's. Every number below is from orion under load: counts, work and
answer digests, no S1 time.

## (1) The engine's exits before any point, 49b1efc

`witness.witnesses` (witness.py:819) compiles the query, then asks `Engine._ends_without_session` (engine.py:1860)
before `_pools`, so before any term is evaluated: True if the set has a memoized INCONSISTENT (`_verdict`) or the
query is over the discovery budget (`_within_budget`). On True the check falls through and `Engine.ask` takes that
exit itself, as with the switch off. The P1 guard (`_patched`) moved in front of that call.

The test is asked after the compile, not before it: 6582 of the 11838 calls on the 20 workloads are refused by the
compile at about 10 us each, and would otherwise pay the budget test first.

344's (a), read again with tools346/ex346.py (which exit makes the test True, py):

| exit of `Engine.ask` | calls of the check before (344) | reach the test now | what the rest do |
|---|---|---|---|
| over budget | 7 (budget) | 7, all True | |
| no-build | 462 (fuzz 40, zero 53, lra 50, value 317, f6 2) | 50, all the set's memoized INCONSISTENT (fuzz 40, zero 5, lra 5) | 412 are refused by the compile, before any point, as before |
| non-commutative | 0 | 0 | a non-commutative symbol has no value in its pool, so it was never certified |

The set's memoized Uninterpreted (`_failed`) is not asked: no call on the workloads probed (fuzz, zero, lra, f6,
value, budget, cert, core) that has one gets past the compile, so the branch would be reached by nothing.

What it costs is not yet measured on a quiet lease. `_within_budget` builds the structural cones (the templates of
every object in them), which a fall-through query pays in `Engine.ask` anyway (the second call reads `_qcones`), and
a certified query pays newly. On orion's instrumented pass the certified calls spend in the test: fuzz 0.80 s of a
15.9 s pass (py) and 0.65 of 10.4 (rust); dev 0.08 of 3.06 and 0.07 of 4.15. That is about 5% of fuzz, more than
S1's spread there (iqr 1 to 2%), so item (5)'s rule that fuzz keeps its gain against on at 345's SHA may not hold.
S1 has to say; plant 758 on the head gives the arm without the test.

State: for an over-budget query the answer, the whole of `Engine.stats` and `last_budget_limited` equal the
switch-off path's (kept test, budgets 0, 1 and 2, on a query two points certify). Not yet shown on the budget
workload's seven queries by a stats comparison of on against off: owed to the gate.

## (2) The work bound, 50d8b77

The check counts term evaluations (`_Query.spend`, witness.py:559): a point is charged the query's compiled terms
(`_Query.size`, the calls of `_term`), an evaluation of an atom for a root (`_roots`, :707) that atom's terms.
`SLICE_WITNESS_WORK`, default 2500, 0 for no bound (`WORK`, :107). Past it the check falls through. The cap of 32
points stays as a second limit.

344's "1.9 ms a point" on budget was mostly not points: the roots are looked for before the first point and cost
about 6 evaluations of an atom per symbol in it. On budget's 12 calls that reach `_pools` the work is 106,500
(median) to 495,296 evaluations, of which 32 points are about 14,500.

Work of the certified calls at cap 32, no bound (tools346/pc346.py rows, wk346.py; wk-20wl.md,
wk-fuzz-seeds-0-1-2-42.md):

| | certified | median | 90% | 99% | max | lost at 2000 | lost at 2500 | lost at 8400 |
|---|---|---|---|---|---|---|---|---|
| dev | 173 | 34 | 114 | 222 | 354 | 0 | 0 | 0 |
| fuzz 424242 | 1284 | 294 | 700 | 1308 | 1980 | 0 | 0 | 0 |
| fuzz seeds 0, 1, 2, 42 | 5241 | 287 to 300 | 633 to 696 | 1178 to 1212 | 2282 | 3 | 0 | 0 |
| wiring | 231 | 34 | 286 | 8356 | 8356 | 16 | 16 | 0 |
| the other 16 workloads | 156 | | | | 434 | 0 | 0 | 0 |

Chosen: 2500, above the 100th percentile of dev and fuzz 424242 (1980) and of the four other seeds (2282).
Certifications before -> after: dev 173 -> 173, fuzz 1284 -> 1284, all 20 workloads 1844 -> 1828; the 16 lost are
wiring's (231 -> 215), sign questions on one long sum at 8138 to 8356 evaluations each. A bound of 8400 loses none
of the 1844 but leaves wiring's fall-through work nearly as it is:

| fall-through work (term evaluations) | no bound | at 2500 | at 8400 |
|---|---|---|---|
| budget | 2,298,460 | 30,000 | 100,800 |
| wiring | 2,834,560 | 856,780 | 2,488,944 |
| fuzz | 1,149,338 | 1,149,292 | 1,149,338 |
| dev | 55,144 | 55,144 | 55,144 |

Answer digests with the switch on, py and rust (both Rust switches), on 43e3ee8: dev 31cd0945c07f02a6, fuzz
173502b6ef285ad6, budget 35bc2c4a937bebc0, wiring a0df9fd43e5180c1: 344's digests (tools346/pc1-sum.txt).

Expected on wiring, not measured: at 2500 the check keeps about 0.25 s of its 0.795 s there (344's (b)), against
about 0.07 s that its certifications save, so on would still read several percent above off; item (5)'s rule for
wiring may not hold at any bound that keeps dev's and fuzz's certifications. S1 has to say.

## (3) Plants, 43e3ee8

| plant | what it does | caught by | fired (orion, py, the seven tests named) |
|---|---|---|---|
| 758 `check-first` | points before the engine is asked (witness.py:849) | 4 failed: the over-budget test [0], [1], [2] and the INCONSISTENT-set test | 11 |
| 759 `skip-work` | the bound is passed over (witness.py:564) | 2 failed: the two work-bound tests | 183 |

No workload reaches a difference under 758: the seven over-budget queries of budget are not certified, so answers
and counters are the same with the check first. Under 759 wiring's certified count reads 231, not 215: answers the
same. The bar's rows (suite and workloads, fired from counter 740) are owed.

## Owed, named here

- (4) the gate, (5) S1, (6) the bar and the landing; rebase onto rust-slice once 345 has landed.
- `Engine._ends_without_session` fills `_kids`, `_cones` and `_qcones` for a certified query: witness.py's docstring
  says so; whether the state comparison of the bar's `witness:on` row reads it has to be checked there.
- harness/state.py (shared) changed: `WORK` classified.
