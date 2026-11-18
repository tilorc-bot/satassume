#!/bin/bash
# gate329.sh SHA NAME [PLANT] (sa-port-329, pareto1 under HOME=~/sp19, a shared lease; from gate328.sh): the answers gate
# of the witness check on the 20 workloads, on the staged tree of SHA (a git archive, so nothing changes under it).
# Each workload runs through live.py --check entry: py and rust (SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust), each with
# SLICE_WITNESS=0 and =1; ans328.py then compares the answers of on against off per workload and mode.
# With PLANT only the =1 runs are made, with SLICE_WITNESS_PLANT=PLANT, and compared against OUT/gate's =0 rows.
# Output OUT/NAME; end marker OUT/NAME/end.txt, the last line of this script.
export HOME=/home/tilo/sp19
G=/home/tilo/sa-rust-ids-work/sa-port-329/s1; T=$G/bench-$1/tree; S=$T/rust-spike/slice; O=/home/tilo/sa-rust-ids-work/sa-port-329/job/$2; PL=${3:-}
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED; export PYTHONPATH=$T:$W/sympy:$W/shim
unset SLICE_WITNESS SLICE_WITNESS_CAP SLICE_WITNESS_PLANT SLICE_CONVERT SLICE_TERM_FRAMES
mkdir -p $O; cd $S; cat $G/bench-$1/SHA > $O/source.txt; sha256sum $S/sa_solver.so $T/satassume/witness.py >> $O/source.txt
$PY -c 'import satassume, sympy; print(satassume.__file__, sympy.__file__)' >> $O/source.txt
WLS=${WLS:-"lra f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls"}
SWS="0 1"; [ -n "$PL" ] && SWS=1
for wl in $WLS; do for m in py rust; do for sw in $SWS; do echo "$wl $m $sw"; done; done; done > $O/todo.txt
export O PL
xargs -P ${N:-16} -L 1 bash -c 'wl=$0; m=$1; sw=$2; f=$O/$wl-$m-$sw
  [ $m = rust ] && export SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust
  [ $sw = 1 ] && [ -n "$PL" ] && export SLICE_WITNESS_PLANT=$PL
  SLICE_WITNESS=$sw $PY live.py $wl $m $f.jsonl --check entry > $f.tot 2> $f.err; echo "$? $wl $m $sw" >> $O/rc.txt' < $O/todo.txt
[ -n "$PL" ] && for wl in $WLS; do for m in py rust; do ln -sf ../gate/$wl-$m-0.jsonl $O/$wl-$m-0.jsonl; done; done
$PY $G/tools/ans328.py $O $WLS > $O/answers.txt 2>&1
echo "END $(date -u +%FT%TZ)" > $O/end.txt
