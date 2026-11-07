#!/bin/bash
# Fresh rerun with branch counts, LRA_MUT 6 and 7 on full workloads, history and hash seeds, solver mutants on the real
# engine, boundary mutants with the suite column. Run under p1_job.sh. Each part leaves its own done file.
OUT=${OUT:-$REAL/sa-rust-ids-work/sa-port-21/checks}; mkdir -p $OUT; date -u >$OUT/start
J=${J:-6}
shards() { # dir wl mode [flags...]: live.py --fork in J shards, merged
  d=$1; wl=$2; m=$3; shift 3
  N=$($PY -c "import live; print(len(live.load('$wl')))")
  for i in $(seq 0 $((J-1))); do
    only=$(seq $i $J $((N-1)) | paste -sd,)
    $PY live.py $wl $m $d/$wl-$m.s$i.jsonl --check entry --fork --only $only "$@" >$d/$wl-$m.s$i.tot 2>$d/$wl-$m.s$i.err &
  done
  wait
  $PY $HOME/merge_shards.py $d/$wl-$m.jsonl $d/$wl-$m.s?.jsonl >>$d/merge.txt
}
# 1. Fresh, final source
F=$OUT/fresh; mkdir -p $F
$PY -c 'import satassume,sa_solver,hashlib; print(satassume.__file__, sa_solver.__file__, hashlib.sha256(open(sa_solver.__file__,"rb").read()).hexdigest())' >$F/tree.txt
for wl in dev fuzz; do for m in py rust; do shards $F $wl $m; done; $PY livecmp.py $F/$wl-py.jsonl $F/$wl-rust.jsonl >$F/$wl.cmp 2>&1; done
date -u >$F/done
# 2. LRA_MUT 6, 7 on a mutants build; 0 is the same build unmutated and must read clean
L=$OUT/lramut; mkdir -p $L/so
(cd solver_rs && PYO3_PYTHON=$PY CARGO_TARGET_DIR=$L/target cargo build --release --features mutants) >$L/build.log 2>&1
cp $L/target/release/libsa_solver.so $L/so/sa_solver.so
for k in 0 6 7; do mkdir -p $L/m$k
  for wl in dev fuzz; do
    LRA_MUT=$k shards $L/m$k $wl rust --so $L/so
    $PY livecmp.py $F/$wl-py.jsonl $L/m$k/$wl-rust.jsonl >$L/m$k/$wl.cmp 2>&1
  done
done
date -u >$L/done
# 3. History and hash seeds
H=$OUT/hist
bash $S/run_history.sh $H $J >$OUT/hist.out 2>&1
$PY historycmp.py $H >$H/cmp.txt 2>&1
date -u >$H/done
# 4. Solver mutants 2, 5, 6, 7, 9 and the boundary mutants with no real-engine catch, on the real engine
ML=$OUT/mutlive; mkdir -p $ML/ref
# lib.rs reaches the core by a relative #[path], and these tools build in a copy of the crate
ln -sfn $S/../lra $OUT/lra
ln -sf $H/recorded-dev-py.jsonl $ML/ref/dev-py.jsonl; ln -sf $H/recorded-fuzz-py.jsonl $ML/ref/fuzz-py.jsonl
$PY mutate_live.py $ML $ML/ref --only 2,5,6,7,9,11,17,18,26,27,29,31,32,33,34 --jobs $J --timeout 1800 >$ML/out.txt 2>&1
date -u >$ML/done
# 5. All boundary mutants, nested and the suite column on the solver and LRA test files
MB=$OUT/mutbound; mkdir -p $MB/builds
ln -sfn $S/../lra $MB/lra
$PY - $MB/builds >$MB/builds.out 2>&1 <<'P'
import os, shutil, sys
from mutate_slice import HERE, M, build, mutated_build
w = sys.argv[1]; crate = os.path.join(w, "crate")
shutil.copytree(os.path.join(HERE, "solver_rs"), crate, dirs_exist_ok=True, ignore=shutil.ignore_patterns("target"))
build(crate, os.path.join(w, "base"))
for i in range(10, len(M)):
    mutated_build(crate, w, i)
print("built", len(M) - 10)
P
cd $T
$PY $S/mutate_boundary.py $MB/builds $MB/work --jobs $J --suite $(ls tests/test_solver*.py tests/test_lra*.py) >$MB/out.txt 2>&1
cd $S
date -u >$MB/done
date -u >$OUT/done
