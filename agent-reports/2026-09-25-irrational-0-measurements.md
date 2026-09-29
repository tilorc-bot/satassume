# Agent report: irrational constants as bounded LRA variables, stage 0, measurements

- **Date:** 2026-09-25
- **Status:** measured, no engine code. Base: branch `stage-constants`
  (`997e723`, main plus item 1: constant propositions answered without the
  assumptions), x86 dev host, SymPy `/home/tilo/sympy`, `PYTHONHASHSEED=0`.
  No timings (shared machine).
- **Headline:** on the refine stream **897 queries (790 distinct, 68
  assumption sets) end None because of `Uninterpreted`**. Every unreadable
  atom sits in the assumptions, so each of these is a whole session that
  never builds. **829 queries (722 distinct, 62 sets) become fully readable
  under the plan**. All their unreadable atoms are `pi` or a Float in a
  linear position. The other 68 (6 sets) hold `oo`/`zoo`, `I` or
  `AccumBounds` and stay unreadable. **No atom is of the nonlinear kind**
  (`pi*x`, `sqrt(2)*x`, `0.5*x`): 0 of 48 distinct unreadable atoms. An
  oracle that rewrites the queries the way the plan reads them makes **105
  queries (89 distinct, 26 sets) more definite** and gives **24 new
  ValueErrors (3 sets)**. Nothing gets less definite and nothing flips. The
  other 700 stay None, and SymPy's `ask` decides only 2 of them. Only one
  base constant occurs, `pi`, plus four Floats. **gate2 has nothing to
  gain**: 0 queries are Uninterpreted there. The explainer's "36 queries
  over 3 inconsistent sets" is right for `main`. On `stage-constants`, 12
  of the 36 are constant propositions that item 1 already answers without
  the assumptions, so **the plan would add 24 ValueErrors**, not 36. SymPy
  raises on all 24.
- **Scope:** new script `agent-reports/scripts/irr0_census.py`. Raw output
  (not committed):
  `/tmp/claude-1000/-home-tilo-satassume/6c6cbdb2-60c6-4eda-b294-7e5e9bf2dd22/scratchpad/stage0/{stream,gate2}.{log,json}`.
- **Read this if:** you build item 2 of `2026-09-25-next-steps.md`, or
  decide whether it is worth building.

## Numbers

### 1. Uninterpreted queries on the refine stream (13,877 queries)

| | queries | distinct | assumption sets | None today |
|---|---:|---:|---:|---:|
| end in `Uninterpreted` | 897 | 790 | 68 | 897 |
| (a) only: every unreadable atom linear in a constant, readable under the plan | **829** | 722 | 62 | 829 |
| (b) constant times a symbol / nonlinear | 0 | 0 | 0 | 0 |
| (c) has `oo`/`zoo`, `I`, `AccumBounds` | 68 | 68 | 6 | 68 |

Per distinct unreadable atom: 41 of type (a), 0 of type (b), 7 of type (c).
The (c) atoms are 4 with `oo`/`-oo`/`zoo` (`Q.lt(x, zoo)`, `Q.le(x, oo)`),
2 with `I` (`Q.ge(x, I)`) and 1 with `AccumBounds(0, 1)`. All 48 atoms are
in the assumptions, none in a proposition. Typical (a) atoms:
`Q.le(x, 3*pi/2)`, `Q.lt(x, -pi/2)`, `Q.ge(pi/2, x)`, `Q.lt(x, 2*pi)`,
`Q.gt(t, -pi/2)`, `Q.ge(x, -pi)`, `Q.le(x, 4.712)`.

A cross-check between the static census and the engine: 29 queries have an
unreadable atom but no `Uninterpreted`. Their proposition is the literal
`False`, answered before any session is built. Every other query agrees
(897 both ways).

One more equality, `Q.eq(x, pi/2)`, is linear in a constant. EUF already
reads it, so it is not Uninterpreted. The plan would give it to LRA as well.

### 2. What the fully readable queries gain (plan oracle)

| outcome against `stage-constants` | queries | distinct | sets | SymPy `ask` (distinct) |
|---|---:|---:|---:|---|
| more definite (None -> True/False) | 105 | 89 | 26 | 60 agree, 29 None, 0 contradict |
| new ValueError (inconsistent assumptions) | 24 | 24 | 3 | 24 agree (SymPy raises) |
| still None | 700 | 609 | | SymPy: 607 None, 1 True, 1 False |
| less definite / contradiction | 0 | 0 | | |

