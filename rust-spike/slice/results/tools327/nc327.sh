#!/bin/bash
# nc327.sh (sa-port-327, pareto0): nancount327.py on the 20 workloads, the bar's clone (6587181), Python's walker.
# Rows: $O/WL.json. End marker: $O/end.txt, written by the last line of this script.
export REAL=/home/tilo HOME=/home/tilo/sp19
X=$HOME/sa-rust-ids-work/sa-port-327; O=$X/nc; H=$HOME/dev/sa-port-326; rm -rf $O; mkdir -p $O
. $HOME/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED O H X
cd $H/rust-spike/slice; export PYTHONPATH=$H:$W/sympy:$W/shim
unset SLICE_CONVERT SLICE_CONVERT_PLANT SLICE_SESSION_PLANT SLICE_TERM_PLANT SLICE_TERM_FRAMES
WLS="f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls lra"
printf '%s\n' $WLS | xargs -P 8 -I{} bash -c 'n=$(echo {} | tr -d :); $PY $X/nancount327.py {} $O/$n.json > $O/$n.out 2> $O/$n.err; echo "{} exit $?" >> $O/wl-exit.txt'
echo "END $(date -u +%FT%TZ)" > $O/end.txt
