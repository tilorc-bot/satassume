#!/bin/bash
# onlease328.sh TAG (sa-port-328, from sa-port-317's onlease317.sh): on pareto1 under ONE quiet lease: one bench-container
# invocation on CPU 2 with sa-eval-bench:1 running time328.sh. Load logged alongside.
# End marker: s1/timing-TAG/end.txt, written by the last `echo "END` line of this script.
B=~/sa-rust-ids-work/sa-port-328/s1
R=$B/timing-$1; [ -e $R ] && { echo "results exist"; exit 3; }; mkdir -p $R
{ date -u; echo "lease $MACHINE_LEASE_ID holder $MACHINE_LEASE_HOLDER"; hostname; lscpu | grep 'Model name'; docker image inspect --format '{{.Id}}' sa-eval-bench:1; cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor; uptime; top -bn1 | sed -n 7,15p | cut -c1-110; } > $R/host-before.txt 2>&1
( while :; do echo "$(date -u +%T) $(cut -d' ' -f1-4 /proc/loadavg)"; sleep 30; done ) > $R/load.txt &
L=$!
BENCH_CPU=2 BENCH_RESULTS_DIR=$R BENCH_WAIT_SECONDS=60 ~/bin/bench-container run sa-eval-bench:1 $B -- env SHA="$SHA" ARMS="$ARMS" ROUNDS="$ROUNDS" WLS="$WLS" timeout -s KILL 120m sh /work/tools/time328.sh > $R/container.out 2>&1
rc=$?
kill $L
{ date -u; echo "rc=$rc"; uptime; top -bn1 | sed -n 7,12p | cut -c1-110; } > $R/host-after.txt
echo "END rc=$rc $(date -u +%FT%TZ)" > $R/end.txt
exit $rc
