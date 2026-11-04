#!/bin/sh
# Inside bench-container: /work = pareto1:~/sa-rust-bench. Cold process per run, round 0 a warmup, modes rotate one place
# each round. base and baseb are the same code (main 9bafaa5): baseb is the A/A noise floor. pid = base + p-id.patch.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export SA_EVAL_DATA=/work/data PYTHONHASHSEED=0
run() {
  case $2 in pid) S=pid-9bafaa5 ;; *) S=base-9bafaa5 ;; esac
  PYTHONPATH=/work/src/$S:/work/sympy:/tmp/shim python /work/tools-rust/rc.py base $3 | sed "s/^{/{\"round\": \"$1\", \"run\": \"$2\", /"
}
O="base pid baseb"
for R in 0 1 2 3 4 5 6 7 8 9 10; do
  for wl in dev fuzz; do for m in $O; do run $R $m $wl; done; done
  O="${O#* } ${O%% *}"
done
