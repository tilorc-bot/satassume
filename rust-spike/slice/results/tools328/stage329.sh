#!/bin/bash
# stage329.sh SHA... (sa-port-329, orion; from stage328.sh): on pareto1, ~/sa-rust-ids-work/sa-port-329/s1/bench-SHA is
# sa-port-317's s1/bench-46750d4 (sympy, evalbench, data; read only there) with tree/ = git archive of SHA from the
# worktree plus 46750d4's x86-64 sa_solver.so: the crate and the slice's Python are source-equal between 46750d4 and SHA
# (checked here by git diff), so no Rust build is needed. Syncs the tools and sa-port-324's two iv plugins.
set -e
T=~/sa-rust-ids-work/sa-port-328/wt; G=~/sa-rust-ids-work/sa-port-329/s1; P=~/sa-rust-ids-work/sa-port-317/s1/bench-46750d4
for a in "$@"; do
  SHA=$(git -C $T rev-parse --short=7 "$a^{commit}")
  git -C $T diff --quiet 46750d4 $SHA -- rust-spike/slice/solver_rs ':(glob)rust-spike/slice/*.py' || { echo "source differs from 46750d4"; exit 2; }
  ssh pareto1 "set -e; mkdir -p $G/bench-$SHA/tree; cd $G/bench-$SHA; [ -e sympy ] || cp -a $P/sympy $P/evalbench $P/data .; echo $SHA > SHA"
  git -C $T archive $SHA | ssh pareto1 "tar -x -C $G/bench-$SHA/tree"
  ssh pareto1 "cp $P/tree/rust-spike/slice/sa_solver.so $G/bench-$SHA/tree/rust-spike/slice/sa_solver.so; sha256sum $G/bench-$SHA/tree/rust-spike/slice/sa_solver.so"
  echo "staged $SHA"
done
rsync -a --exclude __pycache__ $T/rust-spike/slice/results/tools328/ pareto1:$G/tools/
rsync -a --exclude __pycache__ ~/sa-rust-ids-work/sa-port-324/plug/ pareto1:$G/plug/
