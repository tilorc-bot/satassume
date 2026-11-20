# The witness check in Rust (issue 323) — (1) the profile, read: GO for the port; the port is not started

Planner's ruling for sa-port-350 (20 Nov, on sa-port-349 52bdf2d), items 1-7. This file takes them in order. State:
item 1 done; nothing ported, nothing landed. SLICE_WITNESS stays off by default, Python's witness.py the default and
the reference, the unchanged path the default.

## (1) Profile before building, sa-port-350: 6ee354f9, quiet leases on pareto1

Leases 9bfc7252 (00:19Z to 00:23Z 20 Nov; dev and fuzz) and ed799a94 (00:33Z to 00:35Z; wiring), load at most 1.05;
bench-container, CPU 2, sa-eval-bench:1, S1's environment (sa-port-347's s1/common); 5 rounds, cold processes
alternating inside one invocation (tools350/prof350.sh, onlease350p.sh, goprof350.sh; the table by tab350.py). Tree:
the archive of 6ee354f9 with the bench .so 0982a28074215658 (786410d's build; the crate is source-equal, checked).
One digest per workload on every arm, S1's: dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6, wiring a0df9fd43e5180c1.
"rust" is the slice with both Rust switches on (SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust); on = SLICE_WITNESS=1 at
cap 32 and the tree's work bound 2500.

The driver is tools350/prof350.py (tools328/wit328.py with phases). It times from its own process: the package has
no timer. Three kinds of pass: **plain** wraps only `witness.witnesses` (two clock reads per check), and its
`check s` is the check's inclusive time; **phase** wraps the phases as well; **cprof** enables cProfile only inside
`witnesses`. Seconds are medians of 5 rounds of the plain pass; the four phase columns are the phase pass's split of
its own check time (its timers add 6% to 17% to the check, "timer calls" is how many pairs of clock reads one pass
makes, so the split is a ratio and not a time). These are profile times, not S1 times.

| workload, mode | off s | on s | on/off | fires | compiled | certified | check s | share of on | fall-through s | share of on | compile | search | evaluation | guards | moves (share of on s) | timer calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev py | 0.5274 | 0.5213 | -1.1% | 776 | 535 | 173 | 0.0629 | 12.1% | 0.0493 | 9.5% | 14% | 43% | 40% | 4% | 11.6% | 27767 |
| dev rust | 0.6408 | 0.6602 | +3.0% | 776 | 535 | 173 | 0.0698 | 10.6% | 0.0540 | 8.2% | 15% | 42% | 39% | 4% | 10.1% | 27767 |
| fuzz py | 8.0565 | 5.4143 | -32.8% | 2772 | 2732 | 1284 | 0.7902 | 14.6% | 0.4920 | 9.1% | 6% | 41% | 51% | 2% | 14.3% | 206237 |
| fuzz rust | 5.8443 | 4.6582 | -20.3% | 2772 | 2732 | 1284 | 0.8453 | 18.1% | 0.5226 | 11.2% | 7% | 41% | 50% | 2% | 17.8% | 206237 |
| wiring py | 2.7055 | 2.9815 | +10.2% | 4814 | 1503 | 215 | 0.3157 | 10.6% | 0.3013 | 10.1% | 24% | 25% | 49% | 2% | 10.4% | 91850 |
| wiring rust | 3.2137 | 3.5832 | +11.5% | 4814 | 1503 | 215 | 0.3429 | 9.6% | 0.3260 | 9.1% | 25% | 26% | 47% | 2% | 9.4% | 91850 |

Columns: *fires* the calls of the check; *compiled* those
that reached the point search; *check s* inclusive seconds inside `witnesses`; *fall-through s* the part spent on
queries the check did not certify, which is what the check costs with nothing saved; *compile* from the entry of
`witnesses` to the first guard (the two `_formula` walks, the second compile of a query with pi, `_own`);
*evaluation* the probes' functions inside `_roots` plus `_holds` (the closures, Fraction and _PiPoly arithmetic, the
tables, the own assumptions at a point); *search* the rest (`_pools` without its probe evaluations, `_by_index_sum`,
the loop); *guards* `_patched`, `Engine._known_inconsistent` and `_users_knowledge`, which read the engine and stay
Python in the port; *moves* the check's time without the guards, as a share of the pass.

Own against inclusive (the cprof pass; cProfile charges every Python call, so this is call-weighted time under the
check, not wall time): witness.py's own frames are 58% (dev), 44% (fuzz) and 47% (wiring) of the time under the
check; fractions.py 17%, 32%, 24%; builtins (isinstance, all, set.add, and the profiler's own switch at 5%) 23%, 21%,
26%; engine.py 0.1% to 0.3%; everything else at most 3.1%. The same on py and rust within one point. So in wall
terms the check's own share of a Rust pass is about 6% (dev), 8% (fuzz), 4.5% (wiring), against the inclusive 10.6%,
18.1% and 9.6% of the table; the callees are Fraction arithmetic and builtins, which the port moves with it.

What one phase pass counted (round 1, the same on py and rust): term evaluations charged (`spend`) dev 63,337, fuzz
1,610,808, wiring 911,664; queries past the work bound dev 0, fuzz 2, wiring 294; second compiles for pi dev 42,
fuzz 530, wiring 0; points decided (`_holds`) dev 11,447, fuzz 61,692, wiring 30,278.

Read against the stop rule ("if the share that would move can't plausibly beat the S1 spread on wiring and on Rust
dev, stop"):

- **wiring, rust: 9.4% of the pass would move**, against an S1 interquartile share of 1.5% (witness-bounds.md (5);
  1.2% here). The check's inclusive time, 0.343 s, is nearly all of wiring's cost of the switch (on against off
  +0.37 s, +11.5%): 95% of it is spent on the 4,599 queries it does not certify.
- **dev, rust: 10.1% would move**, against 1.7% (0.8% here). On against off is +3.0% here because the 173 certified
  queries save their sessions; the check itself costs 0.070 s of a 0.660 s pass, 0.054 s of it on fall-through.
- fuzz, the control: 17.8% (rust), 14.3% (py) would move.
- The check's own time is 7% to 11% longer in a Rust pass than in a Python pass on the same queries (dev 0.0698 s
  against 0.0629 s, fuzz 0.845 against 0.790, wiring 0.343 against 0.316); compile, search and evaluation each carry
  it (round 1's raw phase seconds: the tools350 rows). The profile does not say why.

The first pass also asked for wiring by evalbench's name, which it does not have (32 KeyError lines in its err.txt, no
row written); prof350.py now loads it as tools342/qt342.py does, and the second lease ran it. No other error output.

**So the stop rule does not trigger, and the port goes ahead.** A native check at a tenth of Python's time would give
about 8% to 9% on wiring and on Rust dev; it needs a factor of about 1.2 on either only to pass the spread. What does not move: the guards, 2% to 4% of the check (0.1% to 0.4% of a pass).

What the reading of the code adds (not measured): under the slice the query's native term table already exists when
the check runs (`term_live._ask` converts before it calls `sympy_api._ask`), so a native check needs no walk of its
own; and the table is there under either walker. HANDOFF-sa-port-350.md has the design notes and the file:line map.

Not done: items 2 to 7. No source change: the tested SHA is 6ee354f9.
