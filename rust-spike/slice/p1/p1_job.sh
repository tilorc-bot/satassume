#!/bin/bash
# p1_job.sh: environment for jobs in ~/sp19 on pareto1. HOME is my directory, so the slice scripts' env.sh is mine.
export REAL=/home/tilo CARGO_HOME=/home/tilo/.cargo RUSTUP_HOME=/home/tilo/.rustup PATH=/home/tilo/.cargo/bin:$PATH HOME=/home/tilo/sp19
export T=$HOME/dev/sa-port-19 S=$HOME/dev/sa-port-19/rust-spike/slice B=$HOME/out
mkdir -p $B
. $HOME/sa-rust-ids-work/env.sh
export PY W SA_EVAL_DATA PYTHONHASHSEED PYTHONPATH=$T:$W/sympy:$W/shim
cd $S
exec bash "$@"
