# Agent report: relevance, only the assumptions connected to the query (item 3, landed)

- **Date:** 2026-09-26
- **Status:** landed on `main` (`99e8827` code and tests, `fe38eb2`
  `tools/relevance_fuzz.py`, `6563bcf` reports); risks on the item 3 issue.
- **Read with:** `2026-09-25-relevance-0-measurements.md` (stage 0, -9.5%
  modelled), `2026-09-25-relevance-1-build.md`, `2026-09-26-relevance-2-connect.md`.

## What landed

A relation-free assumption set is split into components by shared free
symbols (non-rational constants connect the components that mention them;
custom predicates and registered extensions turn the split off). A query
uses only the components touching its free symbols; its session and answer
memo are keyed by that sub-conjunction. A set or query with a relation is
not split (`RELATIONAL = "whole"`): values pinned through equalities,
`zero`, LRA or the rule base connect terms through EUF congruence, and a
rule keyed by rationals still lost 9 answers. The whole set's consistency
is checked once per set (per component, with search and escalation), so
inconsistent assumptions still raise.

## Reviews (three, Opus)

1. Stage 1: a Boolean conflict found only by search was missed by the
   per-component check (ValueError lost): `CHECK_SEARCH` on. Four answers
   lost through values pinned to the same rational (`Q.eq(x,2) &
   Q.eq(y,2) & Q.positive(sin(y))` asked `Q.positive(sin(x))`): led to
   `RELATIONAL = "whole"` (12 such cases, all tests now).
2. The fuzz tool hid one-sided errors (10 pairs); all history-dependent
   (a set inconsistent only through a fact declared on a symbol), both
   sides None in fresh engines; now its own category.
3. Final, on the landing base: LAND, no defect; 67 hand probes and a
   79,200-query relation-free fuzz (fresh recheck of every difference)
   identical to `main`.

## Gates (final)

Stream answers identical to `main` (13,877, 24 errors, 549 more definite
on both sides); gate2 0 changed; suite only the known `test_shared_facts`
pair; relevance fuzz 72,000 queries all the same; real-theory fuzz 1,000
seeds per mode, 0 mismatches.

## Speed (Pi, `tools/ab.py`, 3 rounds, twice)

`main` c8361d7 -> `land-rel`: 3.479 -> 3.189 s (-8.3%), 3.476 -> 3.169 s
(-8.8%). Item 2 had added +29 to +30%; after both, the replay is about
+18% over `main` before item 2 (2.68 s -> 3.18 s) with 106 more definite
answers and the 24 correct errors.

## Risks

1. The soundness argument rests on "no relation, no theory in the session":
   a future feature that brings in EUF or LRA without a relation (pi bounds
   in relation-free sessions, sign facts linked to LRA) must also turn the
   split off.
2. Under assumptions inconsistent only through a fact declared on a symbol,
   whether a query raises depends on engine history, as before.
3. `relevance_fuzz` exercises the split on under 5% of queries (its
   generator is about 40% relations) and does not recheck `whole-only`
   cases in fresh engines; a relation-free mode would make it a real guard.
4. `ab.py` compares only the error count and the first error, not the full
   list.
5. Dormant code: the `"rationals"` rule and `CHECK_SEARCH_RELATIONS` (known
   to lose answers); changing `RELATIONAL` needs `_KEYS.clear()`.
6. Memos: `Engine.splits` (20,000) and `_KEYS` (100,000).
