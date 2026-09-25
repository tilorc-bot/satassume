# Routing report: SymPy fallback only where satassume has no model (issue #7)

Branch `ri/routing`, from refine-identities 4810c71, merged with 207e121. Only
`satrefine/backend.py`, a new test file and one regenerated table comment changed.

## Change

`combined` (the default backend) now asks SymPy only when `backend.route` gives a reason:

| reason | when | why SymPy |
|---|---|---|
| `matrix`, `custom`, `other`, `relation` | `satassume.sympy_api.to_formula` raises `Unsupported` on the proposition or the assumptions (matrix predicate, predicate on a matrix argument, unregistered custom predicate, relation over matrices or wrong arity, non-Boolean) | satassume has no model |
| `no-theory` | the query translates, but no theory interprets one of its relations (`pi/2`, float, `oo`, `AccumBounds` bounds) | satassume drops the whole query, including trivial facts; SymPy is cheap here (about 9 ms per query) |
| `inconsistent` | satassume finds the assumptions inconsistent | unchanged from before: SymPy decides whether to raise |
| `error` | satassume raises anything else | a backend returns None, not crash (SymPy's own error is also turned into None here) |

Everything else, including relations that the LRA/EUF theories interpret (`Q.eq`, `Q.ne`,
`Q.lt`, ... when satassume is undecided), uses satassume's answer as it is.

* Detection uses `to_formula` rather than `out_of_scope`, because `out_of_scope` reports only the
  first category and puts `relation` before `matrix` (`Q.positive(x)` under
  `Q.lt(x, 1) & Q.symmetric(X)` would otherwise never reach SymPy).
* `no-theory` is detected with a thin engine proxy (`_FlagUninterpreted`) passed as
  `sympy_api.ask(..., engine=)`. It turns `Uninterpreted` into a private exception, which
  `sympy_api.ask` would otherwise make into a plain None.
* The `Q.nonzero` guard applies on every SymPy call (`_guarded_sympy_ask`). A test checks it on a
  query routed to SymPy by a matrix conjunct.
* The old behaviour is kept as backend `union` for measurements.

Tests: `tests/refine_identities/test_backend_routing.py` (27 tests). They cover the route table,
that in-scope queries never reach SymPy, that out-of-scope queries do, `union`, the pi-bound
rewrite, AccumBounds not crashing, and a satassume error becoming None.

## Gates (78e6325 against stages-3865d76)

* Suite: 2382 passed, 0 failed (base 2355 passed; the +27 are the new tests and the merge).
* Scoreboard, both modes: identical to base (0 wrong, 0 crash, same/other/miss unchanged per family).
* Differential, all 6 runs: unsound unchanged (2/3/1 for both packages), crash 0. v3's one timeout
  (generated and live seed 2) is gone. Fired counts drop:

| run | v3 fired | identities fired |
|---|---|---|
| gen 2 / 3 / 7 | 458→456, 462→460, 439→434 | 485→484, 488→486, 459→456 |
| live 2 / 3 / 7 | 458→456, 462→460, 439→434 | 484→483, 488→486, 459→456 |

The lost rewrites, found by comparing worker records under `union` and `combined` (seeds 2, 3, 7), and the SymPy answer each one depended on:

| case | SymPy answer used | verdict |
|---|---|---|
| `Rem(1/sqrt(k), n)`, k<0, n<0 odd; `Rem(sqrt(n), 2)`, n<0 odd | `Q.lt(n, 1/sqrt(k))`, `Q.lt(sqrt(n), 2)` True for an imaginary side | unjustified: order on non-real terms |
| `Min(m, 1/sqrt(n))`, n<0; `Min(k, sqrt(m), x)`, m<0 | `Q.lt(m, 1/sqrt(n))` True while `Q.le(m, 1/sqrt(n))` is False | SymPy is self-contradictory; Min of a non-real term |
| `conjugate(1/sqrt(x))`, `Q.nonnegative(x)` | `Q.real(1/sqrt(x))` True | unsound fact (x = 0 gives zoo); the result happens to hold |
| `frac(1/(m + 1))`, `Q.zero(m)` → 0 | `Q.integer(1/(m + 1))` True | correct; a satassume gap |
| `KroneckerDelta(x, z)`, `Q.positive(x) & Q.imaginary(z)` → 0 (v3 only) | `Q.ne(x, z)` (disjunction) True | correct; a satassume gap |

Two identities timeouts under `union` (seed 2 case 945, seed 7 case 296) finish as unchanged.

## The two losses named in the issue

1. The `AccumBounds` crash (`asin(sin(x))` under `Q.le(x, AccumBounds(0, 1))`) was not in the
   backend. It was in `handlers_identities/_simple.py::_affine` (`xreplace` building an
   AccumBounds with a non-real argument), and b2c1589 (ri/stages) fixed it. satassume returns None for
   every query under those assumptions. The backend now also turns any satassume error into None.
2. The loss attributed to `log(x**n)` under `Q.even(n) & Q.nonzero(n) & Q.real(x)` was mislabelled.
   At 8f0e147 that row misses under every backend, including `sympy`. The case that
   satassume-only lost was `log(1/x)` under `Q.zero(x)`, and f686dcc (`0**e = zoo`) restored it.
   On the current branch, satassume-only differs from `union` in one battery case,
   `sqrt(asin(sin(x))**2)` under `Q.nonnegative(x) & Q.le(x, pi/2)`, and the `no-theory` route
   recovers it. `log(x**n)` under even n is a handler gap, not a missing fact.

## Timings

| | before (`union` / base) | after (`combined`) |
|---|---|---|
| refine over the 1,736 battery cases, one process | 135 s (SymPy fallback 112 s, 8,034 calls) | 36 s (SymPy fallback about 13 s; `route`, i.e. satassume, 12 s) |
| battery scoreboard wall time, side by side | 201 s | 98 s |
| gate differential, identities worker | 375-511 s | 86-136 s |
| gate differential, v3 worker | 239-524 s | 56-208 s |
| stage fixpoint (`refine_specialize.py --write`) | 1,117 s (stages report) | 303 s |
| suite, `-n 4`, side by side | 292 s | 294 s |
| suite in gates | 1,190 s (base, `-n 4`) | 374 s (`-n 4`) |
| gates total | 1,191 s | 376 s |

The side-by-side suite runs show no difference, so the gate suite drop mostly comes from less
competing load in the gate run (its differentials got faster).

## Generated tables

After the merge, the fixpoint reproduced every table rule for rule (integer_funcs 11,
complex_parts 40, power_exp_log 17, inverse 7). One derivation record in
`generated/complex_parts.py` changed: `Abs(b**e) -> 1` under `Q.imaginary(e) & Q.positive(b)`
used SymPy's `Q.imaginary(e*log(b))` before. It is now derived through `Q.real(log(b))` and
complex_parts RULES[6]. Committed in 78e6325.

## For satassume (not posted)

* `Q.integer(1/(m + 1))` under `Q.zero(m)` is None. A zero symbol could be substituted (m = 0)
  before deciding.
* `Q.ne(x, z)` for `Q.positive(x) & Q.imaginary(z)` is None. A relation over a non-real term stays
  a free atom. `Q.ne`/`Q.eq` could still be decided through `Q.zero(x - z)`: real minus imaginary
  is not zero.
* SymPy answers to avoid matching: `Q.lt(n, 1/sqrt(k))` True for negative k (non-real side),
  `Q.lt` True with `Q.le` False on the same pair, and `Q.real(1/sqrt(x))` True under
  `Q.nonnegative(x)`.
* The `no-theory` route (pi, float, oo, AccumBounds bounds) is the only remaining relation
  fallback. Issue item 3, treating an uninterpreted relation as an opaque atom, would remove it.

## Commits

Backend 1dcbe03, tests 57e1126, merge 76d46a9,
table 78e6325; report in the last commit.
