#!/bin/bash
# build327.sh SHA (sa-port-327, the build half of sa-port-313's job313.sh): on pareto1 --shared. Builds s1/bench-SHA's
# sa_solver.so in sa-cy-build:1, its nm table and pysampler.so, compiles bytecode. DONE-BUILD in s1/run-SHA at the end.
SHA=$1; G=~/sa-rust-ids-work/sa-port-327/s1; B=$G/bench-$SHA; T=$G/tools; O=$G/run-$SHA
[ -d $B/tree ] || { echo "no $B/tree"; exit 2; }
mkdir -p $O; U="--user $(id -u):$(id -g)"
docker run --rm $U --network=none -v ~/.cargo:/rust/cargo -v ~/.rustup:/rust/rustup -v $B:/b -v $T:/t -v $O:/o -e HOME=/tmp sa-cy-build:1 sh -c '
  set -e
  export PATH=/rust/cargo/bin:$PATH CARGO_HOME=/rust/cargo RUSTUP_HOME=/rust/rustup PYO3_PYTHON=/usr/local/bin/python
  cd /b/tree/rust-spike/slice/solver_rs; rustc --version
  cargo build --release --locked --offline --target-dir /b/target 2>&1 | tail -2
  cp /b/target/release/libsa_solver.so ../sa_solver.so
  nm -n -S ../sa_solver.so > /o/sa_solver.so.nm; wc -l /o/sa_solver.so.nm; sha256sum ../sa_solver.so
  [ -e /t/pysampler.so ] || gcc -O2 -shared -fPIC -I/usr/local/include/python3.12 -o /t/pysampler.so /t/pysampler.c
' > $O/build.txt 2>&1 || { echo "build failed $SHA"; exit 4; }
docker run --rm $U --network=none -v $B:/b -v $T:/t sa-eval-bench:1 sh -c 'cd /b && python -m compileall -q tree/satassume tree/rust-spike/slice evalbench /t/qt195.py > /dev/null; echo compiled rc=$?' >> $O/build.txt 2>&1
echo "BUILT $(date -u +%FT%TZ)" > $O/DONE-BUILD
