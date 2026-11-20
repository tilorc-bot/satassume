# HANDOFF sa-port-365: the formula skeleton's removal, gate and S1 read; a question before the bar (issue 323)

Branch port/skeleton-removal, clone ~/dev/sa-port-5, worktree ~/sa-rust-ids-work/sa-port-363/wt, from rust-slice
966268c. **Tested SHA f5c1f3f4** (source c400113; every later commit is results/ and HANDOFF only). .so: x86-64 venv
a653fd4179da9161, bench 4ae7f5cf1dbbca07, orion aarch64 fcf0524571e0cea9; base 966268c venv 0f78ac2962f34b3a, bench
8b8041d3fe6223c2, orion aarch64 4d8921d9c510e99f. **Nothing is landed, no bar was started, no tool was changed.**

Read rust-spike/slice/results/skeleton-removal.md first (everything measured is there), then HANDOFF-sa-port-363.md
for the file:line map of the source and of the gate's outputs.

## Done by 365
- The gate read: per query 0 differences in all 48 rows, digests equal; live 60 of 60 MATCH; the differential 69,527
  inputs, 0 differences; kept file 33 passed; iv 64 of 64 pairs equal; suite by id equal but for the planted-history
  test. S1 read: no workload worse beyond the spread; wiring faster beyond it in four arms.
- Item 4: 769's P2 line (`power` [0, 0] in all 48 rows) and 771's line, both in skeleton-removal.md (4).
- [137e]'s repeat check on the gate's tree (tools362/rep362.sh unchanged): the id()-reuse signature shows.
- skeleton-removal.md written.

## Open: Status: question, three rows (skeleton-removal.md (7))
1. 6 of 48 cmp.txt rows say DIFFER on the pass total `life.alive` alone (not reproducible on one tree).
2. The differential under plant 771 finds 0 differences (dev and fuzz in the gate; all 20 workloads in 365's run):
   771 is a kept-test catch only.
3. The planted-history test differs new against base by id in the suite's rust and py cells; the repeat check shows
   [137e]'s signature, so by the rule it is the known row.

## Left, once the planner has ruled
- Bar: copy tools361/job361bar.sh, gobar361.sh, chain361.sh to tools363 (SHA, paths, row names, plant list only; show
  the diff against the source scripts). Lines to change in job361bar.sh: :21 (paths), :42 CPP358 and :44
  CONVERT_PLANTS and :57's loop (drop formula-and-as-or; 771 per the ruling on row 2), :52 (the bar script's name and
  branch). gobar361.sh: :7 (WT, X, L), :11, :12, :15. chain361.sh: :9. The bar tests origin/bar/measured-next-SHA's
  head (gobar361.sh:4-5): that branch's name is a row name to change. ONE end marker, written by gobar's last line.
- Probe count: tools361/gopc361.sh and pctab361.py, against 21 of 32.
- From the bar: R5 (term_discard rows), R1/H2, the quiet-catch count with its planted proof
  (SLICE_PLANT_HANDLER=complete_check), the plant table. Add them to skeleton-removal.md.
- bar.sh land, the guard, PUSH=1, rule [91]; check `git log origin/rust-slice` first (966268c when this was written).

## Where 365's outputs are
~/sa-rust-ids-work/sa-port-365: rep/rep.txt (the `alive` repeat on orion), rep362/rep-sum.txt (the planted-history
repeat check), gocd771-end.txt (plant 771 over the 20 workloads; rows on pareto0 under
~/sp19/sa-rust-ids-work/sa-port-365/convdiff-771-all). No job of 365 is running; no lease is held.
