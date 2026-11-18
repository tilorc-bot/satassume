#!/bin/sh
# sweep.sh LABEL N: N fresh processes each of {python,rust} x {orig,keep} x {plain,frames}, 4 at a time.
T=$HOME/dev/sa-port-5; O=$HOME/sa-rust-ids-work/sa-port-318; L=$1; N=$2
mkdir -p $O/runs/$L
( cd $T; git rev-parse HEAD; git diff --name-only 46750d4 HEAD -- satassume rust-spike/slice ':(exclude)rust-spike/slice/results'; git status --short; sha256sum rust-spike/slice/sa_solver.so ) > $O/runs/$L/tree.txt
for i in $(seq 1 $N); do for b in python rust; do for k in orig keep; do for f in plain frames; do
  echo "$T $b $k $f $O/runs/$L/$b.$k.$f.$i.log"; done; done; done; done | xargs -P4 -L1 sh $O/run1.sh
echo "END $(date -u +%FT%TZ)" > $O/runs/$L/end.txt
