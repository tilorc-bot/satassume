#!/bin/bash
# bar.sh NAME BRANCH [PHASE...]   the planner's landing bar for one sa-port step, on pareto1 under ~/sp19.
# bar.sh land TESTED_SHA          on orion, in your clone: rebase on origin/rust-slice, print the incoming diff; PUSH=1 pushes,
#                                 refused when satassume/ or rust-spike/slice/ source (not results/) differs from TESTED.
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
#   extra        each of WLS (live.py workloads, e.g. a hidden-gap one) like live and plants: Python twice, Rust, each of
#                PLANTS; rows in $B/extra                                                          (bar 2, 3; gaps ruling)
#   suiteplants  SUITE_PLANTS on the suite; the word `zero` stands for every PLANTS entry that fired 0 on both workloads
#   fmrows       fm_rows.py on each of FM_WLS: formula's conversion row per workload against results/fm_rows.json
#                ($B/fmrows/check.txt, exit 1 on any difference); then the same under each of FM_PLANTS
#                ($B/fmrows-PLANT/check.txt: a plant is caught there when its check exits 1; its own counter is not read)
#   sum          bar_sum.py: the numbers, against BASE's suite rows
# Environment:
#   BASE          base suite rows (default: the last landing's, sa-port-91's, which rust-slice de8bd3a carries)
#   PLANTS        SLICE_SESSION_PLANT names for dev and fuzz; `term:NAME` is SLICE_TERM_PLANT=NAME instead (term_live's
#                 plants, e.g. term:mark-wrong-pattern, plant 666); the same in SUITE_PLANTS and FM_PLANTS
#   SUITE_PLANTS  plants also run on the suite (may contain `zero`)
#   TESTS         test files in rust-spike/slice, one pytest run (default test_session_limits.py)
#   TESTS_SPLIT   1: one pytest process per file, logs in $B/tests/, a line per file in tests.txt; TESTS=all is every test_*.py
#                 test_handler_count.py, test_catch_count.py and test_cf_diff.py run as p1/one_test.sh says (4f)
#   DIRECT        scripts with arguments, ';'-separated, each run in rust-spike/slice (e.g. "relations_direct.py 300 0")
#   N             pytest -n for the suite (default 8)
#   WLS           live.py workloads for the extra phase (default none: the phase is listed as not run)
#   FM_WLS        live.py workloads for the fmrows phase (default none: the phase is listed as not run)
#   FM_PLANTS     SLICE_SESSION_PLANT names run by the fmrows phase on FM_WLS
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
  # Push guard (planner's ruling, 8 Nov): the landed source must be the tested source. Any file under
  # satassume/ or rust-spike/slice/ (results/ excepted) that differs between TESTED and the rebased HEAD,
  # whether it came in with the rebase or was edited after the bar, needs a full bar on HEAD first.
  GUARD=$(git diff --name-only $TESTED HEAD -- satassume rust-spike/slice ':(exclude)rust-spike/slice/results')
  if [ -n "$GUARD" ]; then
    echo "source differs between tested $TESTED and landing $(git rev-parse --short HEAD) in:"
    echo "$GUARD" | sed 's/^/  /'
    if [ "${PUSH:-0}" = 1 ]; then
      echo "REFUSED: PUSH=1 needs a full bar on $(git rev-parse --short HEAD) (bar.sh land $(git rev-parse --short HEAD) after it)"
      exit 2
    fi
  fi
  if [ "${PUSH:-0}" = 1 ]; then
    run "git push origin HEAD:rust-slice" && echo "landed $(git rev-parse --short HEAD) on rust-slice"
    run "git push -f origin HEAD:$(git rev-parse --abbrev-ref HEAD)"
  else
    echo "not pushed (PUSH=1 pushes)"
  fi
  exit 0
fi

NAME=${1:?NAME}; BR=${2:?BRANCH}; shift 2
PHASES=${*:-build tests suite live plants seed1 extra suiteplants fmrows sum}
export REAL=/home/tilo CARGO_HOME=/home/tilo/.cargo RUSTUP_HOME=/home/tilo/.rustup PATH=/home/tilo/.cargo/bin:$PATH HOME=/home/tilo/sp19
export T=$HOME/dev/$NAME S=$HOME/dev/$NAME/rust-spike/slice B=${OUT:-$HOME/sa-rust-ids-work/$NAME}
BASE=${BASE:-$HOME/sa-rust-ids-work/sa-port-91/suite}
PLANTS=${PLANTS:-}; WLS=${WLS:-}; SUITE_PLANTS=${SUITE_PLANTS:-}; TESTS=${TESTS:-test_session_limits.py}; DIRECT=${DIRECT:-}; N=${N:-8}
mkdir -p $B; CMDS=$B/commands.txt
. $HOME/sa-rust-ids-work/env.sh
export PY W SA_EVAL_DATA PYTHONHASHSEED PYTHONPATH=$T:$W/sympy:$W/shim
run() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$1" | tee -a $CMDS; eval "$1"; }
phase() { echo "$1 $(date -u +%FT%TZ) exit ${2:-0}" >> $B/phases.txt; }
# penv PLANT: the variable that carries a plant: term_live's (`term:NAME`) or session_live's (everything else)
penv() { case $1 in term:*) echo "SLICE_TERM_PLANT=${1#term:}";; *) echo "SLICE_SESSION_PLANT=$1";; esac; }
export -f penv

