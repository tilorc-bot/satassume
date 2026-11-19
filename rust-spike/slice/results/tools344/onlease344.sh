#!/bin/bash
# onlease344.sh NEW BASE (sa-port-344; the last part of tools343/onlease343.sh alone): on pareto1 under ONE quiet lease,
# one bench-container invocation on CPU 2 with sa-eval-bench:1 running pc344.sh: the per-call rows of the witness check
# on budget and wiring, both staged trees, py and rust, 3 cold passes each. B = pareto1 ~/sa-rust-ids-work/sa-port-344/s1
# holds copies (cp -a, bytecode included) of sa-port-343's staged common/ and bench-SHA/. Load logged alongside.
# End marker: s1/end.txt, the last line here.
NEW=$1; BASE=$2; B=~/sa-rust-ids-work/sa-port-344/s1
R=$B/timing-pc; [ -e $R ] && { echo "results exist"; exit 3; }
mkdir -p $R
{ date -u; echo "lease $MACHINE_LEASE_ID holder $MACHINE_LEASE_HOLDER"; hostname; lscpu | grep 'Model name'; docker image inspect --format '{{.Id}}' sa-eval-bench:1; cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor; uptime; top -bn1 | sed -n 7,15p | cut -c1-110; sha256sum $B/bench-*/tree/rust-spike/slice/sa_solver.so $B/bench-*/tree/satassume/witness.py $B/tools/pc344.py; } > $R/host-before.txt 2>&1
( while :; do echo "$(date -u +%T) $(cut -d' ' -f1-4 /proc/loadavg)"; sleep 30; done ) > $R/load.txt &
L=$!
BENCH_CPU=2 BENCH_RESULTS_DIR=$R BENCH_WAIT_SECONDS=60 ~/bin/bench-container run sa-eval-bench:1 $B -- env SHAS="$BASE $NEW" ROUNDS="1 2 3" WLS="budget wiring" timeout -s KILL 30m sh /work/tools/pc344.sh > $R/container.out 2>&1
rc=$?
kill $L
{ date -u; echo "rc=$rc"; uptime; top -bn1 | sed -n 7,12p | cut -c1-110; } > $R/host-after.txt
echo "END rc=$rc $(date -u +%FT%TZ)" > $B/end.txt
exit $rc
