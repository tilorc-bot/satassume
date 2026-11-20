#!/bin/bash
# job353bar.sh (sa-port-353, pareto0; tools347/job347bar.sh with this step's names and rows): the bar for the native
# witness check (issue 323), on the frozen branch bar/witness-native-$SHA (port/witness-native at the tested SHA, so
# later results commits do not move what the bar tests), through p1/bar.sh from that SHA (~/sp19/bar-sa-port-353.sh):
# TESTS=all, the suite, dev and fuzz, the 15 extra workloads, fmrows, N=6, no SLICE_ variable from the launcher, the
# /proc environ watcher. The branch is checked out BEFORE the .so is copied, and the job stops with END so-missing
# unless the copied .so has the expected hash.
# Rows of this step only, as workload rows AND suite rows (bar.sh penv): witness:on (no plant: SLICE_WITNESS=1, Python's
# witness.py, the reference), wnative:on (no plant: SLICE_WITNESS=1 SLICE_CONVERT=rust SLICE_WITNESS_RUST=1) and the five
# plants on the native path, each with those switches on: wnative:wn-integer-half (760, a wrong table entry),
# wnative:wn-work-one (761, the work count off by one), wnative:wn-skip-patched (762, a skipped P1 guard; its site is in
# witness_live.py because the guards stay Python by ruling, and the hook that calls them is the native path's entry),
# wnative:wn-int-side (763, the lookup's type check) and wnative:wn-skip-own (764, a replaced function of witness.py
# passed over). 762 and 764 count their fired sites in witness_live.FIRED, which reaches the bar through plant_count.py
# (`wnative`, suite rows) and the session report's witness_plant_fired (workload rows).
# The plain rows have every switch off (unset): the default path. After the bar: the kept tests under each plant (kept.txt).
# .so: the pareto venv build of the tested SHA's crate (stage352.sh; gobar353.sh checks the hash); pareto0 has no cargo.
# BASE: the last landing's suite rows, sa-port-348's bar on 82d4ddf3, on pareto0 (rust-slice 6ee354f9 adds results to it
# and no source).
# End marker: ~/sp19/sa-rust-ids-work/sa-port-353/bar-end.txt, written by the `echo "END ...` line below.
R=/home/tilo/sp19; W9=$R/sa-rust-ids-work; L=$W9/sa-port-353; B=$L/bar; T=$R/dev/sa-port-353; SHA=$(cat $L/so/source.txt)
rm -rf $L/bar $L/bar-end.txt $L/env-raw.txt; mkdir -p $B
[ -d $T/.git ] || git clone -q https://github.com/tilorc-bot/satassume $T || { echo "END clone-failed $(date -u +%FT%TZ)" > $L/bar-end.txt; exit 2; }
git -C $T fetch -q origin && git -C $T checkout -q -f -B bar/witness-native-$SHA origin/bar/witness-native-$SHA || { echo "END checkout-failed $(date -u +%FT%TZ)" > $L/bar-end.txt; exit 2; }
cp $L/so/sa_solver.so $T/rust-spike/slice/sa_solver.so
[ "$(sha256sum $T/rust-spike/slice/sa_solver.so | cut -c1-16)" = "$(cat $L/so/want.txt)" ] || { echo "END so-missing $(date -u +%FT%TZ)" > $L/bar-end.txt; exit 2; }
{ echo "the pareto venv build of $SHA (build352.sh on pareto1), copied"; cat $L/so/so.txt; sha256sum $T/rust-spike/slice/sa_solver.so; } > $B/build.txt
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
STEP="witness:on wnative:on wnative:wn-integer-half wnative:wn-work-one wnative:wn-skip-patched wnative:wn-int-side wnative:wn-skip-own"
export OUT=$B BASE=$W9/sa-port-348/bar/suite
export PLANTS="$STEP"
export SUITE_PLANTS="$STEP"
export WLS="twin scope loop zero cert budget core f6 opaque rootof value wiring transfer:7:60 transfer2:3:40 cls"
export FM_WLS="f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls lra"
export FM_PLANTS="fm-atoms-merge-pred fm-args-drop-last"
export TESTS=all TESTS_SPLIT=1 DIRECT="relations_direct.py 300 0" N=6
bash $R/bar-sa-port-353.sh sa-port-353 bar/witness-native-$SHA tests suite live plants extra suiteplants fmrows sum > $L/bar.log 2>&1
rc=$?
# the kept tests on the bar's tree and .so: test_witness_native.py with no plant and under each of the five (it reads
# SLICE_WITNESS_RUST_PLANT itself; the bar's tests phase runs it without one) -> $B/kept.txt, one line per plant
( export HOME=$R; . $R/sa-rust-ids-work/env.sh; cd $T/rust-spike/slice; export PYTHONPATH=$T:$W/sympy:$W/shim
  for pl in none wn-integer-half wn-work-one wn-skip-patched wn-int-side wn-skip-own; do
    [ $pl = none ] && unset SLICE_WITNESS_RUST_PLANT || export SLICE_WITNESS_RUST_PLANT=$pl
    $PY -m pytest -q -rf -p no:cacheprovider test_witness_native.py > $B/kept-$pl.log 2>&1
    echo "$pl: rc $? | $(tail -n 1 $B/kept-$pl.log) | $(grep '^FAILED' $B/kept-$pl.log | cut -d' ' -f2 | tr '\n' ' ')"
  done > $B/kept.txt )
echo "END $rc $(date -u +%FT%TZ) $(sha256sum $T/rust-spike/slice/sa_solver.so | cut -c1-8) $(git -C $T rev-parse --short HEAD)" > $L/bar-end.txt
wait
sort $L/env-raw.txt | uniq -c > $L/env-summary.txt
echo "WATCHER-END $(date -u +%FT%TZ)" >> $L/bar-end.txt
