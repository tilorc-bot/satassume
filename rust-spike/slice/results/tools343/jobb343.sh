#!/bin/bash
# jobb343.sh ROOT NEW BASE (sa-port-343, pareto0, under the shared lease of go343.sh, detached; tools342/jobb342.sh for
# NEW only), under HOME=~/sp19, on the staged frozen tree ROOT/s1/bench-NEW/tree. BASE's rows are not run again: they
# are sa-port-342's (pareto1 jobb-dfb544e6/gate-BASE and fz/BASE-*, the same frozen tree, .so and tools), copied by
# go343.sh into ROOT/jobb-NEW before this starts.
#  1. tools328/gate330.sh on NEW: the 20 workloads, py and rust, switch off and on (answers on against off);
#     xans342.py: the answers of NEW against BASE, cell by cell                            -> ROOT/jobb-NEW/gate-NEW, xans.txt
#  2. fz342.py on NEW: answers plus exception type and message, switch on against off, on the harness's fuzz streams
#     (base and custom) and on evalbench's fuzz, seeds 0 1 2 42, each under PYTHONHASHSEED 0 1 2 42; fzcmp342.py
#     compares, NEW and BASE                                                              -> ROOT/jobb-NEW/fz, fz.txt
# End marker: ROOT/jobb-NEW/end.txt, the last line here.
export HOME=/home/tilo/sp19
ROOT=$1; NEW=$2; BASE=$3; G=$ROOT/s1; OUT=$ROOT/jobb-$NEW
mkdir -p $OUT/fz
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA G OUT
N=16 bash $G/tools/gate330.sh $G/bench-$NEW/tree $OUT/gate-$NEW > $OUT/gate-$NEW.out 2>&1
$PY $G/tools/xans342.py $OUT/gate-$NEW $OUT/gate-$BASE > $OUT/xans.txt 2>&1
echo "GATE $(date -u +%T)" > $OUT/progress.txt
unset SLICE_WITNESS SLICE_WITNESS_CAP SLICE_WITNESS_PLANT SLICE_CONVERT SLICE_TERM_FRAMES
for s in $NEW; do for hs in 0 1 2 42; do for seed in 0 1 2 42; do for sw in 0 1; do
  echo "$s harness $seed py $hs $sw"; echo "$s harness-custom $seed py $hs $sw"
  echo "$s evalbench $seed py $hs $sw"; echo "$s evalbench $seed rust $hs $sw"
done; done; done; done > $OUT/fz/todo.txt
xargs -P 16 -L 1 bash -c 's=$0; kind=$1; seed=$2; m=$3; hs=$4; sw=$5; T=$G/bench-$s/tree; S=$T/rust-spike/slice
  [ $m = rust ] && export SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust
  cd $S; f=$OUT/fz/$s-$kind-$seed-$m-$hs-$sw
  PYTHONHASHSEED=$hs SLICE_WITNESS=$sw SLICE_DIR=$S PYTHONPATH=$T:$W/sympy:$W/shim $PY $G/tools/fz342.py $kind $seed $m > $f.json 2> $f.err
  echo "$? $s $kind $seed $m $hs $sw" >> $OUT/fz/rc.txt' < $OUT/fz/todo.txt
$PY $G/tools/fzcmp342.py $OUT/fz $NEW $BASE > $OUT/fz.txt 2>&1
echo "END $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)" > $OUT/end.txt
