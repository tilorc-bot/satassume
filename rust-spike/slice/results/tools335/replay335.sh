#!/bin/sh
# replay335.sh TREE TAG IDS PLANT (sa-port-335, orion): the ids of IDS in that order, one process, as bar.sh suite() runs a
# convert:* row (Rust backend, SLICE_CONVERT=rust, SLICE_CONVERT_PLANT, its plugins and hypothesis profile), without xdist.
T=$1; TAG=$2; IDS=$3; P=$4
. ~/sa-rust-ids-work/env.sh
O=$HOME/sa-rust-ids-work/sa-port-335; D=$O/order/$TAG; mkdir -p $D
export PYTHONPATH=$T:$W/sympy:$W/shim:$T/rust-spike/slice:$O/plug SLICE_SUITE_BACKEND=rust SLICE_CONVERT=rust PYTHONDONTWRITEBYTECODE=1
export SLICE_SUITE_OUT=$D HYPOTHESIS_STORAGE_DIRECTORY=$D/hyp ORDER335=$IDS ORDER335_RAN=$D/ran.txt
unset SLICE_TERM_FRAMES SLICE_TERM_PLANT SLICE_SESSION_PLANT SLICE_CONVERT_PLANT
if [ -n "$P" ]; then export SLICE_CONVERT_PLANT=$P; fi
cd $T
$PY -m pytest -p rust_plugin -p handler_count -p plant_count -p hyp_profile --hypothesis-profile=bar -p order335 -q --tb=line -p no:cacheprovider --rootdir=$T tests > $D/pytest.log 2>&1
echo "EXIT $? plant=$SLICE_CONVERT_PLANT so=$(sha256sum $T/rust-spike/slice/sa_solver.so | cut -c1-8) $(date -u +%T)" > $D/exit.txt
