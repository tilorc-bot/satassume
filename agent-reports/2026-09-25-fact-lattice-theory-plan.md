# Agent report: unary facts as a lattice-valued theory backed by EUF (capability first, speed as a possible second win)

- **Date:** 2026-09-25
- **Status:** design and evaluation plan; nothing implemented. Written for a
  fresh agent starting from `main` at the end of performance round 3
  (report `2026-09-25-perf-round-3-report.md`; issues #9, #11). Companion
  to `2026-09-25-global-solver-evaluation-plan.md` (the persistent
  solver); the two share an acceptance rule and can be done in either
  order, this one first is the recommendation.
- **Scope:** new `satassume/facts_theory.py`; `solver.py` (small),
  `engine.py` (`Session.node`, `query_literal`, `writeback`),
  `compile.py` (`VarTable`), `relations.py` (links), `euf.py` (a merge
  hook), `euf_adapter.py`; `tests/theory_harness.py`,
  `tests/test_solver_incremental.py` (a new mode); on the
  `refine-monorepo` branch, `tools/refine_scoreboard.py` for the outcome
- **Read this if:** you are deciding whether to build it, or you are the
  agent building it

## 0. Read first

1. `satassume/theory.py`: the DPLL(T) contract every theory obeys
   (`register_atom`, `assert_lit`, `check`, `push_level`, `pop_level`,
   optional `propagate` with eager reasons; `EqualitySharing` for
   combination). Everything below is written against it.
2. `satassume/rules.py`: the 33-predicate vocabulary, the rule strings,
   `RULE_INTERNAL` (79 clauses per node, minimized for unit propagation),
   `unit_propagate`.
3. `satassume/euf.py` and `euf_adapter.py`: congruence closure with
   explanations; note the module docstring's last line, "Out of scope:
   ... substitution of equals into predicates (`Q.prime(x)` from
   `Q.eq(x, y) & Q.prime(y)`)". That sentence is the capability gap this
   plan closes.
4. `satassume/relations.py`: how relation atoms are normalized, guarded
   (LRA only sees `lt` through a `real`-guarded twin variable) and linked
   to the unary vocabulary (`positive(e) -> gt(e, 0)`,
   `gt(e, 0) & real(e) -> positive(e)`, `zero(e) <-> eq(e, 0)`).
5. `satassume/engine.py`: `Session.node` (a node's 33 variables and its
   rule block, `register_block` since round 3), `query_literal`
   (propagation, `implied`, escalation, search), `writeback` (root trail
   to the fact cache), and `compile.py`'s `VarTable`.
6. The round 3 reports for the numbers used here:
   `perf3-A1-propagator-solver.md`, `perf3-A2-propagator-engine.md`,
   `perf3-B2a-lazy-node-atoms.md`, `perf3-B5-profile-after-A2.md`,
   `perf3-B6-memo-subsumption.md`; round 2's `perf2-2.5-failed-assumption-memo.md`.
7. Environment and gates: the "Environment" section of
   `2026-09-25-perf-round-3-plan.md` (local venv, the Pi, `tools/ab.py`,
   `tools/gate2.py`, the per-query log).

## 1. How unary facts work today, and what that costs and cannot do

Every expression node the engine visits gets a block of 33 solver
variables, one per predicate of `rules.PREDICATES` (`VarTable.node_base`;
since round 3's B2a the `P` atoms are created lazily). The rule base is
instantiated per node: until round 3 as 79 clauses (`add_pattern`), now
as a propagator (`register_block`, commit `b9f2151`) that does the same
unit propagation without materializing them. Structural knowledge
(`positive(a*b)` from the signs of `a` and `b`) is separate: template
clauses from `templates/`, emitted per node. Facts fixed at root are
copied to the engine's fact cache by `writeback`, which reads the solver's
root trail and maps each variable back to `(node, predicate)`.

Costs, from the B5 profile of `main` after round 3 (Pi, 3.13 s cold
pass):

| what | share of the pass |
|---|---:|
| the rule-block propagator hook inside `_propagate` | 20.0% |
| rule-block registration | 0.9% |
| variable growth (`_grow`), most of it the 33 variables per node | 3.2% |
| trail writes of rule-implied literals: 621,452 per pass (A1 report) | inside the 20% |
| the collector scanning per-variable structures | part of 3.7 to 4.4% |

And a measurement that says most of that work is never used: B2a found
that only **16.9%** of the 293,700 per-node predicate atoms created per
pass were ever read. The implied literals themselves have not been
counted the same way; section 5 makes that count the deciding number.

What the representation cannot do, in the engine's own words
(`euf.py`): substitute equals into predicates. `Q.eq(x, y) & Q.positive(x)`
does not answer `Q.positive(y)`, because `positive(x)` and `positive(y)`
are unrelated Boolean variables and EUF only knows that `x` and `y` are
one class. The relations layer patches three predicates through link
clauses (`positive`, `negative`, `zero` against `lt`/`eq` with `0`); the
other 30 have no bridge to any theory. Round 2 measured the consequence:
1,130 of 2,664 sessions per pass were built only to fail on a relation
atom no theory interprets (now short-circuited by the 2.5 memo, but every
one of those queries is still `None`), and B6 found 251 queries whose
answer is `None` only because the assumptions contain such a relation.
On the refine scoreboard (monorepo branch), all 59 of satassume's losses
against SymPy's `ask` are relation or matrix predicates.

## 2. The idea

Two layers, buildable and measurable separately.

### 2.1 A lattice-valued theory of unary facts (`FactTheory`)

A theory in the sense of `theory.py` whose atoms are the predicate
literals `P(pred, node)`. Its state is, per term, the set of asserted
predicate literals and their **complete closure** under the rule base:
every predicate literal entailed by the asserted set and `RULES`. The
closure is a function of the asserted set alone, so it is memoized once
per distinct asserted set (a bitset pair over 33 predicates: known-true,
known-false) and every later term with the same asserted set pays a dict
lookup. Two things fall out:

- **The rule block leaves the solver.** No 79 clauses, no propagator
  hook, no 33 variables per node unless something mentions them (see
  2.3). A predicate literal is *written to the solver's trail only when
  the solver has a variable for it*, and variables exist only for
  predicates that a query, an assumption, a template clause or a link
  clause names. The other implied facts live in the theory's closure and
  are read on demand.
- **Closure is exact, not just unit propagation.** `RULE_INTERNAL` is
  minimized so that unit propagation over it equals unit propagation over
  the full rule base; consequences that need case analysis (the non-Horn
  rules `real -> negative | zero | positive`, `extended_real ->
  real | infinite`, `!composite -> !positive | !even | prime`) are found
  today only because CDCL decides every predicate variable and the
  propagator reports conflicts. With a memoized closure the theory can
  afford the exact answer: for a new asserted set S, for each undecided
  predicate p, test S ∧ ¬p and S ∧ p for satisfiability under the 79
  clauses with a 33-variable DPLL (microseconds, and memoized per S), and
  record p, ¬p or undecided. This is stronger than today's propagation
  and removes the need for the solver to case-split on predicates at
  all.

Explanations: when an assertion makes a term's set inconsistent, or when
the theory propagates a literal (2.4), the reason must be a clause valid
under the rules whose other literals are false, per the contract. The
theory computes a minimal-ish unsatisfiable subset of the asserted set
by deletion over the 79 clauses (memoized per S; conflicts are rare, 462
per pass on the stream), and for a propagated literal l the subset of S
that entails l the same way. These are exactly the reasons a rule clause
would have given, so `_analyze` and learnt clauses are unaffected.

### 2.2 EUF carries the sets across equal terms

Key the theory's per-term state by the EUF term id of the node's
expression (the adapter already interns every expression it sees;
`term_of`). When EUF merges two classes, `FactTheory` merges their
asserted sets (union) and recomputes the closure; the explanation of any
consequence that used the merge includes EUF's explanation of the
equality (`euf.explain(a, b)`), so reasons stay valid clauses. On
backtrack the merge is undone with EUF's own undo. This is the
"substitution of equals into predicates" that `euf.py` lists as out of
scope, done where it belongs: a fact set attached to a congruence class
instead of a variable per node.

When no equality atom is present (most sessions), EUF need not be
attached and the theory keys by node; the merge hook is simply never
called. So layer 2.1 stands alone, and 2.2 is an extension that costs
nothing until an equality appears.

### 2.3 Which predicate literals still get solver variables

Only those something outside the rule base refers to:

- the query's own literal (`_literal`),
- assumption literals (`assume_formula`),
- literals in template clauses (`clauses_for`) and in extension node
  facts,
- the three link predicates when a relation session links a term,
- root facts imported from the fact cache (or, better, imported straight
  into the theory: see 2.5).

Everything else is closure-only. On the stream, most nodes exist because
a template mentioned them, and templates mention a handful of predicates
per node (sign, zero, integer, real, ...), so the expected variable
count per node drops from 33 to a few. `VarTable` allocates predicate
variables on first mention instead of a block of 33; the `(node, pred)`
to variable map replaces `node_base` arithmetic (`2*b + pred`).

### 2.4 Protocol mapping

- `register_atom(v, (term, pred, sign))`: called when a predicate
  variable is created (2.3). If the term's closure already decides the
  predicate, the theory returns that as a root propagation on the next
  `propagate` (the contract lets a newly registered atom be asserted
  immediately if fixed at root; here the fixing comes from the theory, so
  it goes through `propagate` with a reason).
- `assert_lit(±v)`: add the literal to the term's asserted set, look up
  or compute the closure; conflict if inconsistent, with the explanation
  as the clause. Eager and complete for one term, like EUF's
  `assert_lit`.
- `propagate()`: for every registered, unassigned predicate variable of
  a term whose closure now decides it, report the literal with its
  reason. Because only mentioned predicates have variables, this is a
  small set: the propagation the templates and links actually consume.
- `check()`: nothing left to find (per-term consistency is eager);
  return `(True, model)` where the model is the closure per term, which
  `Solver.theory_models` keeps and `writeback` can read.
- `push_level`/`pop_level`: a trail of `(term, previous asserted set)`
  entries, undone innermost first; merges from 2.2 are entries too.
- Combination: `EqualitySharing` already produces interface equalities
  between LRA and EUF terms; `FactTheory` piggybacks on EUF's classes, so
  it needs no interface atoms of its own. Facts and LRA meet through the
  existing link clauses on the three sign predicates, which keep their
  variables by 2.3.

### 2.5 Engine changes

- `Session.node`: no `register_block`; create the theory's term entry;
  emit template clauses as today (their predicate literals get variables
  on mention).
- `query_literal`: before `implied`/search, ask the theory directly
  whether the query literal is decided by its term's closure under the
  current assumptions (`FactTheory.decided(term, pred)`); a hit answers
  without touching the solver. This is where the "never read" facts stop
  costing anything: they are never materialized.
- `writeback`: root facts come from the theory's root closures
  (`term -> known-true/known-false` sets) instead of the root trail; the
  fact cache keeps its interface (`cache.put(node, pred, value)`).
  Importing cached facts into a new session becomes `assert` at root
  into the theory, no unit clauses.
- `relations.py`: unchanged in what it links; the three link predicates
  get their variables through 2.3.
- `Solver`: no change to the search; one addition, a way for a theory to
  answer "decided at root" queries without a variable, which is a method
  on the theory object the engine calls, not a solver feature. The
  rule-block propagator (`set_rule_block`/`register_block`) stays in the
  solver, unused by the engine, until this design has replaced it on
  every gate; then it is deleted.

## 3. What becomes answerable (capability)

Each row is a class of query that is `None` on `main` today and definite
under the design; the last column says which layer provides it.

| query | today | with the design | layer |
|---|---|---|---|
| `ask(Q.positive(y), Q.eq(x, y) & Q.positive(x))` | None (EUF has no predicate substitution) | True | 2.2 |
| `ask(Q.positive(f(y)), Q.eq(x, y) & Q.positive(f(x)))` | None | True (congruence merges `f(x)`, `f(y)`) | 2.2 |
| `ask(Q.prime(x), Q.eq(x, 2))` and every other fact of a number | None (numbers are not linked) | True: the value term's closed set merges into `x` | 2.2 |
| `ask(Q.ne(x, y), Q.positive(x) & Q.negative(y))` | None unless LRA sees both | False for `eq`: distinct closed sets cannot merge | 2.2 |
| `ask(Q.integer(y), Q.eq(x, y) & Q.even(x))` and any of the 30 unlinked predicates | None | True | 2.2 |
| `ask(Q.positive(x), Q.real(x) & ~Q.negative(x) & ~Q.zero(x))` | True by propagation | True, cheaper | 2.1 |
| `ask(Q.rational(x), Q.real(x) & ~Q.irrational(x))` | needs a case split today | True from the exact closure | 2.1 |
| assumptions with a relation LRA cannot read (`Q.le(x, pi)`, 1,130 failing sessions per pass in round 2) | None by design | still None unless a theory interprets the relation; but every *unary* consequence of the equalities in such sets is now available, and the session no longer fails just because one atom is uninterpreted (the atom stays a free Boolean, as `relations.py` already does for guarded theories) | 2.2 and a small `relations.py` change |

The last row is the honest limit: this design does not interpret
orderings against transcendental constants; that is LRA's job or a new
theory's. What it does is stop a session from being useless because of
one such atom, and answer everything the equalities in it imply.

In the combined refine backend every `None` is a fallback to SymPy's
`ask` at about 24 ms (issue #7), so each query moved from `None` to
definite is worth roughly 80 engine queries of time on the battery
clock. That is why capability is the first goal.

## 4. Where the speed could come from, and what it costs

### 4.1 Removed outright (if the never-read fraction is high)

- The propagator hook, 20.0% of the pass: it exists to write 621,452
  implied literals to the trail per pass. Under the design an implied
  literal is written only if a variable exists for it (2.3). If, as with
  the `P` atoms, most are never read, most of the 20% goes.
- Rule-block registration 0.9% and the per-node share of `_grow`
  (33 variables per node become a few): about 2 to 3%.
- Collector work over per-variable lists: part of 3.7 to 4.4%.
- Node-visit cost (19.8% for 8,895 nodes): the block part is gone; the
  template part stays.

Ceiling: about 25% of the pass, of which the propagator's 20% is the
part conditional on the never-read fraction.

### 4.2 Added

- One `assert_lit` per asserted predicate literal (assumptions, template
  consequences, query literals, root imports): a set update and a dict
  lookup, about the microsecond any Python theory call costs. The count
  is the number of predicate literals that *reach the solver* under 2.3,
  which is the same never-read fraction from the other side.
- Closure computation on memo misses (a 33-variable DPLL, 66 probes,
  microseconds each, once per distinct asserted set; expect hundreds of
  distinct sets, not thousands).
- Explanation computation on conflicts (462 per pass today).
- The `decided` lookup per query before propagation: one dict access.

### 4.3 The lesson of round 3, applied

The propagator (A1/A2) replaced 79 clauses per node with a hook and got
8.6% against a design estimate of 18 to 21%, because it still computed
and wrote every implied literal at about a microsecond each. This design
is different in exactly one respect: it does not write what nobody
reads. So its speed case rests on one number, the fraction of
rule-implied literals that are ever consumed by a query, a template
clause, a link clause, a theory or the fact cache. If that fraction is
under about 30%, the expected net gain is 10 to 20% of the pass; if it is
above 70%, the gain is a few percent and the design is justified by
capability alone. Section 6 makes it the first measurement.

### 4.4 Interaction with the persistent-solver plan

Independent and compatible. The lattice theory reduces what a session
contains (fewer variables, no rule clauses), which makes every session
cheaper to build and lowers the persistent solver's growth; the
persistent solver removes session construction, which the lattice theory
does not touch. If both are done, the theory's per-term state keyed by
EUF term id is naturally persistent.

## 5. Acceptance rule and gates

Answers may become **more definite**, never contradict, and the set of
`InconsistentAssumptions` errors must be identical, the same rule as the
persistent-solver plan (its section 2). Concretely:

1. `tools/ab.py` and `tools/gate2.py` run with a comparison mode that
   reports contradictions (fail), more-definite answers (counted, listed),
   and unchanged (the rest). Add `--allow-more-definite` to both, or a
   small wrapper; do not weaken the default mode.
2. Every more-definite answer on both distributions is verified against
   SymPy's `ask` and, where `ask` says `None`, against the old
   assumptions (`expr.is_*`) and by hand for a sample of 50. A
   more-definite answer that SymPy contradicts is a bug.
3. Fuzz, in `tests/test_solver_incremental.py` as a new mode: random
   per-node assertions and queries, `FactTheory` against the rule block
   as clauses (the oracle), comparing `implied`, `entails`, `solve`
   results and conflict cores; then with EUF attached, `FactTheory` plus
   congruence against an oracle that encodes predicate transfer as
   explicit clauses (`eq(x, y) -> (P(x) <-> P(y))` for every predicate)
   over the same random problems. 4,000 seeds each. The theory harness
   (`tests/theory_harness.py`) checks the protocol order.
4. The test suite: baseline plus new tests; tests that assert on rule
   clause counts or `stats()["rule_blocks"]` are updated with the
   mechanism they test.
5. Speed: `tools/ab.py --rounds 3` against `main` on the Pi, cold and
   second pass; the per-query log with the same fields so the B5 profile
   split can be rerun.
6. Capability: the refine scoreboard on the monorepo branch before and
   after (losses by category, and the number of SymPy fallbacks in the
   combined backend), once that branch is brought up to `main`.

## 6. Stages, each with a stop condition

### Stage 0: measurements, no code (one day)

Scripts under `agent-reports/scripts/`, report
`2026-09-25-facts-0-measurements.md`.

- **The never-read fraction.** Wrap a replay: tag every trail literal
  written by the rule-block hook; count how many are later read by
  `implied`/`entails` answers, by a template or link clause watch, by a
  theory `assert_lit`, or by `writeback`. Report the fraction read and,
  per node, how many predicates are ever mentioned outside the rule base
  (the variable count 2.3 would allocate).
- **Case-split dependence.** Of the 62 definite answers per pass that
  search produces (searches ending unsat), how many rest on a rule-block
  case split versus template or theory reasoning (the conflict's learnt
  clause tells). The exact closure of 2.1 must recover the former.
- **Distinct asserted sets.** Replay counting, per node, the set of
  predicate literals asserted from outside the rule base; the number of
  distinct sets bounds the closure memo's size and miss count.
- **Capability census.** From the stream and the B6 script: queries whose
  assumptions contain `eq` atoms, and how many of those are `None` today
  with a unary predicate on one side of an equality; from the refine
  scoreboard (monorepo branch): the 59 losses by kind, and which would
  be answered by predicate transfer.
- **Stop if:** the never-read fraction is below about 30% *and* the
  capability census finds fewer than about 20 stream queries and fewer
  than about 10 scoreboard losses that the design would answer. Then the
  design is neither a speed nor a capability lever on the workloads we
  have; report and end.

### Stage 1: `FactTheory` alone, replacing the rule block (two to three days)

`satassume/facts_theory.py` (closure memo with the exact 33-variable
check, explanations, trail, protocol methods); `VarTable` predicate
variables on mention; `Session.node` without `register_block`;
`query_literal`'s `decided` short-cut; `writeback` from the theory's
root closures; the fuzz mode against rules-as-clauses. Gate: answers
identical or more definite on both distributions (more-definite is
expected from the exact closure; count them), fuzz 4,000 seeds, suite,
A/B against `main`. **Stop if** the pass is slower than `main` after a
day of tuning, or the fuzz finds a soundness gap in the explanations that
needs a design change. Land on `main` if at or below baseline time (the
capability layer is the goal; stage 1 must only not cost).

### Stage 2: EUF-backed transfer (two days)

The merge hook in `euf.py` (a callback on `_union` with the two class
representatives and an undo entry on `_undo_union`), `FactTheory` keyed
by EUF term with union of asserted sets on merge and EUF explanations in
reasons, `relations.py` no longer failing a session for one
uninterpreted atom (leave it a free Boolean, as for guarded theories),
the fuzz mode with EUF against the explicit-transfer-clause oracle. Gate:
as stage 1, plus the verified list of more-definite answers. **Stop if**
theory combination produces a contradiction the fuzz can reproduce and
the fix needs interface atoms between `FactTheory` and LRA (then write it
up; that is Nelson-Oppen work for a later round).

### Stage 3: the outcome on refine (one day)

Bring `refine-monorepo` up to `main` (last merged 2026-09-23; expect
conflicts in `tools/` and reports), run `tools/refine_scoreboard.py`
before and after, count the SymPy fallbacks in the combined backend, and
report the battery time. Delete `set_rule_block`/`register_block` from
the solver if no gate still needs them.

## 7. Risks

- **Explanations.** A weak explanation (too many literals) is sound but
  makes learnt clauses weaker; a wrong one (a literal not false under the
  assignment) makes the solver raise. The deletion-based minimal subset
  over 79 clauses is simple; memoize it. The theory harness and the fuzz
  cover the contract.
- **Completeness of the exact closure under templates.** The closure is
  complete for the rule base per term; template clauses and links still
  need the solver, and they get variables on mention. A consequence that
  needs a case split *across* a template clause and a rule (a
  predicate the template mentions, decided one way or the other) is
  found by the solver deciding that predicate's variable, which exists
  because the template mentioned it. Predicates no clause mentions need
  no case split by definition. Stage 0's case-split count checks this
  argument on the stream.
- **Theory combination.** `FactTheory` piggybacks on EUF classes; facts
  meet LRA only through the three link predicates. A consequence that
  needs facts and arithmetic together beyond those links (e.g. `even(x)
  & eq(y, x + 1)` giving `odd(y)`) is out of scope, as it is today.
- **Answer drift is one-directional by design** and must be verified
  against SymPy on every more-definite answer; the acceptance rule and
  the review issue exist for this.
- **Refine's semantics.** Refine handlers were written against the
  current answers; more definite answers can change refine's output.
  The scoreboard and the refine test suites decide whether each change is
  an improvement; expect some handler tests to need updating and say so
  in the stage 3 report.
- **Work estimate.** About 400 lines of theory, 100 of engine and
  `VarTable` changes, 60 of EUF hook, 300 of tests and fuzz; five to
  seven agent-days including the gates, one reviewer per stage.

## 8. Practicalities

- Branch `facts-theory`, not `main`; land per stage after review, with
  the more-definite answers listed in a review issue.
- Subagents per the user's current rule: Opus 5.5 only, including
  reviewers.
- Machines: solver and theory fuzz locally, engine A/B on the Pi, never
  both measuring on one machine; every command under 270 s.
- Reports per stage as `agent-reports/2026-09-25-facts-<stage>-*.md`,
  written as the work happens.
