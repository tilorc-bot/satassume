#!/bin/sh
# Inside sa-cy-build:1 (glibc 2.41, as sa-eval-bench:1): /src = the port crate, /out = where the binaries go.
set -e
export PATH=/rust/cargo/bin:$PATH CARGO_HOME=/rust/cargo RUSTUP_HOME=/rust/rustup
cd /src
cargo --version
cargo build --offline --release --target-dir /tmp/t1 && cp /tmp/t1/release/lra-replay /out/rs
cargo build --offline --release --features fxhash --target-dir /tmp/t2 && cp /tmp/t2/release/lra-replay /out/rsfx
cargo build --offline --profile tuned --features fxhash --target-dir /tmp/t3 && cp /tmp/t3/tuned/lra-replay /out/rslto
cargo build --offline --release --features prof --target-dir /tmp/t4 && cp /tmp/t4/release/lra-replay /out/rsprof
cargo build --offline --release --features mutants --target-dir /tmp/t5 && cp /tmp/t5/release/lra-replay /out/rsmut
sha256sum /out/rs /out/rsfx /out/rslto /out/rsprof /out/rsmut
