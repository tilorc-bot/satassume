#!/bin/sh
# Inside sa-cy-build:1 (glibc 2.41, as sa-eval-bench:1): /src = the replay crate, /out = where the binaries go.
set -e
export PATH=/rust/cargo/bin:$PATH CARGO_HOME=/rust/cargo RUSTUP_HOME=/rust/rustup
cd /src
cargo --version
cargo build --release --target-dir /tmp/t1 && cp /tmp/t1/release/replay /out/rs
cargo build --release --features fxhash --target-dir /tmp/t2 && cp /tmp/t2/release/replay /out/rsfx
cargo build --profile tuned --features fxhash --target-dir /tmp/t3 && cp /tmp/t3/tuned/replay /out/rslto
cargo build --release --features prof --target-dir /tmp/t4 && cp /tmp/t4/release/replay /out/rsprof
sha256sum /out/rs /out/rsfx /out/rslto
ls -la /out
