#!/bin/bash
# job317.sh (sa-port-317, pareto0): the full bar for the _Mark note fix in term_live's Rust frames (issue 323),
# port/mark-note's head, through p1/bar.sh from that head (~/sp19/bar-sa-port-317.sh). Config: sa-port-314's full bar
# unchanged (job314.sh: 302's PLANTS, WLS, FM_*, TESTS=all; 310's launcher form with no SLICE_ variable from the launcher,
# N=6, the /proc environ watcher; the six term:tl-* plants 740-745 and frames:rust as workload rows and suite rows; the
# five convert:* as suite rows). No new plant rows: the step moves no site (planner, 18 Nov).
# .so: built on pareto1 by bar.sh's own build phase on the tested SHA (pareto0 has no cargo), copied; build.txt says so.
# BASE: the last landing's suite rows, sa-port-314's bar on 5b1d96f (source-equal to rust-slice 5f53735), on pareto0.
# End marker: ~/sp19/sa-rust-ids-work/sa-port-317/bar-end.txt, written by the `echo "END ...` line below.
R=/home/tilo/sp19; W9=$R/sa-rust-ids-work; L=$W9/sa-port-317; B=$L/bar
rm -rf $L/bar $L/bar-end.txt $L/env-raw.txt; mkdir -p $B
{ echo "built on pareto1 (bar.sh build phase, tested source $(cat $L/p1-source.txt)), copied"; cat $L/p1-build.txt; sha256sum $R/dev/sa-port-317/rust-spike/slice/sa_solver.so; } > $B/build.txt
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
TL="term:tl-term-stale term:tl-ids-reversed term:tl-current-outer term:tl-run-flip term:tl-guard-quiet term:tl-mark-skip"
CPP="convert:enc-true-as-false convert:klass-no-is-expr convert:term-row-no-number convert:walk-args-unreversed convert:enc-int-no-sign"
export OUT=$B BASE=$W9/sa-port-314/bar/suite
export PLANTS="fm-atoms-drop-last fm-atoms-merge-pred fm-args-drop-last fm-implies-swap fm-not-drop ad-lra-class-is class-is ad-lra-atom-object fm-hand-no-give fm-hand-kept rows-product-verdict-flip atom-symbol-key-names term:mark-skips-native term:mark-wrong-pattern term:mark-leaves-entry fm-hand-per-entry nc-memo-true-false occ-walk-first sb-join-address sc-key-id-stale sc-key-id-weak sc-key-id-shared ent-method-first-self gm-guard-skip cl-view-nodes-drop $TL frames:rust"
export SUITE_PLANTS="zero fm-ite-swap same-is dispatch-keeps-memo fm-hand-instrument-by-name fm-hand-patched-direct $CPP $TL frames:rust"
export WLS="twin scope loop zero cert budget core f6 opaque rootof value wiring transfer:7:60 transfer2:3:40 cls"
export FM_WLS="f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls lra"
export FM_PLANTS="fm-atoms-merge-pred fm-args-drop-last"
export TESTS=all TESTS_SPLIT=1 DIRECT="relations_direct.py 300 0" N=6
bash $R/bar-sa-port-317.sh sa-port-317 port/mark-note tests suite live plants seed1 extra suiteplants fmrows sum > $L/bar.log 2>&1
echo "END $? $(date -u +%FT%TZ) $(sha256sum $R/dev/sa-port-317/rust-spike/slice/sa_solver.so | cut -c1-8) $(git -C $R/dev/sa-port-317 rev-parse --short HEAD)" > $L/bar-end.txt
wait
sort $L/env-raw.txt | uniq -c > $L/env-summary.txt
echo "WATCHER-END $(date -u +%FT%TZ)" >> $L/bar-end.txt
