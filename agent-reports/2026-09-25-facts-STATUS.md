# Fact-lattice theory: running status

- **Updated:** 2026-09-25, end of stage 0 (measurements)
- **Branch:** `facts-theory`, rebased onto `origin/main` at `6b935d7` (code baseline `c552806`; the later commits only archive reports)
  (the plan baseline since the orchestrator's note; stage 0 re-measured
  there, same conclusions), bundle at
  `/work/src/bundles/facts-theory.bundle`
- **Stage:** 0 done and reviewed (report
  `2026-09-25-facts-0-measurements.md`). The stop condition is not met on
  either half (see the report's Decision, corrected after review), so
  **stage 1 is next**.

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
  `b6cc969` after the rebase).
- Git identity was not configured in this clone despite the brief; set
  repo-local to `tilorc-bot <tilorc-bot@users.noreply.github.com>`, the
  author of every earlier commit.

## Needs the user (before stage 2, not blocking stage 1)

Uninterpreted relations as free Booleans (the plan's stage 2
`relations.py` change) answer 498 stream queries and fix 6 scoreboard
losses, but turn 36 None answers into ValueError (inconsistent
assumptions) — the plan's acceptance rule forbids any change to that
set — and cost about +35% replay time as a bare change. Allow the 36
(SymPy's semantics), or keep free Booleans out?

## Next

Stage 1 (FactTheory replacing the rule block), starting with the levers
stage 0 found: held assumption levels with theories attached (small
solver change), and exact closure as a table over the rule base's 48
models.
