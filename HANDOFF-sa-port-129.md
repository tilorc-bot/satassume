# HANDOFF sa-port-129: adapters step (issue 323), part B in its bar, part C not started

## State
- port/adapters: 15dff82 (part B code, tested by bar-B1), b62755d (docs: part A addendum, this file). rust-slice is
  d91ee15. Part A's bar-A2 on d91ee15 matches bar-A on every item: d91ee15 stands (port-adapters.md, addendum).
- **bar-B1 running** on pareto1, tested SHA 15dff82: `~/sp19/sa-rust-ids-work/sa-port-129/bar-B1/` (phases.txt, sum.txt
  at the end). Launcher log on orion `~/sa-rust-ids-work/sa-port-129/bar-B1.log`, pid file `bar-B1.pid` there. Config: BASE
  sa-port-125/bar-A2/suite, KEPT_BASE sa-port-125/bar-A2, PLANTS "ad-lra-shared ad-euf-node ad-kind-swap ad-euf-shared
  spec-row-flip adapter-fresh", WLS=loop, SEED1=1, SUITE_PLANTS=zero, TESTS += test_adapters_core.py, DIRECT as bar-A2.
  The bar.sh copy it ran is the one with the push guard (sha256 1f9c6d928980…).

## What part B did (15dff82)
- `solver_rs/src/adapters.rs`: `LRAAdapter` and `EUFAdapter` pyclasses (sa_solver). State in the same Python containers as
  Python's (theory, _solver, _shared / _terms, _node_terms). Term reading stays in the module functions, called back and
  counted: ad:cb_memoized (`_memoized` + interpret/order_sides/integer_form, which lra_live routes to Rust), ad:cb_parse
  (`EUFAdapter.parse`), ad:cb_structural, ad:cb_interned (term_live wraps it), ad:cb_constant_bounds. Theory built with the
  module's `LRATheory`/`EUFTheory` (Rust backend's swaps), ad:cb_theory_new.
- relations_core.rs: `SpecRow.kind` (`AdKind`), set in `spec_row` by `ad_kind` (factory identity with Python's or Rust's
  class); `make_adapter` builds Rust adapters for default kinds, calls a user factory (ad:cb_factory). `rel_adapter` and
  `guarded_adapters` use it. `relations_package` helper. Plants 91-94: ad-lra-shared, ad-euf-node, ad-kind-swap,
  ad-euf-shared (session_live.py `_REL_PLANTS`). Counters 123-133 in session.rs.
- `ad_swap.py` + `test_adapters_core.py`: tests/test_lra_adapter.py and test_euf_adapter.py pass against the Rust classes.
- `p1/bar.sh` land: push guard (planner, 03:24 UTC). `p1/bar_sum.py`: kept-reasons section (planner, 03:42 UTC).

## Local evidence (orion, `~/sa-rust-ids-work/sa-port-129/b1/`, .so before ad-euf-shared was added, same otherwise)
- dev rust: answers 31cd0945c07f02a6 MATCH vs py; **Python adapter constructions 0** (`ad_trace.py`, which patches
  Python's classes' `__init__`, so spec factories keep their identity; sa-port-125's spec_trace.py wraps the factory and so
  would hide a default spec); ad:cb_factory 0; ad:lra_new 199 + ad:euf_new 198 = 397, the old 397 factory() calls;
  ad:cb_theory_new 397; rel:cb_spec_read 6. ad:cb_memoized 5,508, cb_parse 1,501, cb_structural 918, cb_interned 526.
- fuzz rust: 173502b6ef285ad6 MATCH, ad:cb_factory 0, lra_new 3,019, euf_new 3,018.
- Plants on dev: ad-lra-shared fired 1,370 DIFFER (state); ad-kind-swap 254 DIFFER (answers a485b8e5…); ad-euf-shared 465
  DIFFER; **ad-euf-node fires 0 on dev and fuzz: void** (node_term misses `_terms` on neither).
- ad:cb_constant_bounds 0 on dev and fuzz: `register_bounds` past the free_symbols check isn't reached by either.
- Kept reasons, dev rust (local): kept:out-of-scope 24 of 1,985 queries, refused 0.

## Next
1. Read bar-B1's sum.txt; state the five items plus the kept-reasons shares (new section) against bar-A2. Then the no-PUSH
   `sh rust-spike/slice/p1/bar.sh land 15dff82`, then PUSH=1 if the guard allows (docs-only commits after 15dff82 pass it).
2. Report part B in port-adapters.md (extend), port-ownership.md rows :94 (euf_adapter: EUFAdapter and methods to Rust;
   `_inherits_from_basic` stays, conversion by ruling) and :104 (lra_adapter: LRAAdapter and methods to Rust; module
   functions `constant_bounds`, `_memoized`, `to_constraint`, `terms` called back) and the TSV. Step 0 is closed:
   relations.py counts whole, 8 of 32 (footnote realroots/value_units stands).
3. Part C: EqAtom (euf.py:75, built in adapters.rs `register` via module `EqAtom`), Negated/Integral (lra.py:230/:247,
   built in adapters.rs via module `Negated`; Integral in `integer_form`), constfield rows (port-ownership.md :99, and the
   callback rows :124; `enclose` permanent). Ask the architect whether Negated/Integral are in scope (not yet asked).
   Readers: lra.rs:192, lra_py.rs:136 (Negated/Integral), euf_py.rs:2/:77 (EqAtom).
