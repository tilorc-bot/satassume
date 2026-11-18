#!/bin/bash
# prof316.sh (sa-port-316, pareto1, under one quiet lease): pysampler runs of the staged 5b1d96f bench tree (source-equal
# to rust-slice 5f53735) with SLICE_CONVERT=rust, frames on (+rust+frames) and off (+rust). Reads sa-port-314's staged
# tree and tools read-only; writes only under sa-port-316/prof. End marker: prof/end.txt, written by the last line here.
B=~/sa-rust-ids-work/sa-port-314/s1; O0=~/sa-rust-ids-work/sa-port-316/prof
J=""; for i in $(seq 0 29); do J="$J dev:rust:pysample3:$i"; done; for i in $(seq 0 5); do J="$J fuzz:rust:pysample3:$i"; done
U="--user $(id -u):$(id -g)"; rc=0
for s in 5b1d96f+rust+frames 5b1d96f+rust; do
  O=$O0/run-$s; mkdir -p $O; fr=py; case $s in *+frames*) fr=rust;; esac
  { date -u; echo "lease $MACHINE_LEASE_ID"; echo "SLICE_CONVERT=rust SLICE_TERM_FRAMES=$fr"; uptime; } > $O/host.txt
  docker run --rm $U --network=none --cpuset-cpus 2 --cpus 1 --read-only --tmpfs /tmp:rw,size=1g -e PYTHONDONTWRITEBYTECODE=1 -e SLICE_CONVERT=rust -e SLICE_TERM_FRAMES=$fr \
    -v $B/bench-5b1d96f:/work:ro -v $O:/results -v $B/tools:/t:ro sa-eval-bench:1 sh /t/pys.sh $J > $O/container.out 2>&1
  r2=$?; echo "rc=$r2 $(date -u)" >> $O/host.txt; [ $r2 = 0 ] || rc=$r2
done
echo "END rc=$rc $(date -u +%FT%TZ)" > $O0/end.txt
exit $rc
