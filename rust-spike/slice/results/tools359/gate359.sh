#!/bin/bash
# gate359.sh (sa-port-359, pareto0 under HOME=~/sp19, inside job359.sh; G, OUT, NEW from it): item 4's per-query gate on
# the staged frozen tree of NEW with its x86-64 .so. Not a timing.
#  1. kept: test_convert_walk.py in plain pytest (-v): the counters 740-746 fire on their planted cases on this build,
#     and [700-too-deep] runs (no EXCEPTION_HANDLED tool is registered here)                        -> OUT/gate/kept.log
#  2. diff359.py on the gate's 20 workloads and evalbench's fuzz seeds 0 1 2 42, three arms, all with
#     SLICE_TERM_FRAMES=rust SLICE_WITNESS=1: py (SLICE_CONVERT=py, Python's walker, the reference), rust
#     (SLICE_CONVERT=rust), nat (rust with SLICE_WITNESS_RUST=1, S1's configuration); cmp359.py rust against py per
#     workload, and nat's answers digest beside rust's                                             -> OUT/gate/cmp.txt
#  3. p1/convert_diff.sh as the bar's convdiff phase runs it (the differential on every input of the 20 workloads and
#     the suite; live.py --check entry on the Python backend, on Rust with SLICE_CONVERT=py and with =rust), then
#     livecmp.py's whole output for SLICE_CONVERT=py against =rust per workload (answers, sessions, Engine.stats,
#     the moved containers' ids)                                              -> OUT/convdiff, OUT/gate/livecmp-WL.txt
# End marker: OUT/gate/end.txt, the last line here.
T=$G/bench-$NEW/tree; S=$T/rust-spike/slice; O=$OUT/gate; mkdir -p $O
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED T S O G; export PYTHONPATH=$T:$W/sympy:$W/shim SLICE_DIR=$S
for v in $(env | grep -o '^SLICE_[A-Z_0-9]*' | grep -v '^SLICE_DIR$'); do unset $v; done
{ cat $G/bench-$NEW/SHA; sha256sum $S/sa_solver.so; cd $S && $PY -c 'import satassume, sympy, sa_solver; print(satassume.__file__, sympy.__file__, sa_solver.__file__)'; $PY -VV; } > $O/source.txt 2>&1
( cd $T && PYTHONPATH=$PYTHONPATH:$S $PY -m pytest -v -p no:cacheprovider -W ignore rust-spike/slice/test_convert_walk.py > $O/kept.log 2>&1; echo "$? $(tail -n 1 $O/kept.log)" > $O/kept-exit.txt )
WLS="lra f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls fuzz0 fuzz1 fuzz2 fuzz42"
for wl in $WLS; do for arm in py rust nat; do echo "$wl $arm"; done; done > $O/todo.txt
xargs -P ${N:-12} -L 1 bash -c 'wl=$0; arm=$1; n=$(echo $wl | tr -d :); f=$O/$n-$arm
  export SLICE_TERM_FRAMES=rust SLICE_WITNESS=1 SLICE_CONVERT=rust
  case $arm in py) export SLICE_CONVERT=py;; nat) export SLICE_WITNESS_RUST=1;; esac
  cd $S && $PY $G/tools/diff359.py $wl $f.jsonl > $f.out 2> $f.err; echo "$? $wl $arm" >> $O/rc.txt' < $O/todo.txt
for wl in $WLS; do n=$(echo $wl | tr -d :)
  echo "$($PY $G/tools/cmp359.py $O/$n-py.jsonl $O/$n-rust.jsonl 2>&1 | tail -n 1) | nat $(tail -n 1 $O/$n-nat.jsonl | $PY -c 'import json,sys; d=json.loads(sys.stdin.read()); print(d["digest"], d["cv"], d["life"])' 2>&1 | tail -n 1)"
done > $O/cmp.txt
echo "GATE-DIFF $(date -u +%FT%TZ) rows $(wc -l < $O/cmp.txt) EQUAL $(grep -c ' EQUAL | nat' $O/cmp.txt) rc0 $(grep -c '^0 ' $O/rc.txt)/$(wc -l < $O/rc.txt)" > $O/diff-end.txt
N=6 P=7 bash $S/p1/convert_diff.sh $OUT/convdiff > $OUT/convdiff.log 2>&1
for wl in $WLS; do n=$(echo $wl | tr -d :); [ -e $OUT/convdiff/$n-rust-cpy.jsonl ] && ( cd $S && $PY livecmp.py $OUT/convdiff/$n-rust-cpy.jsonl $OUT/convdiff/$n-rust-crust.jsonl > $O/livecmp-$n.txt 2>&1; echo "$n rc=$? $(tail -n 1 $O/livecmp-$n.txt | cut -c1-80)" >> $O/livecmp.txt ); done
echo "END $(date -u +%FT%TZ) $(cat $O/diff-end.txt) | convdiff $(tail -n 2 $OUT/convdiff/total.txt | tr '\n' ' ') | livecmp MATCH $(grep -c 'MATCH' $O/livecmp.txt)/$(wc -l < $O/livecmp.txt)" > $O/end.txt
