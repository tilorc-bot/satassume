#!/bin/bash
# prep80.sh: on pareto1, under a shared lease. A bench dir from sa-port-78's, the prototype's tree built in the bench image family, bytecode compiled.
set -e
A=~/sa-rust-ids-work/sa-port-78/bench; B=~/sa-rust-ids-work/sa-port-80/bench
mkdir -p $B/results $B/tools
for d in base sympy data evalbench SHA; do [ -e $B/$d ] || cp -a $A/$d $B/$d; done
cp -a $A/tools/qt76.py $B/tools/
cd $B
U="--user $(id -u):$(id -g)"
docker run --rm $U --network=none -v ~/.cargo:/rust/cargo -v ~/.rustup:/rust/rustup -v $B:/b -e HOME=/tmp sa-cy-build:1 sh -c '
  export PATH=/rust/cargo/bin:$PATH CARGO_HOME=/rust/cargo RUSTUP_HOME=/rust/rustup PYO3_PYTHON=/usr/local/bin/python
  cd /b/tree/rust-spike/slice/solver_rs; rustc --version
  cargo build --release --locked --offline --target-dir /b/target 2>&1 | tail -2
  cp /b/target/release/libsa_solver.so ../sa_solver.so; sha256sum ../sa_solver.so
' 2>&1 | tee $B/build.log
docker run --rm $U --network=none -v $B:/b sa-eval-bench:1 sh -c 'cd /b && python -m compileall -q tree/satassume tree/harness tree/rust-spike/slice base/satassume base/harness base/rust-spike/slice sympy/sympy evalbench tools/qt76.py > /dev/null; echo compiled'
echo prep-ok
