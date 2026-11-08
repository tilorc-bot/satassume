# Handoff sa-port-175 (6g c3+c4+c5 stack, issue 323): bar running on 2c2990c, nothing landed yet

Handed off at the architect's request (about 188k context) while the bar runs.

## Running (detached; my own waiter shells are stopped)
- **Stack bar on port/stack-6g-c3c5 2c2990c** (c3+c4+c5 on rust-slice 67d108d, 5c10a),
  pareto1, started 17:58 UTC under `machine run pareto1 --shared` (orion launcher PID in
  `~/sa-rust-ids-work/sa-port-175/machine-run2.pid`). **End marker: pareto1
  `~/sp19/sa-rust-ids-work/sa-port-175/bar-6g-c3c5r2/end.txt`**, written by the job (`~/sp19/job-sa-port-175.sh`, a copy is
  `~/sa-rust-ids-work/sa-port-175/job2.sh`; runs `~/sp19/bar-sa-port-175.sh` = rust-spike/slice/p1/bar.sh, sha 1f9c6d928980).
  Expected end about 21:00 UTC. At handoff: build, tests, suite and live done (exit 0).
  - Config: the first stack bar's (sa-port-172 bar-6g-c3c5: S1's plus the 12 c3/c4/c5 rows plants, 38 rows plants, 11
    WLS, SEED1=1, 7 suite plants, 16 DIRECT entries) plus test_procmemo_core.py, test_engmemo_core.py,
    test_factcache_core.py. **BASE = 5c10a's suite** (`sa-port-182/bar-5c10a/suite`). KEPT_BASE = sa-port-172/bar-6g-c3c5.
- The branch HEAD carries this file on top of 2c2990c (results/ only, so the push guard sees no source difference):
  land with `bash rust-spike/slice/p1/bar.sh land 2c2990c`.

## History of the tested source
1. 0643e9c on 3611952: full bar (pareto1 `sa-port-172/bar-6g-c3c5/`, end.txt exit 0 16:54:03Z) equal to base (5c8's rows)
   and to S1's rows (`~/sp19/sa-rust-ids-work/sa-port-175/sum-vs-S1.txt`) on every item.
2. Rebased onto 2d12e81 (5c9a-c) as d0374e9; the guard saw 18 guarded files; a bar started 17:00 (`sa-port-175/bar-6g-c3c5r/`).
3. rust-slice moved to 67d108d (5c10a, guarded source: session.rs, relations_core.rs, factcache.rs, term_live.py,
   session_live.py, memo_check.py, lib.rs, test_factcache_core.py). I stopped the d0374e9 bar in its plants phase (by
   PIDs and its own path; lease released, exit 143; its rows are partial, don't use them), rebased to **2c2990c**, orion
   short check (build OK; shapes, factcache, procmemo, engmemo, rows tests 104 passed), and started bar-6g-c3c5r2.

## Evidence already taken (first stack bar on 0643e9c; recheck the new bar's numbers against it)
- Suite 5,992 passed (5,991 no firing, 1 with: test_ci_stream_reports_only_what_replays) / 126 failed / 23 skipped /
  18 xfailed, 6,159 ids; vs 5c8 and vs S1: new 0, gone 0, changed 0; handlers 39 rows in 2 tests, multiset = base.
  **On 2c2990c expect 5,991/127**: 5c10a's base has `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`
  failed: known id()-reuse failure, a test artifact (sa-port-185, report a28c548), owed; don't edit the test; report by id.
- dev, fuzz, seed1 and 11 WLS all MATCH with Python controls. direct.txt equals S1's (dispatch_direct exit 0, 13 common
  plants exit 1). Kept shares equal to base.
- Plants: every S1 catch still caught (per-plant diff of verdicts vs S1: only additions). New 12: see the draft.
  **rows-recip-tpl-neg fires 0 on all 13 bar workloads and orion's 4**; caught only by its shapes case through the shadow
  (`~/sa-rust-ids-work/sa-port-175/plantshape.py`, output `plantshape-c5.txt`; note the shapes test reads COUNTS before
  `undo()` flushes Rust counters, so plant_fired shows None there; the shadow mismatch is the catch).
- Kept counters `rows:kept:constant_value:Float` and `rows:kept:_imag_templates:number` are 0 on every workload but fire on
  crafted queries (`keptfire.py`, `keptfire.txt`): not false zeros.
- Suite plants vs S1: dispatch-ignores-epoch now 18 changed (S1 12) with handler multiset changed under the plant;
  knowledge-no-query-drop 20 (S1 25: 5 ids no longer change, test_notmpl_elementary expr77/expr80 and three
  test_sympy_api constant-proposition/hermitian ids); others the same. All still caught.
- Direct counts: `~/sp19/sa-rust-ids-work/sa-port-175/kc.py` run in a bar dir prints rows:rust/python, core:derived,
  scaffold per workload; S1's before counts in `~/sa-rust-ids-work/sa-port-175/before-S1.txt` (rust + python = before
  on every workload; e.g. core constant_value 336+1 = 337, _unit_power_units 18+15 = 33: the 15 are the shell's own
  fallback, a non-Rational exponent or e outside the table).
- Orion plant rows (c3c4 on fc939a2, c5 on 0643e9c): `sh ~/sa-rust-ids-work/sa-port-172/plt.sh DIR "" PLANT...` with DIR
  `~/sa-rust-ids-work/sa-port-172/c3c4` or `c5`; both ALL-DONE; worktrees removed.

## Module count: 14 of 32, unchanged
Retrace on d0374e9 (`~/sa-rust-ids-work/sa-port-175/rc-{dev,f6,core,wiring}.txt`, pass 1 `[query]`): core.py still runs
`_bound_split`/`_half_split`/`_imag_split` (derived terms, knowledge_core_live shell), `_coeff_term`, `_imag_term`, and
`ipi_split`/`pi_split` from functions.py; wiring.py's `_attributed.template` and `template.<lambda>` run on dev (6, 31)
and f6 (24, 134). c3-c5 removed `_half_templates`, `_bound_templates`, `irrational_root` from the per-query trace.

## Report draft
`~/sa-rust-ids-work/sa-port-175/c3c5-draft.md` (also below as results/port-6g-c3c5-draft.md): the three sections with
placeholders (RBAR_*, C3_/C4_/C5_ tables and counts, LANDED_SHA, COMMON_TAIL). Fill from bar-6g-c3c5r2, append to
port-6g.md, delete the draft file, then land.

## Next shell
`~/sa-rust-ids-work/sa-port-175/next-shell-scope.md`: `_pi_trig` + plain `_unary` as rows_tpl.rs families (f6 ~780,
core ~340 Python calls per pass), with the file:line map.
