# Agent report: irrational constants, stage 2, tuning the extra cost

- **Date:** 2026-09-25
- **Status:** two commits on branch `irrational-tune` (base `irrational-lra`
  f8d92a9). Answers identical to `irrational-lra` on every query of the
  refine stream. Timings on the Pi 5 (exclusive), SymPy `sympy-pin`,
  `PYTHONHASHSEED=0`.
- **Headline:** the branch's extra cost over main drops from +1.03 s to
  +0.80 s (Pi, best-of-3: main 2.667 s, irrational-lra 3.696 s,
  irrational-tune 3.459-3.490 s). What is left is almost all the price of
  the capability itself: the 663 queries that main answered by failing
  with `Uninterpreted` in 0.05 s now build and search relation sessions.
  The same queries with `pi` replaced by `355/113` (no constant term at
  all) take 0.78 s; the tuned branch takes 0.86 s.
- **Read this if:** you review or land `irrational-lra`, or ask why it is
  slower than main.

## 1. Diagnosis

Source: the Pi per-query logs of main and irrational-lra
(`tools/query_log.py` format), and local probes that wrap the solver.

The whole +1.0 s is in the 663 queries whose assumption set failed with
`Uninterpreted` on main (47 ms there, 1,094 ms on the branch); every
other query is unchanged. Of these, 551 end None (1,038 ms), 88 are
definite, 24 raise. Their sessions are reused normally; the time is
`Solver.entails`' two satisfiable searches per None answer.

None-answering searches compared (Pi logs):

| | queries | ms/query | decisions/solve | conflicts/solve | median vars |
|---|---:|---:|---:|---:|---:|
| main, all None searches | 3,115 | 0.70 | 5.7 | 0.06 | 122 |
| irrational-lra, the 663 new | 551 | 1.89 | 14.7 | 0.30 | 183 |

Cost per decision is the same (60 vs 64 us); these sessions are bigger
(trigonometric propositions with `x/pi`, `floor(x/pi + 1/2)`, `tan(x)`,
each with its three link atoms) and a satisfiable search decides every
free variable.

Decisions by variable kind (local, the 663 queries, 15,187 decisions):
node blocks of proposition subterms 3,927; aux (guard/selector) 3,233;
the symbol's block 2,853; `lt` atoms 2,118; **interface equalities
1,547** (687 of them `eq(pi, x)`, most others pairs with `pi` or the
trig terms); **number nodes 1,502 (`pi.polar` 1,002, `(1/pi).polar`
500)**.

Theory conflicts (331): 118 are the trichotomy of `x` (`x > 0`, `x < 0`,
`x = 0`), 43 the same for `tan`/`sin`/`cos`; about 80 involve a `pi`
bound (`x <= pi/2`, `x > 0`, `pi > lo`). The first kind is what any
relation session of this shape pays.

What is *not* the cost:

- **The bound atoms' precision.** Rebuilding the bounds on a 2**-12,
  2**-24 or 2**-64 relative grid (numerators of 4 to 22 digits) gives the
  same time (947-960 ms on the Pi for the 663 queries, noise level). The
  two bound atoms are single-variable bounds on `pi`, asserted once at the
  root; they are not measurable.
- **Transfer.** Predicate transfer is not engaged in any of these
  sessions.

**The floor, measured:** the stream with `pi` replaced by `355/113` in
exactly these 663 queries (rational relations, no constant term, same
sessions and propositions otherwise) takes 776 ms for them on the Pi,
12,541 decisions, 250 conflicts, 93 cone rebuilds.

## 2. What changed

Three avoidable pieces, each specific to the constant term, in two
commits:

1. `relations: constant terms get no guard node and no interface
   equalities` (2fba580)
   - A guarded atom's term that is a closed number the engine knows to be
     real context-free (`Engine.is_(u, "real")`) gets no guard literal and
     so no node: its `real` literal is true at the root, the literal
     would be false in every clause. This removes the `pi` node (and its
     free `polar` variable) that exists only for the guard. The bounds
     are still asserted.
   - A pair with a non-rational constant term gets no interface equality
     (`eq(pi, x)`). Such an atom would carry an equality with the
     constant between LRA and EUF (`x = pi` derived by LRA reaching
     `f(pi)`); on the stream it decides no query. A relaxation, never
     unsound; on main these pairs did not exist (the constant was never
     an LRA term).
2. `engine: irrational constant nodes do not count towards the cone
   threshold` (d3f4190). `x/pi` brings the node `1/pi`; counted as
   pollution it sent 183 instead of 113 queries to a cone rebuild. The
   count of irrational constant nodes is kept per session (O(1) per
   query). Other queries: unchanged (no answer difference, "other" time
   equal within noise).

Per step on the Pi, the 663 queries (two runs each, ms):

| variant | ms | decisions |
|---|---:|---:|
| irrational-lra | 1,083 / 1,100 | 16,340 |
| + no interface equalities with constants | 1,034 / 1,021 | 14,862 |
| + no guard node for known-real constants | 956 / 946 | 13,857 |
| + constants not counted as pollution (= irrational-tune) | 869 / 854 | 13,287 |
| rational stand-in (`pi` -> `355/113`) | 777 / 775 | 12,541 |

(Queries outside the 663: 2,511-2,620 ms in every variant.)

Local, the 663: conflicts 357 -> 279, cone rebuilds 183 -> 113.

## 3. Checks

- **Answers:** every one of the 13,877 answers equal to irrational-lra
  (dumped and compared, local and Pi). `tools/ab.py irrational-lra
  irrational-tune --rounds 1 --allow-more-definite` locally: both sides
  24 errors, 549 more definite (same queries).
- **Suite** (local, per file): all pass except the known
  `test_shared_facts.py::test_cached_sympy_fact_does_not_make_assumptions_inconsistent`
  (2 params). `tests/test_lra_constants.py`: 33 passed.

## 4. Pi: main vs irrational-tune

`tools/ab.py` on the Pi, `--rounds 3 --allow-more-definite`:

| run | main best | tune best | change |
|---|---:|---:|---:|
| main vs tune #1 | 2.667 s | 3.469 s | +30.1% |
| main vs tune #2 | 2.667 s | 3.490 s | +30.9% |
| irrational-lra vs tune | 3.696 s | 3.459 s | -6.4% |

All rounds within 0.06 s of their side's best. (irrational-lra against
main was +38%, 2.680 against 3.698 s, in the coordinator's runs.)

## 5. The floor

Of the remaining +0.80 s, about +0.73 s is what the 663 queries cost
once their sessions exist at all: the rational stand-in, with no
constant term anywhere, takes 776 ms against main's 47 ms. It is the
ordinary cost of relation sessions of this shape (a symbol bounded on
both sides, propositions over `tan`, `floor(x/pi + 1/2)` and the like,
two satisfiable searches for every None), the same per-decision cost as
any other search in the stream. Nothing constant-specific is in it.

The last ~0.085 s (860 against 776 ms) is the shape the constant forces:
`x/pi` is a nonlinear product, so `1/pi` and `pi` are nodes of the
proposition (their `polar` is decided in search), and `x <= pi/2` is a
two-variable row instead of a bound on `x`. Neither is removable without
losing what the stage reads.

So: avoidable cost removed was 0.23 s of 1.03 s; the floor of the
capability on this stream is about +0.8 s (+30%), nearly all of it
relation reasoning that main skipped by giving up.

## 6. Not done / options for the owner

- A search-side reduction for None answers in relation sessions (the
  0.73 s) is a general engine question, not specific to constants; the
  perf rounds 2-3 measured the search-side plan items and dropped them.
- The bound precision can stay: it costs nothing measurable.
