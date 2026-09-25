#!/bin/bash
# Stage 0 scoreboard runs (satassume backend only; sympy junit reused from base/)
export PATH=/work/.mamba/envs/sympy/bin:$PATH PYTHONHASHSEED=0
L=/work/src/facts-logs/scoreboard
PLUG=/work/src/perf-work/agent-reports/scripts
ENGINE=/work/src/perf-ref   # satassume at e43b318 (main); read-only reference clone
cd /work/src/refine-mono
run() {  # name, extra env...
  name=$1; shift
  d=$L/$name; mkdir -p $d; rm -f $d/info.txt
  echo "== $name start $(date +%T)"
  env "$@" PYTEST_ADDOPTS="-p facts_scoreboard_plugin" FACTS_SB_INFO=$d/info.txt FACTS_SB_QLOG=$d/queries.jsonl \
    timeout 600 python tools/refine_scoreboard.py --backends satassume --junit-dir $d > $d/run.txt 2>&1
  cp $L/base/junit-sympy.xml $d/
  PYTHONPATH=.:/work/src/sympy-pin python tools/refine_scoreboard.py --backends sympy,satassume --reuse $d --show-failures satassume > $d/scoreboard.txt 2>&1
  echo "== $name end $(date +%T)"
}
if [ -n "$1" ]; then MODES="$*"; else MODES="old current base transfer free both"; fi
for m in $MODES; do
  case $m in
    old) run old PYTHONPATH=$PLUG:.:/work/src/sympy-pin ;;
    current) run current PYTHONSAFEPATH=1 PYTHONPATH=$PLUG:$ENGINE:.:/work/src/sympy-pin ;;
    *) run oracle-$m PYTHONSAFEPATH=1 PYTHONPATH=$PLUG:$L/oracle:$ENGINE:.:/work/src/sympy-pin FACTS_SB_MODE=$m FACTS_SB_VERIFY=$L/oracle-$m/verify.jsonl ;;
  esac
done
echo ALLDONE
