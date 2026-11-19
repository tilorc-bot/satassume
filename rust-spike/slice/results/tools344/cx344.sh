#!/bin/bash
# cx344.sh TREE OUT (sa-port-344; tools343/cx343.sh with pc344.py, whose wrappers are registered with witness.accept; pareto0 under a shared lease, HOME=~/sp19; counts, not times): pc344.py in py mode
# with SLICE_WITNESS=1 on the gate's 20 workloads, 4 at a time: per workload the calls of the check and what the
# engine did after each (pc344.py's `exit`). One file per workload, OUT/WL.json; end marker OUT/end.txt.
export HOME=/home/tilo/sp19
T=$1; S=$T/rust-spike/slice; export O=$2 PC=$(dirname $0)/pc344.py S
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED; export PYTHONPATH=$T:$W/sympy:$W/shim
unset SLICE_WITNESS_CAP SLICE_WITNESS_PLANT SLICE_CONVERT SLICE_TERM_FRAMES
mkdir -p $O; cd $S
for wl in lra f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls; do echo $wl; done |
  xargs -P 4 -L 1 bash -c 'SLICE_WITNESS=1 SLICE_DIR=$S $PY $PC $0 py > $O/$0.json 2> $O/$0.err; echo "$? $0" >> $O/rc.txt'
echo "END $(date -u +%FT%TZ)" > $O/end.txt
