#!/bin/bash
# plantrows.sh: plants 768-773 as suite rows over the six kept files (SLICE_CONVERT=rust SLICE_CONVERT_PLANT=NAME, what
# the bar's `convert:NAME` row sets, p1/bar.sh penv), -n 4, into $O/p-NAME. A plant is caught when ids fail in its row
# that pass in k-rust (plantrows.txt). DEEP is deselected as in passes.sh. End marker, written last: $O/plantrows-end.txt.
O=~/sa-rust-ids-work/sa-port-358
HEAD=~/sa-rust-ids-work/sa-port-356/wt
DEEP='rust-spike/slice/test_convert_walk.py::test_a_deep_formula_is_pythons[700-too-deep]'
F=""; for f in test_lazy_reads test_convert_once test_term_live test_term_ids test_knowledge_lazy test_convert_walk; do F="$F rust-spike/slice/$f.py"; done
rm -f $O/plantrows-end.txt $O/plantrows.txt
ids() { grep -E '^(FAILED|ERROR) ' $1/pytest.log | cut -d' ' -f2 | LC_ALL=C sort -u; }
for pl in calls-structural-not power-rows-drop-last read-commutative-not entry-no-assumptions formula-and-as-or entry-skip-replaced; do
  rm -rf $O/p-$pl
  SLICE_CONVERT=rust SLICE_CONVERT_PLANT=$pl SLICE_TERM_FRAMES=rust PYTEST_N="-n 4" sh $HEAD/rust-spike/slice/run_suite.sh $O/p-$pl rust $F -W ignore --deselect "$DEEP" > /dev/null 2>&1
  comm -13 <(ids $O/k-rust) <(ids $O/p-$pl) > $O/p-$pl.only.txt
  echo "convert:$pl: $(cut -d' ' -f2- $O/p-$pl/exit.txt | cut -c1-60); failing only under the plant: $(wc -l < $O/p-$pl.only.txt)" >> $O/plantrows.txt
done
echo "END $(date -u +%FT%TZ)" > $O/plantrows-end.txt
