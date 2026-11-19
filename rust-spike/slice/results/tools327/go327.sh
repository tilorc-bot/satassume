#!/bin/bash
# go327.sh (sa-port-327, orion, detached; from 317's go317.sh): S1 for the _may_be_nan step (issue 323). Arms:
# A = e5db633 (rust-slice) and H = 6587181 (the tested SHA), each with both switches on (+rust+frames).
# Stage and build on pareto1 (--shared), then ONE quiet lease on pareto1: 12 interleaved pinned rounds dev+fuzz
# (time327.sh), then pysampler runs for both arms in two interleaved passes (30 dev + 6 fuzz each). Then the
# post-processing here. End marker: s1/go-end.txt, written by fin() below.
G=~/sa-rust-ids-work/sa-port-327/s1; cd $G
A=e5db633; H=6587181; W="sa-port-327: _may_be_nan into the Rust walk (issue 323)"
fin() { echo "END $1 $2 $(date -u +%FT%TZ)" > $G/go-end.txt; exit $2; }
rm -f $G/go-end.txt
bash tools/stage327.sh $A $H > stage.log 2>&1 || fin stage $?
machine run pareto1 --shared --wait 1h -r "$W: build bench .so for $A and $H" -- bash -c "bash $G/tools/build327.sh $A && bash $G/tools/build327.sh $H" > build.log 2>&1 || fin build $?
machine run pareto1 --quiet --wait 2h -r "$W: S1 pinned timing + samples" -- env TREES="$A+rust+frames $H+rust+frames" PTREES="$A+rust+frames $H+rust+frames" ROUNDS="1 2 3 4 5 6 7 8 9 10 11 12" WLS="dev fuzz" bash $G/tools/onlease327.sh r1 > lease-r1.log 2>&1 || fin lease $?
rsync -a pareto1:$G/timing-r1 pareto1:$G/run-$A+rust+frames pareto1:$G/run-$H+rust+frames pareto1:$G/run-$A pareto1:$G/run-$H $G/ || fin copy $?
echo "END lease-done 0 $(date -u +%FT%TZ)" > $G/lease-end.txt
for s in $A $H; do t=$s+rust+frames; mkdir -p run-$t/nm; cp nm/*.nm run-$t/nm/; cp run-$s/sa_solver.so.nm run-$t/nm/ || fin nm $?; done
python3 pair327.py timing-r1/time.jsonl $A+rust+frames $H+rust+frames > pair-r1.md 2>&1 || echo "pair rc=$?" >> go.notes
for t in $A+rust+frames $H+rust+frames; do
  for wl in dev fuzz; do GD_NM=$G/run-$t/nm python3 tools/prof292.py run-$t $wl $G/prof-$wl-$t.json > prof-$wl-$t.log 2>&1 || fin prof-$wl-$t $?; done
done
fin done 0
