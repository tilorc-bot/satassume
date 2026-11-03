#!/bin/sh
# Inside sa-eval-bench:1, not timed: the Python replay and every Rust binary in check mode, the mutants, and the profile.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONPATH=/work/src/base-9bafaa5:/work/sympy:/tmp/shim
D=/work/lra
T=$D/traces
for wl in dev fuzz; do
  python $D/replay_lra.py $wl $T check
  for b in rs rsfx rslto rsmut; do $D/$b $wl $T check | sed "s/\"rs\"/\"$b\"/"; done
  $D/rsprof $wl $T prof | tail -1
  for m in ${MUTS:-1 2 3 4 5 6 7 8 9}; do
    printf 'mutant %s: ' "$m"
    LRA_MUT=$m timeout 60 $D/rsmut $wl $T check > /tmp/m.out 2>&1
    rc=$?
    if [ $rc -eq 0 ]; then cut -c1-200 /tmp/m.out; else echo "{\"wl\": \"$wl\", \"exit\": $rc}  (124 = no answer in 60 s)"; fi
  done
done
