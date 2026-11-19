#!/bin/bash
# stage327.sh SHA...: on orion. On pareto1, s1/bench-SHA is a copy of sa-port-317's s1/bench-46750d4 (read only there;
# built tree, sympy, evalbench, data, target) with tree/ replaced by git archive of SHA from the worktree's clone
# (target kept, so the build is incremental). Syncs the tools.
set -e
R=/home/tilo/sa-rust-ids-work/sa-port-324/wt; G=~/sa-rust-ids-work/sa-port-327/s1; P=~/sa-rust-ids-work/sa-port-317/s1/bench-46750d4
ssh pareto1 "mkdir -p $G"
for s in "$@"; do
  S=$(git -C $R rev-parse --short=7 "$s^{commit}")
  ssh pareto1 "set -e; if [ ! -e $G/bench-$S ]; then cp -a $P $G/bench-$S; rm -rf $G/bench-$S/tree; mkdir $G/bench-$S/tree; echo $S > $G/bench-$S/SHA; fi"
  ssh pareto1 "[ -e $G/bench-$S/tree/satassume ]" || git -C $R archive $S | ssh pareto1 "tar -x -C $G/bench-$S/tree"
  echo "staged $S"
done
rsync -a --exclude __pycache__ --exclude pysampler.so $G/tools pareto1:$G/
