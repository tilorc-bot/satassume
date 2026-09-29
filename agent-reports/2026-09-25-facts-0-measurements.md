# Agent report: fact-lattice theory, stage 0, measurements

- **Date:** 2026-09-25
- **Status:** measured, no engine code; reviewed (Opus, verdict "sound with
  corrections", applied below). **The stage 0 stop condition is not met on
  either half**: of the rule block's implied literals, 52% are never
  *mentioned* outside the rule base (stage 1 would not write them) and
  about 85% are never *read* (both above the 30% line), and the design, counted as the plan counts it (predicate
  transfer plus uninterpreted relations as free Booleans, section 3's last
  row and stage 2), answers 513 stream queries (above the 20 line). So the
  plan continues with stage 1. Two cautions carried into it: attaching any
  theory to a session costs +14% of the pass today, almost all of it one
  solver policy (held assumption levels are kept only without theories;
  allowing them brings the tax to +3 to 5%), and a theory-propagated
  literal costs 2.2 to 2.8 times a rule-block implication. The projection
  for stage 1 as specified is +4% to +19%; the plan's own stage 1 stop
  ("slower than `main` after a day of tuning") settles it. Capability is
  almost all free Booleans (498 queries, 6 scoreboard losses), which
  breaks the acceptance rule on 36 queries: a decision the user must make
  before stage 2, not before stage 1. Predicate transfer alone answers 15
  stream queries and none of the 59 scoreboard losses.
- **Scope:** measurement only. Scripts (new):
  `agent-reports/scripts/facts_closure.py` (exact closure oracle),
  `facts_census.py` (rule writes, mentions, reads, asserted sets, case
  splits), `facts_capability.py` (capability oracles, SymPy verification),
  `facts_theory_tax.py` (theory tax and per-literal cost), `facts_scoreboard_*`
  (pytest plugin routing the refine suite's `satassume` backend through the
  capability oracles, run scripts, analysis; written by an Opus subagent).
  Pi, SymPy pin `ddbb536d7e`. Measured first at `e43b318`, then, after
  `main` reverted the unreviewed hot-loop and witness-reuse commits and
  landed the reviewed witness reuse, **re-measured on the new baseline
  `c552806`** (the plan baseline from now on; `facts-theory` rebased onto
  it). Every number below is from `c552806` unless marked; the census and
  capability numbers came out identical on both.
- **Read this if:** you decide whether stage 1 of
  `2026-09-25-fact-lattice-theory-plan.md` is built as planned, changed,
  or dropped

## Measurement

Baseline on the Pi at `c552806`: suite `2 failed, 1697 passed, 1 skipped,
4 xfailed, 1 xpassed` (the known `test_shared_facts` pair; 58 s with
`-n 3`), cold replay 2.90 to 2.94 s (at `e43b318`: 1694 passed, 2.92 to
3.01 s).

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
| *read* (dynamic, lower bound): antecedent of a non-rule clause's propagation, in a conflict clause, or the query variable | 81,810 | 14.9% |
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
in the middle; the dynamic read fraction is 15%. (The first version of
the script scanned each `_propagate` call from the trail's end instead of
the queue head and missed entries queued before the call; fixed after
review: writes and mentions unchanged, reads 14.8% to 14.9%.)

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
| cold pass, plain (3 interleaved runs) | 2.904 / 2.940 / 2.912 s |
| cold pass, a no-op theory attached to every session | 3.325 / 3.314 / 3.342 s |
| **theory tax, best against best** | **+14.1%** (at `e43b318`: +13.9%, and +14.8% with an empty `propagate`) |
| micro: implication by the rule block (2,000 blocks, `integer` implies 15 literals each, under an assumption) | 1.69 µs per literal (`e43b318`: 1.54) |
| micro: the same implications by a theory's `propagate` with eager reasons | 4.69 µs per literal (**2.8x**; `e43b318`: 4.65, 3.0x) |

Found in review, and they change the size of both numbers:

- **The tax is mostly one policy.** `Solver._assume` keeps held
  assumption levels only when no theory is attached (two `not theories`
  gates). With both gates removed in a scratch copy, the reviewer measured
  plain 2.754 / 2.806 s against no-op theory 2.896 / 2.898 s: **+3% to
  +5%**, answers identical (unpatched in the same session: +14%). Whether
  held levels are sound with a stateful theory is not established; it is a
  small solver change the plan's scope ("`solver.py` (small)") allows, and
  stage 1 has to decide it.
- **The micro favours the rule block.** Its `implied` keeps held levels and
  so skips the backtrack the theory side pays; counting the backtrack on
  both sides: rule 2.04 µs, theory 4.58 µs, **2.2x**. The tax and the
  per-literal cost also partly count the same `_tpropagate` routing twice.

### 3. Projection for stage 1 as specified

From the B5 split (rule hook 20.0%, registration 0.9%, `_grow` 3.2%,
collector 3.7 to 4.4%) on a 2.95 s pass:

| | seconds |
|---|---:|
| removed: rule hook, registration, 42% of `_grow` (19 of 33 variables kept), some collector work | about -0.70 |
| added: theory tax (measured +14%; +3 to 5% with held levels allowed under theories) | +0.14 to +0.41 |
| added: 263,566 propagations to mentioned variables at 2.2x to 2.8x the rule block's per-literal cost, scaled to the replay (550,530 writes are the B5 hook's 0.59 s, so about 1.07 µs each) | +0.62 to +0.79 |
| added: exact closures (8,128 distinct asserted sets; section 4: a table lookup over the rule base's 48 models) | about +0.05 |
| **net** (first version of this report: +20% to +40%; the review's +33% upper bound mixed methods, corrected on landing) | **about +0.1 to +0.55 s, +4% to +19%** |

Stage 1 as specified is projected slower than `main` over the whole
range, but the range is wide and mostly policy: with held levels under
theories and cheap theory reasons it approaches break-even. The projection
gives no credit to the plan's `decided` short-cut (2.5). The plan's own
stage 1 stop ("slower than `main` after a day of tuning") is where this is
settled by measurement.

### 4. Distinct asserted sets (`facts_census.py`)

After every `_propagate`, for each node block with a new literal not
implied by the rule block: the set of the block's literals assigned for
another reason (decision, assumption, clause, root unit).

- 103,422 observations, **8,128 distinct asserted sets**; the sets of all
  assigned literals of those blocks: 526 distinct. (The first version
  scanned from the trail's end and reported 36,580 / 2,857 / 374; see
  section 1.)
- The DPLL closure of `facts_closure.closure` costs 0.55 ms on average on
  these sets (reviewer), 4.5 s for 8,128 misses: too slow as it stands.
  But **the rule base has exactly 48 models** (enumerated), so the exact
  closure of a set is the literals common to all models containing it: a
  bitwise AND over at most 48 precomputed 66-bit masks, a few µs, and the
  memo is optional. The reviewer checked `closure` against that brute
  force: 0 mismatches on all 2,178 one- and two-literal sets, 2,357 random
  3-to-8-literal sets, and all stream asserted sets.

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
unit propagation in general: of the 2,178 sets of one or two predicate
literals (1,835 of them consistent), 170 get more literals (`antihermitian` gives
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

- **Transfer answers 15 stream queries (15 distinct; the first version
  said 12, corrected on landing)**, all of them with
  `eq` against a number or another term: `real(x)`/`extended_real(x)`
  given `x = pi/2` or `x = 2` (True), `zero(sin(x))` given `x = 2`
  (False), `eq(n, 1)` given `~integer(n)` (False), `eq(n, k)` given
  `integer(n) & nonnegative(n) & k > n` (False: transfer makes `k` real,
  which un-guards LRA). SymPy's `ask` gives the same False on 6, None on
  7, raises ValueError on one (`eq(n, k)` given `integer(n) & negative(n)
  & ~integer(k)`, which is consistent: `n = -1, k = 1/2`) and times out
  on one. All checked by hand: correct.
- The 4 "less definite" are not transfer: they contain no equality and
  answer None in a fresh engine even without the oracle. Their recorded
  answers come from the session's history (learnt or cone-memo clauses of
  earlier queries under the same assumptions), and the oracle's extra
  atoms changed that history. **Risk for every later stage: the engine's
  answers depend on query order, so an internal change can make a
  recorded answer less definite without any loss of reasoning.**
- **Free Booleans answer 498 queries** (407 distinct; ordering relations
  against `pi`, `pi/2`, ... in the assumptions): 388 agree with SymPy's
  `ask`, 19 SymPy cannot decide, none contradicts. With the 36 new
  ValueErrors that makes 443 distinct changed queries (the first version
  said 445 and counted the errors into the agreement figures; corrected
  on landing). **The 36 come from 3 plainly inconsistent assumption
  sets** (`x` negative and positive, twice; `x` positive and zero, each
  with orderings of `t` against `pi/2`), and **SymPy's own `ask` raises
  ValueError on 24 of them**; on the other 12 it answers the unrelated
  proposition (`Q.zero(pi)`: False) without checking the assumptions. Today these 36 are None because the session never
  builds. The acceptance rule of the plan (section 5) requires the set of
  InconsistentAssumptions errors to stay identical, so this change breaks
  it on 36 queries, in the direction of SymPy's own semantics
  (inconsistent assumptions raise).
- The free-Boolean change does not need the fact-lattice theory at all:
  it is the last line of `Relations.process` (plan section 3, last row).

### 7. Capability census, refine scoreboard

Measured at `e43b318` (not re-run on `c552806`: the solver change between
them changes no answer on either gate, and the scoreboard only counts
answers). Done by an Opus subagent on a checkout of `origin/refine-monorepo`
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
| oracle `base` (control) | 416 | 55 | 52 | 8 | 01 (the same Kronecker test) |
| oracle `transfer` | 416 | 55 | 52 | **8 (+0)** | 01 (the same Kronecker test) |
| oracle `free` | 422 | 49 | 46 | 14 (+6) | 01 (the same Kronecker test) |
| oracle `both` | 422 | 49 | 46 | 14 (+6) | 01 (the same Kronecker test) |

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

## Review

Opus reviewer, on `c552806` + this branch: **sound, with corrections**.
Applied above: the asserted-set scan (8,128 distinct, not 2,857), the
memo cost line (it contradicted its own per-miss figure; replaced by the
48-model table), the theory tax as a policy (+3 to 5% with held levels),
the micro's bias (2.2x with the backtrack counted), the projection (+4% to
+19%, not +20% to +40%; the review's figure was +33%, corrected on
landing), "2,178 sets, 1,835 consistent", a docstring
(`integer` implies 15 literals, not 12), and, the one that changes the
decision, the reading of the stop condition's capability half (below).
Checked clean by the reviewer: the `--allow-more-definite` modes (strict
mode unchanged; doctored streams with a contradiction or a less definite
answer fail with and without the flag), the census accounting and literal
conversions, `_sim` as a sound lower bound, `closure` exact. Gates the
reviewer re-ran: gate2 with and without the flag `2863 records (2588 in
scope); changed 0; answers match`; `ab.py . . --rounds 1` strict and with
the flag: answers match; census headline numbers reproduced; tax +13.2%.

## Decision

(Stage 1 measured the design at +56%: the projection's per-literal model
missed the cost of telling the theory every literal and of registering
atoms; see `2026-09-25-facts-1-fact-theory.md`.)

The stop condition for stage 0 is "never-read fraction below about 30%
**and** fewer than about 20 stream queries and fewer than about 10
scoreboard losses the design would answer". Neither half holds:

- never-read fraction about 85% (only 14.9% of the implied literals are
  read); the never-*mentioned* share, what stage 1 would not write, is
  52% (the first version of this report called that the never-read
  fraction; corrected on landing);
- the plan counts uninterpreted relations as free Booleans as part of the
  design (section 3, last row: "2.2 and a small `relations.py` change";
  stage 2), and with them the design answers 513 stream queries and 6
  scoreboard losses. Predicate transfer alone answers 15 and 0; my first
  version counted only those and read the capability half as met, which
  the reviewer rightly called too favourable to stopping.

So **the plan continues with stage 1**, whose own stop condition decides
the speed question the projection leaves open (+4% to +19%). Stage 1
starts from the two levers the measurements expose: held assumption
levels under theories (a small solver change, soundness to be argued and
fuzzed) and a table closure over the 48 models. Carried forward for the
user, before stage 2 (not blocking stage 1): the free-Boolean change turns
36 None answers into ValueError (inconsistent assumptions), which the
plan's acceptance rule forbids, and costs about +35% time in one noisy
round, because queries the round 2.5 memo answered with None in 0.01 ms
now build and search sessions.

## Risks for review

- The mention analysis charges a variable as "needed" if any non-rule
  clause mentions it at any time in the session; a design that allocated
  variables only for predicates a clause could still use would write a
  little less. It cannot write fewer than the 14.9% that are read.
- The theory tax is measured with a theory that does nothing; a real
  `FactTheory` adds its own work on top.
- The case-split simulation ignores LRA/EUF reasoning (42 of the 62
  sessions have theories); it can under-report what propagation decides
  there, not over-report.
- The stage 1 projection is a projection over a wide, policy-dependent
  range, not a measurement.
- Held levels with a theory attached (the lever behind most of the tax)
  are untested for soundness with a stateful theory.
- With `--allow-more-definite`, `ab.py` checks each side only against the
  recording; neither tool checks more-definite answers against SymPy.
- History dependence (the 4 less-definite answers) will show up as
  mismatches in every A/B of any later stage; they need to be told apart
  from real losses, e.g. by re-asking in a fresh engine.
