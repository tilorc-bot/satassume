# Handoff: sa-port-112 to the next 6f session (functions, special, rootof, nodes, physics, stats; issue 323)

**State:** port/6f head fc5dc52 (pushed), on rust-slice 2540ca7 (unmoved at 00:04 UTC 8 Nov; sa-port-109's 5c2/5c3 bars
were running on pareto1 then, so expect 5c2 to land first: rebase rule). Handed off at about 140k context. Read
HANDOFF-sa-port-111.md's "What was done" for the port itself; this file covers what's happened since.

## Running when I left (pareto1, detached; lease reason "sa-port-112 6f bar + f6 mutants on port/6f 3dca145")
Job `~/sp19/p1-job-sa-port-112.sh` (copy on orion: `~/sa-rust-ids-work/sa-port-112/p1-job.sh`), rows under pareto1
`~/sp19/sa-rust-ids-work/sa-port-112/`; ends with `all-done.txt`. Tested source **3dca145** (fc5dc52 adds only
test_knowledge_f6_fallback.py). .so sha256 6115aea8... (`build.txt`). Parts:
- `bar-sa-port-112.sh sa-port-112 port/6f tests suite live plants sum` with BASE=sa-port-104/suite (6e's landing rows),
  PLANTS = the 14 `f6-*` plus `knowledge-value-multigamma-drop`, no SUITE_PLANTS. Read `sum.txt`, `phases.txt`,
  `tests.txt`, suite `handlers.*.jsonl` (quiet firings), `term.*.json` (the suite's `f6:*` counts for the TSV's `runs`).
- beside it: plain rows (`plain/`), then `mutate_knowledge.py mut plain --only base,<16 f6-*>,<5 realroots-*> --jobs 4`
  (`mut/results.jsonl`, one row each; base must be `no` everywhere; `off_by_wl` per workload), then the f6_trace suite
  (`f6trace/`, Python engine, import-time vs runtime for the suite: port-6f-trace.md's missing column).

## Done and checked (orion, `~/sa-rust-ids-work/sa-port-112/short/`, tree fc5dc52's predecessor 3dca145, .so d6bc7de4)
- Shadow runs (sa-port-111's): 0 mismatches on f6, value, rootof, core. `f6:refuse` = `refused:algebra: Float` (f6 90,
  value 138): `shifted`/`_doubled` on a Float term, algebra.rs:45 refuses, `term_live` reruns the query on Python
  (term_live.py:906-925). `scaffold:mismatch` 16 (f6): raw Add form check refuses, same rerun. Explained, not faults.
- **Plain vs atoms MATCH, byte for byte: dev 1,985, fuzz 3,000, f6 2,902, value 3,742, rootof 5,187, core 1,572.**
  `fault` 0. `realroots:root_facts` 5187 under atoms (not doubled). dev reaches `_cosh_shift_split` 3, `shifted` 3; fuzz none.
- **Plants, each fired and caught (atoms+plant vs plain, lines differing):** f6 wl: pi-trig 736/676, cosh-rules 640/640,
  cosh-split 640/640, shifted 388/115, unit-interval 162/95, parts-round 192/132, accum 54/49, idx 32/32, quantity 32/32,
  random 36/33; value wl: genocchi 562/52, doubled 168/25, multigamma 120/7, shifted 2474/22; rootof wl: rootof 5187/3463.
  **value_units footnote plant** `knowledge-value-multigamma-drop` (knowledge_live.py rust_compiled): value wl fired 80,
  10 rows differ (state digests, same answers), all 10 multigamma queries. That's the value_units footnote's own plant.
  **realroots footnote:** its plant is the `realroots-*` Rust mutants scored on the rootof wl in the pareto1 mut run.
- `cargo test tf6` 2 pass. `test_knowledge_f6_fallback.py` 6 pass: both named callbacks fire, answer as Python, a raise
  is a KnowledgeFault. `f6:unit_interval:float` is 0 on every workload; this test is its firing case.
  `f6:multigamma_value:python` 168 on value.

## What's left (in order)
1. Read the pareto1 job (above). If 5c2 landed on rust-slice meanwhile, rebase (`bar.sh land` without PUSH prints the
   incoming diff); 5c2 changes executed code, so rerun the whole bar on the landing source (copy p1-job.sh, drop
   mutate/f6trace, new OUT).
2. Docs (doc only): results/port-6f.md (model port-6e.md: tested/landing SHAs, import time from port-6f-trace.md plus
   the suite trace, ownership before/after, bar 1-5, fallbacks with counts, not run). port-ownership.tsv rows 217-230,
   239-242, 259-266 and the .md rows 60-66; PORT-INVENTORY.md 481-516 (reclasses: `special._register` not port, dead,
   removal is a separate held Python PR; `rootof._coefficients` conversion; `_value_units` offline as is).
   **Ownership before:** 26 rows (not 27 as sa-port-111 wrote: functions 14, nodes 3, physics 1, rootof 3, special 4,
   stats 1), 25 `port` + `_value_units` offline, all Python, owner 6f. TSV total today: Rust 420, called back 28, Python 364.
   **Proposed after:** Rust whole, swapped 9 (`shifted`, `_parts_of_round_rules`, `_pi_trig_rules`, `_cosh_shift_rules`,
   `_cosh_shift_split`, `_accum`, `_facts`, `_doubled`, `_multigamma_rules`). Rust partial 5: the work is in an extracted
   helper that's swapped, the row is the Python wrapper (`_in_unit_interval_units` via `_unit_interval_units` with the
   Float callback, `_genocchi_half` via `_genocchi_half_rules`, `idx_units` via `_idx_facts`, `quantity_units` via
   `_quantity_facts`, `randomsymbol_units`: conversion for its reads plus `_random_units`). Python shells 9 (`_unary`,
   `_exp_ipi`, `parts_of_round_templates`, `_pi_trig`, `_cosh_shift`, `nary`, `multigamma_templates`,
   `accumbounds_templates`, `crootof_units`): today Python, left "arity check + `_common` (6d) + rows' gen (6g)",
   finisher 6d/6g. Per the handoff rule, don't count them as moved Rust code. Conversion 1, not port 1, offline 1.
3. Module count: 6e counted core whole with Python shells over `_common`. On that precedent the six reach 14 of 32,
   with footnotes for functions (`f6:unit_interval:float`) and special (`f6:multigamma_value:python`, SymPy evaluation of
   multigamma's value, a candidate permanent callback like `enclose`). Without it, still 8. Give both and let the planner
   rule. Core's callback footnote stays. Drop the realroots footnote only if a `realroots-*` mutant is `cmp` on rootof in
   `off_by_wl`. The value_units footnote goes: its plant is caught above.
4. `bar.sh land` with PUSH=1, then `agent report` (module count, ownership counts before/after), SendMessage architect.

## Map
- knowledge_f6_live.py: install :61, call/refuse :102, fallback :112, unit_interval :187, multigamma_value :211, splits
  :216-258, PLANTS :40. knowledge_live.py: plants :61-66, value plant in rust_compiled after `_wrap(r)`.
- mutate_knowledge.py: f6 rows after `core-imag-rules-strict`; wls tuple includes f6.
- tf6.rs (323 lines): fns at :32 pi_trig, :79 cosh, :115 genocchi, :123 unit_interval, :161 multigamma, :186 rootof,
  :205 random, :247 cosh split, :273 shifted, :285 doubled.
- Orion runners: `~/sa-rust-ids-work/sa-port-112/{run.sh,one.sh,onep.sh}` (onep.sh sets SLICE_SESSION_PLANT).
