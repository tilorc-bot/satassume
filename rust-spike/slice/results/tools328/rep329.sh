#!/bin/bash
# rep329.sh (sa-port-329, pareto1): the planted-history test repeated, 20 runs a cell: backend rust and python, switch on and off.
export HOME=/home/tilo/sp19
G=/home/tilo/sa-rust-ids-work/sa-port-329/s1; T=$G/bench-5e6e46a/tree; O=/home/tilo/sa-rust-ids-work/sa-port-329/job/rep2; mkdir -p $O
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED; cd $T
for be in rust python; do for sw in 0 1; do for i in $(seq 20); do
  mkdir -p $O/w-$be-$sw-$i; SLICE_WITNESS=$sw SLICE_SUITE_OUT=$O/w-$be-$sw-$i SLICE_SUITE_BACKEND=$be PYTHONPATH=$T:$W/sympy:$W/shim:$T/rust-spike/slice $PY -m pytest -p rust_plugin -p handler_count -p hyp_profile --hypothesis-profile=bar -n 0 -q -p no:cacheprovider "tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence" 2>&1 | tail -1 | sed "s/ in .*//; s/^/$be $sw /" >> $O/rep.txt
done; done; done
sort $O/rep.txt | uniq -c > $O/rep-sum.txt  # the end marker
