#!/bin/bash
# build336.sh SHA (sa-port-336, pareto1, under a shared lease): the two x86-64 builds of SHA's crate from the staged
# tree ~/sa-rust-ids-work/sa-port-336/s1/bench-SHA/tree (a git archive).
#  1. the suite and bar build, as p1/bar.sh's build phase: ~/sp19's venv Python, cargo on the host;
#     -> sa-port-336/so-venv-SHA/sa_solver.so (not put in the bench tree)
#  2. the S1 build, as tools327/build327.sh: in sa-cy-build:1, the bench image's Python -> the bench tree's sa_solver.so,
#     then bytecode compiled in sa-eval-bench:1
# End marker: sa-port-336/build-SHA/DONE-BUILD, the last line here.
SHA=$1; X=/home/tilo/sa-rust-ids-work/sa-port-336; B=$X/s1/bench-$SHA; O=$X/build-$SHA; mkdir -p $O $X/so-venv-$SHA
[ -d $B/tree ] || { echo "no $B/tree"; exit 2; }
( export CARGO_HOME=/home/tilo/.cargo RUSTUP_HOME=/home/tilo/.rustup PATH=/home/tilo/.cargo/bin:$PATH HOME=/home/tilo/sp19
  . $HOME/sa-rust-ids-work/env.sh
  cd $B/tree/rust-spike/slice/solver_rs && CARGO_TARGET_DIR=$X/target-venv PYO3_PYTHON=$PY cargo build --release > $O/venv-build.log 2>&1 \
    && cp $X/target-venv/release/libsa_solver.so $X/so-venv-$SHA/sa_solver.so && $PY -VV > $O/venv-python.txt 2>&1 ) || { echo "venv build failed"; exit 3; }
U="--user $(id -u):$(id -g)"
docker run --rm $U --network=none -v /home/tilo/.cargo:/rust/cargo -v /home/tilo/.rustup:/rust/rustup -v $B:/b -v $X/s1/tools:/t -v $O:/o -e HOME=/tmp sa-cy-build:1 sh -c '
  set -e
  export PATH=/rust/cargo/bin:$PATH CARGO_HOME=/rust/cargo RUSTUP_HOME=/rust/rustup PYO3_PYTHON=/usr/local/bin/python
  cd /b/tree/rust-spike/slice/solver_rs; rustc --version; python -VV
  cargo build --release --locked --offline --target-dir /b/target 2>&1 | tail -2
  cp /b/target/release/libsa_solver.so ../sa_solver.so; sha256sum ../sa_solver.so
' > $O/bench-build.txt 2>&1 || { echo "bench build failed"; exit 4; }
docker run --rm $U --network=none -v $B:/b -v $X/s1/tools:/t sa-eval-bench:1 sh -c 'cd /b && python -m compileall -q tree/satassume tree/rust-spike/slice evalbench /t/qt195.py /t/wit328.py /t/cnt329.py > /dev/null; echo compiled rc=$?' >> $O/bench-build.txt 2>&1
sha256sum $X/so-venv-$SHA/sa_solver.so $B/tree/rust-spike/slice/sa_solver.so > $O/so.txt
echo "BUILT $(date -u +%FT%TZ)" > $O/DONE-BUILD
