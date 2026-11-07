#!/bin/sh
# Builds sa_solver.so next to backend.py, with the Python of env.sh. Not for timing: step 5 builds in the bench image.
set -e
. "$HOME/sa-rust-ids-work/env.sh"
cd "$(dirname "$0")/solver_rs"
PYO3_PYTHON=$PY cargo build --release
cp target/release/libsa_solver.so ../sa_solver.so
