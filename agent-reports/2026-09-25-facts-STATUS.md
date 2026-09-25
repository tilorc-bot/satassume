# Fact-lattice theory: running status

- **Updated:** 2026-09-25, end of stage 0 (measurements)
- **Branch:** `facts-theory` (from `main` at `e43b318`), bundle at
  `/work/src/bundles/facts-theory.bundle`
- **Stage:** 0 done, report `2026-09-25-facts-0-measurements.md`.
  **Stopped and waiting for a user decision** before stage 1 (below).

## Done

- Stage 0 measurements (scripts `agent-reports/scripts/facts_*.py`):
  - rule block: 550,530 implied literals per pass; 52% land on
    variables nothing outside the rule block mentions (the plan's
    never-read fraction; above its 30% stop line); 15% are ever read;
  - 19.1 of the 33 predicates per node are mentioned by templates etc.
    (the plan expected "a few");
  - **theory tax: attaching a do-nothing theory to every session costs
    +13.9% of the pass**, and a theory-propagated literal costs 3.0x a
    rule-block implication. Stage 1 as specified projects to +25% to
    +40%, so its stop condition would trigger;
  - 2,857 distinct asserted sets per pass (closure memo size);
  - 0 of the 62 search answers rest on a case split inside the rule base;
  - capability: predicate transfer across equalities answers 15 stream
    queries (12 distinct, all correct) and **0 of the 59 refine
    scoreboard losses** (current engine already fixes 8; 45 are matrix);
    treating uninterpreted relations as free Booleans answers 498 but
    turns 36 None answers into ValueError (inconsistent assumptions),
    which the plan's acceptance rule forbids, and costs about +35% time.
- `tools/ab.py` / `tools/gate2.py`: `--allow-more-definite` (commit
  `c804733`).
- Git identity was not configured in this clone despite the brief; set
  repo-local to `tilorc-bot <tilorc-bot@users.noreply.github.com>`, the
  author of every earlier commit.

## Needs the user

The stop condition's capability half is met (15 < 20 stream, 0 < 10
scoreboard); the speed half is met in substance (the theory mechanism
costs more than the literals it avoids) but not in letter (52% > 30%).
Pick one (my recommendation first; details in the stage 0 report,
"Decision"):

1. **End the fact-lattice project here.**
2. Separately, uninterpreted relations as free Booleans (498 stream
   answers, 6 scoreboard tests), if you accept 36 None -> ValueError
   changes; needs cost work first (about +35% time).
3. Transfer only in sessions that already have EUF (15 stream, 0 tests).
4. Stage 1 as a solver-internal closure propagator (plan excluded solver
   changes; about 5% realistic).
5. Stage 1 as planned (expected to hit its stop condition).

## Next

Nothing running. On a decision, start the chosen stage on
`facts-theory`.