echo "== bar.sh $NAME $BR phases: $PHASES; script sha256 $(sha256sum "$0" | cut -c1-12)" | tee -a $CMDS
[ -d $T/.git ] || run "git clone -q https://github.com/tilorc-bot/satassume $T"
run "cd $T && git fetch -q origin && git checkout -q -f -B $BR origin/$BR && git rev-parse --short HEAD > $B/source.txt"
echo "tested source $(cat $B/source.txt), rows under $B, base rows $BASE" | tee -a $CMDS
printf 'BASE=%s\nPLANTS=%s\nWLS=%s\nSUITE_PLANTS=%s\nTESTS=%s\nDIRECT=%s\nN=%s\n' "$BASE" "$PLANTS" "$WLS" "$SUITE_PLANTS" "$TESTS" "$DIRECT" "$N" > $B/config.txt
cd $S

suite() { # suite DIR [PLANT]
  local O=$1
  run "rm -rf $O; mkdir -p $O"
  run "( ${2:+export $(penv $2); }export SLICE_SUITE_OUT=$O SLICE_SUITE_BACKEND=rust PYTHONPATH=\$PYTHONPATH:$S HYPOTHESIS_STORAGE_DIRECTORY=$O/hyp; cd $T; \$PY -c 'import satassume; print(satassume.__file__)' > $O/tree.txt; \$PY -m pytest -p rust_plugin -p handler_count -p plant_count -n $N -q --tb=short -p no:cacheprovider tests > $O/pytest.log 2>&1; echo \"\$? \$(tail -1 $O/pytest.log)\" > $O/exit.txt )"
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
  if [ "${TESTS_SPLIT:-0}" = 1 ]; then
    # one pytest process per file (install() refuses once another file's Engine exists); a line per file in tests.txt
    [ "$TESTS" = all ] && TESTS=$(ls test_*.py | tr '\n' ' ')
    run "rm -rf $B/tests; mkdir -p $B/tests; : > $B/tests.txt"
    run "printf '%s\n' $TESTS | PYTHONPATH=\$PYTHONPATH:$S xargs -P 4 -I{} bash $S/p1/one_test.sh {} $B/tests/{}.log >> $B/tests.txt"
    run "echo \"files \$(wc -l < $B/tests.txt); not exit 0: \$(grep -v ' exit 0 ' $B/tests.txt | cut -d' ' -f1 | sort | tr '\n' ' ')\" >> $B/tests.txt"
  else
    # 4f: the files with their own invocation (p1/one_test.sh) run on their own, after the one pytest run of the rest
    OWN=$(printf '%s\n' $TESTS | grep -xE 'test_(handler_count|catch_count|cf_diff)\.py' | tr '\n' ' ')
    REST=$(printf '%s\n' $TESTS | grep -vxE 'test_(handler_count|catch_count|cf_diff)\.py' | tr '\n' ' ')
    : > $B/tests.txt
    [ -n "${REST// /}" ] && run "PYTHONPATH=\$PYTHONPATH:$S \$PY -m pytest $REST -q --tb=short -p no:cacheprovider > $B/tests.txt 2>&1; echo \"exit \$?\" >> $B/tests.txt"
    for f in $OWN; do mkdir -p $B/tests; run "PYTHONPATH=\$PYTHONPATH:$S bash $S/p1/one_test.sh $f $B/tests/$f.log >> $B/tests.txt"; done
  fi
  : > $B/direct.txt
  IFS=';' read -ra DS <<< "$DIRECT"
  for d in "${DS[@]}"; do [ -n "${d// /}" ] && run "echo '== $d' >> $B/direct.txt; \$PY $d >> $B/direct.txt 2>&1; echo \"exit \$?\" >> $B/direct.txt"; done
  phase tests;;
suite) suite $B/suite; phase suite;;
live) run "rm -rf $B/live; sh $S/run_live.sh $B/live entry"; phase live;;
plants)
  for wl in dev fuzz; do for pl in $PLANTS; do echo "$wl $pl"; done; done > $B/plants.todo
  run "xargs -P 10 -L 1 bash -c 'wl=\$0; pl=\$1; L=$B/live; env \$(penv \$pl) SESSION_REPORT=\$L/plant-\$wl-\$pl.session.json \$PY live.py \$wl rust \$L/plant-\$wl-\$pl.jsonl --check entry > \$L/plant-\$wl-\$pl.tot 2> \$L/plant-\$wl-\$pl.err; \$PY livecmp.py \$L/\$wl-py.jsonl \$L/plant-\$wl-\$pl.jsonl > \$L/plant-\$wl-\$pl.cmp 2>&1' < $B/plants.todo"
  phase plants;;
