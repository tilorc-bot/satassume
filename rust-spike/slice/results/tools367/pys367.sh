#!/bin/sh
# pys367.sh WL:KIND:ROUND... (sa-port-367; tools356/pys356.sh with a default-path arm): inside sa-eval-bench:1 on one
# pinned CPU, /work = pareto1 ~/sa-rust-ids-work/sa-port-367/s1/bench-SHA read-only (tree, sympy, evalbench, data, tools),
# /results writable. Each job is one cold process. Two paths:
#   default   the package alone, NO SLICE_ switch in the environment (what SymPy runs; SLICE_DIR is the driver's own
#             variable: where budget_wl.py and knowledge_wiring_wl.py are; the witness check is off, its default)
#   rust-nat  SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust SLICE_WITNESS=1 SLICE_WITNESS_CAP=32 SLICE_WITNESS_RUST=1 (356's)
# KIND: time / dtime (tools342/qt342.py rust|py time), pysample3 / dpysample3 (qt342.py pysample: pysampler.so, SIGPROF
# every 1 ms, native stack plus Python frames), cprof / dcprof (tools356/prof356.py cprof: calls by file),
# dmods (the modules loaded after a default pass: mods367.py).
T=/work/tree; R=/results; Q=/work/tools/qt342.py
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
for v in $(env | sed -n 's/^\(SLICE_[A-Z_]*\)=.*/\1/p'); do unset $v; done
export SLICE_DIR=$T/rust-spike/slice SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYSAMPLER_SO=/work/tools/pysampler.so
export PYTHONPATH=$T:/work/sympy:/tmp/shim
N="SLICE_WITNESS=1 SLICE_WITNESS_CAP=32 SLICE_WITNESS_RUST=1 SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust"
[ -e $R/env.txt ] || { python -VV; python -c 'import sympy,satassume;print(sympy.__version__,sympy.__file__,satassume.__file__)'; sha256sum $SLICE_DIR/sa_solver.so $PYSAMPLER_SO $Q /work/tools/prof356.py; cat /work/SHA; nproc; env | grep SLICE_; } > $R/env.txt 2>&1
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
    dtime) python $Q $wl py time 2>> $R/err.txt | row default $r;;
    pysample3) b=$R/$wl-rust-pysample3-$r; env $N PYSAMPLE_WHAT=3 python $Q $wl rust pysample $b > $b.json 2> $b.err;;
    dpysample3) b=$R/$wl-py-pysample3-$r; PYSAMPLE_WHAT=3 python $Q $wl py pysample $b > $b.json 2> $b.err;;
    cprof) env $N python /work/tools/prof356.py $wl rust cprof > $R/$wl-rust-cprof-$r.json 2>> $R/err.txt;;
    dcprof) python /work/tools/prof356.py $wl py cprof > $R/$wl-py-cprof-$r.json 2>> $R/err.txt;;
    dmods) python /work/tools/mods367.py $wl > $R/$wl-py-mods.json 2>> $R/err.txt;;
  esac
  echo "$job rc=$? $(date -u +%T)" >> $R/progress
done
echo DONE >> $R/progress
