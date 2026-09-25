# Agent report: fact-lattice theory, stage 0, measurements

- **Date:** 2026-09-25
- **Status:** measured, no engine code. **The plan's formal stop condition is
  not met** (the rule block's never-read fraction is 52%, above the 30%
  line), **but two measurements the plan did not ask for say stage 1 as
  specified would be slower than `main`**: attaching any theory to a
  session costs +13.9% of the pass before it does any work, and a literal
  propagated by a theory costs 3.0 times what the rule block pays for the
  same implication. Projected stage 1: +25% to +40% time, so its own stop
  condition is expected to trigger. The capability census finds 15 stream
  queries (12 distinct) and **0 of the 59 refine scoreboard losses** that
  predicate transfer answers, and 498 that a
  different, independent change answers (uninterpreted relations as free
  Booleans), which breaks the acceptance rule on 36 queries. Decision
  needed from the user: see "Decision".
- **Scope:** measurement only. Scripts (new):
  `agent-reports/scripts/facts_closure.py` (exact closure oracle),
  `facts_census.py` (rule writes, mentions, reads, asserted sets, case
  splits), `facts_capability.py` (capability oracles, SymPy verification),
  `facts_theory_tax.py` (theory tax and per-literal cost), `facts_scoreboard_*`
  (pytest plugin routing the refine suite's `satassume` backend through the
  capability oracles, run scripts, analysis; written by an Opus subagent).
  Pi, branch `facts-theory` at `e43b318` (`main`), SymPy pin `ddbb536d7e`.
- **Read this if:** you decide whether stage 1 of
  `2026-09-25-fact-lattice-theory-plan.md` is built as planned, changed,
  or dropped

## Measurement

Baseline on the Pi at `e43b318`: suite `2 failed, 1694 passed, 1 skipped,
4 xfailed, 1 xpassed` (the known `test_shared_facts` pair; 58 s with
`-n 3`), cold replay 2.92 to 3.01 s.

### 1. The never-read fraction (`facts_census.py`)

The replay (13,877 queries, answers identical to the recording) with the
solver and engine wrapped from outside. A *rule write* is a trail entry
the rule block assigns (int reason in `_propagate`, or a root unit of
`_rb_settle`). A variable is *mentioned* when a clause added by something
other than the rule block contains it, tagged by the engine step that
added it.

| | writes | share |
|---|---:|---:|
| rule writes per pass (1,597 solvers, 8,900 node blocks) | 550,530 | 100% |
| at root | 720 | 0.1% |
| variable mentioned outside the rule block (templates, assumptions, query, links, guards, custom), i.e. a variable stage 1 would still allocate (plan 2.3) | 263,566 | **47.9%** |
| same, counting cache units and learnt clauses too | 263,613 | 47.9% |
| **never mentioned**: stage 1 would not write these | 286,964 | **52.1%** |
| *read* (dynamic, lower bound): antecedent of a non-rule clause's propagation, in a conflict clause, or the query variable | 81,465 | 14.8% |
| of these, read but never mentioned (learnt-clause antecedents) | 29 | 0.0% |

By mention source: 42.3% template only, 1.3% query only, 1.2% template and
query, 1.0% link only, the rest small mixtures. Theory atoms are relation
variables, never predicate variables, so no rule write is read by a theory.

**Per node: 19.1 of the 33 predicates are mentioned** (19.97 counting cache
and learnt clauses). The plan (2.3) expected "a few": templates mention
most of a node's vocabulary. Histogram: 846 blocks mention at most 4
predicates, 1,402 mention exactly 22, 501 mention 32. The predicates most
often never mentioned while written: `noninteger` 98% of its writes,
`transcendental` 96%, `antihermitian` 85%, `nonzero` 80%,
`positive_infinite`/`negative_infinite` 74%; the least: `commutative` 13%,
`imaginary` 18%, `algebraic` 19%, `infinite` 19%, `real` 22%.

The plan's rule: under 30% read, a 10 to 20% gain; above 70%, a few
percent. The design-relevant fraction (what stage 1 still writes) is 48%,
in the middle; the dynamic read fraction is 15%.

### 2. What a theory propagation costs (`facts_theory_tax.py`), not asked for by the plan

The plan's section 4.2 counts the added work at "about a microsecond any
Python theory call costs". The solver says otherwise:

