#!/bin/sh
# In bench-container, /work = bench dir, read-only. Split rounds: coarse and fine exclusive timers, with an unwrapped control in the same rotation.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
T=/work/base
export SLICE_DIR=$T/rust-spike/slice SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONPATH=$T:/work/sympy:/tmp/shim
R=/results
{ python -VV; python -c 'import sympy,satassume;print(sympy.__version__,sympy.__file__,satassume.__file__)'; sha256sum $SLICE_DIR/sa_solver.so; cat /work/SHA; nproc; } > $R/env.txt 2>&1
for r in 0 1 2 3 4 5; do
  for wl in dev fuzz; do
    python /work/tools/qt76.py $wl rust time | python -c "import json,sys; r=json.load(sys.stdin); print(json.dumps(dict(round=$r,arm='plain',wl=r['wl'],s=r['s'],digest=r['digest'])))" >> $R/split.jsonl
    python /work/tools/split78.py $wl rust | sed "s/^{/{\"round\": $r, \"arm\": \"coarse\", /" >> $R/split.jsonl
    python /work/tools/split78.py $wl rust --fine | sed "s/^{/{\"round\": $r, \"arm\": \"fine\", /" >> $R/split.jsonl
    SLICE_TERM=py python /work/tools/qt76.py $wl rust time | python -c "import json,sys; r=json.load(sys.stdin); print(json.dumps(dict(round=$r,arm='plain-termpy',wl=r['wl'],s=r['s'],digest=r['digest'])))" >> $R/split.jsonl
    python /work/tools/split78.py $wl term-py | sed "s/^{/{\"round\": $r, \"arm\": \"termpy-wrapped\", /" >> $R/split.jsonl
  done
  echo "round $r $(date -u +%T)" >> $R/progress
done
echo DONE >> $R/progress
