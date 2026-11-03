#!/bin/bash
# drive.sh CLONE OUTDIR SPEC...
CLONE=$1; OUT=$2; shift 2; mkdir -p $OUT
PY=~/dev/sa-eval/.venv/bin/python
ENVP=$(cd ~/dev/sa-eval && $PY -c "import os,sys;from evalbench.common import env_for;print(env_for(sys.argv[1])['PYTHONPATH'])" $CLONE)
for s in "$@"; do
  ( cd $(dirname $0) && PYTHONPATH=$ENVP:$HOME/dev/sa-eval PYTHONHASHSEED=0 $PY ${CHILD:-exh_child.py} $s ${MODE} $OUT/${s/:/_}${MODE:+-$MODE} > $OUT/${s/:/_}${MODE:+-$MODE}.log 2>&1 ) &
done
wait
