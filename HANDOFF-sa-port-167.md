# HANDOFF sa-port-167: stack 6g(c2)+Element._new built, stack bar S1 running on f1e4a74; not landed (issue 323)

## State (8 Nov, ~11:20 UTC)
- **Stack branch port/stack-c2-elemnew** (pushed): port/elemnew d0965f3 (Element._new 9139a9b + sa-port-162 handoff, on
  rust-slice 17442af) + **f1e4a74** = 14b76fd (6g(c2), from port/6g over 30f3309) cherry-picked, no conflicts. Builds on
  orion (`~/sa-rust-ids-work/sa-port-167/build.txt`). **Tested source f1e4a74.** This handoff commit adds only
  HANDOFF-sa-port-167.md and the ownership SHA fix (results/), both outside the push guard.
  6g(c2)'s handoff-only commits on port/6g (ac520b2, c4cc1d2, 8a6ee8d) were not carried: docs, no source.
- **Stack bar S1 running** on pareto1 under shared lease 777925a1 (`machine run` launcher pid on orion
  `~/sa-rust-ids-work/sa-port-167/bar-S1.pid`, log `bar-S1.launcher.out`). Started 11:07Z; build done 11:08. Rows
  pareto1 `~/sp19/sa-rust-ids-work/sa-port-167/bar-S1/`. **End markers, both written on pareto1 by the job itself:**
  bar.sh's `done.txt` and the env script's `end.txt` (`exit N time`). Done = phases.txt has `sum` and end.txt exists.
  Env: pareto1 `~/sp19/bar-sa-port-167-env-S1.sh` (orion copy `~/sa-rust-ids-work/sa-port-167/bar-env-S1.sh`), bar.sh as
  `~/sp19/bar-sa-port-167.sh` (= p1/bar.sh, sha in commands.txt). If the launcher's ssh drops, the job keeps running: take a
  cover lease (`machine lease pareto1 --shared --for 2h -r "sa-port-167 S1 cover"`) and watch the job.
  Config = union of both steps': BASE `sa-port-158/bar-5c7b/suite` (5c7's landing = current rust-slice), KEPT_BASE
  `sa-port-157` (the 10 WLS; budget's base share is in results/port-5c7.md); PLANTS = F2's 13 + sa-port-161's 31 (44);
  WLS the 10 + budget; SEED1=1; SUITE_PLANTS = `elem-eq-flip union-skip-overlap within-no-link` (Element._new's
  side: E2's zero set plus 5c7's two, which F2's `zero` would pick if they fire 0 on dev/fuzz) + 6g(c2)'s four
  (`dispatch-ignores-epoch dispatch-redefines-off dispatch-user-off knowledge-no-query-drop`); explicit, not `zero`, so
  c2's 31 rows plants don't each start a suite; TESTS = F2's 20 files (c2's 19 + test_elem_pyclass.py); DIRECT =
  sa-port-161's 16 (superset of F2's 4). Expect ~1.5-2 h (44 plants x 13 workloads).
- **Bisect fallbacks still running, not mine to land from:** F2 (Element._new solo, 9139a9b, pareto1
  `~/sp19/sa-rust-ids-work/sa-port-162/bar-F2/`, at live 11:04Z; suite 5,992 passed/126 failed/23 skipped/18 xfailed,
  same totals as E2). 6g(c2) solo (14b76fd, `~/sp19/sa-rust-ids-work/sa-port-161/`): phases build..extra done
  (no seed1: SEED1 unset in its config), suiteplants running at 11:05Z, then sum. Its job writes pareto1
  `sa-port-161/done.txt` itself at the end; the orion-side marker was lost with the launcher's ssh (~10:38).
- **Planner's c2 end-marker condition (stack ruling):** before using any c2 solo row, or writing
  `sa-port-161/done.txt` by hand, check it has: suite rows for every id (`suite/` vs base id count 6,159), each
  workload's comparison (`live/*.cmp`, `extra/summary.txt` has 10 `py vs rust` blocks), the plant rows (31 x 12 `.cmp`
  files, `plant-*.cmp`), the handler rows (`suite/` handler file, `extra/*-rust.handlers`). Say in the report it was
  written by hand and what was checked. With the stack bar, c2's landing evidence is S1's; c2 solo is only the bisect
  fallback, so this check matters only if S1 differs from base.
