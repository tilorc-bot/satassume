# Agent report: staged derivation (phase 2 step 4), agent "stages"

- **Date:** 2026-09-25
- **Branch:** `ri/stages`, from `refine-identities` f686dcc. Not merged; the
  coordinator merges.
- **Status:** handed off at the coordinator's request (context size);
  see `agent-reports/stages-handoff.md` for the next steps. Section 1 is
  the go/no-go test.

## 1. Interim: the cheap test (stage 1 from a draft stage 0)

### What "the 26 base rows" are

`complex_parts.RULES` states 27 rows for `re`, `im`, `arg` and `Abs`: 5
`Abs`, 18 `re`/`im`, 4 `arg`. The plan's 26 and `BASE`'s 21 both count
these rows. `BASE` filters by head after SymPy has evaluated the left
sides, so 6 of them no longer have a `re`/`im` head.

**9 of the 27 rows never fire.** SymPy rewrites their left side when the
node is built, so no such node reaches a handler:
- `Abs(conjugate(w))`, `re(conjugate(w))`, `im(conjugate(w))`
- `re(a + b)`, `im(a + b)`
- `re(exp(z))`, `im(exp(z))`
- `re(log(w))`, `im(log(w))`

Some of them became no-op rows, such as `re(w) -> re(w)`. Two of those
had a `Mul` left side and were matched against every product in
`refine_Mul`.

### Draft 1: `re`, `im`, `Abs`, `arg` through `conjugate` (measured, not kept)

Draft 1 was 4 definitions over the existing `sign` and `conjugate` rows:
- `re(z) = (z + conjugate(z))/2`
- `im(z) = (z - conjugate(z))/(2*I)`
- `Abs(z) = z*conjugate(sign(z))`
- `arg(z) = -I*log(sign(z))`

It needed an engine fold that solves a definition back for `conjugate`
(`conjugate(u) = 2*re(u) - u`).

- On one instance per row, it reproduced 27 of 27 (the control, with no
  rows and no definitions, gets 9 of 27).
- It was not sound as stated. `re(x**n)` under a real `x` and an integer
  `n` became `x**n`, which is wrong at `x = 0` for negative `n`: the
  candidate's algebra, `x**n + x**n = 2*x**n`, assumes finite values. The
  sound domain is `Q.finite(z)`, and with it the rows for a real or
  imaginary factor must stay stated, because they hold at infinity.
- It lost coverage on the battery (live mode). In inverse, 10 cases moved
  from "same" to "other form", such as `acos(cos(x))` on `[0, pi]` giving
  `Abs(x)`. In power_exp_log, 1 case moved: `log(x*y)` under
  `Q.negative(x*y)` gave `log(Abs(x*y)) + I*pi`. The cause: SymPy
  distributes `conjugate(x*y)` to `conjugate(x)*conjugate(y)` on
  construction, before a fact about the product (`Q.negative(x*y)`,
  `Q.real(x*y)`) can apply. So the rows about a *whole* argument under a
  sign or realness fact cannot come from a definition through `conjugate`.
  They are what `Q.real` and the sign facts mean.

### Draft 2: through `sign` (kept, commit on `ri/stages`)

Two definitions over the stated `sign` rows. `sign` rows match the whole
argument, so products keep their facts:

```
(Abs(z), z/sign(z),        ~Q.zero(z) & Q.finite(z)),
(arg(z), -I*log(sign(z)),  ~Q.zero(z)),
```

What becomes of the 27 rows:

| rows | fate |
| --- | --- |
| 9 | removed: never fire (SymPy evaluates the left side) |
| 4 | derived: `arg` of positive, negative and imaginary arguments, from the `arg` definition |
| 2 | derived: `Abs` of imaginary arguments, from the `Abs` definition |
| 2 | removed: `re`/`im` of `b**n` for real `b` and integer `n` follow from the real-argument rows, since `ask` proves `b**n` real under the same guard |
| 10 | stated (stage 0): `re`/`im` of real and imaginary arguments (4); `Abs` under `Q.nonnegative`/`Q.nonpositive` (2; they include 0, where `z/sign(z)` is undefined); `re`/`im` of a real or an imaginary factor (4; they hold at infinity) |

