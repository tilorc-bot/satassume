# Step 6d: `knowledge/templates/_common.py`'s per-query rows on Rust; table.py classified (issue 323)

Tested source **9f2f34d** (port/6d on rust-slice d91ee15, adapters part A's landing; rows pareto1
`~/sp19/sa-rust-ids-work/sa-port-130/`, sum.txt, .so febab913). Base suite rows: 6g(a)'s (`sa-port-123/suite`).
Landed: LANDED_SHA.

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
workload against base (KEPT_SHARES), and const_value's fire count per workload (CONST_VALUE).

**Call trace after the port** (rows `~/sa-rust-ids-work/sa-port-130/trace/post-*.txt`): on non-kept queries the only
`_common.py` code that runs is `const_value`: dev pass 1 5,089 (wiring 4,855, convert 228, core 6, and Rust's callback
inside these), pass 2 0. Every other `_common.py` call runs on a kept query: dev `out-of-scope` (48 queries: facts 4,
consts_of 4, pattern_key 4, units 2, Compiled 6), f6/value/opaque `refused` (the query's Python rerun after a Rust refusal).
`Compiled.__init__`<-knowledge_live.py (8 on dev 300 before this commit) is 0: `make_compiled`.

**Shadow** (registry_count.py `--shadow`: each Rust `facts`/`units` also run by Python's own function on a private cache,
compared on objects and every Pattern field, and on TemplateKeyError): 0 differences; facts/units compared dev 272/6,
core 1,251/35, f6 742/49, value 814/0, rootof 368/368, opaque 93/4, fuzz 300/1. The counter fires: with
`common-units-drop` it shows 4 differences on dev 300.

BAR_SECTION

**Module count (count rule): 9 of 32 passed**, was 7 at adapters part A: registry.py and templates/__init__.py, by step
0's two passes (sa-port-127, report a73c635: dev twice in one process, pass 2 `_load` 0 and `_covers` 0, pass 1 68 and
1,368; `_may_be_nan`'s only Rust-side caller is convert.py term_row, 8,863 per pass). Pending, not counted: relations.py
(adapters part B, factory() per session), `_common.py` (const_value's standing and the kept path, report 3796121) and
table.py (the same question). 12 of 32 if all three pass. Footnote kept: realroots and `value_units` are wired, and
neither dev nor fuzz reaches them (6f's workloads do).

**Kept on Python with reason:** `_rows_runtime`'s I/-I values (read once per process when Pow's generator is built, not
per query; I is algebraic and rows' constants are independent generators, so not exact without a reduction step) and
Floats (SymPy's precision semantics, the planner's default). Queries under a non-default registry; Sum/Product/Integral;
`enclose`. limits.py's `_common` names.

**Owed before any backend PR (unchanged from port-6f.md):** `scaffold:rebuilt:f6` and `scaffold:mismatch` until 0; the
NotImplementedError and hook re-entry contract notes; the items in OWED-satassume-rust.md. `_n_conflicts` in rust_plugin.py
is a test-plugin shim (64 tests), not a port.

**Not run:** seed1, history, forced moves, the native path, timing; the mutant 2/5/6/7/9 rerun, the boundary rescore and
suite column, order:_rows evidence (not caught meanwhile), the `_forms` guard test. No evaluator asked for.
