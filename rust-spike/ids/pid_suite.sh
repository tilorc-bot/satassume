#!/bin/bash
# pid_suite.sh NAME [pytest args]: the test suite of the P-id copy, in the copy, no plugin. Output in $W/suite-NAME.{log,xml}.
. ~/sa-rust-ids-work/env.sh
name=$1; shift
cd $W/pid
export PYTHONPATH=$W/pid:$W/sympy:$W/shim
HYPOTHESIS_STORAGE_DIRECTORY=$W/hyp-$name $PY -m pytest "$@" -q --tb=short -p no:cacheprovider --junitxml=$W/suite-$name.xml -o junit_family=xunit2 tests > $W/suite-$name.log 2>&1
tail -1 $W/suite-$name.log
