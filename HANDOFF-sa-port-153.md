# HANDOFF sa-port-153: adapters C2, bar C2b running on 3a34da4 (rebased over 6g(b) b838d3f); not landed (issue 323)

## State (8 Nov, ~07:45 UTC)
- port/adapters (force-pushed, own branch) = **3a34da4**: rust-slice **b838d3f** (6g(b) landed) + c62f25d (pi_laurent,
  was e12e622) + 2 handoff commits of sa-port-152 + 3a34da4 (cert workload, was f296ed1). The rebase had one conflict
  in live.py (6g(b) added `wiring` to the hidden-gap list; resolved keeping both).
- **Landing bar C2b running**: tested 3a34da4, pareto1, rows `~/sp19/sa-rust-ids-work/sa-port-153/bar-C2b/`, launcher
  log orion `~/sa-rust-ids-work/sa-port-153/bar-C2b.log`, local `machine run` PID **894668** (lease 561e88b8), started
  07:42. Env file pareto1 `~/sp19/bar-sa-port-153-env.sh` (script `~/sp19/bar-sa-port-153.sh` = p1/bar.sh, sha 1f9c6d92):
  BASE = `sa-port-140/bar-BC2/suite`, KEPT_BASE = `sa-port-140/bar-BC2`; PLANTS `cf-laurent-rational pay-int-offset
  ad-kind-swap theory-no-assume al-drop-delta`; WLS `f6 value rootof core opaque scope loop zero wiring cert`; SEED1=1;
  SUITE_PLANTS=zero; TESTS = BC2's list + test_cf_laurent.py; DIRECT as BC2 (incl. `common_direct.py common-facts-drop`);
  N=8. Done marker `bar-C2b/done.txt`, summary `bar-C2b/sum.txt`. Clone on pareto1 `~/sp19/dev/sa-port-153`.
- **Base caveat:** BASE is BC2's suite (before 6g(b)). New ids/changed outcomes that 6g(b) brought must be explained
  against 6g(b)'s own bar rows (sa-port-145's bar on 7e730df, results/port-6g.md on rust-slice), or re-run bar_sum with
  BASE = that bar's suite. Kept reasons: same, 6g(b)'s bar rows for the kept base.
- Superseded bar C2 (f296ed1, before 6g(b)) stopped by me at its plants phase (session 3682296 on pareto1 killed);
  rows `bar-C2/` are partial, not a landing bar.
- Local Rust build of 3a34da4 in the clone (orion .so). Uncommitted: nothing. sa-port-152's base worktree removed.

## Results this session (orion, `~/sa-rust-ids-work/sa-port-153/`)
- **Plant fixed:** cf-laurent-rational is void on dev (121 fires) and fuzz (200) because `Y` (lra.py :930-960) is
  `(nt+1)*had*(X+1)*2**16`, far above every split there. New workload `cert` (rust-spike/slice/cert_wl.py, `live.py cert`,
  61 queries): Rust vs Python MATCH; with the plant 119 fires, **2 answers DIFFER (q53, q59: True -> None, the two-term
  `t + y` form at c = 10**8; single-variable bounds are decided by assert_lit's rounding, no split)** and 34 end/stream/
  lra states differ. Same on 3a34da4 (`cert2/`) and on e12e622 (`cert/`).
- **Suite also catches it:** `sp/` (8 LRA test files, rust_plugin, -n 3): without plant 44 failed (all failing on BC2's
  base too: stub cause, theory-level tests), with the plant 46: +`tests/test_lra_exhaustion.py::test_certificate_rational_rows_and_pi_bounds`
  and `::test_certificate_reads_the_constfield_limits`. (On e12e622.)
- **Callback counts (sa-port-152 `trace/`, base 03c075d vs e12e622, Rust, per pass):** pi_laurent dev 121 -> 0, fuzz
  200 -> 0. Element._new dev 703 -> 703 (lra_live _rust 460; lra_backend check 126 -> 69, _state 117 -> 174), fuzz
  1,552 -> 1,552 (_rust 598; check 488 -> 386, _state 466 -> 568): the Elements check stopped building are built by
  _state later, so C2 removes none (step (b)). enclose dev 100 -> 100, fuzz 0 -> 0.
- **(a) six rows:** Element.__repr__ only from the harness (state.py f/lra_text/genexpr/fast, live.py show: dev 2,870,
  fuzz 37,501, unchanged); to_sympy, _coerce_foreign, _sympy_constant, Constant.__repr__ 0 on dev and fuzz. Positive
  control `trace/control.py` -> `trace/control.txt`: every wrapper counts when called (so the zeros aren't false). Rust
  reaches Python constfield only by call-time lookups (constfield.rs:1232 `call_method1("enclose")`, :2066 `_new`), which
  the patch sees. `_coerce_foreign`: only caller Element.__eq__ (constfield.py:1214) with a SymPy operand; suite reaches
  it via tests/test_constfield.py:845 (`PI == sympy.pi`); no engine path: removal candidate next to `_bound`.
- **Numbers:** keep counter 155 and plants 111-113 (architect: 5c7/sa-port-154 takes numbers after ours). 6g(b) didn't
  touch relations_core.rs/session.rs.

## Drafts (not committed)
- `~/sa-rust-ids-work/sa-port-153/docs-draft.patch`: port-ownership.md (:101 pi_laurent out of the called-back row, new
  row landed C2 Rust; :104 six rows "not port: output/display conversion (C2 ruling)"; :131 partials row) and the TSV
  (8 rows: pi_laurent, the six, Element._new finisher "its own step after C2"). Replace `LANDED` with the landed SHA,
  `git apply`. Note: the md's summary count table (385/17/9…) doesn't match the TSV (523 landed Rust …); it was stale
  before C2; say so, don't silently recount.
- `~/sa-rust-ids-work/sa-port-153/report-draft.md`: the report's opening and "What moved".

## Next
1. When bar-C2b is done: read `sum.txt` (by head/rg), the five items. If it differs, see the base caveat first.
2. Check rust-slice: if it moved again, `sh rust-spike/slice/p1/bar.sh land 3a34da4` (no PUSH), read the incoming diff;
   source under the guard -> full bar again. Otherwise `PUSH=1 sh rust-spike/slice/p1/bar.sh land 3a34da4`.
3. Report: extend results/port-adapters.md (form of the B+C1 section, all MUST-STAY items), apply docs-draft.patch,
   commit, push, `agent report`, SendMessage the architect.
