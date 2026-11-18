#!/bin/bash
# job321.sh (sa-port-321, pareto1 under a --shared lease): copy 317's bench-46750d4 into this session's directory, apply
# the scratch count patch, build, run the plants, then one count run of dev and fuzz (+rust+frames). Nothing is written
# into 317's tree; its tools are mounted read-only. End marker: p1/job-end.txt.
G=~/sa-rust-ids-work/sa-port-321/p1; S=~/sa-rust-ids-work/sa-port-317/s1; B=$G/bench-count; O=$G/run-count
fin() { echo "END $1 $2 $(date -u +%FT%TZ)" > $G/job-end.txt; exit $2; }
rm -f $G/job-end.txt; rm -rf $B $O; mkdir -p $O
{ date -u; hostname; echo "lease ${MACHINE_LEASE_ID-} holder ${MACHINE_LEASE_HOLDER-}"; uptime; } > $O/host.txt 2>&1
cp -a $S/bench-46750d4 $B || fin copy 2
sha256sum $S/bench-46750d4/tree/rust-spike/slice/sa_solver.so $S/tools/qt195.py $G/tools/* > $O/sha-before.txt
(cd $B/tree && patch -p1 < $G/tools/count320.patch) > $O/patch.txt 2>&1 || fin patch 4
U="--user $(id -u):$(id -g)"
docker run --rm $U --network=none -v ~/.cargo:/rust/cargo -v ~/.rustup:/rust/rustup -v $B:/b -e HOME=/tmp sa-cy-build:1 sh -c '
  set -e
  export PATH=/rust/cargo/bin:$PATH CARGO_HOME=/rust/cargo RUSTUP_HOME=/rust/rustup PYO3_PYTHON=/usr/local/bin/python
  cd /b/tree/rust-spike/slice/solver_rs; rustc --version
  cargo build --release --locked --offline --target-dir /b/target 2>&1 | tail -2
  cp /b/target/release/libsa_solver.so ../sa_solver.so
  sha256sum ../sa_solver.so
' > $O/build.txt 2>&1 || fin build 5
RUN() { # RUN NAME COUNTFILE CMD...
  n=$1; c=$2; shift 2
  docker run --rm $U --network=none --read-only --tmpfs /tmp:rw,size=1g -e PYTHONDONTWRITEBYTECODE=1 -e SLICE_CONVERT=rust -e SLICE_TERM_FRAMES=rust \
    -e SA320_COUNT=/results/$c -v $B:/work:ro -v $O:/results -v $S/tools:/t:ro -v $G/tools:/m:ro sa-eval-bench:1 sh -c '
    mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench; T=/work/tree
    export SLICE_DIR=$T/rust-spike/slice SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONPATH=$T:/work/sympy:/tmp/shim
    { python -VV; sha256sum $SLICE_DIR/sa_solver.so /t/qt195.py; cat /work/SHA; echo "SLICE_CONVERT=$SLICE_CONVERT SLICE_TERM_FRAMES=$SLICE_TERM_FRAMES SA320_COUNT=$SA320_COUNT"; } > /results/env-'$n'.txt 2>&1
    "$@"' sh "$@"
}
RUN plant plant.cnt python -B /m/plant320.py /results/plant.cnt > $O/plant.txt 2>&1; echo "plant rc=$?" >> $O/progress
for wl in dev fuzz; do
  RUN $wl $wl.cnt python /t/qt195.py $wl rust time /results/$wl-rust-time > $O/$wl-rust-time.json 2> $O/$wl-rust-time.err
  echo "$wl rc=$? $(date -u +%T)" >> $O/progress
done
fin done 0