- `Solver._assume` keeps held assumption levels **only without theories**,
  and a propagation during which a theory propagated is not cached
  (`_theory_imply` bumps `_stamp`); `propagate` goes through
  `_tpropagate`/`_theory_sync` when any theory is attached.
- `_theory_imply` at a decision level stores the reason as a learnt clause
  (a `Clause` object, two watches, `_stamp` bump) for every propagated
  literal.

Measured on the Pi:

| | |
|---|---:|
| cold pass, plain (3 interleaved runs) | 3.006 / 2.916 / 2.978 s |
| cold pass, a no-op theory attached to every session | 3.363 / 3.322 / 3.399 s |
| cold pass, no-op theory with an empty `propagate` | 3.363 / 3.382 / 3.480 s |
| **theory tax, best against best** | **+13.9%** (+14.8% with `propagate`) |
| micro: implication by the rule block (2,000 blocks, `integer` implies 15 literals each, under an assumption) | 1.54 µs per literal |
| micro: the same implications by a theory's `propagate` with eager reasons | 4.65 µs per literal (**3.0x**) |

### 3. Projection for stage 1 as specified

From the B5 split (rule hook 20.0%, registration 0.9%, `_grow` 3.2%,
collector 3.7 to 4.4%) on a 2.95 s pass:

| | seconds |
|---|---:|
| removed: rule hook, registration, 42% of `_grow` (19 of 33 variables kept), some collector work | about -0.70 |
| added: theory tax (measured) | +0.41 |
| added: 263,566 propagations to mentioned variables at the micro's 4.65 µs (scaled by the micro's own ratio to the replay: 550,530 writes at 1.54 µs would be 0.85 s, the B5 hook share is 0.59 s, so x0.69) | +0.85 to +1.23 |
| added: closure memo misses (2,857 distinct asserted sets, below) | +0.1 to 0.3 |
| **net** | **about +0.7 to +1.2 s, +25% to +40%** |

Even with the propagation cost halved by tuning, the tax alone eats most
of the removal. Stage 1's stop condition ("slower than `main` after a day
of tuning") is expected to trigger.

### 4. Distinct asserted sets (`facts_census.py`)

After every `_propagate`, for each node block with a new literal not
implied by the rule block: the set of the block's literals assigned for
another reason (decision, assumption, clause, root unit).

- 36,580 observations, **2,857 distinct asserted sets**; the sets of all
  assigned literals of those blocks: 374 distinct.
- So the closure memo would have about 2,900 entries per pass, a few
  hundred if keyed by the unit-propagated set. The exact closure
  (`facts_closure.closure`, a 33-variable DPLL, candidates narrowed by
  each model found) costs about 0.1 to 1.6 ms in Python per miss.

### 5. Case-split dependence (`facts_census.py`)

62 `entails` calls per pass search and end definite (the plan's 62; 3,130
search and end None). For each, the design's propagation was simulated on
the session's non-rule, non-learnt clauses: unit propagation plus the
exact closure per block, to a fixpoint; the control does the same with the
rule block's unit propagation.

| design / control | theories | queries |
|---|---|---:|
| open / open | yes | 40 |
| refuted by one propagation of the opposite literal / same | no | 20 |
| refuted / same | yes | 2 |
| decided by propagation | | **0** |

**No search answer rests on a case split inside the rule base.** Every
one needs search in the design too (a template or theory case split, or at
least one lookahead), and the exact closure decides nothing the rule
block's unit propagation does not on these queries. The plan's
completeness argument (predicates no clause mentions need no case split)
holds on the stream.

Separately, the exact closure is strictly stronger than the rule block's
unit propagation in general: of the 2,178 consistent sets of one or two
predicate literals, 170 get more literals (`antihermitian` gives
`complex`, `finite`, `commutative`, `!positive`, ...; `!noninteger` gives
`!irrational`). None of those gains shows up in the 62 search answers.

### 6. Capability census, stream (`facts_capability.py`)

Every query of the stream (one answer memo per mode, fresh engine) under
four oracles, compared with the recording:

