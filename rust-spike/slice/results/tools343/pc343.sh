#!/bin/sh
# pc343.sh (sa-port-343; inside bench-container after time342.sh's two invocations, one pinned CPU, /work = pareto1
# ~/sa-rust-ids-work/sa-port-343/s1 read-only, /results writable): pc343.py, the per-call rows of the witness check, on
# WLS for each SHA of SHAS, modes py and rust (both Rust switches), SLICE_WITNESS=1 cap 32, ROUNDS cold passes each.
# One file per pass: /results/pc-SHA-WL-MODE-ROUND.json.
R=/results; C=/work/common
mkdir -p /tmp/shim && ln -sfn $C/evalbench /tmp/shim/evalbench
echo "start $(date -u +%T)" >> $R/progress
for r in $ROUNDS; do for wl in $WLS; do for sha in $SHAS; do for m in py rust; do
  T=/work/bench-$sha/tree; cv=py; [ $m = rust ] && cv=rust
  env SLICE_WITNESS=1 SLICE_WITNESS_CAP=32 SLICE_CONVERT=$cv SLICE_TERM_FRAMES=$cv SLICE_DIR=$T/rust-spike/slice SA_EVAL_DATA=$C/data PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$T:$C/sympy:/tmp/shim python /work/tools/pc343.py $wl $m > $R/pc-$sha-$wl-$m-$r.json 2>> $R/err.txt
  echo "$? $sha $wl $m $r" >> $R/rc.txt
done; done; done; echo "round $r $(date -u +%T)" >> $R/progress; done
echo "DONE $(date -u +%T)" >> $R/progress
