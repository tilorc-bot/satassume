#!/bin/bash
# go317.sh (sa-port-317, orion, detached): S1 for the _Mark note fix (issue 323). Arms: A = 5b1d96f (source-equal to
# rust-slice 5f53735) and H = port/mark-note's head, each with the Rust frames on (+frames) and with both switches on
# (+rust+frames); H also with the frames off (H, H+rust) as the reference the +3% was measured against.
# Stage and build on pareto1 (--shared), then ONE quiet lease on pareto1: ROUNDS interleaved pinned rounds dev+fuzz over
# the six arms (time317.sh), then pysampler runs for the four frames-on arms in two interleaved passes (30 dev + 6 fuzz
# each). Then the post-processing here. End marker: s1/go-end.txt, written by fin() below.
G=~/sa-rust-ids-work/sa-port-317/s1; cd $G
A=5b1d96f; H=${H:?head sha7}
fin() { echo "END $1 $2 $(date -u +%FT%TZ)" > $G/go-end.txt; exit $2; }
rm -f $G/go-end.txt
bash tools/stage317.sh $A $H > stage.log 2>&1 || fin stage $?
machine run pareto1 --shared --wait 1h -r "sa-port-317: fix _Mark note in term_live frames (issue 323): build bench .so for $H" -- bash $G/tools/build317.sh $H > build.log 2>&1 || fin build $?
machine run pareto1 --quiet --wait 2h -r "sa-port-317: fix _Mark note in term_live frames (issue 323): S1 pinned timing + samples" -- env TREES="$A+frames $H+frames $A+rust+frames $H+rust+frames $H $H+rust" PTREES="$A+frames $H+frames $A+rust+frames $H+rust+frames" ROUNDS="1 2 3 4 5 6 7 8 9 10 11 12" WLS="dev fuzz" bash $G/tools/onlease317.sh r1 > lease-r1.log 2>&1 || fin lease $?
rsync -a pareto1:$G/timing-r1 pareto1:$G/run-$A+frames pareto1:$G/run-$H+frames pareto1:$G/run-$A+rust+frames pareto1:$G/run-$H+rust+frames pareto1:$G/run-$H $G/ || fin copy $?
echo "END lease-done 0 $(date -u +%FT%TZ)" > $G/lease-end.txt
for t in $A+frames $A+rust+frames; do mkdir -p run-$t/nm; cp nm/*.nm run-$t/nm/; cp ~/sa-rust-ids-work/sa-port-314/s1/run-$A/sa_solver.so.nm run-$t/nm/ || fin nm $?; done
for t in $H+frames $H+rust+frames; do mkdir -p run-$t/nm; cp nm/*.nm run-$t/nm/; cp run-$H/sa_solver.so.nm run-$t/nm/ || fin nm $?; done
python3 med285.py timing-r1/time.jsonl . $A+frames $H+frames $A+rust+frames $H+rust+frames $H $H+rust > med-r1.md 2>&1 || echo "med rc=$?" >> go.notes
for t in $A+frames $H+frames $A+rust+frames $H+rust+frames; do
  for wl in dev fuzz; do GD_NM=$G/run-$t/nm python3 tools/prof292.py run-$t $wl $G/prof-$wl-$t.json > prof-$wl-$t.log 2>&1 || fin prof-$wl-$t $?; done
done
fin done 0
