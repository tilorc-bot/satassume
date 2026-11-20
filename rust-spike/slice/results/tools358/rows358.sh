# rows358.sh: the bar rows of plants 768-773, to source from the bar's job script (as CPP in results/tools334/job334.sh).
# Each `convert:NAME` row is routed by p1/bar.sh's penv: SLICE_CONVERT=rust SLICE_CONVERT_PLANT=NAME.
# 768 calls-structural-not, 769 power-rows-drop-last, 770 read-commutative-not, 771 entry-no-assumptions,
# 772 formula-and-as-or: wrong values in the tables or the reads, so the differential sees them (CONVERT_PLANTS, the
# bar's convdiff phase) as well as test_convert_walk.py::test_plant_is_caught[768..772] and the suite rows.
# 773 entry-skip-replaced: no workload replaces a definition of convert.py (only kept tests and the instrument
# lazy_reads.py do), so the differential can't see it. A kept-test catch: its suite row fails
# test_convert_walk.py::test_a_replaced_definition_is_called, and test_plant_773_is_caught holds in every row.
CPP358="convert:calls-structural-not convert:power-rows-drop-last convert:read-commutative-not convert:entry-no-assumptions convert:formula-and-as-or convert:entry-skip-replaced"
CONVERT_PLANTS358="calls-structural-not power-rows-drop-last read-commutative-not entry-no-assumptions formula-and-as-or"
