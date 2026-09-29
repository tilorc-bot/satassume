# Fact-lattice theory: running status

- **Updated:** 2026-09-25, end of stage 1
- **Branch:** `facts-theory`, rebased onto `origin/main` at `f01e905` (stage 0 is on main, see `2026-09-25-facts-landing.md`; code baseline `c552806` plus the `tools/ab.py` fix `e884911`)
  (the plan baseline since the orchestrator's note; stage 0 re-measured
  there, same conclusions), bundle at
  `/work/src/bundles/facts-theory.bundle`
- **Stage:** 1 **stopped on its stop condition** (report
  `2026-09-25-facts-1-fact-theory.md`): FactTheory replacing the rule
  block works (answers identical, suite at baseline) but is +56% against
  `main`, with a per-literal floor above the baseline. Prototype on
  branch `facts-stage1-prototype` (bundle `facts-stage1-prototype.bundle`,
  not for landing). **Waiting for the user.**

## Done

- Stage 0 measurements (scripts `agent-reports/scripts/facts_*.py`):
  - rule block: 550,530 implied literals per pass; 52% land on
    variables nothing outside the rule block mentions (never mentioned);
    only 15% are ever read (never-read about 85%);
  - 19.1 of the 33 predicates per node are mentioned by templates etc.
    (the plan expected "a few");
  - **theory tax: attaching a do-nothing theory to every session costs
    +14.1% of the pass** (+3 to 5% if held levels are kept with theories),
    and a theory-propagated literal costs 2.2 to 2.8x a
    rule-block implication. Stage 1 as specified projected +4% to +19% (measured: +56%)
    (corrected in review);
  - 8,128 distinct asserted sets per pass (corrected in review); the rule
    base has 48 models, so exact closure is a table lookup;
  - 0 of the 62 search answers rest on a case split inside the rule base;
  - capability: predicate transfer across equalities answers 15 stream
    queries (15 distinct, all correct) and **0 of the 59 refine
    scoreboard losses** (current engine already fixes 8; 45 are matrix);
    treating uninterpreted relations as free Booleans answers 498 but
    turns 36 None answers into ValueError (inconsistent assumptions),
    which the plan's acceptance rule forbids, and costs about +35% time.
- `tools/ab.py` / `tools/gate2.py`: `--allow-more-definite` (commit
  `60ddd08` (on main)).
- Stage 1: held levels with theories (`e2aa724` + review fix `3fc0244`,
  -4.2% to -4.7%, kept); the FactTheory prototype (+56%, stopped).
- Stage 0 report corrected as the landing side asked (never-read about
  85% vs never-mentioned 52%; projection +4% to +19%; transfer 15
  distinct; free Booleans 407 distinct, 36 errors from 3 sets, SymPy
  raises on 24; scoreboard regressions 1).
- Git identity was not configured in this clone despite the brief; set
  repo-local to `tilorc-bot <tilorc-bot@users.noreply.github.com>`, the
  author of every earlier commit.

## Needs the user

1. **Land `e2aa724` and `3fc0244`** on `facts-theory` (solver: held
   assumption levels with theories attached, -4.2% to -4.7% on the
   stream, answers identical on both gates; reviewed by Opus: land with
   one fix, which is `3fc0244`, plus a new fuzz over the real LRA/EUF
   theories).
2. Whether the fact-lattice idea continues at all. My recommendation: end
   it here. Alternatives: stage 0's option 4 (closure inside the solver's
   propagation loop; about 5% realistic, a solver change the plan did not
   scope).
3. Separately, if anyone should build it: uninterpreted relations as free
   Booleans (498 stream answers, 407 distinct, 388 agreeing with SymPy and
   none contradicting; 6 scoreboard tests) turns 36 None answers into
   ValueError and costs about +35% as a bare change. The 36 come from 3
   plainly inconsistent assumption sets, and SymPy's own `ask` raises
   ValueError on 24 of them.

## Next

Nothing running; waiting for the decisions above.