I read the 29 more-definite answers where SymPy says None by hand. All are
correct and all follow from "a relation makes `x` real" plus the bounds.
Examples: `Q.integer(im(x)/pi)` given `Q.nonnegative(x) & Q.le(x, pi/2)`
is True; `Q.zero(x)` given `Q.ge(x, pi/2) & Q.le(x, 3*pi/2)` is False;
`Q.positive(x)` given `Q.ge(-pi/2, x) & Q.le(x, pi/2)` is False;
`Q.imaginary(x - 2*pi*floor(x/(2*pi) + 1/2))` given
`Q.nonnegative(x) & Q.le(x, pi)` is False. SymPy decides 2 of the 700 that
stay None, both given `Q.ge(Abs(x), 0) & Q.le(Abs(x), pi/2)`:
`Q.infinite(Abs(x))` is False and `Q.real(Abs(x))` is True. The link
`le(Abs(x), c) -> real(Abs(x))` should give them. The oracle probably
misses them because of how it rewrites (see "How measured"). **Upper bound
from these numbers: about 107 more-definite stream queries plus 24 new
errors.** For comparison, item 1 already makes 443 stream queries more
definite relative to the recording (constant propositions under these
same sessions).

### 3. Constants

| constant | distinct atoms | queries | sets | `is_extended_real` | strict 30-digit evalf |
|---|---:|---:|---:|---|---|
| `pi` (as `pi`, `pi/2`, `3*pi/2`, `2*pi`, `-pi/2`, ...) | 37 | 829 | 62 | True | ok |
| Float `1.5707963267948966` | 1 | 20 | 2 | True | ok |
| Float `1.5707963267948967` | 1 | 14 | 1 | True | ok |
| Float `1.571` | 1 | 14 | 1 | True | ok, value 1.5709991455... |
| Float `4.712` | 1 | 11 | 1 | True | ok, value 4.7119750976... |

Every Float query also contains `pi`. With sums split and rational factors
pulled out, `pi/2`, `3*pi/2` and `-pi` are all one variable, `pi`.
`c.evalf(30, strict=True)` returned without error for all five, with no
noticeable delay (this is not a timing claim). No `E`, `sqrt(2)`, `log(2)`,
`sin(1)` or `pi**2` occurs anywhere in the stream's unreadable atoms.

### 4. gate2 (2,863 frozen SymPy test queries)

0 queries are Uninterpreted and the plan oracle changes nothing. One query
has an unreadable atom (`Q.gt(X, 3) & Q.lt(X, 2)` as the proposition, with
a non-scalar `X`), and it is out of scope before any theory sees it.
Separately, the base run differs from the frozen answers on 8 lines. Seven
are only the label: the frozen file says `error:ValueError` and this
script says `error`. The eighth is the transfer answer `Q.prime(x)` given
`Q.prime(y) & Q.eq(x, y)`, which is True now. None of the 8 comes from
this measurement.

### 5. The explainer's section-4 cases

Confirmed on `main`: 36 stream queries over 3 assumption sets, all of the
form `A & Q.gt(t, -pi/2) & Q.lt(t, pi/2) & ...`, where `A` is
`Q.negative(x) & Q.positive(x)` (twice, 15 queries each) or
`Q.positive(x) & Q.zero(x)` (6 queries). Two corrections:

- On `stage-constants`, 12 of the 36 (6 in each of the first two sets) are
  constant propositions such as `Q.zero(pi)`. Item 1 answers those without
  the assumptions, so they never raise. **The plan adds 24 new
  ValueErrors (9 + 9 + 6), and SymPy's `ask` raises on all 24.**
- The inconsistency in these sets has nothing to do with the constant:
  `x` is negative and positive. They raise under the plan only because the
  session gets built at all. `Q.gt(t, -pi/2) & Q.lt(t, pi/2)` is
  satisfiable. The explainer's example `x > 3 & x <= pi/2`, a set that
  only the bounds make inconsistent, does not occur in the stream.

## How measured

`irr0_census.py stream|gate2 FILE OUT.json [--verify S] [--rest]` makes one
pass in stream order, with one `Engine` and one answer memo, as in the
replay:

- **base**: `sympy_api.ask` unchanged. A query counts as Uninterpreted when
  `Engine.ask` or `Engine.is_` raised `Uninterpreted`, detected by wrapping
  both methods, so the engine's failed-session cache is included.
- **static census**: every relation leaf of the proposition, and of the
  assumptions unless the proposition is constant-only
  (`_is_constant_proposition`), is checked against the adapters
  (`lra_adapter.interpret`, `EUFAdapter.parse`). Each unreadable atom is
  classified by a copy of `_lin` that recurses into closed sums and
  rational factors. The irreducible closed rest is type (a) if SymPy says
  it is extended real and finite. A closed non-rational factor of a
  symbolic product is (b), with `b:float` for a Float. Everything else is
  (c).
