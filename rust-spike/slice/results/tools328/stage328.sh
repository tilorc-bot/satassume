#!/bin/bash
# stage328.sh SHA (sa-port-328, orion): on pareto1, s1/bench-SHA is sa-port-317's s1/bench-46750d4 (sympy, evalbench,
# data; read only there) with tree/ = git archive of SHA from this worktree plus 46750d4's sa_solver.so: the crate and
# the slice's Python are source-equal between 46750d4 and SHA (checked here by git diff), so no Rust build is needed.
# Compiles bytecode as build317.sh does. Syncs the tools.
set -e
T=~/sa-rust-ids-work/sa-port-328/wt; G=~/sa-rust-ids-work/sa-port-328/s1; P=~/sa-rust-ids-work/sa-port-317/s1/bench-46750d4
SHA=$(git -C $T rev-parse --short=7 "$1^{commit}")
git -C $T diff --quiet 46750d4 $SHA -- rust-spike/slice/solver_rs ':(glob)rust-spike/slice/*.py' || { echo "source differs from 46750d4"; exit 2; }
ssh pareto1 "set -e; mkdir -p $G/bench-$SHA/tree; cd $G/bench-$SHA; [ -e sympy ] || cp -a $P/sympy $P/evalbench $P/data .; echo $SHA > SHA"
git -C $T archive $SHA | ssh pareto1 "tar -x -C $G/bench-$SHA/tree"
ssh pareto1 "cp $P/tree/rust-spike/slice/sa_solver.so $G/bench-$SHA/tree/rust-spike/slice/sa_solver.so"
rsync -a --exclude __pycache__ $T/rust-spike/slice/results/tools328/ pareto1:$G/tools/
ssh pareto1 "docker run --rm --user \$(id -u):\$(id -g) --network=none -v $G/bench-$SHA:/b -v $G/tools:/t sa-eval-bench:1 sh -c 'cd /b && python -m compileall -q tree/satassume tree/rust-spike/slice evalbench /t/qt195.py /t/wit328.py > /dev/null; echo compiled rc=\$?'; sha256sum $G/bench-$SHA/tree/rust-spike/slice/sa_solver.so"
echo "staged $SHA"
