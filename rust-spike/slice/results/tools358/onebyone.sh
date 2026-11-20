#!/bin/bash
# onebyone.sh TREE OUTPREFIX MODE [TIMEOUT]: the six kept files one at a time under run_suite.sh, each with a timeout.
# DESELECT=ID leaves one test out (the 700-deep formula, once found). faulthandler_timeout dumps every thread's Python stack of a test that runs past 60 s (to pytest.log).
T=$1; P=$2; M=$3; TO=${4:-200}
for f in test_lazy_reads test_convert_once test_term_live test_term_ids test_knowledge_lazy test_convert_walk; do
  [ -f $T/rust-spike/slice/$f.py ] || { echo "$f absent" > $P-$f.absent; continue; }
  rm -rf $P-$f
  s=$(date +%s)
  SLICE_CONVERT=$M SLICE_TERM_FRAMES=rust PYTEST_N="-n 4" timeout $TO sh $T/rust-spike/slice/run_suite.sh $P-$f rust rust-spike/slice/$f.py -W ignore -o faulthandler_timeout=60 ${DESELECT:+--deselect "$DESELECT"} > /dev/null 2>&1
  echo "$f timeout-rc=$? secs=$(( $(date +%s) - s )) pytest: $(cat $P-$f/exit.txt 2>/dev/null || echo "no exit.txt: killed")" >> $P-summary.txt
done
echo END >> $P-summary.txt
