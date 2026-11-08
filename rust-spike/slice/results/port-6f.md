# Step 6f: knowledge/templates/{functions,special,rootof,nodes,physics,stats}.py on Rust (issue 323)

Tested source **15a2710** (port/6f on rust-slice 064a1b4, 5c4's landing; rows pareto1 `~/sp19/sa-rust-ids-work/sa-port-116/`,
.so 4e2bd749). The same bar ran first on 88e180e over d14628d (`sa-port-113/`, same results); 5c4's relations_core.rs and
session.rs changes are executed code, so the bar was rerun whole. Base suite rows: 5c4's (`sa-port-115/bar-5c4/suite`).
Code: `term/tf6.rs`, `knowledge_f6_live.py`, installed by `knowledge_live.install()`, so it runs on the default Rust backend.

**Import time (port-6f-trace.md on dev, fuzz and the four knowledge workloads; the suite trace, Python, 6,084 passed,
`sa-port-112/f6trace/`):** only each module's `<module>` (constants and slot indices), once per process (suite: 6 processes).
Data, not ported. Everything else is runtime, the per-class factories once per class per process. `special._register` runs
0 times anywhere (dead code; reclassed not port). `functions._value_units` is offline by ruling; in the suite trace it runs 8
times, on Python, evaluating `expr.func(c)` and handing the value to atoms' `value_units`, which is on Rust (6b).

**Ownership, the six (port-ownership.tsv):** before: 26 rows, 25 `port` + `_value_units` offline, all Python, owner 6f.
After: 14 Rust: 9 swapped (`shifted`, `_parts_of_round_rules`, `_pi_trig_rules`, `_cosh_shift_rules`, `_cosh_shift_split`,
`_accum`, `rootof._facts`, `_doubled`, `_multigamma_rules`) and 5 partial, Python wrappers over a swapped helper
(`_in_unit_interval_units`, `_genocchi_half`, `idx_units`, `quantity_units`, `randomsymbol_units`). 9 Python shells,
finisher 6d/6g (`_unary`, `_exp_ipi`, `parts_of_round_templates`, `_pi_trig`, `_cosh_shift`, `nary`, `multigamma_templates`,
`accumbounds_templates`, `crootof_units`): what's left in them is the arity check, 6d's `const_key`/`facts`/`units` and 6g's
rows `gen`. Not port: `_coefficients` (conversion), `_register` (dead), `_value_units` (offline). Table total: Rust 420 to
434, called back 28 to 28, Python 364 to 350. (6e marked its 4 shells Rust; on that reading, Rust 443, Python 341.)
`_common`/`table` helpers ported for 6f: none. Rust's output is built into `_common.Rules`; the rest stays for 6d.

**Module count.** 14 of 32 on 6e's precedent (core counted whole with Python shells over `_common`), or 10 of 32 if the
shells keep functions, nodes, rootof and special out (physics and stats count: each has one row, a one-line `units(...)`
call, 6d's, over a swapped helper, like core's partials). Footnotes:
- core.py: 2 named SymPy-arithmetic callbacks (`_unit_power_units` non-Rational exponent, `_imag_templates` all-number Add),
  pending the constfield question after 5c. Unchanged.
