# Lazy links: exactness triage of the 68 SA_LAZY=1 suite failures (sa-lzr-5)

Base: lazy-proto 7ca87fa. No timing in this step. Everything ran on orion.

**Status: question.** The brief asked me to stop when a fix would exceed ~40 lines. I fixed four
small causes. One family is left. It explains all 11 remaining answer changes, and its exact
fix is bigger than ~40 lines (see "What it would take").

## Classification

I ran the suite with SA_LAZY=1 and with SA_LAZY=0 (`pytest -n 8 tests`):

* **SA_LAZY=0:** 1 failure, the structural `test_module_state_inventory_is_classified`.
* **SA_LAZY=1:** 68 failures.
* **Every failure except that structural one is an answer change:** the lazy answer differs
  from SA_LAZY=0 on the same query.

| # | class | tests | query (lazy vs eager) | cause |
|---:|---|---|---|---|
| 24 | (a) answer | test_history 12 (repro_at_both_levels 10 and ci_profiles 2, all at SPEC), test_ref 7, test_ref_fuzz 3, test_unrelated_relation p3/p4 (the `ask_ref` side) | `ask_ref(Q.negative(1 - x), Q.positive(x - 1))`: None vs True, and so on | **C1** |
| 28 | (a) answer: crash vs answer | test_relations: dummy_theory_answers 15, links_to_unary_vocabulary 7, old_assumptions_link, guard_non_real_and_infinite, equality_sharing_is_needed_and_works, real_euf_with_order_stand_in, theories_are_per_session, random_order_queries_are_sound | `AttributeError: 'OrderAdapter' object has no attribute 'integer_form'` vs the expected answer | **C2** |
| 1 | (a) answer | test_lra_integers prop7 | `Q.integer(x)` under `3/4 < x < 5/4 & integer(2x)`: None vs True | **C4** |
| 3 | (a) answer | test_unrelated_relation p0, p1, p2 (engine side, with pads) | e.g. `Q.positive(y)` under `ext_nonneg(y - oo) & ext_pos(y - oo) & a > b`: False vs ValueError | **C6** |
| 11 | (a) answer | test_relevance pinned_values_connect p3/p5/p7, pinned_values_split p3/p5/p7, rational_keys_connect p3, sign_sums_set_raises_for_any_component; test_scope relevance_uses_the_scope_for_sum_pairs; test_switched_glue capability_kept; test_transfer_numbers float_and_rational_argument | `Q.positive(sin(x))` under `Q.eq(x, 2) & Q.positive(sin(2))`: None vs True. `Q.positive(z)` under the bessel set: True vs ValueError. `Q.finite(f(0.5))` under `eq(0.5, f(1/2)) & eq(1/2, f(1/2))`: None vs True | **C3/C7 (open)** |
| 1 | (b) structural | test_history module_state_inventory_is_classified | pins the module-state inventory: `relations.LSTATS` (the prototype's counters) is unclassified. It also fails with SA_LAZY=0. Not edited | |

Counts: 24 + 28 + 1 + 3 + 11 + 1 = 68. Once C1 to C6 were fixed, 13 tests still failed: the
11 answer changes, the structural one, and one in class (c).

**(c) other:** after the fixes, `test_wide_derived_or_against_or_is_fast[or-or]` failed once in
the full parallel run (orion load average 4 to 7, two suites running at once). Run alone it
passes twice (72 passed). It is a timing assertion under load, not an answer change. sa-lzr-4
saw the same flake.

## Causes and fixes

### C1. The reference deferred links but never ran the check

`ref.py` builds a session, and its `Relations` deferred links like the engine's. But
`ref._entails` calls `solver.entails` directly, so no `unbuilt_disagree` ever ran and the
deferred links were simply missing. This is not a gap in the check. The oracle (SPEC) ran
without some of its constraints.

**Fix:** `Relations.lazy` (default True). `ref.py` sets it to False in both of its sessions,
and `process` defers only when `LAZY and self.lazy`. The reference is the spec that the
engine is checked against. It must not rest on the prototype's check, and nothing outside the
tests and harness calls `ask_ref`. (+5 lines)

### C2. An order adapter with no `integer_form` crashed the check

The build calls `_link_integer` only `if hasattr(ad, "integer_form")`. `_disagree` called
`lra.integer_form(e)` unconditionally.

**Fix:** without `integer_form`, the form is None, which gives `lra_unread`, so the link is
built. That builds whenever the check can't read the form, which is exact. (1 line)

### C4. LRA's point need not satisfy the integrality literals

lra.py, "Integrality": "the model `check` returns satisfies the bounds and disequalities but
not necessarily the integrality atoms". In prop7, after `x`'s link is built, M has
`~Integral(x)` while LRA's point is `x = 1`. The check of `2*x` then evaluated `2*1 = 2`,
which is integral, and agreed. Every point with `~Integral(x)` has a non-integral `2x`, which
contradicts `integer(2x)`.

**Fix:** `_int_point(lra, M, lval)` evaluates every registered `Integral` payload that M assigns
at the point. If the point violates one, or a value is no rational (a `constfield.Element`
such as `pi + 1`), `_int_bad` is set. Then every real link's point verdict becomes the soft
`lra_int` and goes to the scratch replay. The scratch replay is a fresh `LRATheory` with all of
M's LRA literals plus every real link's sign and integrality constraints. It accepts only on
`r[0] is True and not gave_up and not exhausted`, which means a genuine model.

### C5 (found while fixing C4; no failing test shows it)

A soft point verdict (`lra_sign` / `lra_int`) used to return before the EUF and polar checks.
So when the scratch replay accepted, the link's EUF reading of `eq(e, 0)`, congruence and
transfer polarity went unchecked.

**Fix:** a soft verdict is kept in `soft`, the EUF and polar checks run, and a hard EUF reason
wins. (+6 lines)

### C6. An atom LRA does not interpret skipped clauses 2

`_interpret` emits `_order_infinite` (clauses 2) whenever `order_sides` is not None, before
and independently of `ad.terms(sat)`. For `0 < y - oo`, the `-oo` summand pushes the side
down, so the clause refutes `extended_positive(y - oo)`. That is #261's channel.

`_disagree` ran its LRA block only `if terms is not None`. sa-lzr-4's `_inf_disagree` was
therefore never reached for an atom with an `oo` summand.

**Fix:** if `terms is None` and `_inf_disagree(...)`, the check returns `lra_inf`. This is
the build's own generator, evaluated on M as before. (+2 lines)

Diff: `satassume/relations.py` +39/-11, `satassume/ref.py` +2.

## Argument (what is exact now)

sa-lzr-4's argument enumerated every constraint a build adds:

* the link clauses;
* clauses 1 and 2;
* the guarded LRA atoms;
* trichotomy;
* `_eq_infinity`;
* the EUF reading of `eq(e,0)`;
* transfer polarity.

C2, C4, C5 and C6 close gaps in how the check evaluates exactly those constraints:

* C6: clause 2 now runs on every order-sides atom.
* C4: an LRA verdict is read from the point only when the point is a model of M's LRA
  literals; otherwise the complete scratch replay decides.
* C5: the EUF and polar checks run for every link.
* C2: an unreadable form builds.

C1 makes the oracle eager.

**That list is not complete.** `build` ends with `process()`, and `_apply_role(..., "link")`
adds tvar sources under the link's selector (`_tsource`):

* `sel -> IL(u)` for the LRA terms of the link atoms;
* `sel -> IE(u)` for the EUF terms of `eq(e, 0)`;
* `sel -> SD(e)` and `SD(0)`: transfer sides, hence `MC`, hence congruence and candidacy.

Interpreting the link atoms can also add new shared terms, so `_share` creates new interface
pairs.

The check evaluates none of these. Here is how they fail:

* **`Q.positive(sin(x))` under `x = 2 & positive(sin(2))`:** only building `sin(x)`'s link
  restores True (one process per subset). Its `IL`/`IE` turn on the interface twin through
  which LRA's `sin(x) = sin(2)` (EUF congruence from x = 2) reaches LRA's sign.
* **The bessel set** (`zero(x) & zero(y) & zero(J(y)) & nonzero(J(x))`): it raises only if
  **both** `x`'s and `y`'s links are built (each pair). The guard of `eq(x, y)`'s twin is
  `IL(x)&IE(x)&IL(y)&IE(y)`, so the check would have to judge all active links together.
* **`f(0.5)` / `f(1/2)`:** only `f(1/2)`'s link restores True. It is EUF+LRA+transfer with an
  empty LRA point, so the likely path is `SD(f(1/2))` and transfer candidacy (C7). I have not
  separated C3 from C7 in this case.

This is the "general case still open" that REPORT-lzr-exact.md named. It is now shown to
change answers in the suite. dev and fuzz 424242 do not exercise it (see below), so they are
not enough evidence for exactness.

## What it would take (the question)

* **A, recommended first. Exact and conservative: about 20 to 30 lines plus a pure
  term-reader.** An active link disagrees ("tvar") if any tvar its build would source
  (`(u, IL)` over its LRA terms, `(u, IE)` over the EUF terms of `eq(e, 0)`, `(e, SD)`,
  `(0, SD)`) is unallocated or false in M. If they are all true in M, the build's sources add
  only implications M already satisfies.

  It needs the link atoms' LRA terms (`lra.terms`, available now) and EUF terms without
  interning. `EUFAdapter.interned` interns, so it needs a read-only twin; `_vclass` already
  walks the same structure.

  It is exact (it builds whenever something is unevaluated). The open question is the cost:
  in sessions with both EUF and LRA, most links may end up built. I would count it on dev and
  fuzz before deciding anything.
* **B, precise, more than 40 lines plus an argument.** Evaluate on M, lval and EUF's (virtual)
  classes every interface twin that would be on after building **all** active links:
  `[lval a == lval b] == [class a == class b]` (and `== M(atom)` where the atom exists), for
  the old pairs and the new `_share` pairs. Then replay transfer candidacy and congruence
  (`_congruent`, `SD`/`EN`/`MC`) on the virtual classes.

  The point is only sufficient (C4's lesson), so a mismatch must go to a joint
  LRA+EUF scratch or build. The free-term values (0 / ±1) create equal points, which would
  cause false mismatches and so cost builds.

**Recommendation:** do A, then count. Try B only if A's built share on dev/fuzz wipes out the
gain.

## Regression tests (`tests/test_lazy_links.py`, 17 pass)

* `test_reference_builds_every_link` (C1)
* `test_integrality_point_is_no_model` (C4: eager and lazy are True)
* `test_uninterpreted_atom_keeps_clauses_2[False/True]` (C6: raises; `lra_inf` fires)

On 7ca87fa (satassume/ stashed), the three lazy tests fail and the eager ones pass.

C2 is covered by test_relations' 28 dummy-adapter tests under the default SA_LAZY=1. C5 has no
failing case of its own; it is a code-reading fix.

## Re-check

* **dev:** `evalbench/dev.py ~/dev/sa-lzr --base cands/base-9bafaa5 --rounds 1` gives
  "1985/1985 identical". The digest is 31cd0945c07f02a6 (protocount).
* **fuzz 424242:** the protocount digest is 173502b6ef285ad6. 9bafaa5's digest is the same
  (REPORT-lzr-exact.md), so all 3000 answers are identical.
* **Suite, SA_LAZY=0:** 1 failure, the same as before, structural (LSTATS).
* **Suite, SA_LAZY=1:** 13 failures: 11 of C3/C7, 1 structural, and the 1 load-flaky timing
  test.

## Links built (deterministic, `tools-lzr/protocount.py`, SA_LAZY=1)

| | dev 7ca87fa → now | fuzz 7ca87fa → now |
|---|---|---|
| None: sessions, links, built | 96, 186, 28 → 29 | 2244, 7303, 1477 (20%) → 1517 (21%) |
| definite: sessions, links, built | 99, 185, 41 → 41 | 337, 1264, 277 → 293 (23%) |
| set checks: n, pending, built | 164, 227, 108 (48%) → 108 | 2919, 5192, 2058 → 2068 (40%) |
| total deferred / built | 375 / 178 → 179 | 9405 / 3817 → 3883 (41%) |
| solves (re-solves) | 611 (148) → 612 (149) | 10750 (2693) → 10762 (2705) |

On fuzz now: `why lra_int` 361, scratch 3130 (scratch_ok 1713), `why lra_inf` 473 (unchanged).
REPORT-lzr-exact.md does not list the 7ca87fa `lra_int` total, so the share due to C4 is not
separated here.
