#!/bin/bash
# onlease327.sh TAG (sa-port-327, from sa-port-301's onlease301.sh): on pareto1 under ONE quiet lease. (1) pinned timing: one
# bench-container invocation on CPU 2 with sa-eval-bench:1, TREES (arms) interleaved and rotated per round (time327.sh);
# (2) pysampler runs for each of PTREES (pys.sh), docker pinned to CPU 2 --cpus 1, same lease. Load logged alongside.
# End marker: s1/timing-TAG/end.txt, written by the last `echo "END` line.
B=~/sa-rust-ids-work/sa-port-327/s1
R=$B/timing-$1; [ -e $R ] && { echo "results exist"; exit 3; }; mkdir -p $R
{ date -u; echo "lease $MACHINE_LEASE_ID holder $MACHINE_LEASE_HOLDER"; hostname; lscpu | grep 'Model name'; docker image inspect --format '{{.Id}}' sa-eval-bench:1; cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor; uptime; top -bn1 | sed -n 7,15p | cut -c1-110; } > $R/host-before.txt 2>&1
( while :; do echo "$(date -u +%T) $(cut -d' ' -f1-4 /proc/loadavg)"; sleep 30; done ) > $R/load.txt &
L=$!
BENCH_CPU=2 BENCH_RESULTS_DIR=$R BENCH_WAIT_SECONDS=60 ~/bin/bench-container run sa-eval-bench:1 $B -- env TREES="$TREES" ROUNDS="$ROUNDS" WLS="$WLS" timeout -s KILL 120m sh /work/tools/time327.sh > $R/container.out 2>&1
rc=$?
echo "timing rc=$rc $(date -u +%T)" >> $R/progress-host
# 317: the sampler runs are interleaved too: two passes over PTREES (dev rounds 0-14 and fuzz 0-2, then dev 15-29 and fuzz 3-5),
# so each arm's 30 dev and 6 fuzz runs straddle the others'.
J1=""; for i in $(seq 0 14); do J1="$J1 dev:rust:pysample3:$i"; done; for i in 0 1 2; do J1="$J1 fuzz:rust:pysample3:$i"; done
J2=""; for i in $(seq 15 29); do J2="$J2 dev:rust:pysample3:$i"; done; for i in 3 4 5; do J2="$J2 fuzz:rust:pysample3:$i"; done
U="--user $(id -u):$(id -g)"
for pass in 1 2; do [ $pass = 1 ] && JOBS=$J1 || JOBS=$J2
for s in $PTREES; do
  O=$B/run-$s; mkdir -p $O; cv=py; fr=py; case $s in *+rust*) cv=rust;; esac; case $s in *+frames*) fr=rust;; esac
  { date -u; echo "pass $pass lease $MACHINE_LEASE_ID"; echo "SLICE_CONVERT=$cv SLICE_TERM_FRAMES=$fr"; uptime; } >> $O/host.txt
  docker run --rm $U --network=none --cpuset-cpus 2 --cpus 1 --read-only --tmpfs /tmp:rw,size=1g -e PYTHONDONTWRITEBYTECODE=1 -e SLICE_CONVERT=$cv -e SLICE_TERM_FRAMES=$fr \
    -v $B/bench-${s%%+*}:/work:ro -v $O:/results -v $B/tools:/t:ro sa-eval-bench:1 sh /t/pys.sh $JOBS >> $O/container.out 2>&1
  r2=$?; echo "rc=$r2 $(date -u)" >> $O/host.txt; echo "pys $s pass $pass rc=$r2 $(date -u +%T)" >> $R/progress-host
  [ $r2 = 0 ] || rc=$r2
done; done
kill $L
{ date -u; echo "rc=$rc"; uptime; top -bn1 | sed -n 7,12p | cut -c1-110; } > $R/host-after.txt
echo "END rc=$rc $(date -u +%FT%TZ)" > $R/end.txt
exit $rc