- **Siblings:** sa-port-168 (5c8, ~/dev/sa-port-7) replaced sa-port-166. No 5c8 bar dir on pareto1 at 11:15Z. Landing
  order: if 5c8's full bar runs when S1 finishes, hold until it lands, then rebase, `bar.sh land` without PUSH, read the
  incoming diff, rerun the full bar if it touches guarded source.

## 6g(c2) evidence already on the stack tree (orion, f1e4a74 built in this clone)
- test_knowledge_core_shapes: 11 passed. Shadow (sa-port-161's shadowcount.py, `~/sa-rust-ids-work/sa-port-167/c2/shadow.txt`,
  tree.txt shows sa-port-19 imported): shadow:direct `_mul_factor_sets` 10 (10 non-empty), `_quotient_templates` 11
  (1 non-empty, `core-quotient-rules`); c1's three 5/5/5 as before; **shadow:mismatch 0** (no key).
- Module-count retrace running detached: `~/sa-rust-ids-work/sa-port-167/c2/rc-core.txt`, `rc-dev.txt` (marker `rc-DONE`),
  `rc.sh OUT WL core.py,wiring.py,functions.py`, pass 1 `[query]` lines. Expected 13 of 32 unchanged (core.py's template
  builders still per query), as c1's section says.
- sa-port-161's orion numbers on 14b76fd: core MATCH 1,636 q, dev MATCH; rows:rust mul/quot core 72/184, dev 46/63;
  rows:python core 158/46, dev 36/19; rows-quot-swap caught core (fired 44, 18 answers, 72 end+stream);
  rows-mul-ipi-drop fired 0 on core/dev (direct ipi set needs an input Mul s; s is derived there) -> void with that
  reason unless S1 shows a reach.

## Next, in order
1. Wait for S1 (`end.txt` + `sum` in phases.txt). Read pareto1 `bar-S1/sum.txt` by sections (`rg -n '^=='`). Check
   completeness as above (every id, every workload compare, 44 x 13 plant .cmp, handler rows).
2. State the five bar items for the stack. Plant tables **per step** (stack ruling): Element._new's (rel-elem-sign-flip
   DIFFER on dev, state only, answers equal; elem-memo-plus1 caught as a wrong value; elem-eq-flip void on workloads,
   caught by its suite run; elem-hash-skew fired and silent, named; elem-repr-bracket, elem-from-neg; controls) and
   6g(c2)'s (rows-quot-swap; rows-mul-ipi-drop void or reached; the c1/b rows plants; the 6g(a) dispatch conditions
   from the suite plants). Counters from `live/*-rust.session.json`, `extra/*-rust.session.json`: cf:elem_new,
   cf:elem_py_read, rel:elem_sign, ad:cb_memoized, rows:rust:/rows:python:`_mul_factor_sets`/`_quotient_templates`.
   If S1 differs from base: bisect as ruled (F2 solo, c2 solo).
3. Reports: finish results/port-elemnew.md in port-adapters.md :283-425's layout (SHAs: tested f1e4a74 over 17442af;
   incoming diffs 30f3309 and 17442af both guarded -> F1/F2; stack built over them -> S1). Add a "Step 6g(c2)" section
   to results/port-6g.md in c1's layout (:181-283): code (HANDOFF-sa-port-161.md :16-27 on origin/port/6g), direct-split
   counts, shadow (above), module count (rc retrace), plant table, landed as a stack with Element._new (bar S1).
   Ownership: rows 653 (TSV) / md :107 now say "stack with 6g(c2), tested f1e4a74"; change if the tested SHA changes.
4. `sh rust-spike/slice/p1/bar.sh land f1e4a74` from port/stack-c2-elemnew (no PUSH), read the incoming diff, then
   `PUSH=1 sh rust-spike/slice/p1/bar.sh land f1e4a74`. `agent report`, SendMessage architect-64. The architect then
   launches 6g(c3) in ~/dev/sa-port-5.

## Bar F1
62a6723 on 30f3309, stopped by sa-port-162 after plants/seed1 when 5c7 (17442af) landed: superseded, not a landing bar.
