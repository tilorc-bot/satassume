# Fact-lattice theory: running status

- **Updated:** 2026-09-25, end of stage 1
- **Branch:** `facts-theory`, rebased onto `origin/main` at `6b935d7` (code baseline `c552806`; the later commits only archive reports)
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
    variables nothing outside the rule block mentions (the plan's
    never-read fraction; above its 30% stop line); 15% are ever read;
  - 19.1 of the 33 predicates per node are mentioned by templates etc.
    (the plan expected "a few");
  - **theory tax: attaching a do-nothing theory to every session costs
    +14.1% of the pass** (+3 to 5% if held levels are kept with theories),
    and a theory-propagated literal costs 2.2 to 2.8x a
    rule-block implication. Stage 1 as specified projects to +4% to +33%
    (corrected in review);
  - 8,128 distinct asserted sets per pass (corrected in review); the rule
    base has 48 models, so exact closure is a table lookup;
  - 0 of the 62 search answers rest on a case split inside the rule base;
  - capability: predicate transfer across equalities answers 15 stream
    queries (12 distinct, all correct) and **0 of the 59 refine
    scoreboard losses** (current engine already fixes 8; 45 are matrix);
    treating uninterpreted relations as free Booleans answers 498 but
    turns 36 None answers into ValueError (inconsistent assumptions),
    which the plan's acceptance rule forbids, and costs about +35% time.
- `tools/ab.py` / `tools/gate2.py`: `--allow-more-definite` (commit
  `60ddd08`).
- Stage 1: held levels with theories (`34f06e5`, -4.7%, kept); the
  FactTheory prototype (+56%, stopped).
- Git identity was not configured in this clone despite the brief; set
  repo-local to `tilorc-bot <tilorc-bot@users.noreply.github.com>`, the
  author of every earlier commit.

## Needs the user

1. **Review and land `34f06e5`** on `facts-theory` (solver: held
   assumption levels with theories attached, -4.7% on the stream, answers
   identical on both gates, fuzz 4,000 theory seeds).
2. Whether the fact-lattice idea continues at all. My recommendation: end
   it here. Alternatives: stage 0's option 4 (closure inside the solver's
   propagation loop; about 5% realistic, a solver change the plan did not
   scope).
3. Separately, if anyone should build it: uninterpreted relations as free
   Booleans (498 stream answers, 6 scoreboard tests) turns 36 None answers
   into ValueError and costs about +35% as a bare change.

## Next

Nothing running; waiting for the decisions above.
