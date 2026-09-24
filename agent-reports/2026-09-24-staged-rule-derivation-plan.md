# Implementation plan: staged rule derivation (stages 0 to 5)

- **Date:** 2026-09-24
- **Status:** plan, not started. To begin after the current phase lands:
  the branch-cut families merged into `refine-identities`, the checker's
  second pass and the trimmer's first pass done.
- **Read this if:** you are restructuring the generator in
  `satrefine/handlers_identities/`, or deciding what counts as a
  hand-written rule.
- **Depends on:** `2026-09-24-refine-from-identities.md` (the approach),
  the scoreboard and battery in `tests/refine_identities/`.
- **TL;DR:** replace the hand-written simple-rule layer (`_simple.py`) with
  a small set of stated definitions (stage 0) and derive every other rule
  in dependency order: complex parts, then `exp` and `log`, powers, trig
  and hyperbolic, inverse functions. Each stage's verified rules are
  installed before the next stage is generated, and the whole sequence is
  repeated until no table changes. Success is the same battery coverage
  and soundness as the current package with fewer hand-stated rows and no
  function-specific Python.

## 1. Goal and the rule it enforces

Every fact about a particular function is either a **stated row** (stage
0, counted and reviewed by hand) or a **derived rule** (generated,
verified numerically, and recorded with its derivation). Python code in
the package holds only **generic machinery**: the matcher, `provable`,
the rewrite ordering, case splits, interval reasoning for `floor` and
`ceiling`, the dispatcher, and the generator.

The test for whether code is machinery or knowledge: if it names a
specific function other than the ones it exists to reason about (`floor`
and `ceiling` for interval reasoning), it is knowledge and becomes a row.

## 2. Current state this starts from

- `_simple.py` holds procedural rules for `re`, `im`, `arg`, `Abs`,
  `floor`, `ceiling` and `Piecewise`, mixing function knowledge
  (`im(log w) = arg w`, `re(exp w) = exp(re w)*cos(im w)`) with generic
  interval reasoning (`stated_bounds`, the `BOUNDS` table,
  `floor_of_bounded`).
- `_specialize.py` generates one family at a time from its identity rows
  with the live engine, verifies each rule at a sample point and at edge
  points, and writes `generated/<family>.py`. Families are generated
  independently; nothing orders them or feeds one family's output into
  another's generation.
- The dispatcher prefers a family's generated table, then its live
  identity handler, then the `_simple.py` fallback.

## 3. Stages

| Stage | Functions | Derived from |
| --- | --- | --- |
| 0 | definitions for `re`, `im`, `arg`, `Abs`, `sign`, `conjugate` | stated by hand |
| 1 | `re`, `im`, `arg`, `Abs`, `sign`, `conjugate` | stage 0 |
| 2 | `exp`, `log` | stages 0 and 1, plus `log`'s two facts |
| 3 | `Pow` | exponential form `b**e = exp(e*log(b))` plus stages 0 to 2 |
| 4 | trig and hyperbolic | their exponential forms plus stages 0 to 3 |
| 5 | inverse functions | the wraps plus stages 0 to 4 |

The plain-rules families (integer functions, combinatorial, Min/Max and
deltas, matrices) are unchanged: their rows are stated rules with no
identity above them. They sit outside the stages and keep their current
tables.

### Stage 0 candidates

Stated, not derived. The list is a starting point; the trimmer shrinks it.

- `re(w) = w`, `im(w) = 0` for real `w`; `re(w) = 0`, `im(w) = -I*w` for
  imaginary `w`
- `re` and `im` are additive, and real factors pull out of both
- `arg(w) = 0` for positive `w`, `pi` for negative, `pi/2` and `-pi/2` on
  the positive and negative imaginary axis
- `im(log w) = arg w`, `re(log w) = log(Abs(w))`
- `|exp z| = exp(re z)`, `arg(exp z) = principal(im z)`
- `Abs` and `sign` of positive, negative and imaginary arguments;
  `conjugate` of real and imaginary arguments; `conjugate` additive and
  multiplicative

Stage 0 lives in one module, `satrefine/handlers_identities/stage0.py`,
using the existing row format so the scoreboard counts it.

## 4. The generation loop

```
tables = {}
repeat:
    changed = False
    for stage in 1..5:
        for family in stage:
            install stage 0 and every table in `tables`
            rules = specialize(family identity rows, catalog)
            rules = [r for r in rules if verify(r)]      # every round
            if rules != tables.get(family):
                tables[family] = rules; changed = True
until not changed
write generated/<family>.py for every family, with derivation records
```

- **Order within a round** follows the stages, so most rules settle in
  the first round. Later rounds catch the genuine cycles: `im(log w)`
  mentions `log` while `log`'s rules need `im`, and `arg(exp z)` needs
  `im` while `im(exp z)` needs `sin`.
