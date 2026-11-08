# Handoff sa-port-163 (step 6g(c), issue 323)

## 6g(c2): 14b76fd, not landed yet; its bar is running on pareto1
- port/6g = ac520b2 (14b76fd plus HANDOFF-sa-port-161.md) plus this file. Both are doc-only at the root, so tested 14b76fd still
  covers the source.
- Bar rows: pareto1 `~/sp19/sa-rust-ids-work/sa-port-161/`. Wait for its **done.txt**, then read sum.txt. Phases so far:
  build 09:52, tests 09:57, suite 09:59 UTC. c1's bar took about 1.5 h, so expect done around 11:20.
- Config is in sa-port-161's HANDOFF (BASE = `~/sp19/sa-rust-ids-work/sa-port-157/suite`). Other bars running on pareto1 at
  handoff: sa-port-158 (5c7) and sa-port-160 (Element._new E2). First to finish lands; see the rebase rule.
- To land: `git checkout port/6g`, rebase on origin/rust-slice, run `bash rust-spike/slice/p1/bar.sh land 14b76fd` without
  PUSH, then with PUSH=1. Then write the 6g(c2) section of rust-spike/slice/results/port-6g.md in c1's form (lines 181-283).
- shadow:direct counts for the c2 section: run `~/sa-rust-ids-work/sa-port-163/shadowcount.py` from the clone root on
  14b76fd's build. c1's counts are in `~/sa-rust-ids-work/sa-port-161/shadow-c1.txt`.
- Orion c2 rows: `~/sa-rust-ids-work/sa-port-161/c2/`. rows-mul-ipi-drop fired 0 on core and dev, because s is a derived Mul
  there. Report it void with that reason unless the bar's plant runs show a reach.

## 6g(c3) power: a8e2a4f; and 6g(c4) WIP: 7270edb, both on branch **port/6g-c3** (pushed, over ac520b2)
- What changed in rows_tpl.rs:
  - `RowsTpl::split` now covers `_exp_arg` (both callers, `matches` Head included), `_unit_angle`, `ipi_split`,
    `irrational_root`, `_unit_power_units` and `_pow_bound_templates`.
  - New `ONE` and `MULTI` consts. `direct_split` picks which ids to read by name. `irrational_root` with a None constant
    returns False with no query and no Python.
  - `direct_rows` handles `_pow_bound_templates`: `Direct1::PowBound`, then `Common::facts` with the key
    `('pow_bound', c0, c1, const_key(e)|None)` and gen `tcore::pow_bound_rules(idx)`. The shadow shows `(c0, c1, u, idx)`.
  - `direct_pow` handles the other five.
  - `pow_build` computes `ipi_rules` with `tcore::ipi_rules` unless `c.kept`, and shadows it.
  - New helper `rat_of`.
- Python side:
  - knowledge_core_live `shadow_split` has special cases for `_pow_bound_templates` (it maps the idx through
    `core._INT_BOUNDS`), `ipi_split` (`_pi_split(arg, True)`), `ipi_rules`, `constant_value`, and the tuple-arg shells.
  - Seven plants, in both lists: rows-exp-arg-none, rows-unit-angle-neg, rows-ipi-split-neg, rows-irrational-false,
    rows-unit-power-drop-last, rows-pow-bound-drop-last, rows-ipi-rules-drop-last.
- test_knowledge_core_shapes: 17/17 on orion, with seven new DIRECT entries and six new cases. Shadowcount for a8e2a4f is in
  `~/sa-rust-ids-work/sa-port-163/shadow-c3-wip.txt`. Every new direct path is reached and there are 0 mismatches. The
  "split" counts treat a False from `irrational_root` as a split, so they are cosmetic.
- Orion checks are **still running, detached**: `~/sa-rust-ids-work/sa-port-163/c3-run.sh` writes to `c3/`, and `c3/ALL-DONE`
  marks the end. It covers core, dev, f6 and wiring, plain and with each c3 plant.
  - So far: core MATCH, dev MATCH.
  - **Don't rebuild the clone's .so until ALL-DONE exists.** Those runs load a8e2a4f's build. The c4 Python edits are
    present in the tree for those runs but inert there (one plant name, a shadow branch).
  - Fire counts: the session.json files, key `plant:fired`.
- 7270edb (c4 WIP, **not built, not run**): `RowsTpl::constant_value` / `direct_constant_value`.
  - Computes exact Rationals for the 7 texts in `_compiled_rows.py`: number/2, 2*number, 2*coefficient, number - 2,
    1/number, Abs(number) - 1, Abs(number) - 2.
  - Falls back to Python for a Float (kept by ruling, counted `rows:kept:constant_value:Float`), for an infinity or nan
    (`:other`), and for 1/number at 0.
  - Plant rows-constant-value-neg. It still needs a shapes case and a build.

## Module count: 13 of 32, unchanged
c2 and c3 leave core.py's template builders running per query. Retrace after each landing with
`~/sa-rust-ids-work/sa-port-161/rc.sh OUT WL core.py,wiring.py,functions.py` and read pass 1's `[query]` lines.
