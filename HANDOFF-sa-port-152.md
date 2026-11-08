# HANDOFF sa-port-152: adapters C2, pi_laurent ported (e12e622, pushed to port/adapters); not landed (issue 323)

## State (8 Nov, ~07:15 UTC)
- port/adapters = **e12e622** over rust-slice 03c075d (unchanged when checked; siblings 145/151 hadn't landed).
  rust-slice NOT touched. No bar run yet. Handed off at the 140k context note.
- C2 ruling (planner, ~06:40, in the brief): (a) class the 6 rows as output/display conversion; (b) `Element._new` is its
  own step AFTER C2, not here; (c) port `pi_laurent` if it's exact arithmetic. It is (Fractions and `_scale` only), so it moved.

## What e12e622 does
- constfield.rs `pi_laurent_elem` (next to `new_py_element`): port of constfield.py:1325 for an Element; pi's index read
  once from `_PI_INDEX` (PyOnceLock). lra_cert.rs `laurent` (now `pub(crate)`, ~:82) calls it: no Python call and no
  `Element._new` at that boundary (was lra_cert.rs:87 `module.pi_laurent(x.to_py())`).
- Counter **155 `cf:pi_laurent`** (session.rs; Element bounds only). Plant **111 `cf-laurent-rational`** (relations_core.rs;
  an Element bound reads as its rational part, pi terms dropped). **112 `cf-laurent-refuse`** (TermRefuse once, then
  `unplant()`) and **113 `cf-laurent-raise`** (ValueError each call): NOT plants, they replace the Python hook of
  test_term_live.py's two lra.rs:935 handler tests (the `HANDLERS` row and
  `test_the_core_certificate_handler_is_quiet_on_an_exception`), since nothing in that handler calls Python now. `live`
  fixture turns the plant off at teardown. Name this shared-file change in the report.
- session_live.py `_REL_PLANTS` += `cf-laurent-rational` (without it SLICE_SESSION_PLANT never reaches Rust: first try
  fired 0). `cf_op("pi_laurent", x)` added; new `rust-spike/slice/test_cf_laurent.py` (Rust vs Python on 316 numbers +
  counter/plant test).

## Local results (orion, `~/sa-rust-ids-work/sa-port-152/`)
- test_term_live.py: Rust 21 passed, Python 20 passed 1 skipped. test_cf_laurent.py: 2 passed.
- `local/`: dev Rust vs Python **MATCH** (31cd0945c07f02a6, 1,985 q), `cf:pi_laurent` 121 on dev (= the old callback count
  121). fuzz-py was still running at handoff; `local/fuzz.cmp` is written by local.sh when done (`local/done.txt`).
- An earlier plant, exponent shift (+1), **fired 121 on dev and MATCHed (not caught)**: the certificate's `Y` only grows,
  so it was replaced by `cf-laurent-rational`. Its runs `plant3-{dev,fuzz}` were launched (plant3.sh); read
  `local/plant3-*.cmp` and `plant3-*.session.json` (`counts.rel:plant_fired`) after `local/plant3.done`. **If it MATCHes on
  dev and fuzz too, the plant is void on workloads** (it is caught by test_cf_laurent.py's direct comparison only if that
  test is run with the plant on, which it isn't): then find a workload that the certificate decides (CERT query in
  test_term_live.py: `Q.zero(x)` given `Q.ge(x, -pi/2)`), or name it void.
- plant2-fuzz died: build_solver.sh `cp`s over the loaded .so. Build to a temp file and `mv` instead while runs are live.
- `trace/`: cf_trace.py on base (worktree `base-tree` at 03c075d, own build) and mine (e12e622-equivalent .so 5c6aa4e…),
  dev and fuzz Rust: per-caller counts of Element._new, pi_laurent, enclose before/after (`trace/{base,mine}-{dev,fuzz}.json`,
  `trace/done.txt`). Expect pi_laurent → 0 and Element._new from `check` to drop by about 121 on dev. Remove the worktree
  when done: `git worktree remove ~/sa-rust-ids-work/sa-port-152/base-tree`.

## (a) evidence for the report
- 6 rows on Rust per NOTES (sa-port-140, tree e7f856d): `Element.__repr__` harness only (state.py/live.py), `to_sympy`,
  `_coerce_foreign`, `_sympy_constant`, `Constant.__repr__` 0 on dev and fuzz. Recheck with `trace/mine-*.json`.
- `_coerce_foreign` (constfield.py:885): only caller `Element.__eq__` (:1214) with a non-constfield operand (a SymPy number).
  No engine path; the suite reaches it through tests/test_constfield.py:845 (`PI == sympy.pi`). Removal candidate next to
  `_bound`, noting removal changes `Element == sympy number` behaviour that test asserts.

## Next
1. Read plant3 and trace results (above). Pick the plant (or name it void) and fix if needed.
2. Full bar on pareto1 as HANDOFF-sa-port-133.md "Bar config" (launch line) with env like pareto1 `~/sp19/bar-sa-port-140-env2.sh`:
   OUT=~/sp19/sa-rust-ids-work/NAME/bar-C2, BASE=`~/sp19/sa-rust-ids-work/sa-port-140/bar-BC2/suite`,
   KEPT_BASE=`.../sa-port-140/bar-BC2`, PLANTS=`cf-laurent-rational pay-int-offset ad-kind-swap theory-no-assume al-drop-delta`,
   same WLS/SEED1/DIRECT/N, TESTS = BC2's list + `test_cf_laurent.py` (bar's tests phase runs without
   SLICE_TERM_TEST_RUST, so cite the local Rust run of test_term_live.py or run it separately on the tested SHA).
3. Rebase per LANDING ORDER, `bar.sh land TESTED` (no PUSH) to read the incoming diff, then `PUSH=1`.
4. Report: extend results/port-adapters.md; port-ownership.md :101 (`pi_laurent` moved), :104 (6 rows: "not port: output/
   display conversion, C2 ruling"), :131; TSV. Per-workload callback counts before/after from `trace/`.
