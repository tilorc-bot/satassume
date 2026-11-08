# HANDOFF sa-port-140: adapters B+C1 landing bar running on d676f36 (issue 323); C2 measured, not ported

## State (06:05 UTC 8 Nov)
- port/adapters (pushed) = **d676f36**: rust-slice bb3df19 (5c7-tests landed) + 9c73482-equivalent part B, docs, part C1,
  and d676f36 (Negated fix). Commits on top of bb3df19, in order: part B code, 3 docs commits, part C1 code, 2 handoff commits,
  d676f36. rust-slice head is now **44f4762** (sa-port-141's docs-only commit: port-5c7-tests.md only), so `bar.sh land`
  rebases over it and the guard passes (results/ excluded).
- **Landing bar BC2 running**: tested d676f36, pareto1, rows `~/sp19/sa-rust-ids-work/sa-port-140/bar-BC2/`, launcher log
  orion `~/sa-rust-ids-work/sa-port-140/bar-BC2.log`, local `machine run` PID **817715** (lease 31c93466), started 06:01:49.
  Env file pareto1 `~/sp19/bar-sa-port-140-env2.sh`: BASE = 6d's `sa-port-131/suite`, KEPT_BASE = `sa-port-131`;
  PLANTS = part B `ad-lra-shared ad-euf-node ad-kind-swap ad-euf-shared spec-row-flip adapter-fresh`, part C1 `pay-neg-twice
  pay-int-offset pay-eq-flip`, controls `theory-no-assume` (scope), `al-drop-delta` (5c6), `common-facts-drop` (6d, DIFFER
  on dev in 6d's bar); WLS `f6 value rootof core opaque scope loop zero`; SEED1=1; SUITE_PLANTS=zero; TESTS = 6d's list +
  test_relations_core.py test_term_ids.py test_adapters_core.py; DIRECT "relations_direct.py 300 0;dispatch_direct.py;
  common_direct.py;common_direct.py common-facts-drop"; N=8. Done marker: `bar-BC2/done.txt`; summary `bar-BC2/sum.txt`.
- Superseded bar BC1 (de64ee2, pre-5c7-tests) stopped at its extra phase; lease released. Not a landing bar. Its partial
  rows are in `bar-BC1/` (suite, live and plants phases finished; useful only as an early read).
- Both bars share the clone `~/sp19/dev/sa-port-140` on pareto1 (bar.sh uses $HOME/dev/NAME): never run two at once.
- Rulings received this session (verbatim in the NEXT brief): one bar for B+C1 (planner, ~05:20); landing order (first bar
  to finish lands; 141 landed first, so ours reruns on the merged tree: done, BC2 is that bar).

## What this session did
- **Void Negated plant explained and fixed (d676f36).** The engine never builds `Negated`: relations.py:526 lowers `ne`
  to `Not(eq)`, and theories get only eq/lt atoms (relations.py:366 `RELATION_ATOMS`). So dev, fuzz and `live.py pay`
  can't reach it (pay-neg-twice fired 0 on all three). tests/test_lra_adapter.py registers `Q.ne` atoms through the public
  adapter API (:351, :387), but the old core test ran it on Python's theory, where the Rust adapter builds Python's Negated
  (`ad:cb_py_payload`). New test `test_rust_adapters_with_rust_theories_pass_the_adapter_tests` (test_adapters_core.py)
  runs the adapter tests under `rust_plugin` + `ad_swap`: 298 passed as on Python; with SLICE_SESSION_PLANT=pay-neg-twice
  2 fail (test_ne_and_eq_through_solver, test_model_is_consistent_with_sympy). Planner: enough for the adapter's own API;
  **footnote "reached only through the adapter API, not through the engine"**. pay_wl.py and live.py's `pay` hook dropped.
- Rebased on 6d (6526445): clean, no renumbering (6d's counters live in term/common.rs). Part B plants 104-107, counters
  140-150; C1 plants 108-110, counters 151-154 stand. Core tests (adapters+relations+scope) 98 passed on orion.
- Rebased on 5c7-tests (bb3df19): one conflict in live.py (their `zero` hook next to our pay hook), resolved keeping
  `zero` only. Incoming diff bb3df19 vs 6526445: live.py +3, zero_wl.py +85, tests/test_public_incremental.py +313,
  results/port-5c7-tests.md. tested-vs-6d-tested source diff: live.py and zero_wl.py only (tests/workload). Note:
  **test_incremental_matches_fresh's public-API version landed with 5c7-tests** (tests/test_public_incremental.py), so
  that MUST-STAY item changes: check port-5c7-tests.md for its wording.

## C2 measurement (not ported), `~/sa-rust-ids-work/sa-port-140/c2/NOTES.txt` and `cf_trace.py`
On Rust, by immediate Python caller (tree e7f856d = d676f36's code on 1401d1f): the 6 "Python" rows don't run per query
in the engine. `Element.__repr__` (dev 2,870, fuzz 37,501) is read only by the harness (state.py, live.py show);
`to_sympy`, `_coerce_foreign`, `_sympy_constant`, `Constant.__repr__` fire 0; gcd trio and `_short` 0. Per-query
callbacks: `Element._new` dev 703 / fuzz 1,552 (lra_live.py `_rust` 460/598: Rust Num → Python Element in payload
coefficients; lra_backend.py `check` 126/488; `_state` 117/466, harness state dump), `pi_laurent` 121/200 (lra_cert.rs:87
on an Element bound), `Constant.enclose` dev 100 (Python Element `_env`), `_generic`/`constant`/`Constant.__init__` 1 (once
per new constant per process: registration, like lazy loading). `radical` not traced (wrapping breaks constfield.rs
`native_of`). So C2's real work: (1) `Element._new` at the boundary: payload coefficients and check results as a Rust
Element pyclass with Python Element's eq/hash/repr (state rule), or keep Python Element as the boundary value and argue it
is conversion; (2) `pi_laurent` in Rust (lra_cert.rs:82-90); (3) classify the 6 rows as display/output conversion with the
trace as evidence (ask the planner), `enclose` permanent (R9). Map: HANDOFF-sa-port-138.md "Next 5".

## Next
1. When BC2's done.txt exists: read `bar-BC2/sum.txt` by section (rg, never whole): tests, suite three numbers + firing
   split, handler multiset vs base, plant table (B and C1 rows separate; each part needs one caught; ad-euf-node expected
   void; pay-neg-twice void on workloads, caught by test_adapters_core in the tests phase), kept-reason shares per
   workload vs base, seed1, direct.txt.
2. Clean: `PUSH=1 sh rust-spike/slice/p1/bar.sh land d676f36` (rebases over 44f4762, docs only). If it differs: land part
   B alone to bisect (planner condition 2). If rust-slice moved again with source: rebase, rebar.
3. Tell the architect at once after landing (141-style followers rebase on us).
4. Reports (docs commit on rust-slice after landing): port-adapters.md part B and part C1 sections with every MUST-STAY
   item; ownership: run `python ~/sa-rust-ids-work/sa-port-140/own_edit.py rust-spike/slice/results/port-ownership.tsv
   LANDED` (prepared: euf_adapter → Rust except `_inherits_from_basic` conversion; lra_adapter → Rust except
   constant_bounds, _memoized, to_constraint, terms, constant_enclosure called back; Negated/Integral/EqAtom → Rust), then
   the matching .md rows :94, :96, :104, :106 and the header "Updated by" line and counts. Module count: 8 of 32 with
   relations.py (footnote realroots/value_units); step 0 closes with part B.
5. C2 as above.