| oracle | same | more definite | new ValueError (inconsistent) | less definite |
|---|---:|---:|---:|---:|
| `base` (unchanged `_ask`) | 13,877 | 0 | 0 | 0 |
| `transfer`: `eq(a, b) -> (P(a) <-> P(b))` for all 33 predicates, per equality atom (layer 2.2) | 13,858 | **15** | 0 | 4 |
| `free`: an uninterpreted relation is a free Boolean, not a None | 13,343 | **498** | **36** | 0 |
| `both` | 13,324 | 513 | 36 | 4 |

- **Transfer answers 15 stream queries (12 distinct)**, all of them with
  `eq` against a number or another term: `real(x)`/`extended_real(x)`
  given `x = pi/2` or `x = 2` (True), `zero(sin(x))` given `x = 2`
  (False), `eq(n, 1)` given `~integer(n)` (False), `eq(n, k)` given
  `integer(n) & nonnegative(n) & k > n` (False: transfer makes `k` real,
  which un-guards LRA). SymPy's `ask` returns None on 11 of the 12 and
  raises ValueError on one (`eq(n, k)` given `integer(n) & negative(n) &
  ~integer(k)`, which is consistent: `n = -1, k = 1/2`). All 12 checked by
  hand: correct.
- The 4 "less definite" are not transfer: they contain no equality and
  answer None in a fresh engine even without the oracle. Their recorded
  answers come from the session's history (learnt or cone-memo clauses of
  earlier queries under the same assumptions), and the oracle's extra
  atoms changed that history. **Risk for every later stage: the engine's
  answers depend on query order, so an internal change can make a
  recorded answer less definite without any loss of reasoning.**
- **Free Booleans answer 498 queries** (445 distinct; ordering relations
  against `pi`, `pi/2`, ... in the assumptions). Against SymPy's `ask`:
  412 of the distinct answers agree, 19 SymPy cannot decide, and the other
  12 are all among the 36 new ValueErrors: assumptions such as
  `negative(x) & positive(x) & t > -pi/2 & ...`, which are inconsistent,
  where SymPy answers the unrelated proposition (`Q.zero(pi)`: False)
  without checking. Today these 36 are None because the session never
  builds. The acceptance rule of the plan (section 5) requires the set of
  InconsistentAssumptions errors to stay identical, so this change breaks
  it on 36 queries, in the direction of SymPy's own semantics
  (inconsistent assumptions raise).
- The free-Boolean change does not need the fact-lattice theory at all:
  it is the last line of `Relations.process` (plan section 3, last row).

### 7. Capability census, refine scoreboard

Done by an Opus subagent on a checkout of `origin/refine-monorepo`
(`20f3b9c`) at `/work/src/refine-mono`, with the branch's refine suite and
handlers and either its own old `satassume` or the current engine
(`e43b318`, via `PYTHONSAFEPATH=1` and `PYTHONPATH`; each run records
which `satassume.__file__` the pytest subprocess loaded). The oracles go
through a pytest plugin (`facts_scoreboard_plugin.py`, `-p` via
`PYTEST_ADDOPTS`) that answers the `satassume` backend with
`facts_capability.answer`. Raw outputs: `/work/src/facts-logs/scoreboard/`.

| `satassume` backend | passed | failed | losses against `sympy` | of the 59 fixed | regressions |
|---|---:|---:|---:|---:|---:|
| the branch's old engine | 412 | 59 | 59 | | |
| current engine (`e43b318`) | 416 | 55 | 52 | 8 | 1 (a stale test expectation, below) |
| oracle `base` (control) | 416 | 55 | 52 | 8 | 0 |
| oracle `transfer` | 416 | 55 | 52 | **8 (+0)** | 0 |
| oracle `free` | 422 | 49 | 46 | 14 (+6) | 0 |
| oracle `both` | 422 | 49 | 46 | 14 (+6) | 0 |

(`sympy` backend: 462 passed, 7 failed, 4 xfailed; the published baseline
reproduces exactly. The `base` control answers all 1,419 distinct queries
like plain `ask`.)

