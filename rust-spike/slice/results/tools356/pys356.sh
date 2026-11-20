#!/bin/sh
# pys356.sh WL:KIND:ROUND... (sa-port-356; sa-port-195's pys.sh for the fastest configuration): inside sa-eval-bench:1 on
# one pinned CPU, /work = pareto1 ~/sa-rust-ids-work/sa-port-356/s1/bench-SHA read-only (tree, sympy, evalbench, data,
# tools: the layout ana195.relpath reads), /results writable. Each job is one cold process. KIND:
#   time       tools342/qt342.py rust time, SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust SLICE_WITNESS=1 SLICE_WITNESS_RUST=1
#              (arm rust-nat: the wall time every share is read against; S1's driver)
#   pytime     qt342.py py time, SLICE_WITNESS=1 (arm py-on32, the reference row)
#   pysample3  qt342.py rust pysample in rust-nat's environment: pysampler.so, SIGPROF every 1 ms, native stack plus
#              Python frames (the records ana356.py reads)
#   cprof      prof356.py rust cprof in rust-nat's environment (calls by file)
T=/work/tree; R=/results; Q=/work/tools/qt342.py
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
unset SLICE_WITNESS_WORK SLICE_WITNESS_PLANT SLICE_WITNESS_RUST_PLANT SLICE_WITNESS_RUST SLICE_CONVERT SLICE_TERM_FRAMES SLICE_CONVERT_PLANT SLICE_TERM_PLANT
export SLICE_DIR=$T/rust-spike/slice SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYSAMPLER_SO=/work/tools/pysampler.so
export PYTHONPATH=$T:/work/sympy:/tmp/shim SLICE_WITNESS=1 SLICE_WITNESS_CAP=32
N="SLICE_WITNESS_RUST=1 SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust"
[ -e $R/env.txt ] || { python -VV; python -c 'import sympy,satassume;print(sympy.__version__,sympy.__file__,satassume.__file__)'; sha256sum $SLICE_DIR/sa_solver.so $PYSAMPLER_SO $Q /work/tools/prof356.py; cat /work/SHA; nproc; } > $R/env.txt 2>&1
row() { python -c "
import json,sys
d=json.loads(sys.stdin.read())
for k in ('per','ans','installed','session','term','lra'): d.pop(k,None)
d.update(arm='$1', round=$2); print(json.dumps(d))" >> $R/time.jsonl; }
for job in "$@"; do
  IFS=: read wl k r <<E
$job
E
  case $k in
    time) env $N python $Q $wl rust time 2>> $R/err.txt | row rust-nat $r;;
    pytime) python $Q $wl py time 2>> $R/err.txt | row py-on32 $r;;
    pysample3) b=$R/$wl-rust-pysample3-$r; env $N PYSAMPLE_WHAT=3 python $Q $wl rust pysample $b > $b.json 2> $b.err;;
    cprof) env $N python /work/tools/prof356.py $wl rust cprof > $R/$wl-rust-cprof-$r.json 2>> $R/err.txt;;
  esac
  echo "$job rc=$? $(date -u +%T)" >> $R/progress
done
echo DONE >> $R/progress
