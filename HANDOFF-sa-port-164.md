# Handoff sa-port-164 (step 6g(c), issue 323), at the context budget, nothing landed this session

## Running when I stopped (both detached; I stopped only my own waits)
- **6g(c2) 14b76fd full bar** on pareto1: wait for `~/sp19/sa-rust-ids-work/sa-port-161/done.txt`, then read sum.txt.
  It was in the live phase at 10:20 UTC (build 09:52, tests 09:57, suite 09:59). sa-port-158's and sa-port-162's bars
  are on pareto1 too: first to finish lands (rebase rule).
- **c3 orion checks** (sa-port-163's `c3-run.sh`, a8e2a4f's .so): wait for `~/sa-rust-ids-work/sa-port-163/c3/ALL-DONE`.
  **Don't rebuild the clone's .so, check out another branch, or edit Python in the clone until it exists**, because those
  runs import the clone's tree. Plain core/dev/f6/wiring: all MATCH.

## c3 plant results so far (plant_fired is the session.json's top-level `plant_fired`, not counts)
Read with `sh ~/sa-rust-ids-work/sa-port-164/plt.sh ~/sa-rust-ids-work/sa-port-163/c3 PLANT...` (workload=fired/verdict).
- rows-exp-arg-none: core 0, dev 0, f6 0; wiring 2 DIFFER (caught on wiring).
- rows-irrational-false: core 16 DIFFER, wiring 2 DIFFER (caught).
- rows-unit-power-drop-last: core 18 DIFFER (caught); dev 0.
- rows-unit-angle-neg: core 33, wiring 5, MATCH everywhere. rows-ipi-split-neg: core 54, wiring 3, MATCH everywhere.
  **Both are void by construction**: negating the angle or c keeps everything the rules read (the units read the angle's
  parity and denominator, IPI_GUARDS read integer/even/odd/half-odd). Replaced on port/6g-c5 by rows-unit-angle-shift
  and rows-ipi-split-shift (plus 1, which flips parity). They need a run on core and wiring once built.
- rows-pow-bound-drop-last, rows-ipi-rules-drop-last, and unit-power on f6/wiring hadn't run yet.

## Branches (all pushed to origin)
- port/6g = c4cc1d2 + this file (doc-only). Land c2 from here: `git checkout port/6g` (after ALL-DONE), then
  `bash rust-spike/slice/p1/bar.sh land 14b76fd`, then with PUSH=1. The shadow:direct counts for the c2 section aren't
  taken yet: build 14b76fd and run `~/sa-rust-ids-work/sa-port-163/shadowcount.py` from the clone root. (sa-port-161's
  shapes-c2.txt only shows 11/11 passed, with no counts.)
- port/6g-c3 = d4f769d: a8e2a4f (c3), 7270edb (c4 WIP), d4f769d (two constant_value shapes cases,
  `rows-constant-value-exp` x**(3/2) and `rows-constant-value-base` (-1/3)**x; DIRECT maps core:constant_value).
  Not built, not run.
- port/6g-c5 = 78ece39 on d4f769d: Rust only, `cargo check` clean, not built.
  - rows_tpl.rs `RowsTpl::add_tpl`/`add_tpl_parts` replaces the four `wiring_fn` calls in Family::Addition. They build
    the same facts key/consts/objs/node and a Rust gen from tcore's half/bound/recip/imag_rules.
  - Kept on Python, each counted: a kept query; `_imag_templates`' all-number case (`rows:kept:_imag_templates:number`).
  - The shadow name is the builder's, and ours is `(key, consts, objs, node, rules)` or None.
  - Four new plants: rows-half-tpl-flip, rows-bound-tpl-neg, rows-recip-tpl-neg, rows-imag-tpl-sign.
  - The c3 plant renames are in this commit too, so split them back onto c3 when rebasing (they belong to the c3+c4 bar).
  - **The Python side is not committed**: `python3 ~/sa-rust-ids-work/sa-port-164/c5_py.py` applies the
    knowledge_core_live `ADD_TPL`/`_add_tpl_py` shadow (it runs core's builder with `facts` captured and the original
    `_*_rules`), knowledge_common_live's four c5 PLANTS, and the two c3 renames. Apply it only after ALL-DONE, and check
    that both plant lists match rows_tpl.rs PLANTS.
  - The c5 shapes cases still need writing: Q.positive(1 + 2*x) and (2 + 3/y) with integer-bound assumptions,
    Q.imaginary(I*x + I*y), and a half sum (x + y)/2 type.

## Next, in order
1. After done.txt: read the bar's five items, land c2 (rows-mul-ipi-drop void: s is a derived Mul on core and dev, so the
   direct (c, I, pi, s) set never forms; name its reach if the bar's plants show one). Write the c2 section of port-6g.md.
2. After ALL-DONE: rebase port/6g-c3 on the landed rust-slice (move the two plant renames there), build, run the shapes
   test plus shadowcount, then c4 on orion with `short.sh` (rows-constant-value-neg, plus the two shift plants on core
   and wiring). Then the full bar on the c3+c4 source and land it.
3. Then c5 (port/6g-c5 rebased), then the module shells in the brief's map.

## Module count: 13 of 32, unchanged (nothing landed this session).
