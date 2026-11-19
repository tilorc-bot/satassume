#!/bin/bash
# rd335.sh TREE TAG CONVERT(py|rust) WL (sa-port-335, orion): rowdump335.py on one workload in TREE, rows under $O/rd/TAG.
T=$1; TAG=$2; c=$3; w=$4
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED PYTHONDONTWRITEBYTECODE=1
O=$HOME/sa-rust-ids-work/sa-port-335; d=$O/rd/$TAG; mkdir -p $d
cd $T/rust-spike/slice; export PYTHONPATH=$T:$W/sympy:$W/shim
unset SLICE_CONVERT_PLANT SLICE_SESSION_PLANT SLICE_TERM_PLANT SLICE_TERM_FRAMES
n=$(echo $w | tr -d :)
SLICE_CONVERT=$c $PY $O/tools/rowdump335.py $w $d/$n.json > $d/$n.out 2>&1; echo "rd $TAG c=$c $w run $? seed $PYTHONHASHSEED $(date -u +%T)" >> $O/rd/exit.txt
