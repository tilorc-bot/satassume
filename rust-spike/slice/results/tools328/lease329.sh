#!/bin/bash
# lease329.sh TAG (sa-port-329, from onlease328.sh): on pareto1 under ONE quiet lease: one bench-container invocation on
# CPU 2 with sa-eval-bench:1 running time329.sh. End marker: s1/timing-TAG/end.txt, the last echo of this script.
B=~/sa-rust-ids-work/sa-port-329/s1
R=$B/timing-$1; [ -e $R ] && { echo "results exist"; exit 3; }; mkdir -p $R
{ date -u; echo "lease $MACHINE_LEASE_ID holder $MACHINE_LEASE_HOLDER"; hostname; cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor; uptime; top -bn1 | sed -n 7,12p | cut -c1-110; } > $R/host-before.txt 2>&1
( while :; do echo "$(date -u +%T) $(cut -d' ' -f1-4 /proc/loadavg)"; sleep 15; done ) > $R/load.txt &
L=$!
BENCH_CPU=2 BENCH_RESULTS_DIR=$R BENCH_WAIT_SECONDS=60 ~/bin/bench-container run sa-eval-bench:1 $B -- env SHA="$SHA" ARMS="$ARMS" ROUNDS="$ROUNDS" WLS="$WLS" timeout -s KILL 30m sh /work/tools/time329.sh > $R/container.out 2>&1
rc=$?
kill $L
{ date -u; echo "rc=$rc"; uptime; } > $R/host-after.txt
echo "END rc=$rc $(date -u +%FT%TZ)" > $R/end.txt
exit $rc
