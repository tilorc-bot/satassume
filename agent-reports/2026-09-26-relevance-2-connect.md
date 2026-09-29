# Agent report: relevance (next-steps item 3), stage 2, what connects

- **Date:** 2026-09-26
- **Status:** fixes the review of stage 1 (LAND WITH FIXES) on branch
  `relevance` (base `irrational-tune` at `064e59e`). A set or a query with
  a relation is no longer split (`sympy_api.RELATIONAL = "whole"`). That
  removes defect (d), and every other lost answer of the same kind found
  here. **-8.1% / -8.4% on the Pi against `irrational-tune`** (two more runs:
  -8.6%, -7.9%). That is about 1% slower than `c04bfc8`. Stream answers are
  identical to `064e59e`, gate2 0 changed, suite only the known failures,
  fuzz 10000-13999 clean.
- **Commits:** `1240d4c` (fuzz tool: one-sided errors), `de2cd52`
  (`RELATIONAL`, tests), `28392d6` (fuzz `--relational`, this report) and
  a report update. Not rebased onto item 2's final `f3fe6a8` (section 6).
- **Read this if:** you land relevance, or you want to split sets with
  relations again.

## 1. What connects terms through the engine

Stage 1 keyed components by symbols, undefined-function classes and closed
non-Rational terms. The review found answers that `irrational-tune` gives in
fresh engines and the branch did not (None). Probes on `064e59e`, one fresh
engine per query (`x, y, z` plain; `X, Y, Z` real; `bj(t) = besselj(1, t)`):

| assumptions | query | base | stage 1 |
|---|---|---|---|
| `x = 2, y = 2, positive(sin(y))` (also bj) | `positive(sin(x))` | True | None |
| `zero(x), y = 0, positive(bj(y))` | `positive(bj(x))` | True | None |
| `x = 2, positive(sin(2))` | `positive(sin(x))` | True | None |
| `~polar(2), x = 2` | `polar(x)` | False | None |
| `x + 1 = 3, y = 2, positive(sin(y))` | `positive(sin(x))` | True | None |
| `2*x = 4, y = 2, positive(sin(y))` | `positive(sin(x))` | True | None |
| `X <= 2, X >= 2, Y <= 2, Y >= 2, positive(sin(Y))` | `positive(sin(X))` | True | None |
| `X <= 0, X >= 0, Y = 0, positive(bj(Y))` | `positive(bj(X))` | True | None |
| `X = Y + 2, Y = 0, Z = 2, positive(sin(Z))` | `positive(sin(X))` | True | None |
| `nonnegative(x), nonpositive(x), y = 0, positive(bj(y))` | `positive(bj(x))` | True | None |
| `x = 2, y = 2, positive(bj(y + 1))` | `positive(bj(x + 1))` | True | None |
| `polar(y), x = 2, y = 2` | `polar(x)` | True | None |

The mechanism, from `relations.py`, `euf_adapter.py` and `theory.py`:

- **EUF merges terms that are pinned to a common value.** A user equality
  `x = 2` puts x and 2 in one class, so `x = 2` and `y = 2` merge x and y.
  Every vocabulary argument `e` of a session with relations gets the link
  `zero(e) <-> eq(e, 0)`, so `zero(x)` and `y = 0` merge x and y too.
- **Values that LRA derives also get there.** Equality sharing
  (`EqualitySharing`) creates an interface atom `eq(a, b)` for every pair
  of terms both LRA and EUF know (x and y, through the links' `eq(e, 0)`).
  Search decides these atoms, and LRA refutes `X != Y` when both are fixed
  to the same value. So `X + 1 = 3`, `2 <= X <= 2` or `X = Y + 2, Y = 0`
  merge X with another term fixed at 2, whatever Rational spells the value.
  The owner's earlier decision (LRA-derived equalities are not *propagated*
  to EUF) does not stop this: the interface atoms are decided in search,
  not propagated, and they exist.
- **Values that the rule base derives, too.** `nonnegative(x) &
  nonpositive(x)` gives `zero(x)`, and the link gives `x = 0` in EUF.
- **What the merge carries.** Congruence merges `sin(x)` with `sin(y)` or
  `sin(2)` (any head: `besselj`, `Add`, `Mul`), and predicate transfer
  (engaged by any user equality) then shares their facts. Between the
  pinned terms themselves the only fact not already decided by the value is
  `polar`.
- **What does not connect.** Without a relation in the set or the query,
  the session has no links and no theory, so nothing merges. Transfer does
  not bring the facts of a Rational to a term LRA pins to it (`2 <= X <= 2`
  does not give `prime(X)`), because numbers are not interface terms.
  Bounds that only say `1 < X < 3, integer(X)` do not fix X either.

So a key made of Rationals cannot describe the connection exactly. The
value that joins two components can come from arithmetic (`x + 1 = 3`
against `y = 2`), from order relations (`<=` and `>=`), or from no Rational
at all (`nonnegative & nonpositive`).

## 2. The two rules, and what they cost