- **plan oracle**: every type-(a) atom of a query whose unreadable atoms
  are all (a) is rewritten. Each irreducible constant becomes a symbol
  `_irr_k`, one per constant, and the assumptions get
  `Q.real(_irr_k) & Q.lt(lo, _irr_k) & Q.lt(_irr_k, hi)`, with bounds from
  the strict 30-digit evalf widened by 1e-25 relative. For a constant-only
  proposition, the bounds alone are the assumptions. The rewritten queries
  go to a second `Engine`, in stream order. Limits: the unary facts of
  `pi` (`positive(pi)`) are not tied to `_irr_k`, and equalities EUF
  already reads are not rewritten. Both limits can only make the oracle
  answer less than the real build would.
- **verification**: SymPy's `ask` with a 5-second alarm on every distinct
  changed query, and with `--rest`, on every fully readable query the
  oracle leaves None.

Commands, run from the worktree (one process at a time):

    PYTHONHASHSEED=0 PYTHONPATH=.:/home/tilo/sympy:tools .venv/bin/python \
        agent-reports/scripts/irr0_census.py stream ~/.cache/satassume/stream.pkl OUT.json --verify 5 --rest
    PYTHONHASHSEED=0 PYTHONPATH=.:/home/tilo/sympy:tools .venv/bin/python \
        agent-reports/scripts/irr0_census.py gate2 ~/.cache/satassume/gate2-frozen.jsonl OUT.json

## What it means for the build

- **The gain is real but narrow**: about 105 more definite stream queries
  and 24 correct new errors. All of it comes from one constant (`pi`) in
  bounds of the form `x <op> k*pi`, plus four Floats. gate2 gains nothing.
  The refine scoreboard's 6 relation losses were not measured here.
- **Nonlinear handling does not matter for this data**: there are no
  `pi*x` atoms. The plan's rule that `x*pi` stays uninterpreted costs
  nothing today.
- **Call sites**:
  - `lra_adapter._lin`, the branch `if not e.free_symbols: ... raise
    _Unhandled(e)`, becomes: split closed `Add`s, pull out a rational
    coefficient (`as_coeff_Mul`), and add the irreducible rest as a term
    of the form. Without the split, `pi/2`, `pi` and `3*pi/2` become
    three unrelated variables, so `x = pi/2 & y = pi -> y = 2*x` cannot
    be proved, and each constant needs its own bounds.
  - The `raise _Unhandled(f)` in the `Mul` branch stays, as the nonlinear
    case.
  - `interpret` then returns `pi` among the terms. `Relations._interpret`
    guards with `real(u)` for every term, so the guard becomes `real(pi)`,
    a context-free fact of the rule base, which gives the rule "a
    constant is real iff SymPy says so". Check that `s.ensure(pi,
    {"real"})` decides it at the root and does not leave a free guard.
  - The bounds need a new hook. The adapter has no way to emit clauses, so
    `Relations._interpret`, where `s._emit` is available, should register
    `lt(lo, c)` and `lt(c, hi)` once per session and constant, with the
    adapter, on fresh aux variables, and emit them as unit clauses.
  - `LRAAdapter.shared_terms` will then contain `pi`, so equality sharing
    creates interface atoms `eq(pi, t)` for every other shared term. Watch
    the cost.
  - `Relations._link_later` skips numbers (`_is_number`), so `pi` gets no
    sign links. That is fine: the bounds carry the sign.
- **Pitfalls seen**:
  - A Float's value is its binary mpf at its own precision, not its
    decimal text. `Float('1.571')` in the stream evaluates to
    1.57099914551... (low precision), and `1.5707963267948966` and
    `...967` are two different constants. Bounds from `evalf` follow
    SymPy's value, which is sound, but `x <= 1.571` is then not
    `x <= 1571/1000`. Reading a Float as its exact rational
    (`Rational(f)`) is simpler and exact, but it is a choice about
    semantics.
  - Use `evalf(..., strict=True)` and assert bounds only when it succeeds.
    A closed expression that is exactly zero but not syntactically zero
    must not get bounds with a sign.
  - Only 26 of the 62 fully readable sessions gain anything. Most of the
    700 queries that stay None ask about things like `x*tan(t)` given
    bounds on `t`, which need knowledge that item 2 does not add (not
    counted by category).
  - The 24 new ValueErrors change the acceptance rule's error set. They
    are the expected sets, SymPy agrees on all 24, and they should be
    listed as allowed.
