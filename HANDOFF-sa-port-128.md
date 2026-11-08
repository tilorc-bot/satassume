# HANDOFF sa-port-128 (step 6d, issue 323)

Branch port/6d, rebased on rust-slice d91ee15 (adapters part A; incoming diff relations_core.rs, session.rs,
session_live.py, which this step's run executes). Head = the WIP commit "Step 6d (WIP)". No bar run yet.

## Done
- Classification (task 1): pre-port trace `registry_count.py WL --passes 1 --trace _common.py,table.py` on core, f6,
  value, rootof, opaque, fuzz: **table.py 0 calls on all six** (core included). Rows ~/sa-rust-ids-work/sa-port-128/
  trace-pre-*.txt. Still to show: core reaches `core_ipi_rules` (knowledge COUNTS), and that table.py's only per-query
  use is `core.ipi_rules`' kept path (counted `common:kept:*`/`kept:<reason>`); then ask the planner per its ruling.
- Code (task 2), builds clean, dev first 300 queries: 0 raised (was 21 before the re-entrancy fix):
  - solver_rs/src/term/common.rs: `Common` (facts, units, instantiate, wide_formulas, make_rules, lits,
    ge2_alternatives, consts_of, pattern_key, const_key) + `Rules` pyclass. Cache is `_common._CACHE` itself (memos and
    register empty it); `Pattern`/`Compiled` made with `__new__` + slots. Callbacks counted: `common:python:gen`,
    `common:python:const_value`; kept query -> Python's function, `common:kept:<name>` (reads term_live._local.stack,
    no Python call). 13 plants (PLANTS at the top of common.rs). Methods take `&self` (re-entrant: gen() calls Rules()).
  - dispatch.rs: `set_common`; `_split` calls Rust `wide_formulas` (`registry:rust:wide_formulas`).
  - py.rs: `PyKnowledge.0`, `pattern`, `extract_rules` made pub(crate). lib.rs/term/mod.rs register `common`.
  - knowledge_common_live.py: binds Rust's names in `_common` and wiring, functions, core, nodes, special, atoms,
    rootof, stats, physics, _rows_runtime (not limits, not table, by ruling); undo restores, incl. lazily imported.
  - knowledge_live.py: imports it, PLANTS += its plants, install after install_dispatch, undo.

## Left
1. After port, dev 300 trace (t-dev300.txt) still shows `Compiled.__init__`<-knowledge_live.py 8 (rust_compiled's
   `Compiled((obj,), pat)`, knowledge_live.py ~:291): build it via Rust (e.g. a `Common.compiled` method) or name it.
   const_value<-wiring.py/core.py/convert.py are wiring's/conversion's own, not _common's per-query rows.
2. Shadow check of `Common.units` against Python `_common.units` on every workload (new generality: arbitrary gen()).
3. Full traces after port on dev (2 passes), core, f6, value, rootof, opaque, fuzz; quick MATCH via live.py.
4. Plants: run each of the 13 (SLICE_SESSION_PLANT) on dev/fuzz/workloads; void ones (max-cache-off, key-shape-off,
   likely pattern-key-type/const-key-type) need a direct test (write common_direct.py like dispatch_direct.py).
5. Bar: `sh rust-spike/slice/p1/bar.sh land SHA` without PUSH first (architect), read incoming diff, then PUSH=1.
   Report results/port-6d.md in port-6g.md's form; port-ownership.md + TSV; `agent report`; push.
