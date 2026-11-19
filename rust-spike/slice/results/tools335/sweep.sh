#!/bin/sh
# sweep.sh LABEL N: N fresh processes each of {python,rust} x {orig,keep} x {plain,walk,both}, 4 at a time.
# End marker: runs/LABEL/end.txt, written by the last line.
T=$HOME/sa-rust-ids-work/sa-port-332/wt; O=$HOME/sa-rust-ids-work/sa-port-335; L=$1; N=$2
mkdir -p $O/runs/$L
( cd $T; git rev-parse HEAD; git diff --name-only f4ce4b2 HEAD -- satassume rust-spike/slice ':(exclude)rust-spike/slice/results'; git status --short; sha256sum rust-spike/slice/sa_solver.so ) > $O/runs/$L/tree.txt
for i in $(seq 1 $N); do for b in python rust; do for k in orig keep; do for f in plain walk both; do
  echo "$T $b $k $f $O/runs/$L/$b.$k.$f.$i.log"; done; done; done; done | xargs -P4 -L1 sh $O/tools/run1.sh
echo "END $(date -u +%FT%TZ)" > $O/runs/$L/end.txt
