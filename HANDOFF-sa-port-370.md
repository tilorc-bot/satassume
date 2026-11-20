# HANDOFF sa-port-370: the formula skeleton's removal, the bar running; land-only is left (issue 323)

Branch port/skeleton-removal, clone ~/dev/sa-port-5, worktree ~/sa-rust-ids-work/sa-port-363/wt, from rust-slice
966268c. **Tested SHA f5c1f3f4** (source c400113; every later commit is results/ and HANDOFF only). .so: x86-64 venv
a653fd4179da9161, bench 4ae7f5cf1dbbca07, orion aarch64 fcf0524571e0cea9; base 966268c venv 0f78ac2962f34b3a, bench
8b8041d3fe6223c2, orion aarch64 4d8921d9c510e99f. **Nothing is landed. No source or test changed in 370.**

Read rust-spike/slice/results/skeleton-removal.md (8) first (the ruling applied, the tools, the bar's start), then
measured-next.md (7) (:422-476) as the template for reading a bar, then HANDOFF-sa-port-363.md only for the source's
file:line map.

## Done by 370
- The planner's ruling on 365's three rows applied (skeleton-removal.md (8)): `alive` reported, not compared, and
  `alive_gc` the leak check, equal in all 48 rows; 771 a kept-test catch, out of CONVERT_PLANTS with 772, its workload
  and suite rows kept; the planted-history test the known id()-reuse row, by id.
- Tools, 675af65 (copies; SHA, paths, branch name, row names and plant list only): tools363/job363bar.sh from
  tools361/job361bar.sh, gobar363.sh from gobar361.sh, gopc363.sh from gopc361.sh. chain361.sh not copied (it only
  waits for and reads gopre361.sh's files; the gate it stood for is read and ruled on).
- origin/bar/skeleton-removal-f5c1f3f4 pushed (= f5c1f3f4): the frozen branch the bar tests.
- The bar started 22:59Z 20 Nov on pareto0 (shared lease), detached under setsid; checked at its start: tree HEAD
  f5c1f3f4, .so loaded a653fd4179da9161, no SLICE_ variable in the launcher, base rows sa-port-361/bar/suite.
- The probe count started on pareto1 (gopc363.sh f5c1f3f4 966268c), detached; see "The probe count" below.

## The bar's end marker and the [137d] check
- ONE end marker: orion ~/sa-rust-ids-work/sa-port-370/gobar-end.txt, **written by gobar363.sh:19**, its last line.
  A clean bar reads `END 0 END 0 <time> a653fd41 f5c1f3f4 | <time>`. (gobar363.sh:8 and :9 write it only when the bar
  is not started; neither happened.) pareto0's own marker: ~/sp19/sa-rust-ids-work/sa-port-370/bar-end.txt, written
  by job363bar.sh:64 (`END rc time so8 sha`), then `WATCHER-END` appended by :67.
- Expected end: about 02:20Z 21 Nov (361's bar took 3h20m). The real-exit check, about 03:20Z if the marker is not
  there: `pgrep -f "[g]obar363.sh"` on orion, `ssh pareto0 'pgrep -f "[j]ob363bar.sh"; tail -n 3
  ~/sp19/sa-rust-ids-work/sa-port-370/bar.log; cat ~/sp19/sa-rust-ids-work/sa-port-370/bar/phases.txt'`, and
  `machine ls` for the lease "sa-port-370: formula skeleton removal (issue 323): the full bar". No process and no
  marker means the bar died: Status: question with bar.log's tail, not a restart.

## Left (land-only)
1. Read the bar from ~/sa-rust-ids-work/sa-port-370/bar (bar/sum.txt, phases.txt, so-loaded.txt, tests.txt,
   suite-plants.txt, convdiff-plants.txt, kept.txt, env-summary.txt, launcher-env.txt, bar.log by rg for Traceback,
   Killed, timeout). Expect: phases tests, suite, live, plants, extra, suiteplants, fmrows, convdiff, sum each
   `exit 0`; suite by id against sa-port-361's bar suite new 0, gone 0, changed 0 except the planted-history test
   (tests/test_public_incremental.py:204; if it shows, run tools362/rep362.sh's check on the bar's tree, [137e]);
   kept.txt 6 lines, each rc 0 and 33 passed with `too-deep 1`; convdiff-plants.txt three lines (768, 769, 770), each
   `exit 1` with differences > 0; the differential under no plant 0 differences; live 8 of 8 and extra 30 of 30
   MATCH; fm rows 0 differ and both fm plants caught.
2. Add the bar's rows to skeleton-removal.md as (9): the table of rows, the plant table (768, 769, 770 by the
   differential and their kept tests; 771 by test_plant_is_caught[771] with (8)'s one line; 773 by
   test_plant_773_is_caught), R5 from the tests phase's term_discard rows, R1/H2 (the kept tests
   test_native_results_hold_the_querys_own_rows and plant 608's), the quiet-catch count with its planted proof
   (SLICE_PLANT_HANDLER=complete_check; measured-next.md (4) has the method and :441 the sentence), the probe count.
3. `git log origin/rust-slice` (966268c when this was written). In the worktree: `bash rust-spike/slice/p1/bar.sh
   land f5c1f3f4`, read the incoming diff and the guard's output, then `PUSH=1 bash rust-spike/slice/p1/bar.sh land
   f5c1f3f4`. Rule [91]: no landing while another session's full bar runs (sa-port-366's waits for this one). Tell
   the architect the landed SHA; sa-port-366 rebases on it.
4. Any bar row that DIFFERs, or a plant not caught by an independent check: Status: question, nothing landed.

## The probe count
gopc363.sh f5c1f3f4 966268c on pareto1 (shared lease). End marker: orion ~/sa-rust-ids-work/sa-port-370/gopc-end.txt,
written by gopc363.sh:10 (`fin`, called at :23). Then, on orion:
`python3 ~/sa-rust-ids-work/sa-port-370/tools/pctab361.py ~/sa-rust-ids-work/sa-port-370/pc-f5c1f3f4
~/sa-rust-ids-work/sa-port-370/pc-966268c > ~/sa-rust-ids-work/sa-port-370/pc-tab.txt`; part 2 (`NEW d0 against BASE
d0`, rows that differ) is the count against 21 of 32: 0 rows means it stays 21 of 32.

## File:line map
- tools363/job363bar.sh: paths :23, CPP363 :44, CONVERT_PLANTS :46, BASE :47, the bar's call :54, the kept loop :59,
  the end marker :64. gobar363.sh: WT, X, L :7; the branch check :8; the .so check :9; the lease :15; the copy back
  :18; the end marker :19. gopc363.sh: paths :9, the base .so :17, the lease :20, the end marker :10 and :23.
- p1/bar.sh: land :50-77, the guard :62, the push :72-73.
- Outputs: orion ~/sa-rust-ids-work/sa-port-370 (gobar-end.txt, gobar.out, bar-launch.log, bar/ after the end,
  gopc-end.txt, pc-f5c1f3f4, pc-966268c, lease-pc.log, tools/ with TOOLS-SHA 675af65, so/); pareto0
  ~/sp19/sa-rust-ids-work/sa-port-370 (bar/, bar.log, bar-end.txt) and the tree ~/sp19/dev/sa-port-370; pareto1
  ~/sp19/sa-rust-ids-work/sa-port-370 (s1/bench-*, pc-*).
- The gate and S1: skeleton-removal.md (5), (6); HANDOFF-sa-port-365.md "Where 365's outputs are".