The 59 losses by kind: 45 matrix (matrix predicates on `MatrixSymbol`s;
out of any unary scalar design), 5 inverse-trig principal branches and 1
trig verifier test (orderings against `pi`, `pi/2`; fixed by `free` only),
4 Min/Max order rules and 2 KroneckerDelta (already fixed by the current
engine's LRA/EUF), 2 binomial/factorial at a literal (`Q.zero(k) |
Q.eq(k, 1)`: the transfer shape, but already answered by the existing
`zero <-> eq(e, 0)` link). The one new loss under the current engine,
`test_kronecker_reversed_assumption_order`, asserts that
`refine(KroneckerDelta(i, j), Q.eq(i, j))` stays unchanged; the engine now
answers `Q.eq(i, j)` under `Q.eq(i, j)` correctly, so the expectation is
stale.

Transfer changes 4 answers in the whole suite (`Q.eq(n, 1)` under
`Q.infinite(n)` and similar, None to False), none of which changes a test
outcome. Every answer an oracle changed agrees with SymPy's `ask` (4 from
transfer, 34 distinct from `free`).

Combined backend (satassume first, SymPy on None; 6,701 queries, 463
passed / 6 failed in all three runs): SymPy fallbacks 3,645 with the old
engine, 3,494 with the current one, 3,412 with the `both` oracle. SymPy
itself answers None on 2,374 of the 2,413 scalar fallbacks and 428 of the
442 relation fallbacks that remain under `both`; none of the 14 relation
fallbacks SymPy still answers needs transfer (10 have an unrelated matrix
predicate in the assumptions, 3 compare infinities, 1 is `Q.eq(nan, 1)`).

## Change

None to the engine. Scripts listed in the header, and this report.

## Gates

No engine change, so none run beyond the baseline: suite as above;
`facts_census.py` and `facts_capability.py` check every answer of their
base replay against the recording (0 differences).

## Decision

The plan's stop condition for stage 0 is "never-read fraction below about
30% **and** fewer than about 20 stream queries and fewer than about 10
scoreboard losses the design would answer". The never-read fraction is
52%, so formally the design survives stage 0 as a speed lever. It does
not survive as one in practice: section 3 projects stage 1 at +25% to +40%,
because the plan priced a theory call at a microsecond and the solver's
theory path costs a 14% tax plus 3 times the rule block per literal. On
capability, predicate transfer answers 15 stream queries (below the 20
line) and none of the 59 scoreboard losses (below the 10 line).

So the capability half of the stop condition is met clearly (15 < 20,
0 < 10), and the speed half is met in substance though not in letter: the
never-read literals exist, but the plan's mechanism for not writing them
(a DPLL(T) theory) costs more than they do. My reading: **the design is
neither a speed nor a capability lever on the workloads we have, and the
plan's intent is to stop here.** Because the letter of the rule is not
met, I stop for the user's decision instead of ending the project myself.
Options, in the order I recommend them:

1. **End the fact-lattice project** here (keep the scripts, the report and
   the `--allow-more-definite` tooling).
2. Separately from this plan, consider **uninterpreted relations as free
   Booleans** (the last line of `Relations.process`): 498 stream answers,
   6 scoreboard losses fixed, 82 fewer SymPy fallbacks in the combined
   backend, all verified against SymPy; but 36 queries with inconsistent
   assumptions then raise ValueError instead of returning None (against
   the plan's acceptance rule, in the direction of SymPy's semantics) and
   the replay costs about +35% time (one noisy round), because the 1,130
   queries per pass that the round 2.5 memo answers with None in 0.01 ms
   now build and search sessions. That needs its own cost work before it
   could land.
3. Predicate transfer only, in sessions that already have EUF (no new
   theory tax): 15 stream queries, 0 scoreboard tests. Cheap but small.
4. Stage 1 redesigned as a solver-internal closure propagator (no theory
   API; per-block bitmask state, memoized exact closure, lazy int reasons,
   writes only to mentioned variables): a solver change the plan excluded;
   ceiling about 10% of the pass (52% of the 20% hook), realistic about 5%
   after the memo's cost.
5. Stage 1 as planned (expected to hit its stop condition).

## Risks for review

- The mention analysis charges a variable as "needed" if any non-rule
  clause mentions it at any time in the session; a design that allocated
  variables only for predicates a clause could still use would write a
  little less. It cannot write fewer than the 14.8% that are read.
- The theory tax is measured with a theory that does nothing; a real
  `FactTheory` adds its own work on top.
- The case-split simulation ignores LRA/EUF reasoning (42 of the 62
  sessions have theories); it can under-report what propagation decides
  there, not over-report.
- History dependence (the 4 less-definite answers) will show up as
  mismatches in every A/B of any later stage; they need to be told apart
  from real losses, e.g. by re-asking in a fresh engine.
