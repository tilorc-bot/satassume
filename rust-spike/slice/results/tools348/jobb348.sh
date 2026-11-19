#!/bin/bash
# jobb348.sh ROOT NEW JBASE (sa-port-348, pareto0, under the shared lease of go348.sh, detached; tools347/jobb347.sh
# without the arms at SLICE_WITNESS_WORK=8400, which the gate of 180e501 read: witness-bounds.md (4)), under HOME=~/sp19, on the staged frozen tree
# ROOT/s1/bench-NEW/tree. JBASE's rows are not run again: they are sa-port-343's (pareto0 jobb-01e8ca74/gate-JBASE and
# fz/JBASE-*; its tree differs from 2030cdc6 in harness/state.py's inventory only), copied by go348.sh into
# ROOT/jobb-NEW before this starts. NEW is the source of the planner's ruling B: the check no longer asks the budget.
#  1. tools328/gate330.sh on NEW: the 20 workloads, py and rust, switch off and on (answers on against off);
#     xans342.py: the answers of NEW against JBASE, cell by cell                          -> jobb-NEW/gate-NEW, xans.txt
#     budget alone with SLICE_WITNESS_PLANT=check-first (the INCONSISTENT read taken out)  -> gate-NEW-cf
#     bs347.py: Engine.stats and last_budget_limited on budget's over-budget queries, on against off -> bs.txt
#  2. fz342.py on NEW: answers plus exception type and message, switch on against off, on the harness's fuzz streams
#     (base and custom) and on evalbench's fuzz, seeds 0 1 2 42, each under PYTHONHASHSEED 0 1 2 42; fzcmp342.py
#     compares, NEW and JBASE                                                              -> jobb-NEW/fz, fz.txt
# End marker: ROOT/jobb-NEW/end.txt, the last line here.
export HOME=/home/tilo/sp19
ROOT=$1; NEW=$2; BASE=$3; G=$ROOT/s1; OUT=$ROOT/jobb-$NEW
mkdir -p $OUT/fz
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA G OUT
unset SLICE_WITNESS SLICE_WITNESS_CAP SLICE_WITNESS_PLANT SLICE_WITNESS_WORK SLICE_CONVERT SLICE_TERM_FRAMES
N=16 bash $G/tools/gate330.sh $G/bench-$NEW/tree $OUT/gate-$NEW > $OUT/gate-$NEW.out 2>&1
$PY $G/tools/xans342.py $OUT/gate-$NEW $OUT/gate-$BASE > $OUT/xans.txt 2>&1
WLS=budget N=4 bash $G/tools/gate330.sh $G/bench-$NEW/tree $OUT/gate-$NEW-cf check-first > $OUT/gate-$NEW-cf.out 2>&1
$PY $G/tools/bs347.py $OUT/gate-$NEW $OUT/gate-$NEW-cf $OUT/gate-$BASE > $OUT/bs.txt 2>&1
echo "GATE $(date -u +%T)" > $OUT/progress.txt
for hs in 0 1 2 42; do for seed in 0 1 2 42; do for sw in 0 1; do
  echo "$NEW harness $seed py $hs $sw"; echo "$NEW harness-custom $seed py $hs $sw"
  echo "$NEW evalbench $seed py $hs $sw"; echo "$NEW evalbench $seed rust $hs $sw"
done; done; done > $OUT/fz/todo.txt
fz() { # fz DIR: the todo's runs into OUT/DIR (SLICE_WITNESS_WORK as exported, if at all)
  FZ=$OUT/$1 xargs -P 16 -L 1 bash -c 's=$0; kind=$1; seed=$2; m=$3; hs=$4; sw=$5; T=$G/bench-$s/tree; S=$T/rust-spike/slice
  [ $m = rust ] && export SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust
  cd $S; f=$FZ/$s-$kind-$seed-$m-$hs-$sw
  PYTHONHASHSEED=$hs SLICE_WITNESS=$sw SLICE_DIR=$S PYTHONPATH=$T:$W/sympy:$W/shim $PY $G/tools/fz342.py $kind $seed $m > $f.json 2> $f.err
  echo "$? $s $kind $seed $m $hs $sw" >> $FZ/rc.txt' < $OUT/fz/todo.txt
}
fz fz
$PY $G/tools/fzcmp342.py $OUT/fz $NEW $BASE > $OUT/fz.txt 2>&1
echo "FZ $(date -u +%T)" >> $OUT/progress.txt
echo "END $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)" > $OUT/end.txt