seed1)
  [ "${SEED1:-0}" = 1 ] || continue
  for wl in dev fuzz; do
    run "( PYTHONHASHSEED=1 \$PY live.py $wl py $B/live/seedx-$wl-py.jsonl --check entry > $B/live/seedx-$wl-py.tot 2> $B/live/seedx-$wl-py.err ) & ( PYTHONHASHSEED=1 SESSION_REPORT=$B/live/seedx-$wl-rust.session.json \$PY live.py $wl rust $B/live/seedx-$wl-rust.jsonl --check entry > $B/live/seedx-$wl-rust.tot 2> $B/live/seedx-$wl-rust.err ) & wait"
    run "\$PY livecmp.py $B/live/seedx-$wl-py.jsonl $B/live/seedx-$wl-rust.jsonl > $B/live/seedx-$wl.cmp 2>&1"
  done
  phase seed1;;
extra)
  [ -n "$WLS" ] || continue
  X=$B/extra; run "rm -rf $X; mkdir -p $X"
  for wl in $WLS; do
    run "( \$PY live.py $wl py $X/$wl-py.jsonl --check entry > $X/$wl-py.tot 2> $X/$wl-py.err ) & ( \$PY live.py $wl py $X/$wl-py2.jsonl --check entry > $X/$wl-py2.tot 2> $X/$wl-py2.err ) & ( SESSION_REPORT=$X/$wl-rust.session.json \$PY live.py $wl rust $X/$wl-rust.jsonl --handlers $X/$wl-rust.handlers --check entry > $X/$wl-rust.tot 2> $X/$wl-rust.err ) & wait"
    run "{ echo '== $wl py vs py (control)'; \$PY livecmp.py $X/$wl-py.jsonl $X/$wl-py2.jsonl; echo '== $wl py vs rust'; \$PY livecmp.py $X/$wl-py.jsonl $X/$wl-rust.jsonl; } >> $X/summary.txt 2>&1"
    for pl in $PLANTS; do echo "$wl $pl"; done > $X/plants.todo
    run "xargs -P 10 -L 1 bash -c 'wl=\$0; pl=\$1; env \$(penv \$pl) SESSION_REPORT=$X/plant-\$wl-\$pl.session.json \$PY live.py \$wl rust $X/plant-\$wl-\$pl.jsonl --check entry > $X/plant-\$wl-\$pl.tot 2> $X/plant-\$wl-\$pl.err; \$PY livecmp.py $X/\$wl-py.jsonl $X/plant-\$wl-\$pl.jsonl > $X/plant-\$wl-\$pl.cmp 2>&1' < $X/plants.todo"
  done
  phase extra;;
suiteplants)
  : > $B/suite-plants.txt
  for pl in $SUITE_PLANTS; do
    if [ $pl = zero ]; then
      for p in $PLANTS; do [ "$(fired dev $p)" = 0 ] && [ "$(fired fuzz $p)" = 0 ] && echo $p >> $B/suite-plants.txt; done
    else echo $pl >> $B/suite-plants.txt; fi
  done
  for pl in $(sort -u $B/suite-plants.txt); do suite $B/suite-$pl $pl; done
  phase suiteplants;;
fmrows)
  [ -n "${FM_WLS:-}" ] || continue
  fmrows() { # fmrows DIR [PLANT]
    run "rm -rf $1; mkdir -p $1"
    run "printf '%s\n' $FM_WLS | ${2:+env $(penv $2) }xargs -P 6 -I{} bash -c 'n=\$(echo {} | tr -d :); \$PY fm_rows.py run $1/\$n.row.json {} > $1/\$n.tot 2> $1/\$n.err'"
    run "\$PY fm_rows.py check $1 > $1/check.txt 2>&1; echo \"exit \$?\" >> $1/check.txt; tail -n 2 $1/check.txt"
  }
  fmrows $B/fmrows
  for pl in ${FM_PLANTS:-}; do fmrows $B/fmrows-$pl $pl; done
  phase fmrows;;
sum) run "\$PY $S/p1/bar_sum.py $B $BASE > $B/sum.txt 2>&1; cat $B/sum.txt"; phase sum;;
*) echo "unknown phase $ph" | tee -a $CMDS;;
esac; done
date -u > $B/done.txt
