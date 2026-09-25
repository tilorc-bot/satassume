# Agent report: fact-lattice theory, landing side (reviews and what landed)

- **Date:** 2026-09-25
- **Status:** stage 0 landed with one tool fix; stage 1 stopped on its
  stop condition (+56%), its two solver commits landed; stage 2 (facts
  shared between equal terms, on the rule block) and a stage 1 retry
  (lazy rule writes inside the solver loop) in progress. Updated per stage.
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

## Stage 1 (FactTheory replacing the rule block), bundle of 2026-09-25 21:44

**Delivered:** the stage 1 report `2026-09-25-facts-1-fact-theory.md`
(stopped: the prototype is +56% against `main` with answers identical;
every predicate literal crossing the Python theory interface costs more
than the rule block's in-loop propagation), the stage 0 corrections the
landing side asked for, and two solver commits: `e2aa724` (held
assumption levels kept with theories attached, -4.2% to -4.7% on the Pi,
the theory tax from +14.1% to +4.9%) and `3fc0244` (a newly registered
theory atom is asked about at root; fixes an older gap where `implied`
was weaker than a fresh solver's in about 5% of real-theory fuzz seeds),
with a new real-theory fuzz (`tests/real_theory_fuzz.py`). The prototype
stays on local branch `facts-stage1-prototype`, not landed.

**Local review** (Opus): land, no defect found.

- Theory levels stay in step with the solver: every path that changes the
  root or needs it backtracks to root (and pops theories) first; a clause
  unit at the top held level goes through `_tpropagate`; held levels
  survive a search only if still on the trail and no learnt clause was
  deleted; stored models are reused only under the same theories and
  registration count.
- `_tpending` is set after `register_atom` backtracks to root and
  consumed at root before any assumption level opens; no double
  assertion.
- Extra probe, LRA in lazy mode, seeds 0 to 3,999: the branch has 1 weaker
  `implied` (no assumptions involved), `main` 849 plus 401: strictly
  better.
- Minor, not a defect: a theory conflict of root literals inside the
  unit-at-held-level path lets `add_clause` return True while the solver
  is already UNSAT; the next call answers correctly.
- Gates re-run locally: solver fuzz 4,000 seeds in plain, block and block
  with theory; real-theory fuzz 4,000 seeds each for lra, euf and both,
  0 mismatches, 0 weaker `implied`; suite `2 failed, 1701 passed, 1
  skipped, 4 xfailed, 1 xpassed` (the known pair); `ab.py` answers match;
  gate2 0 changed.

**More-definite answers:** none (answers identical on both gates).

**Landed:** `e2aa724`, `67ad66f`, `e1bbdba`, `3fc0244`, `db8e7d8`, by
fast-forward. The Pi session was ended at the user's request after this
stage; the rest of the plan continues with local subagents.

## Stage 2 (facts shared between equal terms), local subagents

Built by an Opus subagent on the current rule-block representation (not on
stage 1's FactTheory, which stays unlanded), after the user asked for the
rest of the plan and said sharing facts between equal expressions matters
even if slower, while equalities LRA derives from inequalities need not
reach EUF. Report: `2026-09-25-facts-2-transfer.md`.

**Design:** `satassume/transfer.py` (`TransferTheory`, atoms = node
predicate variables) and a merge hook in `euf.py`: when EUF puts two terms
in one class, every predicate value is copied across with reason = the
premise literal plus EUF's explanation of the equality. EUF is engaged once
per session at the first user or extension equality atom; then every node
is interned into EUF and numbers in equalities are visited as nodes (so
`x = 2` gives `x` every fact of 2). Sessions without an equality are
unchanged apart from one attribute test. `Engine(transfer=False)` turns it
off. `Engine(uninterpreted="free")` (uninterpreted relations as free
Booleans) is built, **off by default**, pending the user's decision (with
it on: 513 more definite, 36 new ValueErrors on the stream).

**Local review** (Opus) of `9b800bb`: land, no failing input.

- Every propagated literal and conflict checked on the spot (predicate,
  signs, witness asserted, explanation literals asserted EUF equalities
  whose congruence closure implies the two terms equal) over 4,750 seeds
  with numbers, `oo`, `zoo`, `pi`, `I`, floats, applications: none invalid.
- Equality semantics hold for every predicate: `x = 2 & x = 3`,
  `x = 1/2 & integer(x)`, `x = oo & x = -oo` raise; floats never contradict
  their equal rational; `nan` nodes skipped; binders opaque to congruence.
  `ask(Q.eq(x, A))` for non-commutative `A` is now False (SymPy None),
  sound since complex implies commutative.
- The fuzz case where transfer turned a ValueError into a definite answer
  (seed 750) is not a regression: `main` shows the same class (an answer
  under assumptions inconsistent only by search depends on whether an
  earlier query searched); the gates' ValueError sets are identical.
- Gates: transfer fuzz (euf seeds 4200 to 10199, lra 4000 to 6499), solver
  fuzz 2,000 per mode, real-theory fuzz 2,000, suite (known pair, plus a
  timing smoke test that fails on `main` too under load), `ab.py` answers
  match with 15 more definite, gate2 0 changed with 1 more definite.

**More-definite answers** (all checked against SymPy at the pin and by
hand; none contradicted):

| stream # | query | assumptions | now | SymPy |
|---|---|---|---|---|
| 4395 | `zero(x)` | `eq(x, pi/2)` | False | None |
| 4396, 4398 | `extended_real(x)`, `real(x)` | `eq(x, pi/2)` | True | None |
| 4400, 4402 | `extended_real(x)`, `real(x)` | `eq(x, 2)` | True | None |
| 4401 | `zero(sin(x))` | `eq(x, 2)` | False | None |
| 12043, 12102 and 4 more | `eq(n, 1)`, `eq(n - 1, 1)`, ... | `~integer(n)` | False | False (same) |
| 12154, 12157 | `eq(n, k)`, `eq(k, n - 1)` | `integer(n) & nonnegative(n) & gt(k, n)` | False | None |
| 12178 | `eq(n, k)` | `integer(n) & negative(n) & ~integer(k)` | False | raises (assumptions consistent: `n = -1, k = 1/2`) |
| gate2 | `prime(x)` | `prime(y) & eq(x, y)` | True | None |

(15 stream answers, 15 distinct; the full list with SymPy's answers is in
the stage 2 report.)

**Speed** (Pi, landing side, `ab.py --rounds 3` against `main` `7068e57`):
ref 2.752 s, cand 3.084 s, **+12.1%**. Being profiled and cut by the
implementer as follow-up commits (to be reviewed as a delta).

**Landed:** `d63d38d`..`9b800bb`, cherry-picked onto `main` (code
identical).