`sympy_api.RELATIONAL` selects the rule. Changing it needs `_KEYS.clear()`,
because the key memo depends on it.

**`"whole"` (the default, chosen).** A set with a relation (or a keyless
relational conjunct), or a query with a relation, is not split. It is
answered under the whole set, exactly as without relevance. Everything else
is split as before. A set without relations has no theory in its session, so
there nothing merges across components and the stage-1 argument holds. For
relational sets the answers are the base's by construction. This fixes all
of the table in section 1.

**`"rationals"` (the narrow rule, measured, not the default).** Relational
sets still split, with these Rationals as extra keys: a side of an equality
(`Q.eq`, `Q.ne`, `Eq`, `Ne`), the 0 of `Q.zero`, and the Rationals inside a
closed term (`sin(2)` has keys `sin(2)` and 2). A Rational that is the
argument of a predicate (`polar(2)`) was a key already. The query's own
Rationals count the same way. It fixes the four cases of the review (first
four rows). It does **not** fix the rows from `x + 1 = 3` down to
`nonnegative & nonpositive`: these stay None, which is lost against the
base. Rationals that only occur in an order relation are not keys, and
making them keys would still miss `x + 1 = 3` against `y = 2` and
`X = Y + 2, Y = 0` against `Z = 2`.

On the stream (13,877 queries, local, one pass):

| | stage 1 (`c04bfc8`) | `"rationals"` | `"whole"` | `irrational-tune` |
|---|---:|---:|---:|---:|
| queries answered by a smaller part | 3,244 | 3,190 | 3,077 | |
| of them, set or query with a relation | 167 | 163 | 0 | |
| engine queries | 4,472 | 4,523 | 4,556 | 6,311 |
| searches | 2,731 | 2,743 | 2,784 | 3,750 |
| consistency checks | 179 | 179 | 170 | |

Only 167 of the 3,244 split answers were under a relation (43 relational
sets, 124 relational queries). This is why the broad rule costs little.

Pi (exclusive, `tools/ab.py`, 3 rounds, best-of):

| pair | runs |
|---|---|
| `irrational-tune` → final (`"whole"`) | **-8.1%, -8.4%**, -8.6%, -7.9% |
| `irrational-tune` → `"rationals"` | -8.6%, -8.8% |
| `irrational-tune` → `c04bfc8` (stage 1) | -8.6%, -10.1% |
| `irrational-tune` → `b23bcc1` (stage 1 before CHECK_SEARCH) | -9.6%, -9.6% |
| `c04bfc8` → final | +0.8%, +1.2%, +1.3% |
| `"rationals"` → final | +0.9% |
| final with `CHECK_SEARCH = False` → final | +0.5%, -0.0% |

- Of stage 1's saving (about -9.5% on this day, -10% in stage 1's report),
  about -8.3% survives with `"whole"`. `"rationals"` would keep about -8.7%,
  but it keeps the lost answers of section 1.
- **`CHECK_SEARCH` (item 3 of the review)** costs 0-0.5%, which is within
  noise. The two `c04bfc8` runs (-8.6%, -10.1%) show how much a single
  run of 3 rounds can move.
- `ab.py` prints "ANSWER MISMATCH" on every item-2 side because of the 24
  errors against the recording (made on `main`). Both sides show the same
  24 errors and 549 more definite answers.

**Why `"whole"`.** The owner's rule is that an answer lost against the base
is a defect. `"rationals"` loses answers that the base gives in fresh
engines (section 1). An exact rule for relational sets would have to know
which terms LRA or the rule base can fix to a value, and which heads
congruence can join. That means roughly every component with a relation or
a sign fact, plus head keys (`sin`, `Add`, `Mul`) across them. For 167
queries (about 1% of the replay) this is not worth the argument. The
relational whole-set check (`_consistent` with search) is only reached
under `"rationals"` now.

## 3. Soundness and completeness after the change

- Sets and queries with a relation are answered exactly as by
  `irrational-tune` (the same `_engine_ask` on the same set). They also
  raise exactly as before.
- Sets without a relation, under queries without one: the session has no
  links, no EUF and no LRA, so stage 1's independence argument (report 1,
  section 2) applies without the "approximately" of its relations
  paragraph. The per-component check (with `CHECK_SEARCH`) certifies
  consistency as before.
