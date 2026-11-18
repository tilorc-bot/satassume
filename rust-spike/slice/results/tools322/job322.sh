#!/bin/bash
# job322.sh [STEPS] (sa-port-322, pareto1 under a --shared lease; from sa-port-321's job321.sh). STEPS default "stage build
# plant count bb". stage: this session's own copies of 317's bench-5b1d96f (source-equal to rust-slice 5f53735): p1/bench-5b1d96f
# untouched (the S1 arm), p1/bench-count with 317's bench-46750d4 target dir (incremental build) and the scratch count
# patch applied. Nothing is written into 317's tree. count: one nc322.py pass of dev and fuzz, both switches on, and one
# with both off. bb: the same pass with BRANCH_BUDGET 32 and 64 (answers recorded, not adopted). End marker: p1/job-end.txt.
# sa-port-323: OUT, TOOLS and ENDF move the outputs, the mounted tools and the end marker to the caller's own directory;
# SLICE_SESSION_PLANT is passed through to the run (the catch and fallback plant needs it at process start).
G=~/sa-rust-ids-work/sa-port-322/p1; S=~/sa-rust-ids-work/sa-port-317/s1; B=$G/bench-count; O=${OUT:-$G/run-count}
M=${TOOLS:-$G/tools}; E=${ENDF:-$G/job-end.txt}
STEPS=${1:-"stage build plant count bb"}
fin() { echo "END $1 $2 $(date -u +%FT%TZ)" > $E; exit $2; }
has() { case " $STEPS " in *" $1 "*) return 0;; esac; return 1; }
rm -f $E; mkdir -p $O
{ date -u; hostname; echo "lease ${MACHINE_LEASE_ID-} holder ${MACHINE_LEASE_HOLDER-} steps $STEPS"; uptime; } >> $O/host.txt 2>&1
U="--user $(id -u):$(id -g)"
if has stage; then
  rm -rf $B
  [ -e $G/bench-5b1d96f ] || cp -a $S/bench-5b1d96f $G/bench-5b1d96f || fin copy 2
  cp -a $G/bench-5b1d96f $B && cp -a $S/bench-46750d4/target $B/target || fin copy2 2
  sha256sum $S/bench-5b1d96f/tree/rust-spike/slice/sa_solver.so $G/bench-5b1d96f/tree/rust-spike/slice/sa_solver.so $S/tools/qt195.py $G/tools/* > $O/sha-before.txt
  (cd $B/tree && patch -p1 < $G/tools/count322.patch) > $O/patch.txt 2>&1 || fin patch 4
fi
if has build; then
  docker run --rm $U --network=none -v ~/.cargo:/rust/cargo -v ~/.rustup:/rust/rustup -v $B:/b -e HOME=/tmp sa-cy-build:1 sh -c '
    set -e
    export PATH=/rust/cargo/bin:$PATH CARGO_HOME=/rust/cargo RUSTUP_HOME=/rust/rustup PYO3_PYTHON=/usr/local/bin/python
    cd /b/tree/rust-spike/slice/solver_rs; rustc --version
    cargo build --release --locked --offline --target-dir /b/target 2>&1 | tail -40
    cp /b/target/release/libsa_solver.so ../sa_solver.so
    sha256sum ../sa_solver.so
  ' > $O/build.txt 2>&1 || fin build 5
fi
RUN() { # RUN NAME CONVERT FRAMES CMD...
  n=$1; cv=$2; fr=$3; shift 3
  docker run --rm $U --network=none --read-only --tmpfs /tmp:rw,size=1g -e PYTHONDONTWRITEBYTECODE=1 -e SLICE_CONVERT=$cv -e SLICE_TERM_FRAMES=$fr -e SLICE_SESSION_PLANT=${SLICE_SESSION_PLANT-} \
    -v $B:/work:ro -v $O:/results -v $M:/m:ro sa-eval-bench:1 sh -c '
    mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench; T=/work/tree
    export SLICE_DIR=$T/rust-spike/slice SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONPATH=$T:/work/sympy:/tmp/shim
    { python -VV; sha256sum $SLICE_DIR/sa_solver.so /m/nc322.py; cat /work/SHA; echo "SLICE_CONVERT=$SLICE_CONVERT SLICE_TERM_FRAMES=$SLICE_TERM_FRAMES"; } > /results/env-'$n'.txt 2>&1
    "$@"' sh "$@"
}
if has plant; then
  RUN plant rust rust python -B /m/plant322.py > $O/plant${SLICE_SESSION_PLANT:+-$SLICE_SESSION_PLANT}.txt 2>&1; echo "plant rc=$? $(date -u +%T)" >> $O/progress
fi
if has count; then
  for wl in dev fuzz; do
    RUN $wl rust rust python /m/nc322.py $wl /results/$wl.jsonl > $O/$wl.out 2> $O/$wl.err; echo "$wl rc=$? $(date -u +%T)" >> $O/progress
    RUN $wl-py py py python /m/nc322.py $wl /results/$wl-py.jsonl > $O/$wl-py.out 2> $O/$wl-py.err; echo "$wl-py rc=$? $(date -u +%T)" >> $O/progress
  done
fi
if has bb; then
  for bb in ${BBS:-32 64}; do for wl in dev fuzz; do
    RUN $wl-bb$bb rust rust python /m/nc322.py $wl /results/$wl-bb$bb.jsonl $bb > $O/$wl-bb$bb.out 2> $O/$wl-bb$bb.err; echo "$wl-bb$bb rc=$? $(date -u +%T)" >> $O/progress
  done; done
fi
fin done 0
