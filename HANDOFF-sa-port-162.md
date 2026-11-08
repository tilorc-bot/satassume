# HANDOFF sa-port-162: Element._new step, rebased on 5c7 (17442af), plant 123 added, bar F2 running; not landed (issue 323)

## State (8 Nov, ~11:00 UTC)
- port/elemnew = **9139a9b** on rust-slice **17442af** (5c7 landed). Pushed (own branch, force after rebase).
  Commits over 17442af: 72a52ac (part 1), 848c06d (159 handoff), baa9008 (part 2), d3d47ff (2b), 5fab5d1 (160 handoff),
  **c7cab1f (plant 123)**, 9139a9b (report draft + ownership rows), plus this handoff.
- **Rebase on 17442af**: conflicts only in part 1's lists. relations_core.rs: 5c7's plants 114-117 kept, my
  "114-117 are port/5c7's" comment dropped. session.rs: 5c7's names 156-169 kept, the `rsv:5c7:*` placeholders dropped;
  NAMES/COUNTS 179 (170-176 elem/memo, 177 cf:elem_sign, 178 rel:elem_sign). Builds; 118 unit tests pass (orion);
  dev MATCH 31cd0945c07f02a6 (`~/sa-rust-ids-work/sa-port-162/q5/`).
- **Bar F2 running** on pareto1, tested **9139a9b**, rows `~/sp19/sa-rust-ids-work/sa-port-162/bar-F2/`, env
  `~/sp19/bar-sa-port-162-env.sh` (orion copy `~/sa-rust-ids-work/sa-port-162/bar-env-F2.sh`), script = p1/bar.sh sha
  1f9c6d92, launcher pid on orion in `~/sa-rust-ids-work/sa-port-162/bar-F2.pid` (shared lease 05eabaf7). Started 10:56Z,
  expect ~1h. Done when phases.txt has `sum`. If the launcher's ssh drops (it did on F1), the job keeps running: take a
  cover lease `machine lease pareto1 --shared --for 2h -r "... cover ..."` and watch the job PID.
  Config: BASE = 5c7's suite rows `sa-port-158/bar-5c7b/suite`; KEPT_BASE = `sa-port-157` (6g(c1); has the 10 WLS, not
  budget: budget's base share is in results/port-5c7.md); PLANTS = rel-elem-sign-flip + the five elem-* + cf-laurent-rational
  pay-int-offset ad-kind-swap theory-no-assume al-drop-delta + 5c7's union-skip-overlap within-no-link; WLS = the 10 + budget;
  SEED1=1; SUITE_PLANTS=zero; TESTS = E2's list (covers 5c7's); DIRECT as E2.
- **Bar E2** (5b705df, on 9c8d981): complete and clean (below). **Bar F1** (62a6723, on 30f3309): stopped by me after
  plants and seed1 when 5c7 landed (rows `bar-F1/`, partial: build/tests/suite/live/plants/seed1 done, no sum). It's not a
  landing bar; its plant rows (incl. rel-elem-sign-flip on dev/fuzz) are in `bar-F1/live/`.

## Bar E2 (5b705df), its own items (sum: orion copy `~/sa-rust-ids-work/sa-port-162/E2-sum.txt`)
1. Suite vs C2b: 5,992 passed, 126 failed, 23 skipped, 18 xfailed, 6,159 ids; new 0, gone 0, changed 0. Passed 5,991 no
   firing + 1 with (`test_ci_stream_reports_only_what_replays`).
2. dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6 MATCH (traced end states too), seed1 MATCH, 10 WLS MATCH (cert
   6a09c059eb266747; others as C2b), 0 Python solvers.
3. Plants: elem-memo-plus1 caught as a wrong value (dev 2,461 D, fuzz 93,210 D, cert 1,532 D, scope 1,039 D, zero 5,612 D;
   value 203 MATCH); elem-from-neg dev 71 D, fuzz 617 D, cert 121 D; elem-repr-bracket dev 2,870 D, fuzz 37,501 D, cert 533 D;
   **elem-eq-flip void on all 12 workloads, caught by the suite** (SUITE_PLANTS=zero:
   `test_lra_constant_coefficients.py::test_pivots_with_constants_leave_a_consistent_tableau` passed -> failed);
   **elem-hash-skew fired dev 179, MATCH everywhere: silent** (hash one off never changes a result: name it);
   controls as C2b (cf-laurent-rational caught on cert only, 119 D).
