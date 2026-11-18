#!/bin/bash
# gate328.sh OUT [PLANT] (sa-port-328, orion, detached): the answers gate of the witness check on the 20 workloads.
# Each workload runs through live.py --check entry four times: py and rust (SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust),
# each with SLICE_WITNESS=0 and =1 (PLANT, if given, is SLICE_WITNESS_PLANT for the =1 runs). ans328.py then compares the
# answers of on against off per workload and mode. End marker: OUT/end.txt, the last line of this script.
T=$HOME/sa-rust-ids-work/sa-port-328/wt; S=$T/rust-spike/slice; O=$1; PL=${2:-}
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED; export PYTHONPATH=$T:$W/sympy:$W/shim
mkdir -p $O; cd $S; git -C $T rev-parse --short HEAD > $O/source.txt; sha256sum $S/sa_solver.so >> $O/source.txt
$PY -c 'import satassume, sympy; print(satassume.__file__, sympy.__file__)' >> $O/source.txt
WLS=${WLS:-"lra f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls"}
for wl in $WLS; do for m in ${MODES:-py rust}; do for sw in 0 1; do echo "$wl $m $sw"; done; done; done > $O/todo.txt
export O PL
xargs -P ${N:-6} -L 1 bash -c 'wl=$0; m=$1; sw=$2; f=$O/$wl-$m-$sw
  [ $m = rust ] && export SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust
  [ $sw = 1 ] && [ -n "$PL" ] && export SLICE_WITNESS_PLANT=$PL
  SLICE_WITNESS=$sw $PY live.py $wl $m $f.jsonl --check entry > $f.tot 2> $f.err; echo "$? $wl $m $sw" >> $O/rc.txt' < $O/todo.txt
$PY $T/rust-spike/slice/results/tools328/ans328.py $O $WLS > $O/answers.txt 2>&1
echo "END $(date -u +%FT%TZ)" > $O/end.txt
