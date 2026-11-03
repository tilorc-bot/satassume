# REPORT sa-lzr-1: lazy relation links (model-based theory combination), BOUND

Baseline satassume 9bafaa5 (branch `lazy-links`, no code change). Instrumentation
scripts (monkeypatches, nothing in the package): `tools-lzr/` in this clone.
Counts are deterministic (orion); times come from the pinned pareto1 run below.

## What exists today, per workload

| | dev (1,985 q) | fuzz seed 424242 (3,000 q) |
|---|---:|---:|
| sessions with relation glue (`Relations` built) | 198 | 3,018 |
| links built (`Relations._link`) | 375 | 9,405 |
| relation atoms interpreted (`_interpret`): the links' `0<e`, `e<0`, `eq(e,0)` | 1,073 (72%) | 27,485 (76%) |
| relation atoms interpreted: user/trichotomy/interface/extension | 428 | 8,912 |
| theory atom registrations (LRA, EUF) | 2,396 | 58,535 |
| transfer atom registrations | 889 | 36,245 |

Profile (dev, cProfile, so the shares are inflated): `Relations.process` 25% of the
pass, `_interpret` 15.2%, `_link` 5.6% (its own clauses and `_link_integer`;
the interpretation of its atoms is under `_interpret`).

## Ceiling: no links at all (answers change; an upper bound only)

`Relations._link` replaced by a no-op (`nolink`), and also transfer off
(`nolink+noxfer`). PINNED (pareto1, bench-container, cold processes, alternating, medians of 6):

| workload | mode | runs | median s | vs base | None-answer s | vs base | n None | range s |
|---|---|---:|---:|---:|---:|---:|---:|---|
| dev | base | 6 | 0.525 | | 0.312 | | 892 | 0.524-0.526 |
| dev | nolink | 6 | 0.381 | -27.5% | 0.253 | -18.9% | 925 | 0.380-0.382 |
| dev | nolink+noxfer | 6 | 0.375 | -28.7% | 0.257 | -17.4% | 941 | 0.373-0.376 |
| fuzz 424242 | base | 6 | 7.992 | | 6.676 | | 2,387 | 7.931-8.054 |
| fuzz 424242 | nolink | 6 | 4.097 | -48.7% | 3.500 | -47.6% | 2,482 | 4.053-4.147 |
| fuzz 424242 | nolink+noxfer | 6 | 3.721 | -53.4% | 3.248 | -51.4% | 2,528 | 3.704-3.773 |

(The None-answer columns compare different sets of queries, because answers change
without links. The whole-pass columns are the ceiling. Transfer beyond the links
is worth only 1 to 5 points.)

Orion (unpinned, 3 rounds) agreed for dev: 0.79 s to 0.58 s (-27%). 33 dev answers
change without links (892 to 925 None), so some links are needed.

## How many links would a model-based loop build? (the bound)

