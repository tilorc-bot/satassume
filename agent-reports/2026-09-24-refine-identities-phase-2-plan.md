# Plan: refine as identities and rule tables — phase 2

- **Date:** 2026-09-24
- **Status:** plan, not started. Written at the end of phase 1 for a fresh
  session that has none of phase 1's conversation; everything needed to
  start is in this file or linked from it.
- **Read this if:** you are running phase 2, or coordinating agents on
  `satrefine/handlers_identities/`.
- **Read first:** `agent-reports/2026-09-24-refine-identities-phase-1-results.md`
  (what exists and how well it works), then this file. Before spawning any
  agent, read `agent-reports/2026-09-24-read-before-running-agents-how-work-gets-lost.md`
  on `main` (not on this branch).
- **TL;DR:** phase 1 rewrote all nine refine handler families of
  `handlers_v3` as tables with 0 wrong answers on a 1,736-case battery.
  Phase 2 does five things, in order: fix a satassume defect on `main` that
  corrupts long test runs, then bring `main` into this branch and
  re-baseline; move a relation-condition decider into the engine and merge
  the Piecewise experiment; replace plain rules with definitions where
  definitions exist; derive the base layer and families in dependency order
  to a fixpoint (stages 0 to 5); close two prover gaps and add matrix
  fuzzing. The measure throughout is fewer hand-stated rows and less
  function-specific Python at unchanged coverage and soundness.

## 1. Background in one page

SymPy's `refine(expr, assumptions)` rewrites an expression into a form
valid under assumptions. Its handlers are procedures. This project writes
them as data:

- **Identity rows** `(lhs, rhs, domain)` hold everywhere in the domain and
  carry the case analysis explicitly. Example: `log(exp(z)) = z + 2*pi*I*floor(1/2 - im(z)/(2*pi))`.
  The engine substitutes, refines the right side under the assumptions, and
  fires only if the bookkeeping (`floor`, `im`, `arg`) collapsed and a
  rewrite ordering strictly decreases.
- **Rule rows** `(lhs, rhs, hypothesis[, unless])` fire when the hypothesis
  is provable through `ask` (and `unless` is not).
- **Exponential forms** `(L, W, domain)` say `L == exp(W)`, for example
  `b**e = exp(e*log(b))`; `derive()` composes them with `f(exp(z))` facts,
  so `log`'s two facts yield the rows for `log(b**e)` and `log(p*r)`.
- **Generation:** `_specialize.py` runs identity rows under a catalog of
  per-variable assumption profiles, keeps profiles where the bookkeeping
  collapsed, verifies each resulting conditional rule numerically at a
  sample and at edge points (0, 1, -1, I, -I, branch-cut points), and
  writes `generated/<family>.py`. The dispatcher uses a generated table as
  a fast path and falls back to the live rows.

The reference implementation is `satrefine/handlers_v3/` (on branch
`refine-monorepo`, and on this branch): 9 families, 56 keys, 3,117 lines.

## 2. Where things stand

### Code and numbers

Branch `refine-identities` (GitHub `tilorc-bot/satassume`), based on
`refine-monorepo`. Package `satrefine/handlers_identities/`.