- functions.py (14 only): 1 named callback, `f6:unit_interval:float` (a Float argument: SymPy's precision semantics).
- special.py (14 only): 1 named callback, `f6:multigamma_value:python` (SymPy evaluates multigamma at a constant;
  a candidate permanent callback like `enclose`).
- **Dropped: realroots and `value_units`**, each with its own plant caught on 6f's workload (reclass ruling). realroots:
  `crootof_units` reaches `root_facts` on the rootof workload (`f6:_facts` 368), and 4 of 5 realroots mutants are caught
  there by the comparison (chain-no-negate 886 answers, sign-boundary 102, squarefree-skipped 114, imaginary-sign 2, on 15a2710; bits-off-by-one only by unit tests). `value_units`: the plant
  `knowledge-value-multigamma-drop` fires 10 times on the value workload, through multigamma's call, and is caught (DIFFER).

**Bar** (on 15a2710)
1. Suite by id against 5c4's rows: 5,958 / 126 / 23 / 18, 6,125 ids; new 0, gone 0, changed outcome 0. Passed with no
   firing 5,957, with a firing 1 (`test_ci_stream_reports_only_what_replays`). S's standing: S's gate is met except for the
   46 named stub failures, one cause. 418 step tests pass (the 14 files in TESTS).
2. Dev (1,985 queries) and fuzz (3,000): answers and end state MATCH, py vs rust and traced vs untraced; Python control
   MATCH. The four knowledge workloads, whole engine Python against Rust: f6 2,902, value 3,550, rootof 4,784 and core 1,572 MATCH.
3. Plants, 15, one per moved function (SLICE_SESSION_PLANT), each against this run's Python: every one fires and is caught
   (DIFFER) on each workload where it fires. Fired on: dev only `f6-shifted` (2); fuzz none (fuzz reaches none of the six);
   f6 wl accum 5, cosh-rules 7, cosh-split 80, idx 1, parts-round 3, pi-trig 38, quantity 1, random 4, shifted 45,
   unit-interval 18; value wl doubled 21, genocchi 50, multigamma 15, shifted 224, value-multigamma-drop 10; rootof wl
   rootof 368; core wl pi-trig 21. tf6.rs mutants (mutate_knowledge, on 88e180e, `sa-port-113/mut/`): 13 of 16 caught (12
   by the comparison, cosh-split-nonint as a crash); not caught by any workload or unit test: `f6-multigamma-zero` (the
   rule for a non-integer `p`, which no query reaches), `f6-doubled-no-raw` (`mul` for `raw_mul` on `2*x`, likely
   equivalent on reachable inputs), `f6-random-integer` (needs a RandomSymbol over an integer-declared symbol; the f6
   workload has none). The plants cover the same functions.
4. Quiet handlers (suite): 39 rows in 2 tests, the same multiset as base (`_consistent` 34 `_ok` + 4 `_rb_clauses`;
   `Engine._build_context`, 1 "Already mutably borrowed", the 46-stub cause). Quiet catches at engine.py:1906: 1, the suite,
   as on base; 0 on dev and fuzz (12 handler files and 30 plant handler files, 0 rows). TermFault and KnowledgeFault 0.
5. Differences: none in answers, state or suite outcomes.

**Python fallbacks and counters (dev / fuzz / suite; f6, value, rootof workloads):** named SymPy-semantics callbacks, loud
(an exception is a KnowledgeFault): `f6:unit_interval:float` 0 / 0 / 2 (workloads 0), `f6:multigamma_value:python` 0 / 0 / 9 (value wl 21). Kept on
Python and counted: `f6:kept` 0 / 0 / 6 (f6 wl 24, value wl 33), `f6:no-query` 0 / 0 / 3,305 (tests calling Engine
directly), `f6:refuse` (Rust's form check refused, reran on Python) f6 wl 10, value wl 15. Scaffolding (`scaffold:rebuilt:f6`, a derived slot term rebuilt by SymPy from
Rust's row and checked against it): dev 3, fuzz 0, suite 116, f6 wl 45, value wl 221; refused on a form mismatch (`scaffold:mismatch`) suite 6, f6 wl 2. Must reach zero before any backend PR.

**Shared files and fixes:** `rust-spike/slice/live.py` (shared) loads the f6, value, rootof and core workloads, so bar.sh's
`extra` phase compares them whole engine Python against Rust under the plants. Lazy-import fix (c62dd7d):
`knowledge_f6_live` imported the six modules at module level, so `import knowledge_live` loaded sympy.stats,
sympy.physics.units and the lazy template modules (test_install_keeps_the_callers_lazy_and_undo_restores failed). install
now swaps loaded modules and the rest through a meta_path hook right after each executes; undo removes the hook and restores
every name. test_fallback_raise_is_loud asks once on Python first (it passed or failed by test order).

**Not run:** seed1, history, forced moves, the native path, timing; the mutant 2/5/6/7/9 rerun, the boundary rescore and
suite column, order:_rows evidence (not caught meanwhile), the `_forms` guard test, the suite under the plants. The
Python-side suite rerun wasn't needed to land. The `_n_conflicts` view in rust_plugin.py is a test-plugin shim (64 tests),
not a port. No evaluator asked for.
