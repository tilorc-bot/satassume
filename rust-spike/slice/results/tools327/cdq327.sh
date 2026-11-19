#!/bin/bash
# cdq327.sh TAG (sa-port-327, pareto0): cd327.sh's differential on four short workloads only (dev cls zero core), the
# three plants side by side, so the plants' liveness on workload inputs is known before the 20-workload run ends.
# End marker: $O/end.txt, written by the last line of this script.
TAG=${1:?tag}
export REAL=/home/tilo HOME=/home/tilo/sp19
X=$HOME/sa-rust-ids-work/sa-port-327; O=$X/cdq-$TAG; H=$HOME/dev/sa-port-326; rm -rf $O; mkdir -p $O
. $HOME/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED O H
cd $H/rust-spike/slice; export PYTHONPATH=$H:$W/sympy:$W/shim
unset SLICE_CONVERT SLICE_CONVERT_PLANT SLICE_SESSION_PLANT SLICE_TERM_PLANT SLICE_TERM_FRAMES
(git -C $H rev-parse --short HEAD; sha256sum sa_solver.so) > $O/tree.txt 2>&1
for pl in nan-no-specials nan-atom-args nan-one-level; do for wl in dev cls zero core; do echo "$pl $wl"; done; done |
  xargs -P 6 -L1 bash -c 'D=$O/$0; mkdir -p $D; SLICE_CONVERT_PLANT=$0 SLICE_CONVERT=py SLICE_CONVERT_DIFF=$D/wl-$1 SLICE_CONVERT_DIFF_READS=0 $PY live.py $1 rust $D/$1.jsonl --check entry > $D/$1.tot 2> $D/$1.err; echo "$1 exit $?" >> $D/wl-exit.txt; rm -f $D/$1.jsonl'
for pl in nan-no-specials nan-atom-args nan-one-level; do D=$O/$pl
  $PY convert_diff.py $D/wl-* > $D/total.txt 2>&1; echo "exit $?" >> $D/total.txt
  echo "$pl $(date -u +%T) $(head -n 1 $D/total.txt | cut -c1-200) $(tail -n 1 $D/total.txt)" >> $O/rows.txt
done
echo "END $(date -u +%FT%TZ)" > $O/end.txt
