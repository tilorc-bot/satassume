#!/bin/bash
# onlease342.sh NEW BASE (sa-port-342; tools336/onlease336.sh for two trees and two invocations): on pareto1 under ONE
# quiet lease: bytecode of both staged trees compiled in sa-eval-bench:1 (the arms run with PYTHONDONTWRITEBYTECODE=1 on
# a read-only mount), then two bench-container invocations on CPU 2 with sa-eval-bench:1 running time342.sh, 12 rounds
# each: timing-s1 (dev and fuzz; py and rust; off and on32; both trees: 8 arms) and timing-bw (budget and wiring, the
# same 8 arms). Load logged alongside. End marker: s1/end.txt, written by the last line of this script.
NEW=$1; BASE=$2; B=~/sa-rust-ids-work/sa-port-342/s1
[ -e $B/timing-s1 ] && { echo "results exist"; exit 3; }
docker run --rm --user $(id -u):$(id -g) --network=none -v $B:/b sa-eval-bench:1 sh -c "cd /b && python -m compileall -q bench-$NEW/tree/satassume bench-$NEW/tree/rust-spike/slice bench-$BASE/tree/satassume bench-$BASE/tree/rust-spike/slice common/evalbench tools/qt342.py tools/wit328.py > /dev/null; echo compiled rc=\$?" > $B/compile.txt 2>&1
ARMS=""; for s in $BASE $NEW; do for a in py-off py-on32 rust-off rust-on32; do ARMS="$ARMS $s:$a"; done; done; ARMS=${ARMS# }
rc=0
for run in "s1 1 dev fuzz" "bw 0 budget wiring"; do
  set -- $run; R=$B/timing-$1; WIT=$2; shift 2; mkdir -p $R
  { date -u; echo "lease $MACHINE_LEASE_ID holder $MACHINE_LEASE_HOLDER"; hostname; lscpu | grep 'Model name'; docker image inspect --format '{{.Id}}' sa-eval-bench:1; cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor; uptime; top -bn1 | sed -n 7,15p | cut -c1-110; } > $R/host-before.txt 2>&1
  ( while :; do echo "$(date -u +%T) $(cut -d' ' -f1-4 /proc/loadavg)"; sleep 30; done ) > $R/load.txt &
  L=$!
  BENCH_CPU=2 BENCH_RESULTS_DIR=$R BENCH_WAIT_SECONDS=60 ~/bin/bench-container run sa-eval-bench:1 $B -- env ARMS="$ARMS" ROUNDS="1 2 3 4 5 6 7 8 9 10 11 12" WLS="$*" WIT=$WIT timeout -s KILL 120m sh /work/tools/time342.sh > $R/container.out 2>&1
  r=$?; [ $r -ne 0 ] && rc=$r
  kill $L
  { date -u; echo "rc=$r"; uptime; top -bn1 | sed -n 7,12p | cut -c1-110; } > $R/host-after.txt
done
echo "END rc=$rc $(date -u +%FT%TZ)" > $B/end.txt
exit $rc
