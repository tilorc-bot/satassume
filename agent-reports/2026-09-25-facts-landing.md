# Agent report: fact-lattice theory, landing side (reviews and what landed)

- **Date:** 2026-09-25
- **Status:** stage 0 reviewed locally and landed with one tool fix; stages
  1 and later not yet delivered. Updated per stage.
- **Scope:** the `facts-theory` branch delivered as bundles from the Pi
  (`/work/src/bundles/facts-theory.bundle`), reviewed and landed from this
  machine. The Pi session writes the stage reports
  (`2026-09-25-facts-<stage>-*.md`, `2026-09-25-facts-STATUS.md`); this
  file records the landing side's review of each stage and what it
  changed.
- **Read this if:** you want to know which fact-lattice stages are on
  `main`, what the local reviews found, and which report numbers they
  corrected

## Stage 0 (measurements), bundle of 2026-09-25 20:52

**Delivered:** 5 commits on `6b935d7`: the stage 0 report and status file,
measurement scripts under `agent-reports/scripts/facts_*`, and
`--allow-more-definite` for `tools/ab.py` and `tools/gate2.py`. No engine
code. Decision in the report: the stop condition is not met, stage 1 next.

**Local review** (Opus): land with fixes.

- **Strict mode unchanged in both tools.** Every difference still fails.
  `ab.py` now records a `ValueError` as the answer `"error"` (still a
  failure) instead of crashing the replay.
- **`gate2.py --allow-more-definite` correct** on doctored frozen files:
  None to True passes; changes to or from `error:ValueError`, True to
  None, True to False fail with and without the flag.
- **`ab.py --allow-more-definite` had a real gap**, fixed here in
  `tools/ab.py` (commit `e884911`): a query recorded None that ref
  answered True and cand False passed, because each side was checked
  only against the recording; an answer that changed between rounds
  passed, because only each side's first run was kept; a stale
  `--more-definite-out` file survived a run with no more-definite
  answers. A second Opus review of the fix found three more (cand
  dropping ref's more-definite answer to None passed; answers 1/0 counted
  as True/False; a crashed run left a stale file); fixed in the same
  commit and confirmed by that reviewer on doctored checkouts.
- **The Decision's reading of the stop condition is correct.** The
  never-read half alone keeps the plan going.
- **Numbers the report states wrongly** (conclusion unchanged; the Pi
  session is asked to correct its report):
  - "never-read fraction 52%" is the *never-mentioned* share (literals
    stage 1 would not write). In the plan's sense (not read by anything)
    it is about 85% (100% minus the 14.9% read). Both are above the 30%
    line.
  - The stage 1 projection's upper bound mixes methods: the row's own
    method (2.2x to 2.8x times 1.07 µs times 263,566) gives +0.62 to
    +0.79 s, not +1.21 s. The net is **+4% to +19%**, not +4% to +33%.
  - Transfer (section 6): 15 distinct more-definite queries, not 12;
    SymPy's `ask` gives the same False on 6, None on 7, ValueError on 1,
    and times out on 1.
  - Free Booleans: the 498 more-definite answers are 407 distinct (388
    agree with SymPy, 19 SymPy None, 0 contradictions); with the 36 new
    errors, 443 distinct changed queries, not 445.
  - Scoreboard table: the regressions column of the oracle rows should
    read 1, not 0 (the Kronecker test with a stale expectation is there
    too), or be labelled as relative to the current engine.
- **The open question for the user is stated accurately but without the
  context that matters:** the 36 queries that become
  `InconsistentAssumptions` come from 3 plainly inconsistent assumption
  sets (`x` negative and positive, twice; `x` positive and zero), and
  SymPy's own `ask` raises `ValueError` on 24 of the 36. It answers the
  other 12 without checking the assumptions.
- **Gates re-run locally** on the branch: solver fuzz, 4,000 seeds in each
  mode, all passed (plain 0 to 3999; rule block prop/mixed 0 to 3999; rule
  block with theory 0 to 3999; chunks of 2,000, 45 to 58 s each). Suite:
  `2 failed, 1697 passed, 1 skipped, 4 xfailed, 1 xpassed` (the known
  `test_shared_facts` pair).

**More-definite answers:** none. Stage 0 changes no engine answer.

**Landed:** the five stage 0 commits and the `ab.py` fix, by fast-forward.
Issue: "fact-lattice theory: landed stages and risks".