| | |
| --- | --- |
| Battery (1,736 cases recorded from the v3 suite) | 1,030 same as v3, 43 other correct form, 13 miss, 634 unchanged as required, 16 extra, 0 wrong, 0 crash |
| Family code | 483 code lines, 203 rows (v3: 1,595 code lines) |
| Shared engine | 1,132 code lines (v3's shared helper: 30) |
| Generated rules | 60, for complex_parts, power_exp_log, inverse |
| Still procedural | interval reasoning for `floor`/`ceiling`; `Piecewise` refinement (both in `_simple.py`) |

Per family rows: complex_parts 3 facts, 3 exp forms, 41 rules (26 of them
the base layer: `re`, `im`, `arg`, `Abs` under sign facts and of `exp`,
`log`, sums, products, conjugates); power_exp_log 4 facts, 3 exp forms, 18
rules; inverse 11 facts, 2 rules; trig 13 rules; hyperbolic 12 rules;
integer_funcs 17; combinatorial 16; minmax_deltas 13; matrices 30.

### Branches

| Branch | State |
| --- | --- |
| `refine-identities` | integration branch; everything below except `ri/piecewise` is merged into it |
| `ri/check`, `ri/branchcut`, `ri/trim` | fully merged; delete (remote and local, and their worktrees under `.claude/worktrees/`) once you have confirmed with `git rev-list --count origin/refine-identities..origin/<b>` = 0 |
| `ri/piecewise` | **unmerged experiment** (head `e31c769`, based on an older `refine-identities`): minmax_deltas as Piecewise definitions. See step 2 |
| `main` | 35 commits not in `refine-identities` (satassume relation work: LRA and EUF theories wired into `ask`, tests, fuzzers, reports). See step 1 |
| `refine-monorepo` | the v3 baseline; do not modify |

### Open defects (needs tests under `tests/refine_identities/needs/`)

- `test_checker_ask_poisons_plain_symbols.py`: **satassume on `main`.** SymPy
  caches `(0**n).is_finite` as True for a plain `n` (wrong: `0**-1` is
  `zoo`). satassume reads a node's cached facts as unconditional,
  declares `Q.negative(n) & Q.nonnegative(x)` inconsistent, and writes a
  derived fact into `n._assumptions`, which is the fact base shared by
  every symbol created without assumptions. After one such `ask`,
  `Symbol('fresh').is_negative` is False. Reproduced on `main` at `07e0bd5`
  with `satassume.sympy_api.ask` directly. Relevant code: `satassume/engine.py`
  (the object cache that reads `_assumptions`, and the writeback). Effect:
  any tool running many cases in one process (scoreboard, fuzz,
  differential) can report wrong results after the first corrupting case.
- `test_checker_abs_of_imaginary_is_zero.py`: SymPy's `ask` says `Abs(x)`
  is zero for imaginary `x`; the combined backend passes it through when
  satassume has no answer. Gives `refine(log(exp(I*Abs(x))), Q.imaginary(x)) = 0`.
- `test_checker_atan2_power_firing_cap.py`: `refine(atan2(y, n**y + 1), Q.negative(y) & Q.nonpositive(n))`
  raises `RefineLoopError` (each `Piecewise` branch redoes `Pow` and
  sign-split work until the 500-firing cap). A crash, not a wrong answer.
- (on `ri/piecewise`) `test_piecewise_conditions.py`: the engine should
  decide relation conditions from signs and relations, with the guard at
  infinity, and the case split should decline instead of crashing on an
  undecided `Piecewise`.

### Decisions already made (do not reopen without the user)

- `log(1/x) -> -log(x)` fires under `Q.extended_positive(x)`, which is wrong
  only at `x = oo` in SymPy's arithmetic. The branch-cut author chose this
  deliberately and documented it, and the checker found the same infinity
  class in a few other rows (phase 1 report, section 4). The user's
  position: agents make their own design decisions; the coordinator does
  not micromanage them.
- Trig and hyperbolic ended phase 1 as plain rule rows, not derived from
  exponential forms. That is a target for stage 4 below, not a defect.

## 3. Environment

- Repository checkout: `/home/tilo/fable-rewrite`. **Do not use the main
  checkout for this work**; it is on branch `relation-speed`, owned by other
  work. Use worktrees under `/home/tilo/fable-rewrite/.claude/worktrees/`
  (the integration worktree is `.claude/worktrees/refine-identities`).
- GitHub: `gh` is logged in as `tilorc-bot`; git identity is `tilorc-bot`.
- SymPy: development checkout at `/home/tilo/orion/sympy` (at `6379c4da69`);
  the released SymPy 1.14 is available through `uv --with sympy`. Tests and
  tools run from a worktree with:

  ```bash
  PYTHONPATH=.:/home/tilo/orion/sympy timeout 1800 uv run --no-project --with pytest --with mpmath python -m pytest -q -p no:cacheprovider tests/refine_identities
  PYTHONPATH=.:/home/tilo/orion/sympy timeout 3000 uv run --no-project --with pytest --with mpmath python tools/refine_identity_scoreboard.py [--family F] [--show]
  PYTHONPATH=.:/home/tilo/orion/sympy timeout 1800 uv run --no-project --with pytest --with mpmath python tools/refine_differential.py --summary --seed 2 --cases 1500
  PYTHONPATH=.:/home/tilo/orion/sympy timeout 3000 uv run --no-project --with pytest --with mpmath python tools/refine_specialize.py --write --family F
  PYTHONPATH=.:/home/tilo/orion/sympy timeout 3000 uv run --no-project --with pytest --with mpmath python tools/refine_ablate.py F
  ```

  The scoreboard needs pytest importable (it loads the battery's list of
  known sampler limits); without it 7 cases show as wrong.
- **Never run the whole `tests` directory in one process**: the suite
  conftests select different handler packages and conflict. Run
  `tests/refine_identities` (or one file) at a time.
- Environment variables: `SATREFINE_HANDLERS=handlers_identities` selects the
  package (the `tests/refine_identities` conftest sets it);
  `SATREFINE_BACKEND=sympy|satassume|combined` (default combined);
  `SATREFINE_IDENTITIES=generated|live` (default generated).
- Timings: generating `log`'s table about 3.5 minutes (case splits); a full
  ablation run 2.5 to 23 minutes per family; a differential run about 4
  minutes per package at 1,500 cases. Budget `timeout` accordingly.
- Machine: shared with other agents (12 cores). Before any timing work read
  `/home/tilo/README.md` (benchmarks go through `~/bin/bench-container`).
  Check for orphaned processes with `ps -eo pid,ppid,etime,pcpu,cmd --sort=-etime | grep python`.
- Other `.claude/worktrees/agent-*` worktrees belong to earlier, unrelated
  tasks; leave them alone.

## 4. How to run agents (what worked in phase 1)

- **One worktree and branch per agent** (`ri/<role>`), created from
  `origin/refine-identities`. The coordinator merges each into
  `refine-identities` and fast-forwards the others.
- **Explicit file ownership in every prompt.** Engine files are
  `satrefine/handlers_identities/_*.py`, `tools/refine_specialize.py`,
  `tools/refine_identity_scoreboard.py`. Family modules are owned per family.
  When two agents would touch the same file, give one a report-only
  deliverable.
- **Requests as failing tests:** an agent needing a change in code it does
  not own commits the smallest failing test under
  `tests/refine_identities/needs/test_<author>_<topic>.py` and reports it;
  the owner makes it pass and moves it into its own tests.
- **Process rules in every prompt:** `timeout` on every long command; one
  heavy run at a time; commit and push before waiting on anything (WIP
  commits are fine); always end with a report, even when out of time.
- **Coordinator:** judge progress from branch commits and file changes, not
  from an agent's "still waiting" message. A phase-1 agent stalled for
  hours with uncommitted work while its messages said it was waiting.
- **Models:** in phase 1 the user limited Fable to two roles (Fable went to
  the engine and to the author of the hardest families; Opus did the
  checker, trimmer, plain-rules author and experiments). Assume the same
  limit unless the user says otherwise.
- Commit messages end with `Co-Authored-By: Claude <model name> <noreply@anthropic.com>`
  for the model that wrote them.
- The battery's test `tests/refine_identities/test_battery.py` proves the
  battery faithful to v3; do not edit `battery_v3.py` by hand. It is
  regenerated by `tools/refine_battery_capture.py` and
  `tools/refine_battery_generate.py`.

## 5. The work, in order

Each step lists its gates (section 6). A step lands on `refine-identities`
only when its gates pass.

### Step 1. Fix the satassume defect, merge `main`, re-baseline

1. On a branch from `main`: stop satassume from treating SymPy's cached
   `_assumptions` facts as unconditional, and never write derived facts
   into a fact base that other symbols share. Turn the needs test into a
   satassume test on `main`. Report the SymPy side (`(0**n).is_finite` is
   True for a plain `n`) as an upstream issue candidate, do not patch SymPy.
   Merge to `main`.
2. Merge `main` into `refine-identities`. The relation work on `main`
   changes which relation queries `ask` answers, so battery and fuzz
   numbers may move.
3. Re-baseline: full scoreboard in both `SATREFINE_IDENTITIES` modes,
   differential seeds 2, 3, 7, the `tests/refine_identities` suite. Record
   the numbers in the step's report; they are the baseline for every later
   step. Investigate any new wrong answer before moving on.
4. Also here: guard the combined backend against the `Abs`-of-imaginary
   answer (or document why not), and fix the `atan2` firing-cap crash
   (the cap should not be reached by repeated work on independent
   branches; cache or bound per-branch work).

### Step 2. Relation-condition decider in the engine; merge the Piecewise experiment

`ri/piecewise` replaced minmax_deltas' 10 Min/Max/KroneckerDelta/Heaviside
rules with 5 Piecewise definitions (13 rows became 8: the 3 DiracDelta rules
stay), with identical battery, tests and differential. Its cost: a 35-line
decider in the family module for relation conditions (`Holds` nodes,
proof forms from signs and relations, the guard that ignores relation
proofs when an argument is known infinite, which is where SymPy's `ask`
wrongly proves `Q.eq(i, j)` for `i = -oo`). SymPy's own handling of `x >= y`
inside a Piecewise derives nothing from signs, raises on sign facts, and
repeats the `-oo` bug. Also: putting `Piecewise` in `opaque` made refusals
about 5 times slower through case splits; the experiment instead gives a
candidate containing an undecided Piecewise an infinite measure.

1. Move the decider into the engine as generic machinery (a condition
   node or equivalent that any table can use), with the `-oo` guard.
2. Make the case split decline on an undecided `Piecewise` instead of
   crashing, and let a table opt out of case splits.
3. Rebase or merge `ri/piecewise` onto the new engine so minmax_deltas uses
   the engine's decider; its family code should drop to about the old 45
   code lines with 8 rows. Merge when gates pass; delete `ri/piecewise`.

### Step 3. Definitions for the plain families

1. **integer_funcs** (17 rows): define `ceiling(x) = -floor(-x)`,
   `frac(x) = x - floor(x)`, `Mod(a, b) = a - b*floor(a/b)`, `Rem` with
   truncation, and keep only primitive `floor` facts (integer argument
   unchanged, integer shifts, stated bounds, which the engine's interval
   reasoning already handles). The experiment's author expects a clear row
   drop with no new machinery. Watch SymPy's `Mod` on non-real arguments
   (phase 1 found `Mod(a, b) = b/2` wrong for non-real `b`).
2. **combinatorial** (16 rows): only if step 3.1 shows the pattern pays.
   `factorial(n) = gamma(n+1)` and the rising/falling factorial and binomial
   as gamma ratios are easy to state, but the gamma facts (poles, integer
   arguments) remain and rewriting back from `gamma` needs an ordering. The
   experiment's verdict was doubtful; measure before committing to it.
3. **matrices** (30 rows): no case structure to collapse; leave as is.

### Step 4. Staged derivation (stages 0 to 5)

Goal: every fact about a particular function is either a hand-stated
**stage 0 row** (counted, reviewed) or a **derived rule** (generated,
verified, recorded with its derivation). Python keeps only generic
machinery: matcher, `provable`, ordering, case splits, interval reasoning
for `floor`/`ceiling`, dispatcher, generator. Rule of thumb: code that
names a specific function (other than the one it exists to reason about)
is knowledge and becomes a row.

| Stage | Functions | Derived from |
| --- | --- | --- |
| 0 | definitions for `re`, `im`, `arg`, `Abs`, `sign`, `conjugate` (and the Piecewise and floor definitions from steps 2 and 3) | stated |
| 1 | `re`, `im`, `arg`, `Abs`, `sign`, `conjugate` | stage 0 |
| 2 | `exp`, `log` | stages 0 and 1 plus `log`'s two facts |
| 3 | `Pow` | `b**e = exp(e*log(b))` plus stages 0 to 2 |
| 4 | trig and hyperbolic | their exponential forms plus stages 0 to 3 |
| 5 | inverse functions | the wraps plus stages 0 to 4 |

Stage 0 candidates: `re`/`im` of real and imaginary arguments; additivity
of `re` and `im` and real factors pulling out; `arg` of positive, negative
and imaginary arguments; `im(log w) = arg w`, `re(log w) = log(Abs(w))`;
`|exp z| = exp(re z)`, `arg(exp z) = principal(im z)`; `Abs` and `sign` of
signed and imaginary arguments; `conjugate` of real and imaginary
arguments, additive and multiplicative. Most of these already exist as
rows in `complex_parts.py`; stage 0 separates the stated ones from the
derivable ones.

The generation loop:

```
tables = {}
repeat (cap 5 rounds, fail loudly listing families still changing):
    changed = False
    for stage in 1..5, for family in stage:
        install stage 0 and every table in `tables`
        rules = specialize(family identity rows, catalog)
        rules = [r for r in rules if verify(r)]          # every round, before installing
        if rules != tables.get(family): tables[family] = rules; changed = True
    stop when not changed
write generated/<family>.py with derivation records
```

- Order within a round follows the stages; later rounds catch real cycles
  (`im(log w)` mentions `log` while `log`'s rules need `im`; `arg(exp z)`
  needs `im` while `im(exp z)` needs `sin`).
- **Verify before installing, every round.** A wrong rule installed early
  propagates into every later stage. A wrong `ask` answer is the one risk
  verification does not catch (it sits below stage 0); step 1 matters for
  this reason.
- **Derivation records:** each generated rule records its identity row and
  profile, the stage 0 rows and generated rules that fired (with their
  round), and the `ask` queries used. Uses: tracing a rule that fails
  verification to its cause; knowing what to rederive when a stage 0 row
  changes.
- Rounds after the first generate with earlier stages' compiled tables
  installed, not the live engine, which should cut generation time (case
  splits are what made `log` take 3.5 minutes). Measure round 1 on one
  family first; if a fixpoint costs more than a few minutes per family,
  regenerate only families whose inputs changed.
- Migrate `_simple.py`: its function knowledge moves to stage 0 rows or is
  derived; the generic interval reasoning stays (rename it, for example
  `_bounds.py`). The range table (`arg`, `atan`, `acot`, `asin`, `acos`) is
  borderline: state the ranges as stage 0 rows if the engine can read bounds
  from rows, otherwise count its entries as stage 0 rows in the metric.
- Suggested order: stage manifest and fixpoint loop reproducing today's
  tables unchanged; then installing tables between stages; then derivation
  records; then stage 0 and the migration, one function at a time with the
  gates after each; then trig and hyperbolic through exponential forms.

Expected outcome, with honest uncertainty: auditability and consistency
(derivation records, one fixpoint check instead of per-family staleness)
are near certain. The row-count reduction is the headline claim and the
least certain: many base facts may be definitions nothing smaller implies.
The first cheap test: run stage 1 from a draft stage 0 and count how many
of complex_parts' 26 base rows it reproduces.

### Step 5. Prover gaps and matrix fuzzing

- `ask` cannot show `(1 - n)/2` is an integer for odd `n`: costs the
  negative-base, odd-exponent power rules their clean form
  (`log(-x**n) + I*pi` instead of `n*log(-x) + I*pi`) and may affect trig
  shifts by odd multiples of `pi/2`.
- `ask` cannot show `re(floor(y))` and `im(floor(y))` are integers for a
  finite, possibly complex `y`: 4 integer_funcs rows exist only for this
  and would fold into the shift rows (17 to 13).
- These are satassume (or SymPy) work, on `main`; decide with the user
  which engine gets the fix.
- **Matrix fuzzing:** the fuzzer generates no matrix expressions and the
  battery's numeric check skips matrix symbols, so matrices have no numeric
  soundness check beyond their own tests. Add matrix expressions to
  `refine_fuzz.py`/`refine_differential.py` with explicit small matrices as
  sample points.

### Step 6. Report and cleanup

Write `agent-reports/<date>-refine-identities-phase-2-results.md` with the
metrics before and after each step, move reports this phase supersedes to
`agent-reports/archive/`, delete merged `ri/*` branches and their worktrees.

## 6. Metrics and gates

| Metric | Gate |
| --- | --- |
| Battery same + other form | must not drop (per family) |
| Battery unchanged-as-required | must stay unchanged |
| Battery wrong, crash | must stay 0 |
| Differential seeds 2, 3, 7 at 1,500 cases | no new unsound or numerically different result |
| Family tests, engine tests | pass |
| Stage 0 rows | reported; the number to minimize |
| Derived rules per family | reported |
| Function-specific Python lines | reported; target 0 |
| Family and engine code lines (excluding blanks, comments, docstrings) | reported; phase 1 per-family total 483, engine 1,132 |
| Generation time per family per round | reported |

`tools/refine_ablate.py F` applies the first three gates plus a fuzz check
to row removals; use it after any step that adds rows.

## 7. Suggested roles

| Step | Role | Model |
| --- | --- | --- |
| 1 | satassume fix on `main`, re-baseline | Fable (touches the assumption engine every result depends on) |
| 2, 4 | engine and generator: decider, Piecewise, staged loop, derivation records, `_simple.py` migration, stage 0 | Fable (one role; the engine and stage 0 touch the same files) |
| 3 | plain-family definitions | Opus |
| 2 to 5 | checker: adversarial pass per step as it lands | Opus |
| 3, 4 | trimmer: ablation over stage 0 and the new definitions | Opus |
| 5 | matrix fuzzing | Opus |

With a two-Fable limit, steps 1 and 2/4 are the two Fable roles; step 1
finishes before step 4 starts, so its agent can move on to it.

## 8. Open questions for the user

- Keep the two-Fable-role limit for phase 2?
- Fix the satassume defect on `main` directly, or through a pull request?
- Close the prover gaps in satassume, SymPy, or both?
- Should `handlers_identities` become the default `SATREFINE_HANDLERS` once
  phase 2 lands? (`handlers` is the default today so the corpus numbers in
  the README keep their meaning.)

## 9. References

- Phase 1 results: `agent-reports/2026-09-24-refine-identities-phase-1-results.md`.
- Process lessons (on `main`): `agent-reports/2026-09-24-read-before-running-agents-how-work-gets-lost.md`.
- The v3 baseline and the three procedural implementations:
  `agent-reports/2026-09-23-refine-three-implementations.md`.
- Archived phase-1 working documents: `agent-reports/archive/` (the `log`
  experiment report, the original staged-derivation plan now folded into
  step 4, the ablation measurements).
- A progress document written during phase 1 for the user (a Claude Docs
  page, "Refine from Identities: Progress Report") is out of date on the
  branch-cut results; this plan and the phase 1 report supersede it.
- Background reading, cited from memory: Corless and Jeffrey, *The unwinding
  number* (SIGSAM Bulletin 1996) for the `floor` bookkeeping; Martin and
  Nipkow, *Ordered rewriting and confluence* (CADE 1990) for the rewrite
  ordering; Baader and Nipkow, *Term Rewriting and All That* (1998);
  Nandi, Willsey et al., *Rewrite rule inference using equality saturation*
  (Ruler, OOPSLA 2021), the closest system to the generator.