complex_parts goes from 45 rows (3 facts, 41 rules, 1 split) to 30
(5 facts, 24 rules, 1 split), and from 91 to 81 code lines. The 27 base
rows become 10 stated rows plus 2 definitions: 15 fewer. 11 of the 15
need no derivation at all.

**Checks.**
- `tests/refine_identities/test_complex_parts.py`: 264 passed (live).
- Live battery scoreboard (`PYTHONHASHSEED=0`): identical per family to
  the shared baseline `int-f686dcc`, including 0 wrong and 0 crash.
- Refusal cost: the complex_parts battery in live mode (242 cases, SymPy
  cache cleared per case, unpinned, load about 10) took 4.9 s fired and
  5.3 s refused before, and 4.1 s and 5.8 s after, with the same 159/83
  split. The definitions do not multiply the `ask` calls.

### Generation cost per family and round

Measured with today's generator (`tools/refine_specialize.py`, one round,
all live), load 12 to 15 on 12 cores:

| family | seconds | rules |
| --- | --- | --- |
| complex_parts | 315 | 36 |
| integer_funcs | 218 | 11 |
| inverse | 27 | 7 |
| power_exp_log | 318 | 17 |

One round is about 15 minutes. A fixpoint needs at least two rounds, and
round 2 regenerates every family whose inputs changed.

### Recommendation

**Go, with the headline reduced.** The row reduction from derivation
proper is small in the base layer: 6 of 27 rows come from 2 definitions.
The larger part of the gain, 11 rows, is rows that were dead or made
redundant by `ask`, and deleting them needs no stages. Most base facts
really are stage 0, as the plan feared: the meaning of `Q.real`,
`Q.imaginary` and the sign facts, and linearity. What remains promising:
- The near-certain parts: the manifest, the fixpoint loop and the
  derivation records. They are written and are being checked for
  reproduction of today's tables.
- Stage 4: trig and hyperbolic through exponential forms, the other place
  where the plan expects derivation (25 rule rows today).
- The `_simple.py` range table as rows.

I continue with plan step 4's order.

## 2. Stage manifest, fixpoint loop, derivation records

New engine module `_stages.py` (113 code lines at the time of writing):
- `STAGES` is the manifest: integer_funcs and complex_parts in stage 1,
  power_exp_log in stage 2 (its `Pow` rows are stage 3 but live in the
  same family), trig and hyperbolic in stage 4 (no generated tables
  today), inverse in stage 5. A generating family missing from the
  manifest is an error (`test_stage_manifest_covers_every_generating_family`).
- `generate()` starts from empty tables and runs the families in stage
  order. Each family is specialized with its own keys on their identity
  rows and every other key through the tables generated so far
  (`_dispatch.tables()` and `_dispatch.live_for(keys)`; the dispatcher's
  result cache keys on the live keys). Verified rules are installed after
  each family, every round. A round regenerates only the families whose
  inputs, the other families' tables, changed since their last
  generation. The loop stops when a round changes nothing and raises
  after 5 rounds, naming the families still changing.
