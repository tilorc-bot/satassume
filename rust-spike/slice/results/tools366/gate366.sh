#!/bin/bash
# gate366.sh (sa-port-366, pareto1 under HOME=~/sp19, inside job366.sh; G, OUT, NEW, BASE from it): item 5's per-query
# gate of the per-term level's removal, on the staged frozen trees of NEW and BASE (f5c1f3f4) with their x86-64 .so.
# Not a timing.
#  1. kept: NEW's test_convert_walk.py in plain pytest (-v): counters 740-746 fire on their planted cases on this
#     build, [700-too-deep] runs, the kept plants are caught                                            -> OUT/gate/kept.log
#  2. tools359/diff359.py on the gate's 20 workloads and evalbench's fuzz seeds 0 1 2 42, on BASE and on NEW, each under
#     SLICE_CONVERT=py and =rust (all with SLICE_TERM_FRAMES=rust SLICE_WITNESS=1, as 359's gate); cmp363.py BASE
#     against NEW per workload and walker (per query: answers, Engine.stats, refusals, counts, raised, terms; per pass:
#     740-746, term_live's counts and RAISED), and tools359/cmp359.py NEW's py against NEW's rust
#                                                                             -> OUT/gate/cmp.txt, OUT/gate/cmp-walk.txt
#  3. live.py --check entry on BASE and on NEW for the 20 workloads, three cells each (the Python backend; Rust with
#     SLICE_CONVERT=py; Rust with SLICE_CONVERT=rust), and NEW's livecmp.py BASE against NEW per workload and cell
#     (answers, sessions, Engine.stats, the moved containers' ids)                              -> OUT/gate/livecmp.txt
#  4. NEW's p1/convert_diff.sh as the bar's convdiff phase runs it (the differential of the two walkers on every input
#     of the 20 workloads and the suite), then under plant term-row-no-number (672: its site is the row this step
#     shortened)                                                                   -> OUT/convdiff, OUT/convdiff-672
#  5. step 2's count: lvl366.py (diff359.py's pass with the walkers' level call counted) on BASE, the same 24 workloads
#     under both walkers, read by lvltab366.py; and dev with the 2000th call raising (LVL366_PLANT), which shows that the
#     raise count fires and what a raise did on BASE                              -> OUT/gate/lvl.txt, lvl-plant.txt
# End marker: OUT/gate/end.txt, the last line here.
O=$OUT/gate; mkdir -p $O
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED O G NEW BASE
for v in $(env | grep -o '^SLICE_[A-Z_0-9]*' | grep -v '^SLICE_DIR$'); do unset $v; done
tree() { export T=$G/bench-$1/tree; export S=$T/rust-spike/slice; export PYTHONPATH=$T:$W/sympy:$W/shim SLICE_DIR=$S; }
export -f tree
for s in $BASE $NEW; do tree $s; { cat $G/bench-$s/SHA; sha256sum $S/sa_solver.so; cd $S && $PY -c 'import satassume, sympy, sa_solver; print(satassume.__file__, sympy.__file__, sa_solver.__file__)'; $PY -VV; } > $O/source-$s.txt 2>&1; done
tree $NEW
( cd $T && PYTHONPATH=$PYTHONPATH:$S $PY -m pytest -v -p no:cacheprovider -W ignore rust-spike/slice/test_convert_walk.py > $O/kept.log 2>&1; echo "$? $(tail -n 1 $O/kept.log)" > $O/kept-exit.txt )
WLS="lra f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls fuzz0 fuzz1 fuzz2 fuzz42"
for wl in $WLS; do for arm in py rust; do for s in $BASE $NEW; do echo "$wl $arm $s"; done; done; done > $O/todo.txt
xargs -P ${N:-12} -L 1 bash -c 'wl=$0; arm=$1; tree $2; n=$(echo $wl | tr -d :); f=$O/$n-$arm-$2
  export SLICE_TERM_FRAMES=rust SLICE_WITNESS=1 SLICE_CONVERT=$arm
  cd $S && $PY $G/tools/diff359.py $wl $f.jsonl > $f.out 2> $f.err; echo "$? $wl $arm $2" >> $O/rc.txt' < $O/todo.txt
for wl in $WLS; do n=$(echo $wl | tr -d :)
  for arm in py rust; do $PY $G/tools/cmp363.py $O/$n-$arm-$BASE.jsonl $O/$n-$arm-$NEW.jsonl 2>&1 | tail -n 1; done >> $O/cmp.txt
  $PY $G/tools/cmp359.py $O/$n-py-$NEW.jsonl $O/$n-rust-$NEW.jsonl 2>&1 | tail -n 1 >> $O/cmp-walk.txt