Simulation, in the real session after the real answer (answers unchanged: the
answer digest equals 9bafaa5's on dev and on fuzz). Every link is already
guarded by its selector `link_sel[e]` ("Switched glue"), so withholding a link
means not assuming its selector (the set's root units of `_set_glue` and the
group selector's implications were turned into plain assumptions so they can
be withheld). The loop, for the set's check and for `q` and `~q` of the query:

1. solve under the built links; UNSAT: done (UNSAT for the full combination,
   since the full clause set is a superset);
2. SAT with model M: a link is in *disagreement* if M violates any clause the
   session emitted under its selector (the selector literal removed): its six
   sign equivalences, the integrality link, the roles of its atoms (twins), the
   transfer enable/side variables and share sources it implies;
3. no disagreement: M with every withheld (inert) selector set true is a model
   of the whole formula (theories read only their atoms and values, which are
   unchanged), so SAT for the full combination; else
4. repair: re-solve with the withheld links' atoms forced to agree with M's
   unary side; SAT and agreeing: done; UNSAT: build the links whose agreement
   literals are in the conflict core; otherwise build the disagreeing ones.

Answer = True if `~q` UNSAT, False if `q` UNSAT, None if both SAT.

| | sessions | active links | built | % built | answer mismatches |
|---|---:|---:|---:|---:|---:|
| dev, query answered **None** | 72 | 146 | **0** | 0% | 0 |
| dev, definite | 84 | 161 | 44 | 27% | 0 |
| dev, set checks | 164 | 227 | 0 | 0% | 0 |
| fuzz 424242, **None** | 1,965 | 6,565 | **0** | 0% | 0 |
| fuzz 424242, definite | 295 | 1,128 | 72 | 6.4% | 0 |
| fuzz 424242, set checks | 2,919 | 5,192 | 12 | 0.2% | 0 |

Derived query literals (`q` a tuple: `nonzero`, `nonnegative`, ...) were not
simulated (dev 39, fuzz 321 queries); nothing suggests they differ.
Solves per session in the simulation: about 3 for a None query (check, `q`,
`~q`; today: check plus `entails`, often 2), 3.8 for a definite one.
Without the clause-level check (sign equivalences only) the first version lost
7 dev answers, all `Q.integer(x/pi + 1/2)`-shaped: the integrality link is part
of what must be checked. With it: 0.

**The None problem is exactly where links are never needed**: in all 2,037 None
sessions the first models already satisfy every link. Links are built for
definite answers (the refutation needs them) and almost never for set checks.

## Pinned exactness cases

`test_relevance.py::test_sign_sums_set_raises_for_any_component` and
`test_scope.py::test_relevance_uses_the_scope_for_sum_pairs` (`bj = besselj(1, ·)`):
`Q.zero(x) & Q.zero(y) & Q.zero(bj(y)) & Q.nonzero(bj(x)) & Q.positive(z - 1) &
Q.negative(z - 3)`. The simulated check is UNSAT after building 4 of the 6
links (x and y via their `zero <-> eq(·, 0)` disagreement, then the ones the
core names), so all four queries still raise. The set without `Q.nonzero(bj(x))`:
SAT, 0 links built, `Q.zero(bj(x))` None as today. The criterion keeps them
because a disagreement is any violated link clause, transfer and congruence
included, not a hand-picked subset.

## Design for the build (recommended)

The simulation decides with the link atoms present (only their clauses withheld),
so it does not save their interpretation, which is the cost. A build must decide
disagreement *without* the atoms `0<e`, `e<0`, `eq(e,0)` of an unbuilt link:

* Session construction: `_link(e)` records `e` as pending instead of building
  (for every linked term; the user relation atoms are still interpreted).
* After each SAT result that an answer rests on (the set check's `solve`, the
  query's `entails`/`consistent`), `Relations.unbuilt_disagree(model)` returns
  the pending terms whose link a model of the theories would violate:
  - LRA: `e`'s linear form evaluated in LRA's model (an unregistered variable
    takes its model value, 0) against M's `extended_positive/negative/zero(e)`
    and `integer(e)`; a non-finite or non-extended-real `e` in M: disagree;
  - EUF/transfer: `e` in an EUF term (argument of an application EUF reads,
    or such an application) and M's `zero(e)` differs from "EUF has `e` in the
    class of 0": disagree; `zero(e)` true and `polar(e)` != `polar(0)`: disagree.
  These triggers are conservative: a spurious disagreement only builds a link
  (speed), never changes what the answer rests on.
* Build the disagreeing links (`_link` + `process`), re-solve; repeat. The
  loop ends: each round builds at least one of finitely many links.
* Propagation-decided answers: today `implied` may settle a query only because
  of a link; with lazy links that query goes to search instead (same answer,
  different path). The engine's `query_literal` keeps its order (propagate,
  escalate, search), and an UNSAT/None is final only after the loop.
* History independence: what is built is a function of the session's models,
  which are a function of (set, query) (deterministic solver, fresh session per
  query), so nothing new crosses queries.

Exactness argument (for the PR): UNSAT over built links is UNSAT for all
(monotonicity: the full formula has more clauses). SAT with no disagreement:
the model, extended by the theory values used in the check (the LRA assignment
satisfies every unbuilt link's sign/integrality by evaluation; EUF's model
gets `e` merged with 0 exactly when M says `zero(e)`, which by the EUF trigger
creates no new congruence), satisfies the full formula. So every answer equals
the eager one.

## Recommendation

Bound well over 5% (ceiling -27.5% dev, -48.7% fuzz, pinned; None sessions build 0 links): build it (step 2), in a successor session (sa-lzr-2) per architect-64. Expected: links (and their atom
interpretation, transfer polar atoms and interface shares) skipped in every None
session, which is the target; the cost is the per-model evaluation and about one
extra solve per definite answer. Risk: the LRA/EUF model-evaluation triggers are
the new code (`Relations` + a model accessor on the LRA and EUF adapters); the
simulation shows the counts, not the trigger's own spurious-disagreement rate.
That rate is measurable first on the prototype.
