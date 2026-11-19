#!/bin/sh
# s7.sh TREE TAG TARGET [PLANT] (sa-port-335, orion): one fresh pytest process on TARGET under the Rust backend with
# SLICE_CONVERT=rust and, if given, SLICE_CONVERT_PLANT=PLANT (as bar.sh suite() sets a convert:* row).
# Output: ~/sa-rust-ids-work/sa-port-335/s7/TAG.log, last line EXIT.
T=$1; TAG=$2; TGT=$3; P=$4
. ~/sa-rust-ids-work/env.sh
O=$HOME/sa-rust-ids-work/sa-port-335
export PYTHONPATH=$T:$W/sympy:$W/shim:$T/rust-spike/slice SLICE_SUITE_BACKEND=rust SLICE_CONVERT=rust PYTHONDONTWRITEBYTECODE=1
unset SLICE_SUITE_OUT SLICE_TERM_FRAMES SLICE_TERM_PLANT SLICE_SESSION_PLANT SLICE_CONVERT_PLANT
if [ -n "$P" ]; then export SLICE_CONVERT_PLANT=$P; fi
cd $T
$PY -m pytest -p rust_plugin -q --tb=line -p no:cacheprovider --rootdir=$T "$TGT" > $O/s7/$TAG.log 2>&1
echo "EXIT $? plant=$SLICE_CONVERT_PLANT so=$(sha256sum $T/rust-spike/slice/sa_solver.so | cut -c1-8)" >> $O/s7/$TAG.log
