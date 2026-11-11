# HANDOFF sa-port-276: formula step (issue 323), sixteenth part

Branch `port/formula`, head = this commit, on rust-slice **9151316**. **Unbarred, unlanded.** Handed off at the context
budget after the gate's first item (the plant table), between items. Numbers: rust-spike/slice/results/port-formula.md,
section "sa-port-276" (the file's last section). Before this: HANDOFF-sa-port-274.md.

## Done this session
- **d6f57a2**: fm_rows.py writes each run's `fired` (term_live `plant:*`, session_live PLANT_FIRED), so the plants
  `fm:plant_fired` doesn't count (600, 611, 664-667) show their firing; plant 666 counts its cut (term_live.py, rollback).
- **The plant table (ee2f6fb)**, pareto1 sweep `sw1` on d6f57a2 (153 runs, exit 0; plain rows: 20 workloads, 0 differ):
  - **612 caught**: answers on cert, transfer:7:60, transfer2:3:40, zero; fm row on budget, lra, scope; cls by the state
    comparison (livecmp DIFFER, `_SPLIT` 23 vs 25; plain MATCH). Its kept test asserts behaviour (atoms vs Python's).
  - **608**: lra caught (fm:again 98 -> 69, answers equal). Void on f6: the reconversions there are the session's own
    `fnode` (session.rs:1324), never `Hand.node` (formula.rs:639, KEPT's only reader). Void on twin: fm:again 0.
  - **662 kept-test catch (R1)**, per the planner.
  - **600, 664, 665, 611, 667: kept-test catches** with one-line reasons in the table (665 fires on no workload: nothing
    clears the memos mid-run; 611/667 fire on the 4 workloads with discarded runs, read by term_discard only).
  - **666 is speed-only since ded8c3f**: the discard now rolls back the dispatch memo, so the rerun refills the cut
    `_CACHE`; its kept test test_cache_rollback.py:41 FAILS ("plant 666 no longer fires"). To the planner: a wrong-value
    plant at the same site, or drop R3's `_CACHE` exemption (cutting `_CACHE` back may now be harmless).
- **knowledge_live.py `undo`** (ee2f6fb): removes only the stores still in `NATIVE_EXTRA` (test_cache_fix.py undoes inside a
  test and again in its fixture; 3 errors since ded8c3f). test_cache_fix.py 6 pass serially.
- **Carrier line**: slice-only (term_live's fallback from adapters.rs `Reader.id` comparing classes by identity; main runs
  relations.py itself). Read from the code, not run on main.
- Discarded runs per workload, this head: f6 13, opaque 7, value 15, wiring 1, lra 456, the other 15 are 0.

## Not done (gate order)
1. 666's replacement or retirement (planner), and its failing kept test; 664 under xdist (-n 4 failed once, before the
   undo fix; not rerun).
2. 4c (relations.py:1116 `engine.is_(u, "real")`: no crafted query reached it in 244's try; find a suite/workload query
   with equal-but-distinct numbers or footnote it), 4d (now covered by the table), 4e, 4h, 4j; 4f's bar invocation, 4i's line.
3. The bar: FM_PLANTS with 612/613; add cls to WLS so the extra phase runs 612 under the state comparison (bar.sh :137).
- Not run on this head: the suite, the slice files other than the 8 in `kt`, the 20 workloads under `--check entry`.

## File:line map (this head)
- formula.rs: PLANTS :103, plant 612 :291-:299, `Hand.node` :630 (KEPT read :639), `Hand` drop :707 (KEPT fill :712),
  `fm:again` tick :544. session.rs: `fnode` :1318 (convert :1324), `atoms_of` :1345.
- term_live.py: `_Mark._note` :207, `rollback` :233 (611 :241, 667 :249, 666's count just before the popitem loop).
- knowledge_live.py: dispatch stores :268, `undo` :285.
- fm_rows.py: `run` :29 (`fired` in `dump`). p1/bar.sh: plants :121, extra :137, fmrows :150-:159.
- Kept tests: test_formula_nodes.py:155 (612), :274 (600); test_cache_fix.py:140 (664), :172 (665);
  test_cache_rollback.py:38 (666, failing); test_discard_exempt.py:74 (667), :104 (611).
- relations.py:1116 (4c); test_cbm_noid.py:255 (the cache.store key test, via `is_(u, 'extended_real')`).

## Helpers and output
- pareto1 `~/sp19/sa-rust-ids-work/sa-port-276/`: sweep276.sh OUT, sw_sum.py DIR, sw1/; tree `~/sp19/dev/sa-port-276`
  at d6f57a2 (.so 3f92f9fe..., cargo needs PATH=/home/tilo/.cargo/bin RUSTUP_HOME/CARGO_HOME=/home/tilo/...).
- orion `~/sa-rust-ids-work/sa-port-276/`: p612e/run.sh WL (py, rust, rust+612 under --check entry, livecmp), kt/run.sh
  (8 kept test files), f6probe/ (probe.py, probe2.py: all session_counts at exit; PLANT=).
- No plant or counter taken. Free: plants 614-629, 668-669; counters 649-659, 673-679.
