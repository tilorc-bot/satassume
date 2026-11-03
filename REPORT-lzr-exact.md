# Lazy links: why fuzz 424242 lost 12 answers, and the exact fix (sa-lzr-4)

Base: lazy-proto 9914059. No timing was done in this step. Counts and answers come from orion.

## Cause (one cause for all 12)

Take #2210: `Q.nonzero(x + 1/2)` under `Q.gt(x,1) & Q.lt(y,1) & Q.le(x + y - 3/2, 1/2 - y)`.
The negation's check accepted this model:

* `x = +oo` (extended_positive, not finite),
* `y = -oo`,
* `e = x + y - 3/2` extended_real and extended_negative,
* the link of `e` active and **unbuilt**.

Building only that one link makes the answer True again. Building any one of the other
four links leaves it None (one process per subset).

The full link set makes this model UNSAT through **clause 2** (`Relations._order_infinite`,
"infinite terms") of the link atom `lt(e, 0)`. In `e`, `x` has coefficient +1 and is
`positive_infinite`, so it pushes `e` up. Clause `positive_infinite(x) -> ~lt(e, 0)` then
holds, and the link `extended_negative(e) <-> lt(e, 0)` turns it into
`~extended_negative(e)`. In SymPy terms, `oo - oo` is nan, which is not below 0. Clause 2 is
the only unguarded theory constraint that a link adds over infinite terms.

`_disagree` missed it. Its LRA part runs only when every term of `e` is a finite real in M
(`real`). When a term was infinite it skipped LRA, and nothing else evaluated clause 2 of the
link atoms. So the check reported no disagreement.

**Classification:** with the fix below, all 12 return the 9bafaa5 answer, and the new reason
`lra_inf` fires in every one of them. The table counts how often each check sent a link to be
built for that query:

| # | lazy now | lra_inf | other reasons in the same query |
|---:|---|---:|---|
| 52 | False | 1 | lra_sign 1 |
| 227 | True | 1 | lra_sign 1 |
| 509 | False | 1 | |
| 646 | False | 1 | lra_sign 1 |
| 1442 | True | 2 | |
| 1742 | True | 1 | |
| 1891 | False | 1 | atom 1 |
| 2010 | False | 1 | lra_sign 1, euf 1 |
| 2166 | True | 1 | lra_sign 1 |
| 2210 | True | 1 | lra_sign 2 |
| 2403 | True | 1 | |
| 2866 | True | 1 | lra_sign 1, lra_int 2 |

On 9914059, `lra_inf` did not exist and these 12 were None. No second cause is needed:
`lra_inf` alone restores all 12, and fuzz is 3000/3000 identical.

## Fix (`satassume/relations.py`, +43 / -7 lines incl. docstrings)

* `_order_infinite(var, sides, emit=None, lits=None)`: the clause generator itself is not
  changed. Where it emits and where it gets a term's (positive_infinite, negative_infinite,
  extended_real) variables are now parameters. The defaults (`session.emit`, the new
  `_inf_lits`, which does the same `ensure` + `var` as before, in the same order) leave the
  eager build unchanged.
* `_inf_disagree(ad, e, want, M)`: for each of the two link atoms `0 < e` and `e < 0` it runs
  the **same** `_order_infinite` with:
  * a collecting `emit`;
  * `lits` that give each term pseudo-variables valued from M's basis
    (`positive_infinite = extended_positive & !finite`, as in `rules.DEFINITIONS`);
  * the atom valued as the link makes it (`extended_positive(e)` and `extended_negative(e)`
    in M).

  If any clause is violated, it reports a disagreement. It skips an atom where `_interpret`
  emits no clauses 2: `order_sides` is None, or `e` is its own term. If a term has no node,
  M cannot value it, so the link is reported as disagreeing and gets built. That is a build
  for a proven cause, not an unconditional one.
* `_disagree` calls it when the LRA form exists but some term is not a finite real in M
  (reason `lra_inf`).

### Why the check is now exact for this cause

Take an active unbuilt link `e` where some term `u` of `e`'s linear form is not a finite real
in M. Building the link would add these constraints:

1. **The link clauses.** They define the atoms' values: `gt = P`, `lt = N`, `eq = Z`.
2. **Clause 1** of the two lt atoms. `_interpret` leaves it out for link atoms: the rule base
   already implies it (`extended_positive`/`extended_negative` imply `extended_real`).
3. **Clause 2** of the two lt atoms. This is now evaluated literally on M, by the generator
   the build itself uses.
4. **The LRA atoms.** These are `r <-> t` for the order atoms, the twin `e = 0` of
   `eq(e, 0)`, and the integrality clause. Each is guarded by `real(u1) & ... & real(uk)`
   over the same term list, so M satisfies every one, since one guard literal is true. The
   fresh theory atoms `t`/`i` are constrained by nothing else, so their polarities can follow
   any LRA model.
5. **Trichotomy.** It is not built between the two link atoms of one term. A pre-existing
   atom equal to a link atom is checked by step (1) of `_disagree` against M.
