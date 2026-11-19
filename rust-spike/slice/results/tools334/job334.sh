#!/bin/bash
# job334.sh (sa-port-334, pareto0): the bar for the F_MAYBE_NAN removal (issue 323), port/maybe-nan-removal's head, through
# p1/bar.sh from that head (~/sp19/bar-sa-port-334.sh), with only the rows this step needs (planner's ruling on 327, item
# 5). From tools324/job326.sh: TESTS=all, the suite, dev and fuzz, the 15 extra workloads, fmrows, N=6, no SLICE_ variable
# from the launcher, the /proc environ watcher. Plant and switch rows, as workload rows AND suite rows: plant 753
# dispatch-nan-arg-on and dispatch-opaque-off (both at Dispatch::opaque's use of may_be_nan), and the no-plant rows
# walk:rust and both:rust (term_row changed on both walkers). Suite rows only, as in 326: the five convert:* plants of
# the Rust walker. Left out: the three convert:nan-* rows (plants 746-748, retired with the bit) and the fm-*, term:*,
# frames:rust and other plants of steps this one does not touch (326's bar on 6587181 has them).
# .so: built on pareto1 from the tested SHA by tools334/pc334.sh's head run (pareto0 has no cargo), copied; build.txt.
# BASE: the last landing's suite rows, sa-port-326's bar on 6587181 (source-equal to rust-slice ec34788), on pareto0.
# End marker: ~/sp19/sa-rust-ids-work/sa-port-334/bar-end.txt, written by the `echo "END ...` line below.
R=/home/tilo/sp19; W9=$R/sa-rust-ids-work; L=$W9/sa-port-334; B=$L/bar
rm -rf $L/bar $L/bar-end.txt $L/env-raw.txt; mkdir -p $B
{ echo "built on pareto1 (pc334.sh head run, tested source $(cat $L/p1-source.txt)), copied"; cat $L/p1-build.txt; sha256sum $R/dev/sa-port-334/rust-spike/slice/sa_solver.so; } > $B/build.txt
unset SLICE_CONVERT SLICE_CONVERT_PLANT SLICE_SESSION_PLANT SLICE_TERM_PLANT SLICE_TERM_FRAMES
{ echo "launcher environment, SLICE_ variables:"; env | grep '^SLICE_' || echo "(none)"; } > $L/launcher-env.txt
(
  while [ ! -e $L/bar-end.txt ]; do
    for e in /proc/[0-9]*/environ; do
      v=$({ tr '\0' '\n' < $e; } 2>/dev/null | grep -E '^SLICE_(SUITE_OUT|CONVERT|CONVERT_PLANT|SESSION_PLANT|TERM_PLANT|TERM_FRAMES)=' | sort | tr '\n' ' ')
      case $v in *SLICE_SUITE_OUT=$B/*)
        p=${e%/environ}; row=${v##*SLICE_SUITE_OUT=$B/}; row=${row%% *}
        echo "$row $(cat $p/comm 2>/dev/null) ${v//SLICE_SUITE_OUT=$B\/$row /}";;
      esac
    done >> $L/env-raw.txt
    sleep 5
  done
) &
CPP="convert:enc-true-as-false convert:klass-no-is-expr convert:term-row-no-number convert:walk-args-unreversed convert:enc-int-no-sign"
STEP="dispatch-nan-arg-on dispatch-opaque-off walk:rust both:rust"
export OUT=$B BASE=$W9/sa-port-326/bar/suite
export PLANTS="$STEP"
export SUITE_PLANTS="zero $STEP $CPP"
export WLS="twin scope loop zero cert budget core f6 opaque rootof value wiring transfer:7:60 transfer2:3:40 cls"
export FM_WLS="f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls lra"
export FM_PLANTS="fm-atoms-merge-pred fm-args-drop-last"
export TESTS=all TESTS_SPLIT=1 DIRECT="relations_direct.py 300 0" N=6
bash $R/bar-sa-port-334.sh sa-port-334 port/maybe-nan-removal tests suite live plants extra suiteplants fmrows sum > $L/bar.log 2>&1
echo "END $? $(date -u +%FT%TZ) $(sha256sum $R/dev/sa-port-334/rust-spike/slice/sa_solver.so | cut -c1-8) $(git -C $R/dev/sa-port-334 rev-parse --short HEAD)" > $L/bar-end.txt
wait
sort $L/env-raw.txt | uniq -c > $L/env-summary.txt
echo "WATCHER-END $(date -u +%FT%TZ)" >> $L/bar-end.txt
