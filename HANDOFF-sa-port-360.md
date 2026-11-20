# HANDOFF sa-port-360 (20 Nov, ~13:05Z): items 4 and 5 read; one row of the differential differs: a question, no bar, nothing landed

Branch port/measured-next, pushed to the clone's origin. Worktree ~/sa-rust-ids-work/sa-port-356/wt in clone
~/dev/sa-port-5. Output: ~/sa-rust-ids-work/sa-port-360 (359's jobs: sa-port-359, read only). Nothing runs detached.

TESTED SHA 00535462 (source b580119 plus the ruled skipif; unchanged by this step: only results, tools360 and this
file were added). .so of 00535462: x86-64 venv build 0f78ac2962f34b3a (gate, suite, differential, bar; orion
sa-port-359/so/sa_solver-00535462.so), x86-64 bench build 8b8041d3fe6223c2 (S1), aarch64 4d8921d9c510e99f (worktree,
untracked). Base de88d9b9: venv 37b7560e245df518, bench 0b6f073f5c5a600b, aarch64 e0365239348de148.

## Read by 360 (all in results/measured-next.md (4) and (5); summaries in results/tools360)
1. Item 4, the gate: per query 24 of 24 EQUAL (359); livecmp MATCH 20 of 20 (moved ids, sessions, Engine.stats);
   answers 60 of 60; suite by id 0 ids differ in every pair of cells (6,317 ids, 127 failed in each cell, base
   included); iv 0 of 128 runs differ; the six kept files: 0 ids only on rust, the 15 alike ids and the 8 base-only ids
   by id with the cause; R5 clean on dev, lra, fuzz and its plant caught; quiet handlers 0 on the 20 workloads in three
   arms, the counter shown to fire (661 rows on dev under SLICE_PLANT_HANDLER=complete_check).
2. **The differential: 69,476 inputs, 1 difference** (`Q.commutative(Trace(M*N))`, True; the suite's). Cause read:
   OWED [157]'s interpreter hang. `is_complex` of `M*N` hits the recursion limit; with handler_count's
   EXCEPTION_HANDLED tool on, the read returns only at every third call depth, and Rust's `read` item sits one Python
   frame shallower than `_Walk.read`, so the two walkers hang at different depths (tools360/depth360.py: Python's
   returns at D = 2, 5, Rust's at D = 1, 4; with no tool both give None and the same raised entry at every depth).
   The same suite pass without `-p handler_count` (pareto0, x86-64 0f78ac2962f34b3a; tools360/nohandler360.sh): 40,163
   inputs, 0 differences, 10,781,055 reads compared, slow 1 (the known `sin(exp(exp(exp(5))))` input), exit 0. The
   depth table is the same on x86-64 (tools360/depth360-x86.txt).
3. The planner's `current()` check: at every `_engine_ask` call `term_live.current()` is this ask's own `_Query` or a
   `_Refused`, never an earlier query's (STALE 0 of 14,115 calls on 8 workloads, both walkers); None after every ask
   and at a direct call outside one. `_engine_ask` is called only from `_ask`, which term_live wraps. So 359's base row
   is memory-only: to be OWED. No source change.
4. Item 5, S1: the rule is met. rust-nat head against de88d9b9: dev -3.2%, fuzz -1.7%, budget -0.9%, wiring -3.5%, each
   beyond the spread; Python rows within the spread; lease quiet (load 0.99-1.07).

## The question (Status: question)
The bar's convdiff phase runs the same suite pass under `-p handler_count` (p1/convert_diff.sh:21), so it would exit 1
on that input as the file stands. Not removable in this step without (a) dropping `-p handler_count` from the
differential's suite pass (a shared bar file; the plugin's rows are not read by the differential), (b) listing the
input as an exact known row of the differential, or (c) adding a Python frame to the native read (not proposed: it
would be code whose only purpose is to hang where Python hangs). My recommendation is (a). The planner rules.

## Not done
- Item 6: the bar. results/tools360/job360bar.sh and gobar360.sh are WRITTEN, NEVER RUN (copied from tools354 with
  this step's rows: wnative:on as the no-plant row with the port on, rows358's six convert:NAME rows as PLANTS and
  SUITE_PLANTS, CONVERT_PLANTS for the convdiff phase, phases `tests suite live plants extra suiteplants fmrows
  convdiff sum`, BASE sa-port-354's bar suite rows, the kept file under each plant in plain pytest). Before running:
  push origin bar/measured-next-SHA at the tested SHA, copy sa-port-359/so/* to sa-port-360/so (or your own name's
  directory: change the paths), check `machine ls`. If the ruling changes p1/convert_diff.sh, the tested SHA changes:
  the crate does not, so the .so hashes stay, but restage the tree (tools359/stage359.sh).
- [137e]'s keep-alive check when the planted-history test shows in the bar (it failed in all five suite cells of
  359's job, base and Python's walker included).
- bar.sh land, guard, PUSH=1, rule [91]; the probe count against 21 of 32; measured-next.md (6).
- OWED items to name: the memory-only base row (3 above); the 15 plugin-mode ids ([157](b)) still undiagnosed.
- `git worktree remove` ~/sa-rust-ids-work/sa-port-357/base when no step needs it.

## File:line map
- results/measured-next.md: (4) the gate table, the one difference, the current() check; (5) S1; (6) the bar, not run.
- results/tools360: depth360.py (the depth table; depth360-aarch64.txt, depth360-x86.txt), trace360.py (the input,
  one process), current360.py (current360-nat.txt, -py.txt), nohandler360.sh and gonohandler360.sh (the differential's
  suite pass without the plugin, pareto0), job360bar.sh and gobar360.sh (the bar, not run), byid-00535462.txt,
  s1-med-00535462.txt, convdiff-total-00535462.txt.
- p1/convert_diff.sh: the suite pass :19-:21 (`-p rust_plugin -p handler_count -p plant_count`), total :23.
  convert_diff.py: fresh :54, reads :99, diff :116 (`reads stopped` :157-:158), install :177.
- sympy_api.py: _ask :567, its three calls of _engine_ask :570, :598, :602, _engine_ask :1118. term_live.py: stack
  :150, current :160, the wrapper's push and pop :1101-:1111, the second run :1126-:1133, _ask_once :1135.
- live.py: the handler plant :439-:448, the per-query record `caught` :509-:511, `.handlers` :359-:361.
- test_lazy_reads.py: planted :115 (replaces `_Walk.term_row`), the nan test's `term` :314.
- Everything else: HANDOFF-sa-port-359.md "File:line map", then 358's, 357's, 356's. Plants from 774, counters from 747.
