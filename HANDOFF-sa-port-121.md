# Handoff sa-port-121 (step 6g(a), issue 323)

Branch port/6g, head after this commit, on rust-slice 7e2ece0 (6f). Tested source of the bar: 7113e58.

## Done so far
- 6g(a) code, 1cc3f1e + 7113e58: `rust-spike/slice/solver_rs/src/term/dispatch.rs` (pyclass `Dispatch`): ports
  `TemplateRegistry.clauses_for` (registry.py:226), `templates_for`'s class walk (:194: MRO, `_redefines` :62, lazy `_load`
  :141 called back once per class and epoch, counted `registry:python:_load`, import-time by the ownership ruling), `_split`
  (:265) and `_applied_to_nan`/`_may_be_nan` (templates/__init__.py:142-172). Class cache is a dict keyed on classes under
  `==` (as `_mro_cache`; the ordering_of_classes case: `Function('f')` twice across `clear_cache()`). Memo (PyDict, bound
  50,000) and class cache emptied when `state.epoch.EPOCH[0]` moves. A class with a template whose `__module__` isn't
  satassume.knowledge.templates or a live module goes whole to Python's `TemplateRegistry.clauses_for`
  (`registry:python:user`). Templates are still called back per node, each counted `registry:python:<qualname>`, until
  6g(b)/(c); `Compiled.wide_formulas` (_common, 6d) called back, counted.
- Wiring: `knowledge_live.install_dispatch()` (knowledge_live.py, before `install`) sets the instance attribute
  `registry.clauses_for = Dispatch.clauses_for`; `Engine.__init__` (engine.py:1318-1346) then takes Rust's bound method;
  with lra on it's wrapped by relations.py:423 `with_closed_units` (5c5's file, unchanged; Python per node, 5c5's).
  Counts flush into COUNTS at exit/undo; `plant:fired` goes to session_live.PLANT_FIRED.
- Plants (knowledge_live.PLANTS, SLICE_SESSION_PLANT): dispatch-ignores-epoch, -opaque-off, -redefines-off, -user-off.
- `dispatch_direct.py` (rust-spike/slice): same (compiled, formulas) as Python on 27 nodes and memo hits, opaque on 6,
  register-after-query matches Python, user path taken. Each plant fires and exits 1 there (orion, 02:00 UTC).
- Bar on 7113e58, pareto1 rows ~/sp19/sa-rust-ids-work/sa-port-121/ (sum.txt; base sa-port-116/suite), 02:01-02:26 UTC:
  suite 126 failed, 5958 passed, 23 skipped, 18 xfailed; by id new 0, gone 0, changed 0; passed with no firing 5957, with a
  firing 1 (test_ci_stream_reports_only_what_replays); handler multiset same as base (39 rows: 34 `_ok`, 4 `_rb_clauses`,
  1 "Already mutably borrowed" at _build_context). Tests 418 passed; direct exit 0. dev, fuzz, f6, value, rootof, core all
  MATCH (answers and end state), 0 handler rows. Plants: the 4 dispatch plants fired 0 on all six workloads (void there);
  knowledge-value-multigamma-drop fired 10 on value, DIFFER (control, as 6f). Suite plants: ignores-epoch changed 21
  outcomes (test_registry_versioning, test_templates, test_transfer_fuzz, ...) and 3 new TemplateKeyError handler rows;
  redefines-off changed 1 (test_s10_override::test_reproducers). opaque-off and user-off not run on the suite.
- Reach (knowledge.json): registry:rust dev 222, fuzz 190, core 780, f6 647, rootof 737, value 980 (+ memo hits);
  registry:opaque 0, registry:python:user 0, registry:epoch-clear 0 on all six workloads.
- Module count (count rule): registry.py and templates/__init__.py look whole once 6g(a) lands (their per-query items are
  Rust; `_load` import-time, `register` user API, user path ruled, `facts_for` only on the non-default path), so 9 of 32
  if both are among the 32: check against port-ownership.tsv before stating it.

## Left for 6g(a)
1. Gaps ruling: an `opaque` hidden-gap workload (`knowledge_opaque_wl.py` with `queries()`, like knowledge_core_wl.py;
   add "opaque" to live.py:270's tuple): queries built from `_applied_to_nan`'s cases (functions over nan/oo/zoo args,
   e.g. Abs(x + oo), sin(oo - x), gamma(zoo), Piecewise with oo - oo in a condition, Subs(nan, x, 1)). Show
   dispatch-opaque-off fires and is caught on it; rerun bar with WLS="f6 value rootof core opaque" (or only `extra` and
   `sum` phases if the code is unchanged). Epoch and user path: name them reached by the suite and dispatch_direct only
   (a workload is an ask stream and doesn't register).
2. Optionally run dispatch-user-off and dispatch-opaque-off as SUITE_PLANTS.
3. results/port-6g.md in port-6f.md's form; land with `PUSH=1 sh rust-spike/slice/p1/bar.sh land TESTED_SHA`
   (rebase rule: 5c5 landing first means showing the lra-on path MATCH), `agent report`, push.
Then 6g(b) rows families (wiring.py any_arity :539, rows_block :565, product :620, addition :650, power :223) and 6g(c)
the core and 6f shells (brief's map).
