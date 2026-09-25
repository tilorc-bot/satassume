# Agent report: staged derivation (phase 2 step 4), agent "stages"

- **Date:** 2026-09-25
- **Branch:** `ri/stages`, from `refine-identities` f686dcc. Not merged; the
  coordinator merges.
- **Status:** interim. Section 1 is the go/no-go test. Later sections are
  added as the work lands.

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