- **Derivation records.** `_dispatch.tracing()` collects, while a
  profile is refined, the rows that fired (a `note` in `rule_handler` and
  `identity_handler`) and the `ask` queries answered `True`.
  `_specialize.records` keeps them per found rule. The generated modules
  carry them as comments above each row: the round, the source identity
  row and profile, the rows fired (labelled `family.TABLE[i]`, or
  `family.generated[i]` for another family's installed table) and the
  asks.
- `tools/refine_specialize.py --write` runs the fixpoint and writes every
  table. `--family F` regenerates one family against the committed
  tables of the others. `test_generated.py`'s up-to-date test now checks
  exactly that for each family, which is the fixpoint property.
- One shared `table_order` sorts a generated table, both in memory during
  the fixpoint and in the written module. A left side over bare symbols
  (`log(x)`) goes after structured ones (`log(b**e)`), then fewer symbols
  first, as before.

**Reproduction check.** On a copy of f686dcc with only the new
infrastructure (old tables, old order), the fixpoint gave the same rows
in the same order for all four generated families. It stopped after
round 2, and round 2 skipped inverse because its inputs had not changed.
Time, at load 3 to 15 on 12 cores:

| family | round 1 | round 2 |
| --- | --- | --- |
| integer_funcs | 170 s | 159 s |
| complex_parts | 234 s | 253 s |
| power_exp_log | 300 s | 319 s |
| inverse | 26 s | skipped |
| total | | 1,461 s |

Installing earlier tables did not make generation faster. The live
fallback runs whenever a table declines, and specialization mostly
explores profiles where the tables decline.

## 3. `_simple.py`: the range table as rows

`_simple.BOUNDS` and `arg`'s special case in `_range` were function
knowledge in the engine. They are now range rows
`(head(y), interval, condition)`, stated by the owning family and
registered with `register_ranges`:
- `complex_parts.RANGES` has 2 rows for `arg`: open at `pi` off the
  negative axis, else `(-pi, pi]`.
- `inverse.RANGES` has 4 rows: `atan`, `acot`, `asin`, `acos`.

`_simple._range` reads the first row whose condition is provable. The
interval reasoning stays in `_simple.py`. I kept the module name, since
a rename would only churn imports for the other teams. The scoreboard's
row table gains `ranges` and `stage0` columns. `stage0` counts every
stated table once, in its owner: complex_parts' `EXP_FORMS` is
power_exp_log's, and `SPLITS`, `NEGATIVE_BASE` and `BOUNDED` were not
counted before.

## 4. Stage 4, trig and hyperbolic (considered and rejected)

Prototype (script in the session scratchpad, battery trig and hyperbolic
cases, live mode):
- `tan`, `cot`, `sec` and `csc` as definitions over the `sin`/`cos`
  shift rows (12 shift rows become 4 definitions).
- A top-down fold that reads the definitions backwards
  (`sin(u)/cos(u) -> tan(u)`). Bottom-up folds `1/cos` to `sec` first
  and leaves `sin(x)*sec(x)`.
- `AccumBounds` opaque, so there are no new firings at infinity.

Results:
- No misses, and no new firings where v3 expects unchanged.
- 14 trig cases moved from "same" to "other form" in my harness: 208/8
  (rows) against 194/22 (definitions). The forms are `(-1)**(1/2 - k/2)`,
  `sec(x)/(-1)**(k/2)` and uncombined `(-1)**a*(-1)**b`.
- Two stated rows for base -1 bring it to 202/14: `(-1)**a*(-1)**b =
  (-1)**(a + b)` and `(-1)**(-x) = (-1)**x` for integer `x`.
- The rest needs one of two things. One is a matcher that extracts a
  sign from a rational coefficient: `(-1)**(-A)` does not match
  `(-1)**(-k/2)`. The other is the step 5 prover gap: `ask` cannot show
  `(1 - k)/2` is an integer for odd `k`.

Net: about 6 rows fewer, a new engine fold of about 20 lines, and 6
trig cases in a worse form. Hyperbolic through trig (`sinh(z) =
-I*sin(I*z)`) folds by itself, because SymPy evaluates `sin(I*x)` to
`I*sinh(x)`. But v3's hyperbolic rows fire only when `m mod 4` is known,
while the trig rows fire for any even or odd `n`. A derivation would
therefore fire where v3 expects unchanged, which the gate forbids unless
the trig rows are restricted the same way. I did not land stage 4. The
trig family's docstring already says the exponential-form derivation
"produces quotient forms that are not v3's", and the measurement agrees.

**Decision (coordinator, 2026-09-25): rejected.** Stage 4 is not done.
Trig through definitions saves about 6 rows (12 shift rows become 4
definitions, plus 2 new base -1 rows) and needs a new engine fold of
about 20 lines. The cost is 6 to 14 trig battery cases moving from
"same" to "other form": 208/8 with the rows against 194/22 with the
definitions, or 202/14 with the two extra rows. Hyperbolic through trig
fires where v3 expects unchanged, because the trig rows fire for any
even or odd `n` while v3's hyperbolic rows need `m mod 4`. The gate
forbids that. The trig and hyperbolic families keep their stated rows.

## 5. Gates at 3865d76 (`/home/tilo/fable-rewrite/.claude/gates/stages-3865d76`, base `int-f686dcc`)

Run with `JOBS=9 SLOTS=11 SUITE_WORKERS=4`, `PYTHONHASHSEED=0`, 1,191 s.
It covers every commit after b44342b: 6ae3602, the merge c8dab08, 04b9b1e
and 3865d76. The fixpoint rerun on this head wrote the four generated
files byte for byte as committed (section 6), so the gated tables are
the regenerated ones.

- **Suite:** 2,355 passed, 0 failed, 1,917 skipped, 30 xfailed. The
  baseline had 2,350 passed and 2 failed, and both failures were needs
  tests that this branch fixes.
- **Scoreboard, live:** identical per family to the baseline (1,033 same,
  40 other, 13 miss, 629 unchanged as expected, 21 extra, 0 wrong,
  0 crash).
- **Scoreboard, generated:** identical except power_exp_log, which goes
  from 98 same / 3 other to 100 same / 1 other. Totals: 1,032 same,
  41 other, 13 miss, 629 unchanged as expected, 21 extra, 0 wrong,
  0 crash.
- **Differential** (seeds 2, 3, 7, both modes): 0 numerically different
  results, and no crashes. The unsound counts on the identities side
  (2, 3, 1) are the same as the baseline's in every run. Changes against
  the base:
  - Seed 3 in both modes and seed 7 in generated mode: one case each
    moves from "both fire, same result" to "different but numerically
    equal". These are the same form differences seen at b44342b.
  - Seed 2: v3 timed out on one case (timeout=1 on the v3 side, which
    had 328 s against 174 s in the base run). That removes one
    both-fire case. The identities side is unchanged.

## 6. Metrics

| | f686dcc | now (3865d76) |
| --- | --- | --- |
| stage 0 rows (every stated table once, plus `_simple.BOUNDS` entries before) | 180 | 166 |
| complex_parts stated rows | 45 | 32 (5 facts, 24 rules, 2 ranges, 1 split) |
| generated (derived) rules: complex_parts / power_exp_log / integer_funcs / inverse | 36 / 17 / 11 / 7 | 40 / 17 / 11 / 7 |
| function-specific lines in the engine (approximate, lines naming a function other than their subject) | about 27 | about 14 |
| family code lines | 472 | 478 (complex_parts 88, inverse 57, minmax_deltas 31) |
| engine code lines | 1,235 | 1,434 (`_stages` 125, `_dispatch` 211, `_engine` 623) |
| generation time, round 1 (s): integer_funcs / complex_parts / power_exp_log / inverse | 218 / 315 / 318 / 27 | 164 / 198 / 306 / 27 |
| generation time, round 2 (s) | 679 at b44342b (166 / 230 / 283 / skipped) | 422 (155 / 267 / skipped / skipped) |
| fixpoint total (s) | 1,461 (first run, on the old tables) | 1,117 |

Rows are from the scoreboard's `count_rows()`, lines from the gate
summary.

Fixpoint rerun on 3865d76 (`refine_specialize.py --write`,
`PYTHONHASHSEED=0`, load about 2): 2 rounds. Every generated table
changed only in round 1. The rule rows are identical to b44342b in all
four families, and the written files are byte-identical to the
committed ones, comments included. So the same-infinity `eq` proof and
the firing cap per chain change no derived row.

Round 2 with the "regenerate only if a table it looked up changed"
check (6ae3602) regenerates integer_funcs and complex_parts. It skips
power_exp_log and inverse. The handoff expected complex_parts alone, but
integer_funcs is first in stage order. In round 1 it ran against empty
tables for the keys of the later families, so round 2 has to run it
again. Round 2 costs 422 s, against 679 s at b44342b.

## 7. Commits on `ri/stages`

746d4ad, 5134182, 0fb75d5, 1813eb1, 27274dc, b44342b, 6ae3602, c8dab08
(merge of `origin/refine-identities` 4810c71), 04b9b1e, 3865d76 (handoff), and the
commit with the final gate numbers (this report).
