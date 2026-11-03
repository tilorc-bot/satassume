#!/bin/sh
# Inside sa-cy-build:1 (the bench image's glibc and Python 3.12): /src = this crate, /out = where the modules go.
set -e
export PATH=/rust/cargo/bin:$PATH CARGO_HOME=/rust/cargo RUSTUP_HOME=/rust/rustup PYO3_PYTHON=/usr/local/bin/python
cd /src
cargo --version
cargo build --release --target-dir /tmp/t1 && mkdir -p /out/full && cp /tmp/t1/release/libxbench.so /out/full/xbench.so
cargo build --release --features abi3 --target-dir /tmp/t2 && mkdir -p /out/abi3 && cp /tmp/t2/release/libxbench.so /out/abi3/xbench.so
sha256sum /out/full/xbench.so /out/abi3/xbench.so
