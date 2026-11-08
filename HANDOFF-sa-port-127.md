# HANDOFF sa-port-127 (step 6d, issue 323)

Branch port/6d, head 6e2d0ed (rust-slice f65cc68 + rust-spike/slice/registry_count.py). No 6d code written.
Next brief: ~/dev/architect/briefs/NEXT-port-6d.txt (task, file:line map, must-stay).

## Step 0 (architect's request; report a73c635, Status: progress)
- registry.py PASS: dev (1,985) twice in one process, default Rust backend (live.py --check plain install),
  process + engine memos emptied before pass 2, no epoch bump. pass 1: `_load` 68, `_covers` 1,368,
  `register` 28 (lazy built-in modules); pass 2: 0, 0, 0. Plant SLICE_PLANT_COUNT=1 shows counters fire.
  Why beyond dev: dispatch.rs class_entry (:171-220) calls `_load` only when building a class entry, cached
  per class until EPOCH moves; EPOCH moves at registry.py:189, extensions.py:85, engine.py:1428/:1444 only.
- templates/__init__.py PASS: `_may_be_nan` <- convert.py term_row only, 8,863 per pass. `_applied_to_nan`
  (:171) runs only on Python's `TemplateRegistry.clauses_for` (Python backend, or `registry:python:user`).
- Rows: ~/sa-rust-ids-work/sa-port-127/rc-dev3.txt, rc-dev-trace.txt.

## 6d head start: trace on dev (registry_count.py dev --trace _common.py,table.py)
- table.py: 0 calls on Rust, both passes. Runtime caller only core.ipi_rules (core.py:480) -> Rust
  `core_ipi_rules` (knowledge_core_live.py:341) except kept queries; offline: tools/totality.py:556,
  gen_offline_data.py:44.
- _common pass 1: const_value 5,089; Rules.rule 618; Compiled.__init__ 315; facts 276; consts_of 197;
  pattern_key 168; units 14; Rules.__init__ 24; _signed 28; const_key 6. Pass 2: units 6, Compiled 6, _signed 4
  (Dispatch's per-expr memo answers the rest).

## Run the probe
    . ~/sa-rust-ids-work/env.sh; export PYTHONPATH=$PWD:$W/sympy:$W/shim   # from the clone root
    cd rust-spike/slice; $PY registry_count.py dev [--limit N] [--trace _common.py,table.py]
