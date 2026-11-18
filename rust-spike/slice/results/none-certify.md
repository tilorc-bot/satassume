# Class (i) None answers: are the two models real witnesses? (issue 323, read-only)

sa-port-325, 18 Nov 2026. Source read: report/none-classes 4cb3642 (package source-equal to rust-slice 5f53735).
**No package code changed. SymPy is used only in the offline scratch check, never at query time.** There is no count
build in this step: the models are read by a driver that wraps five methods in its own process (`tools325/cap325.py`),
so nothing is patched, and nothing is committed to the package. **Shares from shared-lease runs are not wall times**:
every time below is 322's quiet-lease S1 median for the query (pareto1, 12 rounds, both switches on unless said); no new
timing was taken.

## What the numbers say

1. **Nearly every class (i) None is a real independence.** An exact witness pair (a point where the assumptions hold
   and the proposition is true, and one where it is false) exists for 370 of 418 dev queries (88.5%) and 2165 of 2200
   fuzz queries (98.4%).
2. **The engine's own models are poor witnesses.** Read as points, both models certify in 204 dev (48.8%) and 416 fuzz
   (18.9%) queries. The rest fail or cannot be checked at the model's point, and a simple point then certifies most of
   them. A model is a type assignment more than a point: it puts symbols at infinity (so `x + y` is nan), and its
   blocks often describe no number.
3. **The room for a wrong or incomplete None is small.** Not certified and not uncheckable: 8 dev queries and 1 fuzz
   query. By my reading 4 or 5 of them have a definite true answer (dev 11, 12, 1204, perhaps 788; fuzz 732).
4. **A session-free check would find both witnesses for 88.0% (dev) and 98.0% (fuzz) of class (i)**, a median of 3 and
   8 exact substitutions. The sessions of those queries are 39.3% of dev time and 72.9% of fuzz time. The check's own
   cost is not measured, so this is a ceiling, not a saving.
5. **No answer is contradicted.** The same search over all 4985 queries finds no definite answer with a witness
   against it and no ValueError with a point satisfying the set.

## Method

- **Pass.** `tools325/cap325.py` runs dev (1985) and fuzz seed 424242 (3000) in recorded order through the pure-Python
  package (no Rust backend), `PYTHONHASHSEED=0`, on orion. Digests equal the count build's: dev `31cd0945c07f02a6`,
  fuzz `173502b6ef285ad6`. The class is 322's (`tools322/sum322.py` `klass` on 322's rows); all 418 and 2200 class (i)
  queries show a deciding entailment with two satisfiable solves here too. The Rust arm's models were not read: the
  models are the Python solver's.