6. **`_eq_infinity`.** It only applies to an `oo`/`-oo` side, and `e` has none: a form with
   `oo` is not read, which gives `lra_unread` and a build.
7. **EUF reading `eq(e, 0)`, and transfer polarity.** These are unchanged checks (3) and (4)
   of `unbuilt_disagree`. They do not depend on finiteness.

So every constraint that building the link adds is either satisfied by M or detected. With
every term a finite real, clause 2 is vacuous. Every push literal is false, and `e` has no
`oo` summand. The existing LRA sign/integrality check and the scratch replay apply as before.

## Interface equalities in these cases

They do arise. #2210's session has the interface atom `eq(x, y)` from `_share`, and x and y
are the only terms in all 12 queries. But under this cause they cannot change the verdict:

* The LRA twin of an interface equality carries the term guard `real(a) & real(b)`, as every
  LRA atom does. In all 12 the deciding term is infinite in M, so the twin is vacuous.
* EUF reads the atom's own variable, which EUF check (3) covers.

The general case is still open, and this step did not touch it. In that case all terms are
real, and an unbuilt link makes a term newly shared between LRA and EUF, so the
`IL(u) & IE(u)` guard of an interface equality would switch on only after the build.
Neither dev nor fuzz 424242 shows a case that depends on it: dev 1985/1985 and fuzz
3000/3000 are identical. The exactness argument for that case still has to be written, or
the case still has to be checked, before lazy links can be called exact.

## Regression test

`tests/test_lazy_links.py` has these tests:

* **The 12 queries, run on fresh engines (`DictCache`).** Each test sets `relations.LAZY` to
  False, then True. The eager answer must be definite, and the lazy answer must equal it.
* **#2210 by hand.** `x = oo` forces `x + 2y <= 2`, so `y = -oo`, and then `x + y - 3/2` is
  nan, which no order atom holds. So `x` is a finite real above 1, and the answer is True.
  The test also checks that `lra_inf` fired.

On 9914059 all 13 tests fail (relations.py stashed). With the fix all 13 pass.

## Answers

* **dev:** `evalbench/dev.py ~/dev/sa-lzr --base ~/dev/sa-eval/cands/base-9bafaa5` gives
  "1985/1985 identical". The digest is 31cd0945c07f02a6, unchanged, and `lra_inf` never
  fires on dev.
* **fuzz 424242:** I compared all 3000 answers with 9bafaa5's (protime.py on
  cands/base-9bafaa5). 0 differ, and both digests are 173502b6ef285ad6.

## Links built (deterministic, `tools-lzr/protocount.py`, SA_LAZY=1)

| | dev before → after | fuzz before (9914059) | fuzz after |
|---|---|---|---|
| None queries: sessions, links, built | 96, 186, 28 (15%), unchanged | 2256, 7364, 1113 (15%) | 2244, 7303, 1477 (20%) |
| definite: sessions, links, built | 99, 185, 41 (22%), unchanged | 325, 1203, 266 (22%) | 337, 1264, 277 (22%) |
| set checks: n, pending, built | 164, 227, 108 (48%), unchanged | 2919, 5192, 1929 (37%) | 2919, 5192, 2058 (40%) |
| total deferred / built | 375 / 178, unchanged | 9405 / 3313 (35%) | 9405 / 3817 (41%) |
| solves (re-solves) | 611 (148), unchanged | 10271 (2210) | 10750 (2693) |

On fuzz, `lra_inf` causes 473 builds (None 365, definite 5, set checks 103). The lazy gain
shrinks only on fuzz, where infinite-term models are common. On None queries the built share
goes from 15% to 20%. Dev is unaffected. The session counts now match eager (2244/337).

Instruments: `tools-lzr/protocount.py` now writes its answer file to `$ANS_DIR` (default
`.`) instead of a stale scratch path.

## Test suite (orion, SA_LAZY=1, `pytest -n 8 tests`)

The fix introduces no new test failures.

* **With the fix:** 68 tests fail.
* **On 9914059 (relations.py stashed):** the same 68 fail, plus one timing test,
  `test_wide_derived_or_against_or_is_fast[nor-or]`.

The suite had not been re-run since sa-lzr-2 added the scratch LRA replay, so these
failures belong to the prototype. By file:

| file | failures |
|---|---:|
| test_relations | 28 |
| test_history | 13 |
| test_relevance | 8 |
| test_ref | 7 |
| test_unrelated_relation | 5 |
| test_ref_fuzz | 3 |
| test_transfer_numbers | 1 |
| test_switched_glue | 1 |
| test_scope | 1 |
| test_lra_integers | 1 |

I have not sorted out which failures are structural tests that expect built links and
which are real answer changes. At least one is a wrong None from the lazy check that is
not this cause:

* `test_lra_integers` prop7: `Q.integer(x)` under
  `Q.gt(x, 3/4) & Q.lt(x, 5/4) & Q.integer(2*x)`.
* Lazy answers None. Eager (SA_LAZY=0) answers True: the file passes, 808 passed.
* This is an integrality gap: `lra_int` / the scratch replay. It is the next exactness
  case to diagnose.
