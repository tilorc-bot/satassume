#!/bin/sh
# pcrun346.sh OUT [WL...] (sa-port-346; orion, counts and work only, not an S1 time): pc346.py on each workload, for each
# of MODES (default "py rust"; rust sets both Rust switches), SLICE_WITNESS=1 cap 32, with the caller's
# SLICE_WITNESS_WORK and SLICE_WITNESS_PLANT, J (default 4) at a time. One file per run: OUT/pc-WL-MODE.json; OUT/rc.txt.
. $HOME/sa-rust-ids-work/sa-port-346/env346.sh
O=$1; shift; mkdir -p $O; cd $O; : > rc.txt
one() { SLICE_WITNESS=1 SLICE_WITNESS_CAP=32 SLICE_CONVERT=$2 SLICE_TERM_FRAMES=$2 $PY $T/rust-spike/slice/results/tools346/pc346.py $1 $2 > $O/pc-$1-$2.json 2> $O/err-$1-$2.txt; echo "$? $1 $2" >> $O/rc.txt; }
n=0
for wl in "$@"; do for m in ${MODES:-py rust}; do
  one $wl $m & n=$((n+1)); [ $((n % ${J:-4})) = 0 ] && wait
done; done; wait
echo "END $(date -u +%T) $(wc -l < rc.txt) runs, nonzero: $(grep -vc '^0 ' rc.txt)" > $O/end.txt
