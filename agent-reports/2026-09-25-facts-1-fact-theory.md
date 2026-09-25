# Agent report: fact-lattice theory, stage 1, FactTheory replacing the rule block

- **Date:** 2026-09-25
- **Status:** **stopped on the stage's stop condition**: FactTheory as a
  DPLL(T) theory replacing the rule block works (suite at baseline, answers
  identical on both gates) but the cold pass is **+56% against `main`**
  after tuning, and the cost is per literal in the theory interface, not
  in anything tuning reaches. The prototype is kept on branch
  `facts-stage1-prototype` (not for landing). One solver change made for
  it stands on its own and is on `facts-theory` for landing: **held
  assumption levels with theories attached, -4.7%** (commit `34f06e5`).
- **Scope:** `satassume/solver.py` (held levels with theories; kept),
  `tests/theory_harness.py`, `tests/test_verify_integration.py` (kept);
  on the prototype branch also `satassume/facts_theory.py` (new),
  `engine.py`, `compile.py`, more of `solver.py`, `theory.py`.
- **Read this if:** you decide what happens after stage 1, review commit
  `34f06e5`, or want to revive the design in another form

## Measurement

Pi, `main` at `6b935d7` (code as `c552806`), SymPy pin `ddbb536d7e`.

### The kept change: held levels with theories (`34f06e5`)

Stage 0 found that most of the +14% any attached theory costs is one
policy: `Solver._assume` kept held assumption levels only without
theories, so every session with a relation atom re-propagated its
assumptions on every query. Allowing them (and propagating a clause
attached at the top held level through `_tpropagate`, so theories hear
of it) gives:

    ab.py --rounds 3 (against main):  ref 2.884s  cand 2.749s  change -4.7% (faster); answers match
    gate2:                            2863 records (2588 in scope); changed 0; answers match
    theory tax (stage 0 script, noop theory on every session): +14.1% before, +4.9% after (2.758 / 2.892 s)

### The prototype: FactTheory replacing the rule block

As the plan specifies (section 2.1, 2.3, 2.5):

- `satassume/facts_theory.py`: per term (a node, keyed by its base
  variable) the told, asserted (told and not already implied), background
  and closure masks over the 33 predicates; the **exact closure** as a
  table over the rule base's 48 models (4.6 µs per memo miss, 0.4 µs per
  hit; checked against the stage 0 DPLL oracle on 5,211 sets, 0
  mismatches); conflict cores and propagation reasons minimal by deletion,
  memoized; eager per-term consistency (complete, so `check` returns None);
  root closures for writeback.
- engine: no `register_block`; a node's 33 variables are still allocated
  as a block (the precompiled template patterns address them by offset)
  but as **non-decision variables unknown to the theory** until a clause
  or the query mentions them (`Session._mention`: bulk registration and
  decision flag); cached facts imported as background facts of the theory
  (no unit clauses); writeback from the theory's root closures.
- solver additions: non-decision variables (`set_decision`, skipped by
  `_pick_branch`), `register_atoms` (bulk), `theory_changed`, **transient
  theory reasons** (a theory that re-derives its implications from its
  own state may have its reasons kept only as reasons: no learnt clause,
  no watches, no `_stamp` bump).

Gates on the prototype: suite `2 failed (known pair), 1697 passed, 1
skipped, 4 xfailed, 1 xpassed`; stream: all 13,877 answers identical to
the recording (**no more-definite answer**: the exact closure's extra
strength never reaches a query of the stream, as stage 0's case-split
count predicted); gate2 with `--allow-more-definite`: 0 more definite,
answers match. The plan's FactTheory fuzz (4,000 seeds against the rule
block as clauses) was not built: the stage stopped first.

**Speed:**

    ab.py --rounds 3 --allow-more-definite (prototype against main):
      ref 2.937s  cand 4.589s  change +56.3% (slower); answers match

| version of the prototype (cold pass, stream) | seconds |
|---|---:|
| first working version (dict state, closure recomputed, learnt reasons) | 5.73 |
| list state, closure cached per term, told-and-implied fast path | 4.53 |
| + transient reasons (implications re-derived by the theory) | 4.57 to 4.72 |
| + one-pass implication for transient theories | 4.57 to 4.65 |
| `facts-theory` (rule block, held levels with theories) | 2.75 |
| `main` | 2.88 to 2.94 |

What the solver does, summed over the pass's 1,597 sessions:

| | `main` | prototype |
|---|---:|---:|
| decisions | 65,817 | 40,771 |
| propagations (trail literals processed) | 802,942 | 442,290 |
| theory propagations (FactTheory) | | 133,728 (260,003 with transient reasons) |
| `assert_lit` calls on FactTheory | | about 403,000 |
| registered predicate variables | | about 170,000 (19.1 per node, as stage 0 measured) |

The solver does much less work (fewer decisions, 45% fewer propagated
literals), but every predicate literal now crosses the theory interface:
reported by `_theory_sync` (a lookup per trail entry), told through
`assert_lit`, and every implication comes back through `propagate` as an
external literal with a reason list that `_theory_imply` converts and
checks, then is told back. Sampling split of the prototype's pass
(`agent-reports/2026-09-perf-rounds/scripts/profile_split.py`, 1,177
samples): **theories 44.9%** (FactTheory, the solver's sync/implication
code, LRA and EUF; LRA/EUF were 8.7% on `main`), search internals 7.3%,
watch lists 5.7%, `_mention` 4.8%, collector 4.3%. By phase, 17% of the
pass is theory work inside searches of reused sessions.

**Why tuning cannot reach the baseline.** The rule block costs `main`
about 0.55 s (B5's 20% hook share); it writes 550,530 literals at about
1 µs each inside `_propagate`'s own loop. The prototype replaces that with
about 660,000 theory events (400,000 asserts, 260,000 propagations), of
which FactTheory's and the solver's share is about 1.5 to 1.9 s. Break
even needs about 0.6 µs per event including its trail write; a Python
method call across the interface plus the bookkeeping on both sides is
several times that; after the first restructuring (5.73 to 4.53 s) the
later tuning steps moved the pass by 0 to 3%, against a gap of 65%. The remaining levers are outside stage 1 as specified:
not writing implied literals at all until something reads them (a lazy
value protocol between solver and theory), or moving the closure into the
solver's own propagation loop (option 4 of stage 0: per-block masks,
table closure, int reasons, writes only to mentioned variables), which
drops the theory interface the plan's stage 2 builds on.

## Change

On `facts-theory` (for landing): `34f06e5` (held levels with theories,
with the protocol checker and one test updated to the invariant "every
theory is at the solver's level"), `facts_closure.py` oracle fix, this
report, STATUS. On `facts-stage1-prototype` (not for landing): the
prototype, one commit on top.

## Gates

- `34f06e5`: incremental solver fuzz, theory mode seeds 0 to 3,999 and
  plain mode 0 to 2,999: ok; suite `2 failed (known pair), 1697 passed, 1
  skipped, 4 xfailed, 1 xpassed`; `ab.py --rounds 3` -4.7%, answers match;
  gate2 answers match.
- Prototype: as above (answers identical, +56.3%).

## Decision

Stage 1 stops on its own condition ("slower than `main` after a day of
tuning"): at +56% with a per-literal floor above the baseline, more
tuning of this design is not worth the day. Stage 2 (EUF-backed transfer)
was specified on top of stage 1's FactTheory, and stage 0 found it worth
15 stream queries and no scoreboard test on its own, so it is not started.

For the user:

1. **Land `34f06e5`** (held levels with theories, -4.7%), after review.
2. Choose whether anything of the fact-lattice idea continues:
   - end it here (my recommendation: the capability it adds by itself is
     small, and the speed lever needs a different mechanism);
   - or option 4 of stage 0 (closure inside the solver's propagation
     loop, writes only to mentioned variables; ceiling about 10%,
     realistic about 5%; a solver change the plan did not scope);
   - separately, the free-Boolean treatment of uninterpreted relations
     (498 stream answers, 6 scoreboard tests) needs your decision on the
     36 inconsistent-assumption changes and its cost (+35%) before anyone
     builds it.

## Risks for review

- `34f06e5` changes when theories are popped: they now stay at held
  levels between public calls. Any theory whose state is read between
  calls must read it knowing that (the engine reads none; tests that
  assumed level 0 were updated). Held levels are dropped by every path
  that changes the root or registers an atom; a theory whose
  `propagate` depends on something other than its asserted literals and
  registered atoms could make the held trail stale (LRA and EUF do not).
- The prototype's non-decision variables change the meaning of a model
  (non-decision variables are None) and of `check` ("every decision
  variable assigned"); both are on the prototype branch only.
