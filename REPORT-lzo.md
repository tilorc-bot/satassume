# sa-lzo-1: model-checked lazy escalation (outer loop): bound

Status: question. The loop is exact and keeps answers identical, but it is
slower than escalating everything. Recommendation: drop it (do not build).

Baseline 9bafaa5, branch `lazy-outer`. Scripts are in `bound-lzo/`:
`esc_breakdown.py` (what escalation builds today, by step and caller),
`lazy_sim.py` (the loop as a monkeypatch of `Engine._complete_check` and
`Engine._ask`, `engine.py` unchanged), `drive.sh` (pinned interleaved A/B).

## What today's escalation costs (dev, 1,985 queries; fuzz seed 424242, 3,000)

`Session.escalate`, all callers (orion, exclusive time, one cold process):

| | dev | fuzz 424242 |
|---|---:|---:|
| pass | 0.789 s | 12.68 s |
| escalate total | 0.054 s (6.8%) | 0.335 s (2.6%) |
| parked pattern clauses (`pending_c`) emitted | 0.042 s, 17,612 clauses | 0.330 s, 141,889 clauses |
| parked formulas (`pending`) compiled | 0 | 0 |
| derived nodes visited (`deferred`) | 0.011 s, 99 nodes | 0 |
| calls: set check / `_ask` / `_decide` | 175 / 304 / 11 | 1,077 / 2,439 / 106 |

So the most the loop can save is the escalation itself: 6.8% of dev, 2.6% of
fuzz, assuming checks are free and no search is added. Almost all of it is
parked pattern clauses. On these workloads parked formulas never occur, and
derived nodes occur on dev only.

## The loop (as simulated)

`lazy_sat(s, A)`: visit every unvisited node of the cone, then repeat:
solve under `A` on the built facts; if UNSAT, answer UNSAT; otherwise check
every parked clause against the model (lazy variables completed with
`Solver._fill`), build the clauses it falsifies, and solve again. Stop when
the model satisfies every parked clause.

- Set check (`_complete_check`): `lazy_sat(s, lits)` replaces
  `escalate()` + `solve(lits)`.
- Query (`_ask`): when propagation leaves the query open and the session is
  incomplete, the outcome is `lazy_sat(lits + [-q])` and `lazy_sat(lits + [q])`,
  read as `Solver.entails` reads its two searches (both UNSAT means
  inconsistent). Derived-predicate queries (tuple literals: 135 on dev, 294
  on fuzz) still escalate as today.

