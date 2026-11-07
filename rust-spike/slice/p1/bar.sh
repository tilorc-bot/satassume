#!/bin/bash
# bar.sh NAME BRANCH [PHASE...]   the planner's landing bar for one sa-port step, on pareto1 under ~/sp19.
# bar.sh land TESTED_SHA          on orion, in your clone: rebase on origin/rust-slice, print the incoming diff; PUSH=1 pushes.
#
# One parameterised script in place of the job/land/plant/sum scripts each session rewrote (sa-port-89's and -91's).
# It prints every command it runs, with a UTC time, to stdout and to $B/commands.txt, and records the tested SHA, the
# .so's sha256 and the tree each run imported. It reports the bar's numbers (the `sum` phase, bar_sum.py) and never
# decides pass or fail: the worker reads and states each of the five bar items. A phase that didn't run is listed as
# not run in the summary.
#
# Run from orion:  scp rust-spike/slice/p1/bar.sh pareto1:sp19/bar-NAME.sh
#                  machine run pareto1 --shared --wait 4h -r WHY -- setsid bash ~/sp19/bar-NAME.sh NAME BRANCH
# Phases, in this order (default: all):
#   build        cargo build of the clone's crate (x86-64), copied to rust-spike/slice/sa_solver.so
#   tests        TESTS by pytest and DIRECT scripts, in rust-spike/slice
#   suite        the suite with rust_plugin and handler_count, rows in $B/suite                     (bar 1, 4)
#   live         run_live.sh: dev and fuzz, Python twice and Rust, traced and untraced              (bar 2)
#   plants       each of PLANTS on dev and fuzz against this run's Python                           (bar 3)
#   seed1        dev and fuzz at PYTHONHASHSEED=1, Python against Rust (only if SEED1=1)
#   suiteplants  SUITE_PLANTS on the suite; the word `zero` stands for every PLANTS entry that fired 0 on both workloads
#   sum          bar_sum.py: the numbers, against BASE's suite rows
# Environment:
#   BASE          base suite rows (default: the last landing's, sa-port-91's, which rust-slice de8bd3a carries)
#   PLANTS        SLICE_SESSION_PLANT names for dev and fuzz
#   SUITE_PLANTS  plants also run on the suite (may contain `zero`)
#   TESTS         test files in rust-spike/slice, one pytest run (default test_session_limits.py)
#   DIRECT        scripts with arguments, ';'-separated, each run in rust-spike/slice (e.g. "relations_direct.py 300 0")
#   N             pytest -n for the suite (default 8)
#   OUT           output directory (default ~/sp19/sa-rust-ids-work/NAME)
set -u
if [ "${1:-}" = land ]; then
  TESTED=${2:?tested SHA}
  run() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$1"; eval "$1"; }
  run "git fetch -q origin"
  echo "tested $TESTED; its base $(git merge-base $TESTED origin/rust-slice); origin/rust-slice $(git rev-parse --short origin/rust-slice)"
  run "git diff --stat $(git merge-base $TESTED origin/rust-slice) origin/rust-slice | tail -20"
  run "git rebase origin/rust-slice" || exit 1
  echo "landing source $(git rev-parse --short HEAD); diff tested..landing, files:"
  run "git diff --stat $TESTED HEAD | tail -20"
  if [ "${PUSH:-0}" = 1 ]; then
    run "git push origin HEAD:rust-slice" && echo "landed $(git rev-parse --short HEAD) on rust-slice"
    run "git push -f origin HEAD:$(git rev-parse --abbrev-ref HEAD)"
  else
    echo "not pushed (PUSH=1 pushes)"
  fi
  exit 0
fi

NAME=${1:?NAME}; BR=${2:?BRANCH}; shift 2
PHASES=${*:-build tests suite live plants seed1 suiteplants sum}
export REAL=/home/tilo CARGO_HOME=/home/tilo/.cargo RUSTUP_HOME=/home/tilo/.rustup PATH=/home/tilo/.cargo/bin:$PATH HOME=/home/tilo/sp19
export T=$HOME/dev/$NAME S=$HOME/dev/$NAME/rust-spike/slice B=${OUT:-$HOME/sa-rust-ids-work/$NAME}
BASE=${BASE:-$HOME/sa-rust-ids-work/sa-port-91/suite}
PLANTS=${PLANTS:-}; SUITE_PLANTS=${SUITE_PLANTS:-}; TESTS=${TESTS:-test_session_limits.py}; DIRECT=${DIRECT:-}; N=${N:-8}
mkdir -p $B; CMDS=$B/commands.txt
. $HOME/sa-rust-ids-work/env.sh
export PY W SA_EVAL_DATA PYTHONHASHSEED PYTHONPATH=$T:$W/sympy:$W/shim
run() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$1" | tee -a $CMDS; eval "$1"; }
phase() { echo "$1 $(date -u +%FT%TZ) exit ${2:-0}" >> $B/phases.txt; }