- **Termination.** Catalogs are finite, rules are only added when
  verified, and a rule set that stops changing ends the loop. Cap rounds
  at 5 and fail loudly if the cap is hit, listing the families still
  changing.
- **Verification every round, before installation.** A rule that fails
  is never installed for the next round. This is the defence against a
  wrong rule, or a wrong `ask` answer, propagating upward through every
  later stage.
- **Speed.** Rounds after the first generate with the compiled tables of
  earlier stages installed, not the live engine, so bookkeeping that
  used to need a case split collapses by table lookup. Record the time
  per family per round; a family that exceeds its budget is a finding,
  not something to wait on.

## 5. Derivation records

Each generated rule is written with a comment or a side table recording:

- the identity row it came from and the assumption profile;
- the stage 0 rows and generated rules that fired, in order, with the
  round each was generated in;
- the `ask` queries whose answers were used.

Two uses: when a rule fails verification, its record points at the step
that caused it (the `Q.zero(b**2)` bug in SymPy's `ask` would have been
one line); and when a stage 0 row or generated rule changes, the records
say exactly which downstream rules to rederive. The fixpoint loop
rederives everything anyway; the records make the change reviewable.

## 6. Migrating `_simple.py`

1. Move every function-specific rule in `_simple.py` into `stage0.py` or
   delete it if stage 1 derives it. Keep a list of anything that cannot
   move, with the reason.
2. Keep the generic parts in `_simple.py`, renamed to `_bounds.py` or
   similar: `stated_bounds`, `floor_of_bounded` and the `BOUNDS` table of
   ranges. The `BOUNDS` table is borderline: the range of `arg` or `atan`
   is a fact about those functions. State the ranges as stage 0 rows of
   the form `(atan(x), Q.ge(atan(x), -pi/2) & Q.le(...))` if the engine
   can read bounds from rows; otherwise keep the table and count its
   entries as stage 0 rows in the metric.
3. Remove the dispatcher's fallback to `_simple.py` for function
   knowledge. The fallback to vendored SymPy handlers is already gone for
   keys a family owns; confirm no key still falls through to a vendored
   handler.

## 7. Metrics and gates

Report per family, before and after:

| Metric | Gate |
| --- | --- |
| battery same + other form | must not drop |
| battery quiet | must stay unchanged |
| battery wrong, crash | must stay 0 |
| differential fuzz unsound (seeds 2, 3, 7) | no new unsound result |
| stage 0 rows | reported, the number to minimize |
| derived rules per family | reported |
| function-specific Python lines | target 0 |
| generation time, per round | reported; a budget per family |

The comparison baseline is the package as it stands when this work
starts, measured with the same battery and seeds.

## 8. Work split

| Role | Model | Work |
| --- | --- | --- |
| Engine and generator | Fable | the fixpoint loop, stage manifest, derivation records, installing tables between rounds, migrating `_simple.py` |
| Stage 0 author | Fable | writes `stage0.py`, checks each definition against SymPy's conventions (principal branch, `arg` of negatives is `pi`), and moves rules out of `_simple.py` |
| Checker | Opus | adversarial pass per stage as it lands, with edge points; checks that no rule was installed unverified |
| Trimmer | Opus | ablation over stage 0 rows: a row is removable if the fixpoint without it still passes the gates |

The engine and stage 0 roles can be one Fable agent if the two-role limit
applies; they touch the same files. Every agent follows the rules in
`agent-reports/2026-09-24-read-before-running-agents-how-work-gets-lost.md`
on `main`: `timeout` on every long run, one family per generation run,
commit and push before waiting, always report.

## 9. Order of work

1. Baseline: run the scoreboard and the three differential seeds on the
   finished current package and record the numbers.
2. Stage manifest and fixpoint loop in `_specialize.py`, with the current
   family modules unchanged. Check the loop reproduces the current tables
   (it should, since nothing is fed forward yet).
3. Install tables between stages. Measure: coverage should rise or hold,
   generation time should fall after round 1.
4. Derivation records.
5. `stage0.py`, then migrate `_simple.py` one function at a time, running
   the gates after each.
6. Checker pass, trimmer pass on stage 0.
7. Report with the before and after metrics.

## 10. Risks

- **The base does not bottom out cleanly.** Some facts may resist being
  either stated or derived without the engine's interval reasoning. Keep
  them as stated rows with a note, rather than bending the machinery.
- **Cycles slow convergence.** If a family keeps changing across rounds,
  the ordering or a stage 0 row is wrong. The round cap turns this into a
  loud failure.
- **Wrong rules propagate.** Mitigated by verifying every round before
  installation and by derivation records; a wrong answer from `ask`
  remains the unguarded risk, since `ask` sits below stage 0.
- **Generation time.** Each round is a full generation. Measure round 1
  first on one family; if the fixpoint costs more than a few minutes per
  family, generate only families whose inputs changed in the previous
  round.
