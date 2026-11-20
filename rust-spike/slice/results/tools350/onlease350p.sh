#!/bin/bash
# onlease350p.sh SHA NAME WL... (sa-port-350; tools347/onlease347.sh for the profile): on pareto1 under ONE quiet lease: bytecode
# of the staged tree compiled in sa-eval-bench:1, then one bench-container invocation on CPU 2 running prof350.sh,
# 5 rounds on the workloads named, results in s1/NAME. Load logged alongside. End marker: s1/NAME-end.txt, the last
# line here.
SHA=$1; NAME=$2; shift 2; B=~/sa-rust-ids-work/sa-port-350/s1; R=$B/$NAME
[ -e $R ] && { echo "results exist"; exit 3; }
mkdir -p $R
docker run --rm --user $(id -u):$(id -g) --network=none -v $B:/b sa-eval-bench:1 sh -c "cd /b && python -m compileall -q bench-$SHA/tree/satassume bench-$SHA/tree/rust-spike/slice common/evalbench tools" > $B/compile.txt 2>&1
{ date -u; echo "lease $MACHINE_LEASE_ID holder $MACHINE_LEASE_HOLDER"; hostname; lscpu | grep 'Model name'; docker image inspect --format '{{.Id}}' sa-eval-bench:1; cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor; uptime; top -bn1 | sed -n 7,15p | cut -c1-110; } > $R/host.txt 2>&1
( while :; do echo "$(date -u +%T) $(cut -d' ' -f1-4 /proc/loadavg)"; sleep 30; done ) > $R/load.txt &
L=$!
BENCH_CPU=2 BENCH_RESULTS_DIR=$R BENCH_WAIT_SECONDS=60 ~/bin/bench-container run sa-eval-bench:1 $B -- env SHA=$SHA ROUNDS="1 2 3 4 5" WLS="$*" timeout -s KILL 60m sh /work/tools/prof350.sh > $R/container.out 2>&1
rc=$?
kill $L
{ date -u; echo "rc=$rc"; uptime; } > $R/host-after.txt
echo "END rc=$rc $(date -u +%FT%TZ)" > $B/$NAME-end.txt
exit $rc