- Tests (`tests/test_relevance.py`, 34 pass): the 12 rows above are
  `PINNED` (the review's four plus `polar`) and `DERIVED`. In the default
  mode, each is not split and gives the base's answer on both sides. Under
  `"rationals"` (fixture), the `PINNED` ones connect. The stage-1 tests of
  splitting by relations run under the `"rationals"` fixture.

## 4. One-sided errors in the fuzz (`tools/relevance_fuzz.py`)

The tool used to file "part None, whole error" as `whole-only`, which is
allowed. It now classifies every one-sided error:

- `error-comp-none` / `error-whole-none`: an error on that side, None on
  the other;
- `error-comp` / `error-whole`: an error against a definite answer.

It lists each with the answers of two fresh engines (`fresh`: [comp,
whole]), counts `KIND-fresh` when those still differ, and exits 1 on a
contradiction or on a one-sided error that fresh engines reproduce.
`--relational` sets the mode of the relevance side.

The 10 pairs that stage 1 hid, re-run on `c04bfc8` with the new tool:

| seed | set | pairs | fresh [comp, whole] |
|---|---|---|---|
| 1731 | `finite(z) & integer(2*y) & (v + 1 <= 1/2)` | 2 | [None, None] |
| 2445 | `nonnegative(y) & rational(z**2) & (u + v < u) & ~odd(z + 1)` | 1 | [None, None] |
| 4901 | `negative(z) & ~rational(y) & (v + 1 < 1)` | 5 | [None, None] |
| 9312 | `~zero(x) & nonzero(2*u) & ~ne(y, v + y)` | 1 | [None, None] |

(9 in 1000-5199 and 1 in 8000-9399, as the review counted.)

- **Confirmed for all 10.** Each set is inconsistent only through the facts
  declared on `v` (positive): `v + 1 <= 1/2`, `u + v < u` and `v + 1 < 1`
  need `v < 0`, and `y = v + y` needs `v = 0`. In a fresh engine without
  relevance, the queries about v (`positive(v)`, `real(v)`, `zero(v)`)
  raise. The fuzz's queries about other symbols give None on both sides.
  The whole side raised for them only after the seed's earlier queries (its
  fact cache and sessions). So the error is history-dependent on the whole
  side, and the comp side agrees with a fresh whole engine.
- All four sets hold a relation. With `"whole"` they are no longer split,
  and the same seeds give identical answers on both sides.

## 5. Gates (final code)

| gate | result |
|---|---|
| stream answers, `064e59e` vs final, all 13,877, exact, errors included (local) | **identical** (24 errors on both) |
| `tools/ab.py 064e59e final --rounds 1 --allow-more-definite` (local) | both 24 errors, 549 more definite |
| gate2 `--allow-more-definite` | 0 changed, 1 more definite (#2860, out:relation), as before |
| suite, 3 chunks | all pass except the known `test_shared_facts.py::test_cached_sympy_fact_does_not_make_assumptions_inconsistent` (2 params) |
| `relevance_fuzz` 10000-13999 (8 chunks), final code | 96,000 queries, **all the same** (4,778 answered by a part); 0 in every one-sided category |

For comparison, `--relational rationals` on seeds 10000-10999 (24,000
queries, 6,897 answered by a part) gives 3 one-sided errors in seeds 10022
and 10257. All of them are under sets with a relation and involve `v`:
- `error-whole-none` ×2, fresh [None, None];
- `error-whole` ×1 (`Q.rational(u) | Q.gt(2*u, 1)`: part True, whole
  error), fresh [True, True].

None of them reproduces in fresh engines. The default rule does not split
these sets.

## 6. Pi hygiene

Item 2's final cost (the coordinator's request), same Pi, 3 rounds, best-of:

| pair | runs |
|---|---|
| `main` before item 2 (`2457d1b`) → `irrational-tune` `f3fe6a8` | +29.1%, +30.1% (2.68 → 3.46-3.49 s) |
| `main` `c8361d7` (item 2 landed) → `irrational-tune` `f3fe6a8` | +0.3%, +0.2% (same code in `satassume/`) |

**Not rebased.** The coordinator asked for `relevance` to be rebased onto
`irrational-tune` `f3fe6a8`, or onto main, before the final gates and
timing. Both the rebase and a merge were refused by this session's
permission classifier. Every gate and timing above is on `relevance` as
it stands, on `064e59e`. The rebase is left to the owner. Item 2 since
`064e59e` touched `lra_adapter.py` and a test, and `sympy_api.py` not at
all. Once the branch is rebased, the gates should be re-run.

Bundles `/tmp/relfix-1.bundle`, `/tmp/relfix-2.bundle`; refs `refs/remotes/land/relfix-{final,tune,c04,main,tune2}`
in `/work/src/perf-work`; worktrees `/work/src/wt-relfix-{tune,final,rat,nocs,c04,b23,main,tune2,pre}`
(`rat` and `nocs` are `de2cd52` with the flag edited in place); logs
`/tmp/relfix-ab*.log`, script `/tmp/relfix-ab.sh`. All removed afterwards.
The two idle `claude` processes were not touched.

## 7. Risks

- **Lost saving:** about 1% of the replay against stage 1. It can come back
  later with a rule that is exact for relational sets (section 2).
- **The fuzz exercises the split less now.** Most fuzz sets hold a relation,
  so only about 5% of fuzz queries are answered by a part (585 of 12,000
  in one chunk). Relation-free splitting is what the stream uses (3,077
  queries). `--relational rationals` keeps fuzzing the other rule.
- `"rationals"` stays in the code as the measured alternative, and so does
  its relational consistency check. Remove both if nobody wants them back.
