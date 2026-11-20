#!/bin/bash
# pc354.sh TREE OUT CELLS (sa-port-354, item 6; tools340/pc340.sh with this step's cells; pareto0 or pareto1, shared
# lease): the count probe on a staged tree, with satassume/witness.py and rust-spike/slice/witness_live.py among the
# probed files. Cells: d0 (every switch unset: the default, Python frames and walker, the check off), w1 (SLICE_WITNESS=1
# SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust: Python's witness.py on the path the native check needs) and nat (w1 plus
# SLICE_WITNESS_RUST=1). Per workload and cell: Python's reference under the same SLICE_WITNESS (live.py WL py), then
# Rust under pcby354.py, compared by livecmp --end-only.
# Rows: OUT/exit.txt ("pc CELL WL ref E run E cmp E2"). End marker: OUT/end.txt, written by fin().
H=${1:?tree}; O=${2:?out}; CELLS=${3:-"d0 w1 nat"}; export HOME=/home/tilo/sp19
mkdir -p $O; rm -f $O/end.txt $O/exit.txt
fin() { echo "END $1 $(date -u +%FT%TZ)" > $O/end.txt; exit; }
. $HOME/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED O H
TOOLS=$(cd $(dirname $0) && pwd); export TOOLS
unset SLICE_CONVERT SLICE_CONVERT_PLANT SLICE_SESSION_PLANT SLICE_TERM_PLANT SLICE_TERM_FRAMES SLICE_WITNESS SLICE_WITNESS_PLANT SLICE_WITNESS_CAP SLICE_WITNESS_WORK SLICE_WITNESS_RUST SLICE_WITNESS_RUST_PLANT
(cat $H/../SHA 2>/dev/null; sha256sum $H/rust-spike/slice/sa_solver.so; echo "seed $PYTHONHASHSEED") > $O/tree.txt
export PCF=rust-spike/slice/knowledge_live.py:rust-spike/slice/session_live.py:satassume/engine.py:satassume/sat/formula.py:satassume/knowledge/compile.py:rust-spike/slice/term_live.py:satassume/knowledge/templates/wiring.py:rust-spike/slice/knowledge_common_live.py:rust-spike/slice/knowledge_core_live.py:rust-spike/slice/convert.py:satassume/knowledge/templates/__init__.py:satassume/theories/lra/lra_adapter.py:satassume/sympy_api.py:satassume/witness.py:rust-spike/slice/witness_live.py
cd $H/rust-spike/slice || fin no-tree; export PYTHONPATH=$H:$W/sympy:$W/shim
$PY -c 'import satassume, sa_solver, satassume.witness as w; print(satassume.__file__, sa_solver.__file__, w.__file__)' >> $O/tree.txt || fin import-failed
WLS="lra f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls"
cenv() { case $1 in d0) echo "SLICE_NONE=1";; w1) echo "SLICE_WITNESS=1 SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust";; nat) echo "SLICE_WITNESS=1 SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust SLICE_WITNESS_RUST=1";; esac; }
renv() { [ $1 = d0 ] && echo "SLICE_NONE=1" || echo "SLICE_WITNESS=1"; }
one() { n=$(echo $1 | tr -d :); c=$2; d=$O/$c; mkdir -p $d
  env $(renv $c) timeout 14400 $PY live.py $1 py $d/$n-py.jsonl --check plain > $d/$n-py.out 2>&1; r=$?
  env $(cenv $c) PYCALLS_FILE=$PCF timeout 14400 $PY $TOOLS/pcby354.py $d/$n.json $1 rust $d/$n.jsonl --check plain > $d/$n.out 2>&1; e=$?
  $PY livecmp.py $d/$n-py.jsonl $d/$n.jsonl --end-only > $d/$n.cmp 2>&1; e2=$?
  echo "pc $c $1 ref $r run $e cmp $e2 $(date -u +%T)" >> $O/exit.txt; rm -f $d/$n.jsonl $d/$n-py.jsonl; }
export -f one cenv renv
for c in $CELLS; do for wl in $WLS; do echo "$wl $c"; done; done | xargs -P 10 -L 1 bash -c 'one "$@"' _
fin done
