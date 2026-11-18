#!/bin/bash
# rr318.sh (sa-port-318): reruns the suite row term:tl-term-stale with bar.sh suite()'s own command line, 3 times on
# 314's tree (5b1d96f, .so c1ede79e) and 3 times on 317's (46750d4, .so 9acc8c3b), interleaved, one at a time, N=6.
# Question: does this planted row reproduce by id on one source? Rows in ~/sp19/sa-rust-ids-work/sa-port-318/rr/.
# End marker: ~/sp19/sa-rust-ids-work/sa-port-318/rr-end.txt, written by the last line of this script.
set -u
export HOME=/home/tilo/sp19
L=$HOME/sa-rust-ids-work/sa-port-318; mkdir -p $L/rr; rm -f $L/rr-end.txt
. $HOME/sa-rust-ids-work/env.sh
export PY W SA_EVAL_DATA PYTHONHASHSEED
for i in 1 2 3; do for n in 314 317; do
  T=$HOME/dev/sa-port-$n; S=$T/rust-spike/slice; O=$L/rr/tl-term-stale-$n-$i
  rm -rf $O; mkdir -p $O
  ( export SLICE_TERM_PLANT=tl-term-stale SLICE_TERM_FRAMES=rust; export SLICE_SUITE_OUT=$O SLICE_SUITE_BACKEND=rust PYTHONPATH=$T:$W/sympy:$W/shim:$S HYPOTHESIS_STORAGE_DIRECTORY=$O/hyp; cd $T; { git rev-parse --short HEAD; git status --short | head -5; sha256sum $S/sa_solver.so; $PY -c 'import satassume, sa_solver; print(satassume.__file__, sa_solver.__file__)'; } > $O/tree.txt 2>&1; $PY -m pytest -p rust_plugin -p handler_count -p plant_count -p hyp_profile --hypothesis-profile=bar -n 6 -q --tb=short -p no:cacheprovider tests > $O/pytest.log 2>&1; echo "$? $(tail -1 $O/pytest.log)" > $O/exit.txt )
  echo "$(date -u +%FT%TZ) $n-$i $(cat $O/exit.txt)" >> $L/rr/progress.txt
done; done
echo "END 0 $(date -u +%FT%TZ)" > $L/rr-end.txt
