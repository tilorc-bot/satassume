# Lazy links: option A, the "tvar" check (sa-lzr-8)

Base: a2ca3b7. This is forward-chain-3b's ruling, option A of REPORT-lzr-exact2.md.

**Bottom line.** A is exact: the 11 suite answer changes are gone, and dev and fuzz 424242 are
identical to 9bafaa5. But it builds nearly every link: 374 of 375 deferred links on dev and
9032 of 9405 (96%) on fuzz 424242, against 179 and 3883 (41%) on a2ca3b7. Lazy links under
A save almost nothing. Unallocated tvars cause about 88% of the "tvar" verdicts (below).

## The change

`Relations._tvar_disagree` (satassume/relations.py) runs at the end of `_disagree`, after
every other check. It overrides a soft LRA verdict, and the other reasons keep their counts.
An active unbuilt link of `e` disagrees ("tvar") if one of the following holds:

* a tvar its build would source (`_apply_role`) is unallocated or false in M:
  * `IL(u)` for the LRA terms of `0 < e`, `e < 0` and `eq(e, 0)`;
  * `IE(u)` for the terms EUF interns for `eq(e, 0)`;
  * `SD(e)` and `SD(0)`;
* or the build would make a term newly shared (a term outside `sharing._seen` that the
  current shared-term sets plus the build's terms put in two theories), which means new
  interface pairs (`_share`);
* or an adapter the build would create does not exist yet.

The EUF term reader is `EUFAdapter.interned`. It already only walks the terms and does not
intern them, so no twin was needed. The terms are over-approximated: an atom a theory does
not register still counts. So the check can only cause extra builds, never skip a needed
one. The code is 39 lines including the docstring, plus 3 changed lines.

`harness/state.py` now classifies `relations.LSTATS`: the prototype's counters are written
and never read by an answer. The inventory test passes.

## Regression tests (`tests/test_lazy_links.py::test_build_sources_are_checked`, 6)

The 11 suite failures reduce to 6 distinct whole-set queries:

* the bessel set raises;
* `positive(sin(x))` under `x = 2 & positive(sin(2))`;
* the two DERIVED `sin` cases (p5, p7);
* `finite(f(0.5))` and `~negative(f(0.5))` under `1/2 = f(1/2) & 0.5 = f(1/2)`.

Each test asserts that eager and lazy give the expected answer. All 6 pass now, and all 6 fail
on a2ca3b7.

## Re-check

* **Suite, SA_LAZY=1 (`pytest -n 8 tests`):** 1 failure, `test_solver.py::test_performance_smoke_300_vars`
  (timing; host load was about 12, and it passes alone). An earlier run with the check placed
  first had two other failures: test_2210 and `keeps_clauses_2[True]` assert that `why lra_inf`
  fires. That is why the check now runs last.
* **The same suite on a2ca3b7:** 12 failures, the 11 of C3/C7 and the inventory test (the
  timing test passed that run).
* **dev:** the protocount digest is 31cd0945c07f02a6, the same as a2ca3b7 and 9bafaa5, so
  1985/1985 answers are identical.
* **fuzz 424242:** the digest is 173502b6ef285ad6, the same as 9bafaa5, so 3000/3000
  answers are identical.

## Links built (deterministic, `tools-lzr/protocount.py`, SA_LAZY=1)

| | dev a2ca3b7 → A | fuzz 424242 a2ca3b7 → A |
|---|---|---|
| None: sessions, links, built | 96, 186, 29 → 77 | 2244, 7303, 1517 → 3621 |
| definite: sessions, links, built | 99, 185, 41 → 68 | 337, 1264, 293 → 512 |
| set checks: n, pending, built | 164, 227, 108 → 227 | 2919, 5192, 2068 → 4820 |
| total deferred / built | 375 / 179 → 374 (99.7%) | 9405 / 3883 (41%) → 9032 (96%) |
| solves (re-solves) | 612 (149) → 683 (285) | 10762 (2705) → 13324 (5320) |
| "why tvar" (links no other check catches) | — → 317 | — → 7920 |

### What makes a link "tvar"

I classified every link for which `_tvar_disagree` holds by the tvar kinds that are
unallocated or false. This was a run with the check placed right after "atom": 333 links on dev
and 8757 on fuzz. There is no "share-only" case on either set.

| | dev (333) | fuzz (8757) |
|---|---|---|
| only unallocated (IE, IL, SD) | 290 | 5934 |
| only unallocated (IE, SD) | 10 | 1792 |
| a false IE or IL (plus unallocated) | 33 | 1030 |
| a false SD | 0 | 1 |
| no adapter yet | 0 | 4 |

Almost every session has both adapters (EUF and LRA), so this is the EUF+LRA case, and A
builds nearly every link in it. The cause is the "unallocated" clause, not false tvars:

* `IL`/`IE` are allocated only for terms already in an interface pair, a number mention or
  a congruence clause.
* `SD` is allocated only when transfer runs.

So in most sessions a link's tvars do not exist yet.

### A sharper A (not built, for the lead's decision)

A missing tvar is harmless when the build does not allocate it: `_tsource` only records the
source, and an extension of M can set the variable true. The build allocates a tvar in three
places:

* `_share_guard` for new pairs, which the share clause already checks;
* the `MC` path of `_tsource` (`SD` with `MC` allocated);
* `sync_transfer`/`_xswitch` for terms that become nodes or candidates.

If those three are checked instead of "unallocated", the dev "tvar" count would drop to about
the 33 false ones, and fuzz to about 1031. That estimate comes from the table above, not from
a run. It needs a written argument that nothing else in `process()` allocates a tvar. I have
not made that argument.

## Could the check be exact by construction?

Probably yes for clauses and sources, but not cheaply. The check would run the build's own generation (`_link`, then `process` up to the theories) into a collecting emitter: clauses go to a list, `_fresh` and `_atom_var` hand out virtual variables, and theory atoms stay payloads, with no `register_atom` and no EUF interning. It would then evaluate the result on M. A clause over M's variables is read directly. Clauses with virtual variables need a tiny SAT extension over those variables only, and this is where it beats A: `sel -> IL(u)` with a new `IL(u)` is satisfiable, not a disagreement. LRA payloads are read on the point, with C4's fallback to the scratch replay. EUF payloads are read through `_vclass`'s virtual classes. Three things stay open. What `process` reads from theory state (`_share`'s pair sets, transfer candidacy, `_congruent`) must run against the same virtual state, which is B's replay moved inside the build code. Every generator would need an emitter parameter. A virtual variable must never leak into a later build. On cost, I timed fuzz 424242 on a2ca3b7 with SA_LAZY=1 (orion, unpinned, so fractions only). Registration leaves take 51% of build time: `add_clause` 20%, `register_atom` 13%, `register_integer` 7%, EUF interning 4%, `ensure_vars` 4% and node `ensure` 3%. Generation is the other 49%: relation atoms, `_order_infinite`/`_inf_lits`, `_order_sides`, guards, `_apply_role` and the `_share`/`sync_transfer` bookkeeping. So the check costs about half a build per active unbuilt link, plus the evaluation, and a link it then builds pays generation twice. At a2ca3b7's 41% built rate the best case saves about 0.51 × 0.59 − 0.49 × 0.41 ≈ 10% of eager link-build time before evaluation, so I would not build it for speed. The cheaper way to stop counting unallocated tvars as disagreements is the sharper A above.

Scripts: `tools-lzr/tvarsplit.py` (the "tvar" classification; it wraps `_tvar_disagree`) and
`tools-lzr/buildsplit.py` (registration vs generation inside `build`). Both take `dev` or
`fuzz SEED` and run like protocount.
