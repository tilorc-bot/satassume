#!/bin/bash
# cd324.sh TAG (sa-port-324, pareto1; after pc324.sh has checked out and built ~/sp19/dev/sa-port-324-pc): the convert
# step's differential (convert_diff.py, as p1/convert_diff.sh's first line runs it) on every input of the 20 workloads,
# without a plant and under each of plants 746-748. Both walkers convert each input and the tables, ids, objects and
# classes are compared (term rows hold the F_MAYBE_NAN bit); lazy reads are not asked (SLICE_CONVERT_DIFF_READS=0: this
# step moves no read). A plant is caught when its total says differences > 0; nothing here reads the plant.
# Rows: $O/PLANT/total.txt and wl-exit.txt. End marker: $O/end.txt, written by the last line of this script.
TAG=${1:?tag}
export REAL=/home/tilo HOME=/home/tilo/sp19
X=$HOME/sa-rust-ids-work/sa-port-324; O=$X/cd-$TAG; H=$HOME/dev/sa-port-324-pc; rm -rf $O; mkdir -p $O
. $HOME/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED O H
cd $H/rust-spike/slice; export PYTHONPATH=$H:$W/sympy:$W/shim
(git -C $H rev-parse --short HEAD; sha256sum sa_solver.so; $PY -c 'import satassume, convert, sa_solver; print(satassume.__file__, convert.__file__, sa_solver.__file__)') > $O/tree.txt
WLS="f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls lra"
for pl in none nan-no-specials nan-atom-args nan-one-level; do
  export D=$O/$pl; mkdir -p $D
  if [ $pl = none ]; then unset SLICE_CONVERT_PLANT; else export SLICE_CONVERT_PLANT=$pl; fi
  printf '%s\n' $WLS | xargs -P 10 -I{} bash -c 'n=$(echo {} | tr -d :); SLICE_CONVERT=py SLICE_CONVERT_DIFF=$D/wl-$n SLICE_CONVERT_DIFF_READS=0 $PY live.py {} rust $D/$n.jsonl --check entry > $D/$n.tot 2> $D/$n.err; echo "{} exit $?" >> $D/wl-exit.txt; rm -f $D/$n.jsonl'
  $PY convert_diff.py $D/wl-* > $D/total.txt 2>&1; echo "exit $?" >> $D/total.txt
  echo "$pl $(date -u +%T) $(head -n 1 $D/total.txt | cut -c1-200) $(tail -n 1 $D/total.txt)" >> $O/rows.txt
done
echo "END $(date -u +%FT%TZ)" > $O/end.txt
