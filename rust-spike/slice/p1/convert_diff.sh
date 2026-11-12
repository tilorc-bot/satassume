#!/bin/bash
# p1/convert_diff.sh OUT [PLANT]   the convert step's differential test (convert_diff.py, issue 323) on a whole run.
#
# Without PLANT: every input of the 20 workloads and of the suite is converted by both walkers (Python's `_Walk` and
# Rust's, every item on) and compared, every lazy read of every term included: OUT/total.txt has the number of inputs
# and of differences, and `exit 0` only when there are inputs and no difference. Then the answers: each workload on the
# Python backend, on the Rust backend with SLICE_CONVERT=py (the differential's own run) and with SLICE_CONVERT=rust,
# compared by livecmp.py: OUT/answers.txt, one line per workload and pair.
# With PLANT (a convert.WALK_PLANTS name): the differential alone under SLICE_CONVERT_PLANT, on PLANT_WLS (default dev
# fuzz). A plant is caught when total.txt says differences > 0 (exit 1); nothing here reads the plant.
# Needs PY, PYTHONPATH (the tree, sympy, the shim), SA_EVAL_DATA and PYTHONHASHSEED as p1/bar.sh exports them.
O=${1:?OUT}; PL=${2:-}; S=$(cd "$(dirname "$0")/.." && pwd); T=$(cd "$S/../.." && pwd); N=${N:-6}; P=${P:-6}
WLS=${WLS:-"f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls lra"}
if [ -n "$PL" ]; then export SLICE_CONVERT_PLANT=$PL; WLS=${PLANT_WLS:-"dev fuzz"}; fi
mkdir -p "$O"; cd "$S" || exit 2; export O
$PY -c 'import satassume, convert, sa_solver; print(satassume.__file__, convert.__file__, sa_solver.__file__)' > $O/tree.txt
printf '%s\n' $WLS | xargs -P $P -I{} bash -c 'n=$(echo {} | tr -d :); SLICE_CONVERT_DIFF=$O/wl-$n $PY live.py {} rust $O/$n-rust-cpy.jsonl --check entry > $O/$n-rust-cpy.tot 2> $O/$n-rust-cpy.err; echo "{} exit $?" >> $O/wl-exit.txt'
if [ -z "$PL" ]; then
  ( export SLICE_CONVERT_DIFF=$O/suite SLICE_SUITE_OUT=$O/suite-rows SLICE_SUITE_BACKEND=rust PYTHONPATH=$PYTHONPATH:$S HYPOTHESIS_STORAGE_DIRECTORY=$O/hyp
    mkdir -p $O/suite-rows; cd "$T" || exit 2
    $PY -m pytest -p rust_plugin -p handler_count -p plant_count -n $N -q --tb=short -p no:cacheprovider tests > $O/suite-pytest.log 2>&1; echo "$? $(tail -n 1 $O/suite-pytest.log)" > $O/suite-exit.txt )
fi
$PY convert_diff.py $O/wl-* $O/suite > $O/total.txt 2>&1; echo "exit $?" >> $O/total.txt
[ -n "$PL" ] && exit 0
printf '%s\n' $WLS | xargs -P $P -I{} bash -c 'n=$(echo {} | tr -d :); $PY live.py {} py $O/$n-py.jsonl --check entry > $O/$n-py.tot 2> $O/$n-py.err; SLICE_CONVERT=rust $PY live.py {} rust $O/$n-rust-crust.jsonl --check entry > $O/$n-rust-crust.tot 2> $O/$n-rust-crust.err
  for pair in "py rust-crust" "py rust-cpy" "rust-cpy rust-crust"; do set -- $pair; echo "{} $1 vs $2: $($PY livecmp.py $O/$n-$1.jsonl $O/$n-$2.jsonl 2>&1 | tail -n 1 | cut -c1-80)"; done >> $O/answers.txt'
echo "workloads $(echo $WLS | wc -w); answer rows $(wc -l < $O/answers.txt), MATCH $(grep -c ': MATCH$' $O/answers.txt)" >> $O/total.txt