- **Exact evaluator** (`tools325/exact325.py`). A point is substituted into the query's original proposition and
  assumptions (`xreplace`, so only SymPy's arithmetic on explicit numbers runs; no assumption query). A term's value
  is decided only when it is a rational, +oo, -oo, zoo, a + b*I, a + b*pi (sign by rational bounds on pi) or one of six
  named constants; predicates are decided by a hand-written table of the 14 basis predicates, derived ones by
  `rules.DEFINITIONS`. Everything else is **uncheckable** with its reason (nan, a transcendental value, a function
  value such as sin(1), an order relation at a value that is not an extended real, `polar`). Truth is three-valued.
- **Model point (a).** For each satisfiable solve of the deciding entailment: a symbol takes its LRA value when its
  block says finite and extended real, else a representative with the block's row; the combination that reproduces
  most blocks of the model is kept. Symbols outside the session (the relevance split) get the first simple values
  that keep the assumptions true. A heuristic picks the point; the substitution decides.
- **Search (b).** Before any session: per symbol 0, 1, -1, 2, -2, 1/2, -1/2, the exact roots of the query's linear
  atoms with their midpoints, the query's constants, then infinities, a few complex values and more rationals;
  values a one-symbol assumption makes false are dropped; points are tried simplest first, at most 2000.
- Full output `tools325/sum325.out.txt`; rerun with `tools325/run325.sh OUT` (30 s). Rows: orion
  `~/sa-rust-ids-work/sa-port-325/run3/`.

## (a) The two polarity models, substituted exactly

Counts are class (i) own rows; time is the queries' S1 time and its share of the workload.

| row | dev | dev time | fuzz | fuzz time |
|---|---|---|---|---|
| certified both ways | 204 (48.8%) | 115.5 ms, 17.3% | 416 (18.9%) | 778.3 ms, 13.2% |
| one way | 111 (26.6%) | 122.0 ms, 18.3% | 391 (17.8%) | 859.9 ms, 14.6% |
| neither | 8 (1.9%) | 12.9 ms, 1.9% | 238 (10.8%) | 519.6 ms, 8.8% |
| uncheckable | 95 (22.7%) | 62.3 ms, 9.4% | 1155 (52.5%) | 2228.8 ms, 37.8% |

Of the certified, the point reproduces every block of the model in 173 dev and 288 fuzz queries; 158 and 345 use
field arithmetic only.

Why a side is not certified (sides, not queries):

| reason | dev | fuzz |
|---|---|---|
| fail: the model's point gives the proposition the other value | 96 | 274 |
| fail: the assumptions are false at the model's point | 31 | 602 |
| uncheckable: nan at the point (an infinity minus an infinity, zoo) | 76 | 1375 |
| uncheckable: a transcendental constant or a function value | 61 | 114 |
| uncheckable: an order relation at a value that is not an extended real | 4 | 158 |
| uncheckable: other | 4 | 7 |

A failed side says the point I read from the model is not a witness. It does not say the None is wrong: the model
fixes types, and where no relation mentions a symbol any number of that type is "the model's point". Why a point
fails the assumptions was not resolved further (no LRA value of a closed term such as pi is involved: 0 cases; the
point does not reproduce a block in 13 of 32 dev and 226 of 625 fuzz failed sides).

**The same queries with any exact witness** (a model's point or a searched point, per side):

| | dev | fuzz |
|---|---|---|
| exact witness pair exists | 370 (88.5%) | 2158, and 7 more by hand-picked points: 2165 (98.4%) |
| uncheckable: the missing side is undecided at some point tried | 40, 36.4 ms, 5.5% | 34, 69.3 ms, 1.2% |
| unresolved: every point tried that satisfies A gives p one value | 8, 13.3 ms, 2.0% | 1 |

The 7 fuzz rows (1056, 1217, 1840, 2275, 2283, 2612, 2687) were search misses: `tools325/hand325.py` certifies each
with a point I picked (output `hand325.out.txt`).

**Unresolved, to follow up (workload, id):**

- dev 11 `Q.even(k/2 + 1/2)` and dev 12 `Q.odd(k/2 + 1/2)` under `Q.odd(k) & Q.even(k/2 - 1/2)`: k is 1 mod 4, so the
  answers are False and True. Incomplete Nones (my reading).
- dev 1204 `Q.infinite(arg(x)/(2*pi) + 1/2)` under `Q.nonzero(x)`: False at all 32 points; False by my reading.
- dev 788 `Q.integer(2*re(x)*im(x)/pi)` under `0 <= x**2 <= pi/2`: True at all 7 decided points; True if the set
  forces x real (my reading).
- dev 795, 796, 797, 798 (parity of `floor(x**2/pi + 1/2)`, same set): the other side is at x**2 = pi/2, a point the
  evaluator cannot decide. Independent by my reading; listed because no exact point shows it.
- fuzz 732 `Q.eq(x + 2*y + 1, 2*x)` under `Q.finite(y) & Q.gt(y, -1) & Q.eq(2*x + 2, 2*x - 1)`: the set holds only at
  x = +-oo, where the proposition is True under SymPy's `oo == oo`. True, or the set is meant to be inconsistent; a
  question about equality at infinity, not about the solver.

**Uncheckable ids.** Dev (40): 211 247 498 537 550 555 567 568 755 760 779 787 791 810 823 933 1099 1122 1123 1124
1125 1126 1130 1132 1439 1458 1475 1476 1493 1495 1496 1497 1498 1499 1506 1510 1517 1519 1525 1527 (trig, exp, arg and
sign values). Fuzz (34): 304 339 362 384 452 491 519 559 727 843 887 929 1072 1109 1285 1307 1375 1500 1509 1661 1795
1881 1920 2119 2173 2228 2291 2300 2563 2615 2834 2897 2907 2928. The fuzz ones I read (2834, 2928: `x - 1 >= x - 3/2`
under a bound on y) are true for every extended real x and undefined for a complex x: whether None is right there
depends on what a relation means off the real line.

**Every one-way and neither query by workload and id**: `tools325/lists325.txt` (1998 rows: all class (i) queries not
certified both ways by their models, with each side's verdict, whether the search found it, and the end state).

## (b) A witness before any session

| | dev | fuzz |
|---|---|---|
| class (i) with both witnesses from simple points alone | 368 of 418 (88.0%) | 2157 of 2200 (98.0%) |
| their session time, both on | 262.0 ms: 83.8% of class (i), 39.3% of the workload | 4294.7 ms: 97.9%, 72.9% |
| the same, default arm | 289.9 ms, 38.4% | 4627.5 ms, 72.8% |
| substitutions until both found: median, 90%, 99%, max | 3, 25, 136, 226 | 8, 70, 373, 945 |
| at a cap of 8 substitutions | 294 (70.3%), 195.4 ms, 29.3% | 1096 (49.8%), 2098.5 ms, 35.6% |
| at a cap of 32 | 337 (80.6%), 231.1 ms, 34.7% | 1748 (79.5%), 3413.9 ms, 57.9% |
| at a cap of 128 | 359 (85.9%), 250.3 ms, 37.6% | 2044 (92.9%), 4056.1 ms, 68.8% |

- **This is the session time skipped, not a saving.** The check costs something on every contextual query, including
  the definite ones that never find a pair. Its cost in Rust was not measured (in SymPy a substitution took about
  65 us, 23.8 s for fuzz's 366,961; that is this script on a shared machine, not a wall time).
- **The check's own model** (needs the session, skips only the two polarity solves): held for 377 dev and 2054 fuzz
  queries; its point satisfies the assumptions and decides the proposition exactly in 305 and 1667; the other side is
  then found by search in 288 and 1645. 323 showed the polarity solves are not where the time is, so this variant
  buys little.
- **Answers.** The path returns None only when both witnesses verify, and a verified pair proves None. Over every
  query: 557 + 536 dev and 204 + 202 fuzz definite answers and 207 fuzz ValueErrors, none contradicted. The search does
  fire on None answers (779 of 892 dev, 2338 of 2387 fuzz find both), so the zero is not a counter that cannot fire.
- **Class (ii) on the side:** 159 of 165 fuzz Nones where BRANCH_BUDGET ran out inside a polarity solve, and all 5
  where it ran out elsewhere, have an exact witness pair. They are real independences, as 323 read from 12 of them.

## (c) Proposals

1. **Not supported as a change yet; supported as the next measurement: a witness check before the session
   (answers identical, speed only).** Up to 32 exact substitutions of simple points; return None only when both
   verify, otherwise go on exactly as now. Ceiling: 34.7% of dev and 57.9% of fuzz S1 time. What is missing is the
   cost: it needs an exact evaluator of converted terms in Rust (rationals, the infinities, refuse everything else),
   which is new runtime code, and a quiet-lease S1 with it. It is an optimisation, so it comes after "something that
   works"; it adds nothing SymPy could not use, since it reads only the query. Where it sits against the memos and
   the routing of spec.md s1 is undecided.
2. **Follow up the unresolved list** (dev 11, 12, 788, 1204; fuzz 732): each is a rule or a semantics question, and
   any rule needs its own soundness proof for Tilo. That is the whole measured size of the wrong-or-incomplete None
   problem in class (i) on these workloads, apart from the 74 uncheckable queries.

Not proposed: using the engine's models as witnesses (they certify 48.8% and 18.9%); certifying at query time with
SymPy (ruled out). 323's proposal 1 stays parked.

## Limits

- Two workloads, one hash seed, the pure-Python solver's models (answers equal the Rust arm's by digest; its models
  were not compared).
- "Exact" rests on SymPy's arithmetic for explicit numbers, including its conventions at infinity (`oo == oo`,
  `oo >= oo`, `1/0 = zoo`), and on my table for the 14 predicates. Issue 247 applies: these are not ground truth
  either; the table and conventions are short enough to review (`exact325.py`).
- A searched pair proves independence; a missing pair proves nothing. "Unresolved" readings are mine, not proofs.
- The 74 uncheckable queries (dev 40, fuzz 34) are not counted as right or wrong.
- Exact repeats and memo answers carry the class of their first occurrence and were not re-certified.
