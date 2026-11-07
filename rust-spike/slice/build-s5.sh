#!/bin/sh
# Inside sa-cy-build:1 (bench image's glibc and Python 3.12): /src = solver_rs at c230ee0, /out = slice5.
set -e
export PATH=/rust/cargo/bin:$PATH CARGO_HOME=/rust/cargo RUSTUP_HOME=/rust/rustup PYO3_PYTHON=/usr/local/bin/python
cd /src
cargo --version; rustc --version
cargo build --release --locked --offline --target-dir /tmp/t1 2>&1 | tail -1 && cp /tmp/t1/release/libsa_solver.so /out/full/sa_solver.so
cargo build --release --locked --offline --features abi3 --target-dir /tmp/t2 2>&1 | tail -1 && cp /tmp/t2/release/libsa_solver.so /out/abi3/sa_solver.so
sha256sum /out/full/sa_solver.so /out/abi3/sa_solver.so
