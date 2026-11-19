#!/bin/bash
# job344bar.sh (sa-port-344, pareto0; tools337/job337bar.sh with this step's names and rows): the bar for the exact-pi
# step of the witness check (issue 323), on the frozen branch bar/witness-reasons-bfceccc9 (port/witness-reasons at the
# tested SHA, so later results commits do not move what the bar tests), through p1/bar.sh from that SHA
# (~/sp19/bar-sa-port-344.sh): TESTS=all, the suite, dev and fuzz, the 15 extra workloads, fmrows, N=6, no SLICE_
# variable from the launcher, the /proc environ watcher. The branch is checked out BEFORE the .so is copied, and the
# job stops with END so-missing unless the copied .so has the expected hash.
# Rows of this step only, as workload rows AND suite rows: witness:on (no plant, SLICE_WITNESS=1) and the three plants
# of the step, each with the switch on: witness:pi-sign (755), witness:pi-rational (756), witness:pi-enclosure (757).
# The plain rows have the switch off (unset): the default path.
# .so: the pareto venv build of 29c5a0db's crate (cad764d46471b1c6); the crate is source-equal at bfceccc9
# (gobar344.sh checks it); pareto0 has no cargo.
# BASE: the last landing's suite rows, sa-port-337's bar on 786410d, on pareto0 (rust-slice 29c5a0db adds test-only
# commits to it, so their ids show as new or changed).
# End marker: ~/sp19/sa-rust-ids-work/sa-port-344/bar-end.txt, written by the `echo "END ...` line below.
R=/home/tilo/sp19; W9=$R/sa-rust-ids-work; L=$W9/sa-port-344; B=$L/bar; T=$R/dev/sa-port-344
rm -rf $L/bar $L/bar-end.txt $L/env-raw.txt; mkdir -p $B
[ -d $T/.git ] || git clone -q https://github.com/tilorc-bot/satassume $T || { echo "END clone-failed $(date -u +%FT%TZ)" > $L/bar-end.txt; exit 2; }
git -C $T fetch -q origin && git -C $T checkout -q -f -B bar/witness-reasons-bfceccc9 origin/bar/witness-reasons-bfceccc9 || { echo "END checkout-failed $(date -u +%FT%TZ)" > $L/bar-end.txt; exit 2; }
cp $L/so/sa_solver.so $T/rust-spike/slice/sa_solver.so
[ "$(sha256sum $T/rust-spike/slice/sa_solver.so | cut -c1-16)" = "$(cat $L/so/want.txt)" ] || { echo "END so-missing $(date -u +%FT%TZ)" > $L/bar-end.txt; exit 2; }
{ echo "the pareto venv build of 29c5a0db (crate source-equal at $(cat $L/so/source.txt)), copied"; cat $L/so/so.txt; sha256sum $T/rust-spike/slice/sa_solver.so; } > $B/build.txt
unset SLICE_CONVERT SLICE_CONVERT_PLANT SLICE_SESSION_PLANT SLICE_TERM_PLANT SLICE_TERM_FRAMES SLICE_WITNESS SLICE_WITNESS_PLANT SLICE_WITNESS_CAP
{ echo "launcher environment, SLICE_ variables:"; env | grep '^SLICE_' || echo "(none)"; } > $L/launcher-env.txt
(
  while [ ! -e $L/bar-end.txt ]; do
    for e in /proc/[0-9]*/environ; do
      v=$({ tr '\0' '\n' < $e; } 2>/dev/null | grep -E '^SLICE_(SUITE_OUT|CONVERT|CONVERT_PLANT|SESSION_PLANT|TERM_PLANT|TERM_FRAMES|WITNESS|WITNESS_PLANT|WITNESS_CAP)=' | sort | tr '\n' ' ')
      case $v in *SLICE_SUITE_OUT=$B/*)
        p=${e%/environ}; row=${v##*SLICE_SUITE_OUT=$B/}; row=${row%% *}
        echo "$row $(cat $p/comm 2>/dev/null) ${v//SLICE_SUITE_OUT=$B\/$row /}";;
      esac
    done >> $L/env-raw.txt
    sleep 5
  done
) &
STEP="witness:on witness:pi-sign witness:pi-rational witness:pi-enclosure"
export OUT=$B BASE=$W9/sa-port-337/bar/suite
export PLANTS="$STEP"
export SUITE_PLANTS="$STEP"
export WLS="twin scope loop zero cert budget core f6 opaque rootof value wiring transfer:7:60 transfer2:3:40 cls"
export FM_WLS="f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls lra"
export FM_PLANTS="fm-atoms-merge-pred fm-args-drop-last"
export TESTS=all TESTS_SPLIT=1 DIRECT="relations_direct.py 300 0" N=6
bash $R/bar-sa-port-344.sh sa-port-344 bar/witness-reasons-bfceccc9 tests suite live plants extra suiteplants fmrows sum > $L/bar.log 2>&1
echo "END $? $(date -u +%FT%TZ) $(sha256sum $T/rust-spike/slice/sa_solver.so | cut -c1-8) $(git -C $T rev-parse --short HEAD)" > $L/bar-end.txt
wait
sort $L/env-raw.txt | uniq -c > $L/env-summary.txt
echo "WATCHER-END $(date -u +%FT%TZ)" >> $L/bar-end.txt
