#!/bin/bash
# pc317.sh REF TAG (sa-port-317, pareto1): the 2x2 of the term frames switch against SLICE_CONVERT on the 20 workloads, on
# origin/REF (the head of port/mark-note for the gate; rust-slice after landing for the probe count). 315's pc315.sh with
# its own clone and output. Per workload: Python's reference (live.py WL py), then four Rust cells under pycalls.py (pc304's
# 13 files), each compared with the reference by livecmp --end-only. Rows: $O/exit.txt ("pc f=F c=C WL run E cmp E2").
# End marker: $O/end.txt, written by fin() below (the last line of this script, or a failed clone/build).
REF=${1:?ref}; TAG=${2:?tag}
export REAL=/home/tilo CARGO_HOME=/home/tilo/.cargo RUSTUP_HOME=/home/tilo/.rustup PATH=/home/tilo/.cargo/bin:$PATH HOME=/home/tilo/sp19   # as ~/sp19/p1_job.sh
O=$HOME/sa-rust-ids-work/sa-port-317/pc-$TAG; mkdir -p $O/py; rm -f $O/end.txt $O/exit.txt
H=$HOME/dev/sa-port-317-pc
fin() { echo "END $1 $(date -u +%FT%TZ)" > $O/end.txt; exit; }
[ -d $H/.git ] || git clone -q https://github.com/tilorc-bot/satassume $H
git -C $H fetch -q origin && git -C $H checkout -q -f --detach origin/$REF || fin clone-failed
. $HOME/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED O H
(cd $H/rust-spike/slice/solver_rs && CARGO_TARGET_DIR=$O/target PYO3_PYTHON=$PY cargo build --release > $O/build.log 2>&1 && cp $O/target/release/libsa_solver.so ../sa_solver.so) || fin build-failed
(git -C $H rev-parse --short HEAD; sha256sum $H/rust-spike/slice/sa_solver.so; echo "seed $PYTHONHASHSEED") > $O/tree.txt
export PCF=rust-spike/slice/knowledge_live.py:rust-spike/slice/session_live.py:satassume/engine.py:satassume/sat/formula.py:satassume/knowledge/compile.py:rust-spike/slice/term_live.py:satassume/knowledge/templates/wiring.py:rust-spike/slice/knowledge_common_live.py:rust-spike/slice/knowledge_core_live.py:rust-spike/slice/convert.py:satassume/knowledge/templates/__init__.py:satassume/theories/lra/lra_adapter.py:satassume/sympy_api.py
cd $H/rust-spike/slice; export PYTHONPATH=$H:$W/sympy:$W/shim
$PY -c 'import satassume, sa_solver, term_live; print(satassume.__file__, sa_solver.__file__, hasattr(sa_solver, "TermFrames"))' >> $O/tree.txt
WLS="lra f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls"
ref() { n=$(echo $1 | tr -d :); timeout 14400 $PY live.py $1 py $O/py/$n.jsonl --check plain > $O/py/$n.out 2>&1; echo "ref $1 $? $(date -u +%T)" >> $O/exit.txt; }
one() { n=$(echo $1 | tr -d :); f=$2; c=$3; d=$O/f$f-c$c; mkdir -p $d
  SLICE_TERM_FRAMES=$f SLICE_CONVERT=$c PYCALLS_FILE=$PCF timeout 14400 $PY pycalls.py $d/$n.json $1 rust $d/$n.jsonl --check plain > $d/$n.out 2>&1; e=$?
  $PY livecmp.py $O/py/$n.jsonl $d/$n.jsonl --end-only > $d/$n.cmp 2>&1; e2=$?
  echo "pc f=$f c=$c $1 run $e cmp $e2 $(date -u +%T)" >> $O/exit.txt; rm -f $d/$n.jsonl; }
export -f ref one
for w in $WLS; do echo "$w"; done | xargs -P 8 -L 1 bash -c 'ref "$@"' _
for f in py rust; do for c in py rust; do for w in $WLS; do echo "$w $f $c"; done; done; done | xargs -P 8 -L 1 bash -c 'one "$@"' _
fin done
