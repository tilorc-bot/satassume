# Step 6d: `knowledge/templates/_common.py`'s per-query rows on Rust; table.py classified (issue 323)

Tested source **c69cd6a** (port/6d rebased on rust-slice 1401d1f, 5c6's landing; rows pareto1
`~/sp19/sa-rust-ids-work/sa-port-131/`, sum.txt). Base suite rows: 5c6's (`sa-port-134/bar-5c6/suite`). Two rebases since the
first bar: on scope (803d073) and then on 5c6 (1401d1f), both clean; each incoming diff changed code the run executes, so
each got a full rerun. Earlier bars, stopped and kept as interim rows: 9f2f34d (adapters part A base, `sa-port-130/`) and
3624226 (scope's rebase, `sa-port-131-stopped-3624226/sum-interim.txt`). c69cd6a = 9f2f34d's code plus a test-only fix
(1325cc2): three slice tests asserted knowledge_live's `common:resolve`/`common:pattern` counts, which Rust's facts/units
bypass; they now read Rust's `Common` counts.
Landed: **1e44a7c** on rust-slice (incoming diff from 1401d1f empty; tested..landed adds only HANDOFF-sa-port-131.md).

**Code.** `term/common.rs` (`Common`, `Rules`): `facts` and `units` (_common.py:325, :340) over `_common._CACHE` itself (the
epoch memo `state.memos` empties and `register` clears), `MAX_CACHE`'s clear-all (:322), `TemplateKeyError`'s shape check
(:280), `units`' closing over the rule base and its `_signed` (:394); `Compiled` (:287) made with `__new__` and its slots set,
for `facts`/`units` and, through `Common.make_compiled`, for knowledge_live's symbol/constant/value templates;
`instantiate` (:162) and `Compiled.wide_formulas` (:299), which 6g(a)'s dispatch now calls on Rust
(`registry:rust:wide_formulas`, dispatch.rs:132-145; `compiled_t` is still the Python `Compiled` class Dispatch receives
at knowledge_live.py:214, and the objects it gets are Rust-made `Compiled`s of that class, so its reads are unchanged);
`Rules` (`rule`, `equiv`, :59-75), `lits` (:55), `ge2_alternatives` (:77), `consts_of` (:399), `pattern_key` (:407),
`const_key` (:50). `resolve` and `Pattern.__init__` were Rust already (6c); here Rust calls them directly.
`knowledge_common_live.py` binds Rust's names in `_common` and the runtime template modules that import them by name
(wiring, functions, core, nodes, special, atoms, rootof, stats, physics, _rows_runtime); not limits.py (kept on Python by
ruling) and not table.py (below). Still Python, named and counted: the template's `gen()` (`common:python:gen`, the
templates' own code until 6g(b)/(c)), `const_value` (`common:python:const_value`, a SymPy read of a numeric constant), and
on a kept query Python's own function (`common:kept:<name>`).

**table.py: not ported, classified.** Its only runtime caller is `core.ipi_rules` (core.py:480), which on Rust is
`sa_solver.core_ipi_rules` (knowledge_core_live.py:341) except on a kept query; its other users are offline
(tools/totality.py:556, gen_offline_data.py:44). Trace (registry_count.py `--trace _common.py,table.py`, every call tagged
with the query's kept reason): **0 calls into table.py on all seven workloads**, dev (two passes), core, f6, value, rootof,
opaque and fuzz, before the port (sa-port-128) and after it. Core reaches ipi on Rust (`core:ipi_rules` 28, `core:kept` 0).
Planner's ruling (03:42 UTC 8 Nov, addenda/sa-port-kept-reasons-ruling.txt): `out-of-scope` and `refused` are named
kept reasons, so table.py counts whole with the footnote "kept paths only", and `const_value` is a named SymPy callback, so
`_common.py` counts whole with the footnote "const_value". Condition: the share of queries kept per reason on each
workload against base, and const_value's fire count per workload: both below.

**Call trace after the port** (rows `~/sa-rust-ids-work/sa-port-130/trace/post-*.txt`): on non-kept queries the only
`_common.py` code that runs is `const_value`: dev pass 1 5,089 (wiring 4,855, convert 228, core 6, and Rust's callback
inside these), pass 2 0. Every other `_common.py` call runs on a kept query: dev `out-of-scope` (48 queries: facts 4,
consts_of 4, pattern_key 4, units 2, Compiled 6), f6/value/opaque `refused` (the query's Python rerun after a Rust refusal).
`Compiled.__init__`<-knowledge_live.py (8 on dev 300 before this commit) is 0: `make_compiled`.

**Shadow** (registry_count.py `--shadow`: each Rust `facts`/`units` also run by Python's own function on a private cache,
compared on objects and every Pattern field, and on TemplateKeyError): 0 differences; facts/units compared dev 272/6,
core 1,251/35, f6 742/49, value 814/0, rootof 368/368, opaque 93/4, fuzz 300/1. The counter fires: with
`common-units-drop` it shows 4 differences on dev 300.

**Bar** (on c69cd6a, .so 39ea2fff, every run imported the clone's tree)
1. Suite by id against 5c6's rows: 5,958 passed / 126 failed / 23 skipped / 18 xfailed, 6,125 ids; new 0, gone 0, changed
   0. Passed with no firing 5,957, with a firing 1 (`test_ci_stream_reports_only_what_replays`). S's standing: S's gate is
   met except for the 46 named stub failures, one cause. 426 step tests pass (6g's 14 files + test_scope_core.py);
   dispatch_direct.py and common_direct.py exit 0.
2. Dev (1,985) and fuzz (3,000): answers and end state MATCH, py vs rust, traced vs untraced, Python control. Workloads,
   whole engine Python against Rust: f6 (2,902), value (3,742), rootof (5,187), core (1,572), opaque (2,546) and scope (169)
   MATCH, each with its Python control MATCH. lra on throughout, as at 6g(a).
3. Plants (13, in `term/common.rs` and the binding): fired and caught (DIFFER) on workloads: `common-compiled-swap` (all 8),
   `common-facts-drop` (all 8), `common-consts-of-skip` (all but rootof), `common-rule-drop` (dev, core, f6, opaque, value;
   fires 0 on fuzz, rootof, scope), `common-units-drop` (dev, fuzz, core, f6, opaque, rootof; 0 on value, scope). Fire but
   MATCH: `common-pattern-key-type` and `common-const-key-type` (they change the cached key's type, which nothing reads
   differently; caught by common_direct). **Void on every workload (fired 0):** `common-equiv-one` (`Rules.equiv`),
   `common-ge2-drop` (`ge2_alternatives`), `common-key-shape-off` (`TemplateKeyError`'s shape check), `common-lits-flip`
   (`lits`), `common-max-cache-off` (`MAX_CACHE`'s clear-all), `common-wide-drop` (`Compiled.wide_formulas`). What catches
   them: common_direct.py, exit 1 for each of the 13 plants (exit 0 clean); the suite also catches `common-lits-flip` (43
   outcomes, test_rows_nary.py) and `common-key-shape-off` (1, test_templates.py::test_pattern_cache_rejects_a_key_reused_for_another_shape);
   the other four change no suite outcome. The suite's plant counter reads 0 for these (they count in knowledge COUNTS).
4. Quiet handlers (suite): 39 rows in 2 tests, multiset same as base (34 `_ok` + 4 `_rb_clauses` in `_consistent`;
   1 "Already mutably borrowed" at `_build_context`, the 46-stub cause). TermFault 0. 0 handler rows on dev, fuzz, the six
   workloads and the 26 plant runs' handler files.
5. Differences: none in answers, state or suite outcomes.

**Reached:** `facts`, `Compiled`/`make_compiled` and `consts_of` on every workload (consts_of not rootof); `Rules.rule` on dev,
core, f6, opaque, value; `units` on all but value and scope; `pattern_key`/`const_key` on most. Reached only by
common_direct.py (and, for `lits` and the shape check, the suite): `Rules.equiv`, `ge2_alternatives`, the shape check,
`lits`, `MAX_CACHE`'s clear-all, `wide_formulas` (dispatch calls it, but no workload template has wide rows). table.py:
0 calls on non-kept queries; core reaches ipi on Rust (`core:ipi_rules` 28, core workload).

**Kept shares (ruling 1)** (`kept_shares.py`, denominator converted + kept:*; base 5c6's rows for dev/fuzz, 6g(a)'s
e5c78e9 for core/f6/value/rootof/opaque, scope's own bar for scope): **identical to base on every workload, no rise.**
dev out-of-scope 24 of 1,221 (1.97%); fuzz, core, rootof, scope none kept; f6 refused 13 of 2,902 (0.45%: algebra Float 10,
lra callback on a derived term 1, scaffold rebuilt form differs 2); value refused 15 of 3,717 (0.40%, Float); opaque
refused 7 of 2,546 (0.27%: infinity/nan 5, holds inf/nan/Float 2). No other named exception fired.

**const_value (ruling 2)**, Rust's callback `common:python:const_value` on this bar: dev 4,605 (pass 2 0), fuzz 2,310,
core 28,473, f6 7,906, value 11,922, rootof 0, opaque 834, scope 449. Memo standing: Rust calls it only on a `_CACHE` miss
(per pattern key, cross-query within a registry epoch, common.rs:322-352), once per (slot, pred) that resolve reads, with
no memo inside a miss; the direct Python callers (wiring, functions, convert, core, knowledge_live, special, nodes) have
no per-term per-query memo, but every caller is 0 on dev pass 2. So it's a speed item for later, not a count question.
The follow-up (can `constfield` decide these from its enclosures?) is open for after 5c.

**Module count (count rule): 11 of 32**, was 9 at 6g(a): 7 + registry.py + templates/__init__.py (step 0's two passes,
sa-port-127, report a73c635: dev twice in one process, pass 2 `_load` 0 and `_covers` 0, pass 1 68 and 1,368; `_may_be_nan`'s
only Rust-side caller is convert.py term_row, 8,863 per pass) + table.py + `_common.py` (planner's ruling of 03:42 UTC 8 Nov,
after this clean bar). Footnotes: table.py, kept paths only (0 calls on non-kept queries on all seven workloads; it runs
only through `core.ipi_rules` on a kept query); `_common.py`, `const_value` (a named SymPy-semantics callback, fire counts
below); realroots and `value_units` are wired, and neither dev nor fuzz reaches them (6f's workloads do). Pending, not
counted: relations.py (adapters part B, `factory()` per session).
Kept-reason shares (STATUS line): dev out-of-scope 1.97%; refused f6 0.45%, value 0.40%, opaque 0.27%; fuzz, core, rootof, scope 0; all equal to base.

**Kept on Python with reason:** `_rows_runtime`'s I/-I values (read once per process when Pow's generator is built, not
per query; I is algebraic and rows' constants are independent generators, so not exact without a reduction step) and
Floats (SymPy's precision semantics, the planner's default). Queries under a non-default registry; Sum/Product/Integral;
`enclose`. limits.py's `_common` names.

**Owed before any backend PR (unchanged from port-6f.md):** `scaffold:rebuilt:f6` (dev 3, f6 45, value 221, opaque 15 on
this bar) and `scaffold:mismatch` (f6 2) until 0; the
NotImplementedError and hook re-entry contract notes; the items in OWED-satassume-rust.md. `_n_conflicts` in rust_plugin.py
is a test-plugin shim (64 tests), not a port.

**Quiet catches at the complete check** (`Engine._build_context`, handler_count.py; its planted raises are in
test_handler_count.py): suite 1 (the 46-stub cause, above), 0 on dev, fuzz, the six workloads and the plant runs.

**Not run:** seed1, history, forced moves, the native path, timing; the mutant 2/5/6/7/9 rerun, the boundary rescore and
suite column, order:_rows evidence (not caught meanwhile), the `_forms` guard test. No evaluator asked for.
