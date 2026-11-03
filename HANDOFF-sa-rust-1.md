# HANDOFF sa-rust-1: Rust ceiling measurement (issue 323)

State: instrumentation written and trialled on orion. **No pinned run yet, so there is no
result.** REPORT-rust-ceiling.md and the issue comment are not written. Stopped on context
(architect request), not on a blocker.

## To do
1. Set up pareto1:~/sa-rust-bench (see tools-rust/run.sh header). Run under
   `machine run pareto1 --quiet -r WHY -- bench-container run sa-eval-bench:1 ~/sa-rust-bench -- sh /work/tools-rust/run.sh`
   (BENCH_CPU=2 as in sa-lzr; background; about 12 min by estimate).
2. Run `samp fuzz` and plain `mon` once on orion first: neither has been run yet. Dev may need a
   shorter RC_PERIOD for enough samples (about 500 per run at the default).
3. Write the analysis (not started): medians over rounds 1-6, shares split None / definite, Amdahl
   1/(S+(1-S)/k) for k = 10, 50, and overhead of each mode against base. Every digest must equal
   9bafaa5's: dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6.
4. Write the report, push, comment on issue 323 (aggregates only), report and stop. No PR, no Rust.

## Tools (tools-rust/; run per sa-lzr's handoff: PYTHONPATH=clone:~/dev/sa-eval/ext/sympy:~/dev/sa-eval/.shim, PYTHONHASHSEED=0, cwd ~/dev/sa-eval/.shim)
- rc.py MODE WL. base / bdry (outermost timers on Engine.ask, is_, is_many, verdict) / mon
  (sys.monitoring intervals on sympy/ code, outermost entry by function, with calibration) / moncall
  (mon + callers; names only) / samp (SIGALRM sampler; "raw" and "corr" bracket the safepoint bias) /
  fn (coarse.py) / enc (encode.py).
- coarse.py: exclusive timers on functions that read or build SymPy behind the boundary.
- encode.py: flat-table encoding per boundary call: q (fresh), intern (process-wide), cl (closure of
  what the sessions touched; a lower bound on eager resolution, without patterns or linear forms).

## Planned definition of S
- S0: outside the bdry timers (conversion, relevance, memos).
- S as the code stands: S0 + SymPy frames inside the boundary + encoding, plus a stated, unmeasured
  crossing cost per ask as a sensitivity (no Rust, so it cannot be measured here).
- Resolved before the boundary: S0 + encoding (asks free, optimistic), and a second row where hash/eq
  vanish (integer ids) but non-hash asks still run once per query in Python.
- Separately: S if the fn groups stay in Python whole.
- Bracket for SymPy time: mon interval sum (upper), minus T_mon - T_base (lower), calibrated estimate
  and samp raw/corr in between.

## Draft boundary
- Stays before the call (sympy_api.py): ask, check_strict, _ask, _ask_general, is_constant_proposition,
  _relevant, _Split, _keys and helpers, _part_consistent, _consistent, _formula, to_formula,
  relation_atom, _engine_ask; the answer memo.
- Moves: Engine.ask / is_ / is_many / verdict and everything under them: Session, Solver, Relations,
  LRA and EUF cores, transfer, EqualitySharing.
- Behind the boundary but reads or builds SymPy (the fn groups): clauses_for and templates,
  closed_units; lra_adapter readers, constfield.from_sympy; EUFAdapter.parse and friends; relations.py
  readers (_is_number, _key, sympy_atom, ...); Engine._struct, _cone_info, _within_budget,
  _noncommutative, theory_scope.
- Correction to the issue: "query preparation" (Session.prepare_query) is session work (ensure,
  _relations), not a thin SymPy step. It belongs behind the boundary; fn mode times it all-in.
- Boundary calls are not one per query: outermost calls were dev 1,115 (ask 776, is_ 275, verdict 64)
  and fuzz 3,296 (2,812 / 169 / 315).

## Trial observations: orion only, NOT results
Orion was contended (the same dev run took 0.8 to 2.6 s) and is aarch64. Use its counts; its shares are
only a hint and none of these may be quoted as measured.
- Outside the boundary: about 6% dev (fn, 0.058 of 0.893 s), about 3% fuzz (bdry, 0.364 of 12.62 s).
- fn groups, summed: about 23% dev, about 19% fuzz; `struct` is most of it (dev 0.154 s, fuzz 1.39 s).
  Check whether that holds pinned and why it is so large.
- Encoding: dev q 0.008 / intern 0.005 / cl 0.011 s; fuzz q 0.051 / intern 0.027 / cl 0.110 s: about 1%
  or less.
- Outermost SymPy asks inside (moncall, deterministic): dev 282,918, fuzz 5,946,570, mostly
  Basic.__hash__. Actual construction is rare on dev: AssocOp.__new__ 144, Integer.__new__ 283;
  Basic.has 2,042 behind the cacheit wrapper. So a crossing cost per ask matters for fuzz.
- Digests matched for: dev base, bdry, samp, fn, enc, moncall; fuzz fn, enc, bdry, moncall.
  An early fn run changed dev answers (staticmethod wrapped wrongly; fixed), so keep checking.

## Known gaps
- `session_custom_calls` counts Session._custom, which also takes relation atoms, so it is NOT a count of
  user callbacks. Count ext.facts_for / ext.node_facts instead to report callbacks.
- The Basic.__hash__ count may include hash calls made through P.__hash__; check when categorising
  mon's `by` into hash / eq / construct / read / order / evaluate (the category map is not written).
- Step 4 of the brief (memo bound) applies only if the result lands near 2x.