echo "== bar.sh $NAME $BR phases: $PHASES; script sha256 $(sha256sum "$0" | cut -c1-12)" | tee -a $CMDS
[ -d $T/.git ] || run "git clone -q https://github.com/tilorc-bot/satassume $T"
run "cd $T && git fetch -q origin && git checkout -q -f -B $BR origin/$BR && git rev-parse --short HEAD > $B/source.txt"
echo "tested source $(cat $B/source.txt), rows under $B, base rows $BASE" | tee -a $CMDS
printf 'BASE=%s\nPLANTS=%s\nSUITE_PLANTS=%s\nTESTS=%s\nDIRECT=%s\nN=%s\n' "$BASE" "$PLANTS" "$SUITE_PLANTS" "$TESTS" "$DIRECT" "$N" > $B/config.txt
cd $S

suite() { # suite DIR [PLANT]
  local O=$1
  run "rm -rf $O; mkdir -p $O"
  run "( ${2:+export SLICE_SESSION_PLANT=$2; }export SLICE_SUITE_OUT=$O SLICE_SUITE_BACKEND=rust PYTHONPATH=\$PYTHONPATH:$S HYPOTHESIS_STORAGE_DIRECTORY=$O/hyp; cd $T; \$PY -c 'import satassume; print(satassume.__file__)' > $O/tree.txt; \$PY -m pytest -p rust_plugin -p handler_count -p plant_count -n $N -q --tb=short -p no:cacheprovider tests > $O/pytest.log 2>&1; echo \"\$? \$(tail -1 $O/pytest.log)\" > $O/exit.txt )"
}
fired() { # fired WL PLANT: the larger of the Python-side and Rust-side counts in the plant run's session report
  $PY -c "import json,sys; d=json.load(open(sys.argv[1])); print(max(d.get('plant_fired',0), d.get('counts',{}).get('rel:plant_fired',0)))" $B/live/plant-$1-$2.session.json 2>/dev/null || echo 0
}

for ph in $PHASES; do case $ph in
build)
  run "cd $S/solver_rs && CARGO_TARGET_DIR=$B/target PYO3_PYTHON=\$PY cargo build --release 2>&1 | tail -1 > $B/build.txt; cd $S"
  run "cp $B/target/release/libsa_solver.so $S/sa_solver.so && sha256sum $S/sa_solver.so >> $B/build.txt"
  phase build $?;;
tests)
  run "\$PY -m pytest $TESTS -q --tb=short -p no:cacheprovider > $B/tests.txt 2>&1; echo \"exit \$?\" >> $B/tests.txt"
  : > $B/direct.txt
  IFS=';' read -ra DS <<< "$DIRECT"
  for d in "${DS[@]}"; do [ -n "${d// /}" ] && run "echo '== $d' >> $B/direct.txt; \$PY $d >> $B/direct.txt 2>&1; echo \"exit \$?\" >> $B/direct.txt"; done
  phase tests;;
suite) suite $B/suite; phase suite;;
live) run "rm -rf $B/live; sh $S/run_live.sh $B/live entry"; phase live;;
plants)
  for wl in dev fuzz; do for pl in $PLANTS; do echo "$wl $pl"; done; done > $B/plants.todo
  run "xargs -P 10 -L 1 bash -c 'wl=\$0; pl=\$1; L=$B/live; SLICE_SESSION_PLANT=\$pl SESSION_REPORT=\$L/plant-\$wl-\$pl.session.json \$PY live.py \$wl rust \$L/plant-\$wl-\$pl.jsonl --check entry > \$L/plant-\$wl-\$pl.tot 2> \$L/plant-\$wl-\$pl.err; \$PY livecmp.py \$L/\$wl-py.jsonl \$L/plant-\$wl-\$pl.jsonl > \$L/plant-\$wl-\$pl.cmp 2>&1' < $B/plants.todo"
  phase plants;;
seed1)
  [ "${SEED1:-0}" = 1 ] || continue
  for wl in dev fuzz; do
    run "( PYTHONHASHSEED=1 \$PY live.py $wl py $B/live/seedx-$wl-py.jsonl --check entry > $B/live/seedx-$wl-py.tot 2> $B/live/seedx-$wl-py.err ) & ( PYTHONHASHSEED=1 SESSION_REPORT=$B/live/seedx-$wl-rust.session.json \$PY live.py $wl rust $B/live/seedx-$wl-rust.jsonl --check entry > $B/live/seedx-$wl-rust.tot 2> $B/live/seedx-$wl-rust.err ) & wait"
    run "\$PY livecmp.py $B/live/seedx-$wl-py.jsonl $B/live/seedx-$wl-rust.jsonl > $B/live/seedx-$wl.cmp 2>&1"
  done
  phase seed1;;
suiteplants)
  : > $B/suite-plants.txt
  for pl in $SUITE_PLANTS; do
    if [ $pl = zero ]; then
      for p in $PLANTS; do [ "$(fired dev $p)" = 0 ] && [ "$(fired fuzz $p)" = 0 ] && echo $p >> $B/suite-plants.txt; done
    else echo $pl >> $B/suite-plants.txt; fi
  done
  for pl in $(sort -u $B/suite-plants.txt); do suite $B/suite-$pl $pl; done
  phase suiteplants;;
sum) run "\$PY $S/p1/bar_sum.py $B $BASE > $B/sum.txt 2>&1; cat $B/sum.txt"; phase sum;;
*) echo "unknown phase $ph" | tee -a $CMDS;;
esac; done
date -u > $B/done.txt
