#!/bin/bash
# job360bar.sh (sa-port-360, pareto0; tools354/job354bar.sh with this step's rows and paths): the bar for the convert.py
# port (issue 323), on the frozen branch bar/measured-next-$SHA (port/measured-next at the tested SHA, so later results
# commits do not move what the bar tests), through p1/bar.sh from that SHA (~/sp19/bar-sa-port-360.sh): TESTS=all, the
# suite, dev and fuzz, the 15 extra workloads, fmrows, the convdiff phase (p1/convert_diff.sh: the differential, then
# each of CONVERT_PLANTS), N=6, no SLICE_ variable from the launcher, the /proc environ watcher. The branch is checked
# out BEFORE the .so is copied, and the job stops with END so-missing unless the copied .so has the expected hash.
# Rows of this step only, as workload rows AND suite rows (bar.sh penv): wnative:on (no plant, the port on:
# SLICE_WITNESS=1 SLICE_CONVERT=rust SLICE_WITNESS_RUST=1, S1's configuration) and tools358/rows358.sh's six plants,
# convert:NAME (SLICE_CONVERT=rust SLICE_CONVERT_PLANT=NAME): 768 calls-structural-not, 769 power-rows-drop-last,
# 770 read-commutative-not, 771 entry-no-assumptions, 772 formula-and-as-or (wrong values: the differential sees them
# too, CONVERT_PLANTS), 773 entry-skip-replaced (a kept-test catch: no workload replaces a definition of convert.py).
# The plain rows have every switch off (unset): the default path, Python's walker. After the bar: the kept file under
# no plant and each plant (kept.txt), in plain pytest, where [700-too-deep] must show PASSED (the planner's condition).
# NOT RUN by sa-port-360: the differential's suite pass differs on one input under -p handler_count (measured-next.md
# (4), OWED [157]), so the convdiff phase would exit 1 as p1/convert_diff.sh stands; a question to the planner first.
# .so: the pareto venv build of the tested SHA's crate (tools359/stage359.sh; gobar360.sh checks the hash).
# BASE: the last landing's suite rows, sa-port-354's bar on b7302f83 (rust-slice de88d9b9), on pareto0.
# End marker: ~/sp19/sa-rust-ids-work/sa-port-360/bar-end.txt, written by the `echo "END ...` line below.
R=/home/tilo/sp19; W9=$R/sa-rust-ids-work; L=$W9/sa-port-360; B=$L/bar; T=$R/dev/sa-port-360; SHA=$(cat $L/so/source.txt)
rm -rf $L/bar $L/bar-end.txt $L/env-raw.txt; mkdir -p $B
[ -d $T/.git ] || git clone -q https://github.com/tilorc-bot/satassume $T || { echo "END clone-failed $(date -u +%FT%TZ)" > $L/bar-end.txt; exit 2; }
git -C $T fetch -q origin && git -C $T checkout -q -f -B bar/measured-next-$SHA origin/bar/measured-next-$SHA || { echo "END checkout-failed $(date -u +%FT%TZ)" > $L/bar-end.txt; exit 2; }
cp $L/so/sa_solver.so $T/rust-spike/slice/sa_solver.so
[ "$(sha256sum $T/rust-spike/slice/sa_solver.so | cut -c1-16)" = "$(cat $L/so/want.txt)" ] || { echo "END so-missing $(date -u +%FT%TZ)" > $L/bar-end.txt; exit 2; }
{ echo "the pareto venv build of $SHA (tools359/stage359.sh on pareto1), copied"; cat $L/so/so.txt; sha256sum $T/rust-spike/slice/sa_solver.so; } > $B/build.txt
unset SLICE_CONVERT SLICE_CONVERT_PLANT SLICE_SESSION_PLANT SLICE_TERM_PLANT SLICE_TERM_FRAMES SLICE_WITNESS SLICE_WITNESS_PLANT SLICE_WITNESS_CAP SLICE_WITNESS_WORK SLICE_WITNESS_RUST SLICE_WITNESS_RUST_PLANT
{ echo "launcher environment, SLICE_ variables:"; env | grep '^SLICE_' || echo "(none)"; } > $L/launcher-env.txt
(
  while [ ! -e $L/bar-end.txt ]; do
    for e in /proc/[0-9]*/environ; do
      v=$({ tr '\0' '\n' < $e; } 2>/dev/null | grep -E '^SLICE_(SUITE_OUT|CONVERT|CONVERT_PLANT|SESSION_PLANT|TERM_PLANT|TERM_FRAMES|WITNESS|WITNESS_PLANT|WITNESS_CAP|WITNESS_WORK|WITNESS_RUST|WITNESS_RUST_PLANT)=' | sort | tr '\n' ' ')
      case $v in *SLICE_SUITE_OUT=$B/*)
        p=${e%/environ}; row=${v##*SLICE_SUITE_OUT=$B/}; row=${row%% *}
        echo "$row $(cat $p/comm 2>/dev/null) ${v//SLICE_SUITE_OUT=$B\/$row /}";;
      esac
    done >> $L/env-raw.txt
    sleep 5
  done
) &
CPP358="convert:calls-structural-not convert:power-rows-drop-last convert:read-commutative-not convert:entry-no-assumptions convert:formula-and-as-or convert:entry-skip-replaced"
STEP="wnative:on $CPP358"
export CONVERT_PLANTS="calls-structural-not power-rows-drop-last read-commutative-not entry-no-assumptions formula-and-as-or"
export OUT=$B BASE=$W9/sa-port-354/bar/suite
export PLANTS="$STEP"
export SUITE_PLANTS="$STEP"
export WLS="twin scope loop zero cert budget core f6 opaque rootof value wiring transfer:7:60 transfer2:3:40 cls"
export FM_WLS="f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls lra"
export FM_PLANTS="fm-atoms-merge-pred fm-args-drop-last"
export TESTS=all TESTS_SPLIT=1 DIRECT="relations_direct.py 300 0" N=6
bash $R/bar-sa-port-360.sh sa-port-360 bar/measured-next-$SHA tests suite live plants extra suiteplants fmrows convdiff sum > $L/bar.log 2>&1
rc=$?
# the kept file on the bar's tree and .so: test_convert_walk.py in plain pytest (no monitoring tool, so [700-too-deep]
# runs: the ruling's row) with no plant and under each of the six, SLICE_CONVERT=rust -> $B/kept.txt, one line per plant
( export HOME=$R; . $R/sa-rust-ids-work/env.sh; cd $T; export PYTHONPATH=$T:$W/sympy:$W/shim:$T/rust-spike/slice SLICE_CONVERT=rust
  for pl in none calls-structural-not power-rows-drop-last read-commutative-not entry-no-assumptions formula-and-as-or entry-skip-replaced; do
    [ $pl = none ] && unset SLICE_CONVERT_PLANT || export SLICE_CONVERT_PLANT=$pl
    $PY -m pytest -v -rf -p no:cacheprovider -W ignore rust-spike/slice/test_convert_walk.py > $B/kept-$pl.log 2>&1
    echo "$pl: rc $? | $(tail -n 1 $B/kept-$pl.log) | too-deep $(grep -c '700-too-deep. PASSED' $B/kept-$pl.log) | $(grep '^FAILED' $B/kept-$pl.log | cut -d' ' -f2 | tr '\n' ' ')"
  done > $B/kept.txt )
echo "END $rc $(date -u +%FT%TZ) $(sha256sum $T/rust-spike/slice/sa_solver.so | cut -c1-8) $(git -C $T rev-parse --short HEAD)" > $L/bar-end.txt
wait
sort $L/env-raw.txt | uniq -c > $L/env-summary.txt
echo "WATCHER-END $(date -u +%FT%TZ)" >> $L/bar-end.txt
