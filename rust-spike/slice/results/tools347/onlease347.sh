#!/bin/bash
# onlease347.sh NEW BASE (sa-port-347; tools343/onlease343.sh with time347.sh's arms, no per-call pass): on pareto1 under
# ONE quiet lease: bytecode of both staged trees compiled in sa-eval-bench:1 (the arms run with
# PYTHONDONTWRITEBYTECODE=1 on a read-only mount), then two bench-container invocations on CPU 2 with sa-eval-bench:1
# running time347.sh, 12 rounds each: timing-s1 (dev and fuzz) and timing-bw (budget and wiring), each with 12 arms:
# BASE py and rust, off and on32; NEW py and rust, off, on32, cf (SLICE_WITNESS_PLANT=check-first) and w8400
# (SLICE_WITNESS_WORK=8400). Load logged alongside. End marker: s1/end.txt, written by the last line of this script.
NEW=$1; BASE=$2; B=~/sa-rust-ids-work/sa-port-347/s1
[ -e $B/timing-s1 ] && { echo "results exist"; exit 3; }
docker run --rm --user $(id -u):$(id -g) --network=none -v $B:/b sa-eval-bench:1 sh -c "cd /b && python -m compileall -q bench-$NEW/tree/satassume bench-$NEW/tree/rust-spike/slice bench-$BASE/tree/satassume bench-$BASE/tree/rust-spike/slice common/evalbench tools/qt342.py tools/wit328.py tools/arm347.py > /dev/null; echo compiled rc=\$?" > $B/compile.txt 2>&1
ARMS=""; for m in py rust; do for a in off on32; do ARMS="$ARMS $BASE:$m-$a"; done; for a in off on32 cf w8400; do ARMS="$ARMS $NEW:$m-$a"; done; done; ARMS=${ARMS# }
rc=0
for run in "s1 1 dev fuzz" "bw 0 budget wiring"; do
  set -- $run; R=$B/timing-$1; WIT=$2; shift 2; mkdir -p $R
  { date -u; echo "lease $MACHINE_LEASE_ID holder $MACHINE_LEASE_HOLDER"; hostname; lscpu | grep 'Model name'; docker image inspect --format '{{.Id}}' sa-eval-bench:1; cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor; uptime; top -bn1 | sed -n 7,15p | cut -c1-110; } > $R/host-before.txt 2>&1
  ( while :; do echo "$(date -u +%T) $(cut -d' ' -f1-4 /proc/loadavg)"; sleep 30; done ) > $R/load.txt &
  L=$!
  BENCH_CPU=2 BENCH_RESULTS_DIR=$R BENCH_WAIT_SECONDS=60 ~/bin/bench-container run sa-eval-bench:1 $B -- env ARMS="$ARMS" ROUNDS="1 2 3 4 5 6 7 8 9 10 11 12" WLS="$*" WIT=$WIT timeout -s KILL 150m sh /work/tools/time347.sh > $R/container.out 2>&1
  r=$?; [ $r -ne 0 ] && rc=$r
  kill $L
  { date -u; echo "rc=$r"; uptime; top -bn1 | sed -n 7,12p | cut -c1-110; } > $R/host-after.txt
done
echo "END rc=$rc $(date -u +%FT%TZ)" > $B/end.txt
exit $rc