**Derived nodes (the hard case).** The simulation visits every derived node
the cone reaches: it registers the node's rule block and parks all of its
clauses (`node(n, set())`), and the model check then covers those clauses
like any others. I found no cheaper exact test for leaving a derived node
unvisited. Its templates T(d) constrain its arguments, which are in M, so
leaving d out is sound only if some assignment of d's variables satisfies
RB(d) ∧ T(d), and the whole unvisited cone below d, given M on the
arguments. Templates are meant to be total (#54, #61), which would make
that always true, but nothing proves it per query. Testing it is a small
SAT problem over d's block, which costs about as much as a visit. So the
rule is "visit always, park everything". The bound shows that even a free
pass on derived nodes would add at most 1.4% on dev, which changes nothing.

## Exactness argument

The built facts are a subset of the cone's facts. So UNSAT under the
assumptions on the built facts is UNSAT on the whole cone. INCONSISTENT,
True and False therefore stay exact, because a definite answer rests on an
UNSAT. The loop stops only when a model M of the built facts satisfies
every parked clause. Lazy variables are completed per block with a model
of that block that agrees with M's assigned values, the same completion
`_fill` gives every stored-model reader. At that point every node of the
cone is visited, so M is a model of the full cone. A SAT verdict, or a
None answer, needs that model, and it is backed by a real witness of the
complete facts. A clause the check misjudges (a variable with no value is
counted as falsifying) is only built early, which costs time and never
correctness. The loop depends only on the query and its session, so
history independence is unchanged.

Checked: answers identical to 9bafaa5 on dev (1,985 of 1,985) and on fuzz
seed 424242 (3,000 of 3,000).

## Bound

Counts (deterministic):

| | dev today | dev loop | fuzz today | fuzz loop |
|---|---:|---:|---:|---:|
| parked clauses in escalated sessions | 16,316 | 16,316 | 158,270 | 158,270 |
| parked clauses built | 16,316 | 1,831 (11%) | 158,270 | 10,964 (7%) |
| derived nodes visited | 99 | 42 (+ tuple fallback) | 0 | 0 |
| searches (set checks + queries) | 650 | 1,296 | 3,682 | 8,503 |
| model-check passes | 0 | 1,013 | 0 | 7,910 |
| search rounds per lazy `lazy_sat` (check / query) | 1 | 1.74 / 1.67 | 1 | 1.70 / 1.46 |

Time that today spends building what the loop does not build: about
0.89 × 0.042 s + 0.6 × 0.011 s ≈ 0.044 s, 5.5% of the dev pass (fuzz: about
0.31 s, 2.4%). That figure is gross. Net of the extra searches and the
checks (orion, 3 interleaved rounds on dev):

| phase (dev) | today | loop |
|---|---:|---:|
| `escalate` | 0.056 s | 0.017 s (tuple fallback only) |
| model checks (`check_and_build`) | 0 | 0.032 s |
| `_complete_check` (includes its escalate or loop) | 0.076 s | 0.083 s |
| `_ask` (includes its escalate or loop, searches) | 0.331 s | 0.350 s |
| pass | 0.820 s | 0.857 s (+4.5%) |

Fuzz 424242, orion: `_complete_check` 1.10 s to 1.18 s, `_ask` 6.77 s to
7.21 s, pass 12.82 s to 13.15 s (+2.5%).

Pinned A/B (pareto1, quiet lease, `bench-container`, one CPU, 6 rounds of
cold processes, plain and loop alternating, PYTHONHASHSEED=0, `drive.sh`):

| workload | today (median) | loop (median) | speedup | per round |
|---|---:|---:|---:|---|
| dev, all | 0.526 s | 0.549 s | 0.958x | 0.947 to 1.007 |
| dev, None | 0.312 s | 0.329 s | 0.949x | 0.935 to 0.987 |
| fuzz 424242, all | 8.02 s | 8.56 s | 0.936x | 0.924 to 0.940 |
| fuzz 424242, None | 6.70 s | 7.19 s | 0.931x | 0.919 to 0.935 |

Net bound: **-4.2% on dev, -6.4% on fuzz** (the loop is slower).
sa-lzp-1's pinned split (escalation is 5.8% of dev, of which emission is
5.0% and derived nodes 0.8%) agrees with the orion shares above.

Downstream effect (forward-chain-3b's question). The models violate fewer
parked clauses than sa-lzp-1's count of clauses that are ever unit or
false: 11% on dev against 33.7%, and 7% on fuzz against 26%. Propagation
and search over the smaller formula still get no cheaper in total. `_ask`
and the set check both get slower, because every saving there goes to the
extra search rounds.

Why it loses: one check pass over the parked clauses in Python, about
1.3 µs a clause, costs half of what emitting them costs (about 2.4 µs a
clause). The loop also runs at least two passes for every None answer
(¬q and q), and 1.5 to 1.7 search rounds per satisfiable call, which
doubles the number of searches. Smaller formulas do not pay that back:
searches have few decisions and conflicts (dev: 7,738 decisions and 257
conflicts in total). Even with free checks and no extra rounds, the ceiling
is 5.5% on dev and 2.4% on fuzz, at the 5% threshold. With a single check
pass it is about 2 to 3%, and with the rounds it is negative.

## Recommendation

Drop it. The outer loop's unit of work (a search, then a scan of the
parked clauses) is too coarse for facts this cheap to build. If lazy facts
are to pay at all, the criterion has to live inside the solver, where a
parked clause is checked only when its watched literals become false. That
is sa-lzp-1's scope (a lazy propagator), not this one. I am not building
anything.
