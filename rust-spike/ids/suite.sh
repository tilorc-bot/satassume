#!/bin/bash
# suite.sh NAME [ENV=VAL ...]: the test suite under one ids configuration, xdist -n 4. NAME=base runs without the plugin.
# Output in $W/suite-NAME.{log,xml}; last line of the log is the pytest summary.
. ~/sa-rust-ids-work/env.sh
name=$1; shift
cd ~/dev/sa-rust
export PYTHONPATH=$PYTHONPATH:$PWD/rust-spike/ids
plug="-p ids_plugin"; [ "$name" = base ] && plug=""
HYPOTHESIS_STORAGE_DIRECTORY=$W/hyp-$name env "$@" $PY -m pytest $plug ${IDS_N--n 4} -q --tb=short -p no:cacheprovider --junitxml=$W/suite-$name.xml -o junit_family=xunit2 tests > $W/suite-$name.log 2>&1
tail -1 $W/suite-$name.log
