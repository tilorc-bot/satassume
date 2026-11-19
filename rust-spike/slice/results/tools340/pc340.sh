#!/bin/bash
# pc340.sh TREE OUT (sa-port-340, pareto1): the count probe (tools334/pc334.sh) on a staged tree, with satassume/witness.py
# added to the probed files and the witness switch as the cell: w0 (SLICE_WITNESS unset, the default) and w1
# (SLICE_WITNESS=1). The other switches stay at their defaults (Python frames, Python walker). Per workload and cell:
# Python's reference under the same switch (live.py WL py), then Rust under pcby334.py, compared by livecmp --end-only.
# Rows: OUT/exit.txt ("pc w=W WL run E cmp E2"). End marker: OUT/end.txt, written by fin().
H=${1:?tree}; O=${2:?out}; export HOME=/home/tilo/sp19
mkdir -p $O; rm -f $O/end.txt $O/exit.txt
fin() { echo "END $1 $(date -u +%FT%TZ)" > $O/end.txt; exit; }
. $HOME/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED O H
TOOLS=$(cd $(dirname $0) && pwd); export TOOLS
(cat $H/../SHA-$(basename $H) 2>/dev/null; sha256sum $H/rust-spike/slice/sa_solver.so; echo "seed $PYTHONHASHSEED") > $O/tree.txt
export PCF=rust-spike/slice/knowledge_live.py:rust-spike/slice/session_live.py:satassume/engine.py:satassume/sat/formula.py:satassume/knowledge/compile.py:rust-spike/slice/term_live.py:satassume/knowledge/templates/wiring.py:rust-spike/slice/knowledge_common_live.py:rust-spike/slice/knowledge_core_live.py:rust-spike/slice/convert.py:satassume/knowledge/templates/__init__.py:satassume/theories/lra/lra_adapter.py:satassume/sympy_api.py:satassume/witness.py
cd $H/rust-spike/slice || fin no-tree; export PYTHONPATH=$H:$W/sympy:$W/shim
$PY -c 'import satassume, sa_solver, satassume.witness as w; print(satassume.__file__, sa_solver.__file__, w.__file__)' >> $O/tree.txt || fin import-failed
WLS="lra f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls"
wenv() { [ "$1" = 1 ] && echo "SLICE_WITNESS=1" || echo "SLICE_WITNESS_UNSET=1"; }
one() { n=$(echo $1 | tr -d :); w=$2; d=$O/w$w; mkdir -p $d
  env $(wenv $w) timeout 14400 $PY live.py $1 py $d/$n-py.jsonl --check plain > $d/$n-py.out 2>&1; r=$?
  env $(wenv $w) PYCALLS_FILE=$PCF timeout 14400 $PY $TOOLS/pcby334.py $d/$n.json $1 rust $d/$n.jsonl --check plain > $d/$n.out 2>&1; e=$?
  $PY livecmp.py $d/$n-py.jsonl $d/$n.jsonl --end-only > $d/$n.cmp 2>&1; e2=$?
  echo "pc w=$w $1 ref $r run $e cmp $e2 $(date -u +%T)" >> $O/exit.txt; rm -f $d/$n.jsonl $d/$n-py.jsonl; }
export -f one wenv
for w in 0 1; do for wl in $WLS; do echo "$wl $w"; done; done | xargs -P 10 -L 1 bash -c 'one "$@"' _
fin done
