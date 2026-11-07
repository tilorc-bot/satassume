#!/bin/bash
# onlease80.sh NAME: on pareto1 under the quiet lease. One bench-container invocation on S's CPU and image, load logged.
B=~/sa-rust-ids-work/sa-port-80/bench
R=$B/results/$1; [ -e $R ] && { echo "results exist"; exit 3; }; mkdir -p $R
{ date -u; echo "lease $MACHINE_LEASE_ID holder $MACHINE_LEASE_HOLDER"; docker image inspect --format '{{.Id}}' sa-eval-bench:1; uptime; } > $R/host-before.txt 2>&1
( while :; do echo "$(date -u +%T) $(cut -d' ' -f1-4 /proc/loadavg)"; sleep 30; done ) > $R/load.txt &
L=$!
BENCH_CPU=2 BENCH_RESULTS_DIR=$R BENCH_WAIT_SECONDS=60 ~/bin/bench-container run sa-eval-bench:1 $B -- timeout -s KILL 27m sh /work/tools/run_floor.sh > $R/container.out 2>&1
rc=$?
kill $L
{ date -u; echo "bench-container rc=$rc"; uptime; top -bn1 | sed -n 7,12p | cut -c1-110; } > $R/host-after.txt
exit $rc
