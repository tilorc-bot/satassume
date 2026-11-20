#!/bin/bash
# onlease367p.sh SHA NAME (sa-port-367; tools356/onlease356p.sh with the default path as the second arm): on pareto1 under ONE
# quiet lease. Bytecode of the staged bench-SHA compiled in sa-eval-bench:1; then (1) pinned wall time: one
# bench-container invocation on CPU 2, 5 rounds of dev, fuzz, budget and wiring, arms rust-nat and default (no SLICE_ switch) alternating
# (pys367.sh time/dtime); (2) the sampler and cProfile rows, docker pinned to CPU 2 --cpus 1 on the same lease: two
# interleaved passes of dpysample3 and pysample3 (per path: dev and budget 30 runs, fuzz 6, wiring 8) and one cprof pass
# per workload and path, plus mods367.py per workload.
# Load logged alongside. End marker: s1/NAME-end.txt, the last line here.
SHA=$1; NAME=$2; B=~/sa-rust-ids-work/sa-port-367/s1; W=$B/bench-$SHA; R=$B/$NAME
[ -e $R ] && { echo "results exist"; exit 3; }
mkdir -p $R/time $R/run; U="--user $(id -u):$(id -g)"
docker run --rm $U --network=none -v $W:/b sa-eval-bench:1 sh -c "cd /b && python -m compileall -q tree/satassume tree/rust-spike/slice evalbench tools > /dev/null; echo compiled rc=\$?" > $R/compile.txt 2>&1
{ date -u; echo "lease $MACHINE_LEASE_ID holder $MACHINE_LEASE_HOLDER"; hostname; lscpu | grep 'Model name'; docker image inspect --format '{{.Id}}' sa-eval-bench:1; cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor; uptime; top -bn1 | sed -n 7,15p | cut -c1-110; } > $R/host.txt 2>&1
( while :; do echo "$(date -u +%T) $(cut -d' ' -f1-4 /proc/loadavg)"; sleep 30; done ) > $R/load.txt &
L=$!
J0=""; for r in 1 2 3 4 5; do for wl in dev fuzz budget wiring; do J0="$J0 $wl:time:$r $wl:dtime:$r"; done; done
BENCH_CPU=2 BENCH_RESULTS_DIR=$R/time BENCH_WAIT_SECONDS=60 ~/bin/bench-container run sa-eval-bench:1 $W -- timeout -s KILL 60m sh /work/tools/pys367.sh $J0 > $R/container-time.out 2>&1
rc=$?; echo "timing rc=$rc $(date -u +%T)" >> $R/progress-host
J1=""; for i in $(seq 0 14); do J1="$J1 dev:dpysample3:$i dev:pysample3:$i budget:dpysample3:$i budget:pysample3:$i"; done; for i in 0 1 2; do J1="$J1 fuzz:dpysample3:$i fuzz:pysample3:$i"; done; for i in 0 1 2 3; do J1="$J1 wiring:dpysample3:$i wiring:pysample3:$i"; done
J2=""; for i in $(seq 15 29); do J2="$J2 dev:dpysample3:$i dev:pysample3:$i budget:dpysample3:$i budget:pysample3:$i"; done; for i in 3 4 5; do J2="$J2 fuzz:dpysample3:$i fuzz:pysample3:$i"; done; for i in 4 5 6 7; do J2="$J2 wiring:dpysample3:$i wiring:pysample3:$i"; done
for wl in dev fuzz budget wiring; do J2="$J2 $wl:cprof:0 $wl:dcprof:0 $wl:dmods:0"; done
for JOBS in "$J1" "$J2"; do
  docker run --rm $U --network=none --cpuset-cpus 2 --cpus 1 --read-only --tmpfs /tmp:rw,size=1g -v $W:/work:ro -v $R/run:/results sa-eval-bench:1 timeout -s KILL 90m sh /work/tools/pys367.sh $JOBS >> $R/container-run.out 2>&1
  r2=$?; echo "pys rc=$r2 $(date -u +%T)" >> $R/progress-host; [ $r2 = 0 ] || rc=$r2
done
kill $L
{ date -u; echo "rc=$rc"; uptime; } > $R/host-after.txt
echo "END rc=$rc $(date -u +%FT%TZ)" > $B/$NAME-end.txt
exit $rc
