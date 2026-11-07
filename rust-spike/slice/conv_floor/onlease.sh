#!/bin/bash
# onlease.sh RUNSCRIPT NAME: on pareto1 under the quiet lease. One bench-container invocation on S's CPU and image, load logged.
B=~/sa-rust-ids-work/sa-port-78/bench
R=$B/results/$2; [ -e $R ] && { echo "results exist"; exit 3; }; mkdir -p $R
{ date -u; echo "lease $MACHINE_LEASE_ID holder $MACHINE_LEASE_HOLDER"; docker image inspect --format '{{.Id}}' sa-eval-bench:1; cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor; uptime; top -bn1 | sed -n 7,12p | cut -c1-110; } > $R/host-before.txt
( while :; do echo "$(date -u +%T) $(cut -d' ' -f1-4 /proc/loadavg)"; sleep 30; done ) > $R/load.txt &
L=$!
BENCH_CPU=2 BENCH_RESULTS_DIR=$R BENCH_WAIT_SECONDS=60 ~/bin/bench-container run sa-eval-bench:1 $B -- timeout -s KILL 27m sh /work/tools/$1 > $R/container.out 2>&1
rc=$?
kill $L
{ date -u; echo "bench-container rc=$rc"; uptime; top -bn1 | sed -n 7,12p | cut -c1-110; } > $R/host-after.txt
exit $rc
