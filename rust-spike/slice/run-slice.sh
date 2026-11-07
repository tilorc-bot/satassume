#!/bin/sh
# Inside bench-container: /work = pareto1:~/sa-rust-bench, read-only; /results is writable. Cold process per run, the first round of each
# seed a warmup, and the three backends rotate one place each round. /work/slice5 holds qtime.py, backend.py and {full,abi3}/sa_solver.so.
# Time passes only: the sampler can't see inside a Rust call, so it would not compare the backends.
# Compile the source with this image's Python first (compileall, on a writable mount): /work is read-only, and with no bytecode query 0 compiles
# lazy imports inside the timer, about 50 ms on every backend. See results/step5-timing.md. Modules: build-s5.sh. State check: check-s5.sh.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
D=/work/slice5
export SA_EVAL_DATA=/work/data
SRC=/work/src/slice-c230ee0:/work/sympy:/tmp/shim
one() {  # seed round backend workload
  case $3 in
    py)   PYTHONHASHSEED=$1 PYTHONPATH=$SRC python $D/qtime.py $4 time ;;
    full) PYTHONHASHSEED=$1 SLICE_BACKEND=rust PYTHONPATH=$SRC:$D/full python $D/qtime.py $4 time ;;
    abi3) PYTHONHASHSEED=$1 SLICE_BACKEND=rust PYTHONPATH=$SRC:$D/abi3 python $D/qtime.py $4 time ;;
  esac | sed "s/^{/{\"seed\": $1, \"round\": $2, \"backend\": \"$3\", /" >> /results/out.jsonl
}
O="py full abi3"
for spec in "0:${ROUNDS0:-0 1 2 3 4 5 6 7 8 9 10}" "1:${ROUNDS1:-0 1 2 3 4 5}" "2:${ROUNDS2:-0 1 2 3 4 5}"; do
  seed=${spec%%:*}
  for R in ${spec#*:}; do
    for wl in dev fuzz; do for b in $O; do one $seed $R $b $wl; done; done
    O="${O#* } ${O%% *}"
  done
done