done
echo "GATE-DIFF $(date -u +%FT%TZ) rows $(wc -l < $O/cmp.txt) EQUAL $(grep -c ' EQUAL$' $O/cmp.txt) walk-EQUAL $(grep -c ' EQUAL$' $O/cmp-walk.txt)/$(wc -l < $O/cmp-walk.txt) rc0 $(grep -c '^0 ' $O/rc.txt)/$(wc -l < $O/rc.txt)" > $O/diff-end.txt
LWLS="f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls lra"
for wl in $LWLS; do for s in $BASE $NEW; do echo "$wl $s"; done; done > $O/live-todo.txt
xargs -P ${P:-7} -L 1 bash -c 'wl=$0; tree $1; n=$(echo $wl | tr -d :); f=$O/live-$n; cd $S
  $PY live.py $wl py $f-py-$1.jsonl --check entry > $f-py-$1.tot 2> $f-py-$1.err; a=$?
  SLICE_CONVERT=py $PY live.py $wl rust $f-cpy-$1.jsonl --check entry > $f-cpy-$1.tot 2> $f-cpy-$1.err; b=$?
  SLICE_CONVERT=rust $PY live.py $wl rust $f-crust-$1.jsonl --check entry > $f-crust-$1.tot 2> $f-crust-$1.err; echo "$a $b $? $wl $1" >> $O/live-rc.txt' < $O/live-todo.txt
tree $NEW
for wl in $LWLS; do n=$(echo $wl | tr -d :); for c in py cpy crust; do
  ( cd $S && $PY livecmp.py $O/live-$n-$c-$BASE.jsonl $O/live-$n-$c-$NEW.jsonl > $O/livecmp-$n-$c.txt 2>&1; echo "$n $c rc=$? $(tail -n 1 $O/livecmp-$n-$c.txt | cut -c1-80)" >> $O/livecmp.txt ); done; done
echo "GATE-LIVE $(date -u +%FT%TZ) rows $(wc -l < $O/livecmp.txt) MATCH $(grep -c 'MATCH' $O/livecmp.txt) rc0 $(grep -c '^0 0 0 ' $O/live-rc.txt)/$(wc -l < $O/live-rc.txt)" > $O/live-end.txt
N=6 P=7 bash $S/p1/convert_diff.sh $OUT/convdiff > $OUT/convdiff.log 2>&1
N=6 P=7 bash $S/p1/convert_diff.sh $OUT/convdiff-672 term-row-no-number > $OUT/convdiff-672.log 2>&1
for wl in $WLS; do for arm in py rust; do echo "$wl $arm 0"; done; done > $O/lvl-todo.txt
for arm in py rust; do echo "dev $arm 2000"; done >> $O/lvl-todo.txt
xargs -P ${N:-12} -L 1 bash -c 'wl=$0; arm=$1; tree $BASE; n=$(echo $wl | tr -d :); f=$O/lvl$2-$n-$arm-$BASE
  export SLICE_TERM_FRAMES=rust SLICE_WITNESS=1 SLICE_CONVERT=$arm LVL366_PLANT=$2
  cd $S && $PY $G/tools/lvl366.py $G/tools/diff359.py $wl $f.jsonl > $f.out 2> $f.err; echo "$? $wl $arm $2" >> $O/lvl-rc.txt' < $O/lvl-todo.txt
$PY $G/tools/lvltab366.py $O/lvl0-*-$BASE.jsonl > $O/lvl.txt 2>&1
$PY $G/tools/lvltab366.py $O/lvl2000-*-$BASE.jsonl > $O/lvl-plant.txt 2>&1; grep -h "TermFault\|lvl366 plant" $O/lvl2000-*.err | sort | uniq -c >> $O/lvl-plant.txt
echo "END $(date -u +%FT%TZ) $(cat $O/diff-end.txt) | $(cat $O/live-end.txt) | convdiff $(tail -n 2 $OUT/convdiff/total.txt | tr '\n' ' ') | 672 $(head -n 1 $OUT/convdiff-672/total.txt | cut -c1-120) $(tail -n 1 $OUT/convdiff-672/total.txt) | LVL rows $(wc -l < $O/lvl.txt) raised0 $(grep -c "calls-raised 0 queries-with-a-raise 0" $O/lvl.txt) rc0 $(grep -c "^0 .* 0$" $O/lvl-rc.txt)/$(grep -c " 0$" $O/lvl-rc.txt)" > $O/end.txt
