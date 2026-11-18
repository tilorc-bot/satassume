#!/bin/bash
# job326.sh (sa-port-326, pareto0): the full bar for `_may_be_nan` in the Rust walk (issue 323), port/may-be-nan's head,
# through p1/bar.sh from that head (~/sp19/bar-sa-port-326.sh). Config: sa-port-317's full bar (job317.sh: 302's PLANTS,
# WLS, FM_*, TESTS=all; no SLICE_ variable from the launcher, N=6, the /proc environ watcher; term:tl-* 740-745 and
# frames:rust as workload and suite rows; the five convert:* as suite rows) plus, as workload rows AND suite rows: the
# no-plant rows walk:rust (SLICE_CONVERT=rust) and both:rust (and SLICE_TERM_FRAMES=rust), and the three plants
# convert:nan-no-specials, convert:nan-atom-args, convert:nan-one-level (746-748; planner, 18 Nov ~19:40Z, (d)).
# .so: built on pareto1 by bar.sh's own build phase on the tested SHA (pareto0 has no cargo), copied; build.txt says so.
# BASE: the last landing's suite rows, sa-port-317's bar on 46750d4 (source-equal to rust-slice e5db633), on pareto0.
# End marker: ~/sp19/sa-rust-ids-work/sa-port-326/bar-end.txt, written by the `echo "END ...` line below.
R=/home/tilo/sp19; W9=$R/sa-rust-ids-work; L=$W9/sa-port-326; B=$L/bar
rm -rf $L/bar $L/bar-end.txt $L/env-raw.txt; mkdir -p $B
{ echo "built on pareto1 (bar.sh build phase, tested source $(cat $L/p1-source.txt)), copied"; cat $L/p1-build.txt; sha256sum $R/dev/sa-port-326/rust-spike/slice/sa_solver.so; } > $B/build.txt
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
NAN="convert:nan-no-specials convert:nan-atom-args convert:nan-one-level"; NEW="walk:rust both:rust $NAN"
export OUT=$B BASE=$W9/sa-port-317/bar/suite
export PLANTS="fm-atoms-drop-last fm-atoms-merge-pred fm-args-drop-last fm-implies-swap fm-not-drop ad-lra-class-is class-is ad-lra-atom-object fm-hand-no-give fm-hand-kept rows-product-verdict-flip atom-symbol-key-names term:mark-skips-native term:mark-wrong-pattern term:mark-leaves-entry fm-hand-per-entry nc-memo-true-false occ-walk-first sb-join-address sc-key-id-stale sc-key-id-weak sc-key-id-shared ent-method-first-self gm-guard-skip cl-view-nodes-drop $TL frames:rust $NEW"
export SUITE_PLANTS="zero fm-ite-swap same-is dispatch-keeps-memo fm-hand-instrument-by-name fm-hand-patched-direct $CPP $TL frames:rust $NEW"
export WLS="twin scope loop zero cert budget core f6 opaque rootof value wiring transfer:7:60 transfer2:3:40 cls"
export FM_WLS="f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls lra"
export FM_PLANTS="fm-atoms-merge-pred fm-args-drop-last"
export TESTS=all TESTS_SPLIT=1 DIRECT="relations_direct.py 300 0" N=6
bash $R/bar-sa-port-326.sh sa-port-326 port/may-be-nan tests suite live plants seed1 extra suiteplants fmrows sum > $L/bar.log 2>&1
echo "END $? $(date -u +%FT%TZ) $(sha256sum $R/dev/sa-port-326/rust-spike/slice/sa_solver.so | cut -c1-8) $(git -C $R/dev/sa-port-326 rev-parse --short HEAD)" > $L/bar-end.txt
wait
sort $L/env-raw.txt | uniq -c > $L/env-summary.txt
echo "WATCHER-END $(date -u +%FT%TZ)" >> $L/bar-end.txt
