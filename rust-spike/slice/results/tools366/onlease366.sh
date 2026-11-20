#!/bin/bash
# onlease366.sh NEW BASE (sa-port-366; tools359/onlease359.sh with this step's arms): on pareto1 under ONE quiet lease:
# bytecode of both staged trees compiled in sa-eval-bench:1 (the arms run with PYTHONDONTWRITEBYTECODE=1 on a read-only
# mount), then two bench-container invocations on CPU 2 with sa-eval-bench:1 running time366.sh, 12 rounds each:
# timing-s1 (dev and fuzz) and timing-bw (budget and wiring), each with 12 arms: BASE and NEW, each py on32 (the package
# alone, a control: it runs no convert.py), cpy off and on32 (the slice with SLICE_CONVERT=py SLICE_TERM_FRAMES=rust)
# and rust off, on32 and nat (SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust; nat adds SLICE_WITNESS_RUST=1). Load logged
# alongside. End marker: s1/end.txt, written by the last line of this script.
NEW=$1; BASE=$2; B=~/sa-rust-ids-work/sa-port-366/s1
[ -e $B/timing-s1 ] && { echo "results exist"; exit 3; }
docker run --rm --user $(id -u):$(id -g) --network=none -v $B:/b sa-eval-bench:1 sh -c "cd /b && python -m compileall -q bench-$NEW/tree/satassume bench-$NEW/tree/rust-spike/slice bench-$BASE/tree/satassume bench-$BASE/tree/rust-spike/slice common/evalbench tools/qt342.py tools/wn359.py > /dev/null; echo compiled rc=\$?" > $B/compile.txt 2>&1
ARMS=""; for a in py-on32 cpy-off cpy-on32 rust-off rust-on32 rust-nat; do ARMS="$ARMS $BASE:$a $NEW:$a"; done; ARMS="${ARMS# }"
rc=0
for run in "s1 dev fuzz" "bw budget wiring"; do
  set -- $run; R=$B/timing-$1; shift; mkdir -p $R
  { date -u; echo "lease $MACHINE_LEASE_ID holder $MACHINE_LEASE_HOLDER"; hostname; lscpu | grep 'Model name'; docker image inspect --format '{{.Id}}' sa-eval-bench:1; cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor; uptime; top -bn1 | sed -n 7,15p | cut -c1-110; } > $R/host-before.txt 2>&1
  ( while :; do echo "$(date -u +%T) $(cut -d' ' -f1-4 /proc/loadavg)"; sleep 30; done ) > $R/load.txt &
  L=$!
  BENCH_CPU=2 BENCH_RESULTS_DIR=$R BENCH_WAIT_SECONDS=60 ~/bin/bench-container run sa-eval-bench:1 $B -- env ARMS="$ARMS" ROUNDS="1 2 3 4 5 6 7 8 9 10 11 12" WLS="$*" timeout -s KILL 150m sh /work/tools/time366.sh > $R/container.out 2>&1
  r=$?; [ $r -ne 0 ] && rc=$r
  kill $L
  { date -u; echo "rc=$r"; uptime; top -bn1 | sed -n 7,12p | cut -c1-110; } > $R/host-after.txt
done
echo "END rc=$rc $(date -u +%FT%TZ)" > $B/end.txt
exit $rc
