#!/bin/bash
# Combined backend (satassume first, SymPy for every None) with fallbacks logged
export PATH=/work/.mamba/envs/sympy/bin:$PATH PYTHONHASHSEED=0
L=/work/src/facts-logs/scoreboard
PLUG=/work/src/perf-work/agent-reports/scripts
ENGINE=/work/src/perf-ref   # satassume at e43b318 (main); read-only reference clone
cd /work/src/refine-mono
run() {
  name=$1; shift
  d=$L/$name; mkdir -p $d; rm -f $d/info.txt
  echo "== $name start $(date +%T)"
  env "$@" PYTEST_ADDOPTS="-p facts_scoreboard_plugin" FACTS_SB_INFO=$d/info.txt FACTS_SB_QLOG=$d/queries.jsonl \
    timeout 900 python tools/refine_scoreboard.py --backends combined --junit-dir $d > $d/run.txt 2>&1
  echo "== $name end $(date +%T)"
}
for m in "$@"; do
  case $m in
    old) run combined-old PYTHONPATH=$PLUG:.:/work/src/sympy-pin ;;
    current) run combined-current PYTHONSAFEPATH=1 PYTHONPATH=$PLUG:$ENGINE:.:/work/src/sympy-pin ;;
    *) run combined-oracle-$m PYTHONSAFEPATH=1 PYTHONPATH=$PLUG:$L/oracle:$ENGINE:.:/work/src/sympy-pin FACTS_SB_MODE=$m ;;
  esac
done
echo ALLDONE