4. Handlers: 39 rows in 2 tests, multiset = base (34 `_ok`, 4 `_rb_clauses`, 1 `_build_context` borrow). Quiet catches
   0 on dev/fuzz/seed1/WLS; plant files have rows (ad-kind-swap dev 2, fuzz 315). TermFault 0.
5. Known differences: none. Tests 654 passed; DIRECT as C2b (common-facts-drop fired 8, 6 DIFFERENCES, the control).
Kept shares: all equal to base (dev out-of-scope 24/1,985; f6 refused 13; value 15; opaque 7; wiring 1).

## Plant 123 (rel-elem-sign-flip), caught on dev before landing (orion, 62a6723 build)
`~/sa-rust-ids-work/sa-port-162/p123/` vs q4's Python: fired 100 (= rel:elem_sign 100), **end/stream DIFFER on 50
queries, answers equal** (answers_sha 31cd0945c07f02a6 both): caught by the state comparison, not by an answer.
`p123/cmp.txt`. Unplanted dev on that tree MATCH (`q4/`).

## Other numbers for the report
- Element._new Rust crossings (cf_trace): dev 703 -> 0, fuzz 1,552 -> 0, cert 163 -> 0 (q3, and q4/q5 dev on rebased trees:
  only `_generic` 1). f6 30, core 24, wiring 3, opaque 2 unchanged (sa-port-160 `t4/`), all inside `constant`/`radical`
  or Python from_sympy. `Element.__repr__` (Python) 0 now: the harness repr is PyElem's (cf:elem_repr dev 2,870, fuzz
  37,501, cert 533). `Constant.enclose` dev 100 -> 0.
- `ad:cb_memoized` dev 5,508, fuzz 164,954, cert 2,270, unchanged (E2 / q-runs; take F2's live/extra session.json).
- Module count: 13 of 32 unchanged, checked against ~/dev/architect/STATUS.md lines 11-17 (lists solver, euf, lra,
  transfer, lra_cert; realroots.py, templates/atoms.py; registry.py, templates/__init__.py; scope.py; table.py,
  _common.py; relations.py). constfield.py not whole (`constant`, `radical`, `_generic`, `Constant.__init__`, gcd trio,
  `_short`, `enclose`); lra_adapter.py (`_memoized`, `constant_bounds`).

## Next, in order
1. Wait for F2 `sum`; scp sum.txt to orion, read by sections (`rg -n '^=='`). State the five items; plant table with
   rel-elem-sign-flip's row (dev must DIFFER), elem-memo-plus1 as a wrong value, elem-eq-flip (suite) and elem-hash-skew
   (silent) named; budget workload MATCH; kept shares vs base; counters from `live/*-rust.session.json`,
   `extra/*-rust.session.json` (cf:elem_new, cf:elem_py_read, rel:elem_sign, ad:cb_memoized).
2. Finish results/port-elemnew.md (draft has What moved, plant 123, `_memoized` decision, state-rule search). Add, in
   port-adapters.md part C2's layout (:283-425): SHAs and incoming diff (tested 9139a9b over 17442af; the 30f3309 and
   17442af incoming diffs, both guarded source -> full bars F1/F2), the bar (F2's five items; E2 as the earlier bar),
   plants table, reached, Element._new / _memoized before-after (above), module count, kept reasons, not run (as C2's
   list), F1 stopped and why. Ownership md/TSV already updated in 9139a9b (sa-port-162 note, rows 653/768); fix the
   tested SHA there (62a6723 -> F2's) if it differs.
3. `sh rust-spike/slice/p1/bar.sh land 9139a9b` (no PUSH), read the incoming diff; guarded source -> full bar again.
   Else commit report, `PUSH=1 sh rust-spike/slice/p1/bar.sh land 9139a9b`. `agent report`, SendMessage the architect.
