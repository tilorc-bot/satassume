#!/bin/bash
# Not timed. Digests, counts and shuffled-order replays for base and the P-id copy, on orion.
. ~/sa-rust-ids-work/env.sh
D=$HOME/dev/sa-rust/rust-spike/ids
PIDP=$W/pid:$W/sympy:$W/shim
BASEP=$PYTHONPATH
R=$W/pid-results; mkdir -p $R
for wl in dev fuzz; do
  PYTHONPATH=$BASEP $PY $D/pid_count.py $wl recorded > $R/count-base-$wl.json &
  PYTHONPATH=$PIDP $PY $D/pid_count.py $wl recorded > $R/count-pid-$wl.json &
  PYTHONPATH=$PIDP $PY $HOME/dev/sa-rust/tools-rust/rc.py mon $wl > $R/mon-pid-$wl.json &
  for s in 7 11 13; do PYTHONPATH=$PIDP $PY $D/pid_count.py $wl shuffled:$s > $R/count-pid-$wl-s$s.json & done
  wait
done
PYTHONPATH=$PIDP $PY $D/inventory.py fuzz $R/inv-pid-fuzz.json > $R/inv-pid-fuzz.log 2>&1 &
PYTHONPATH=$PIDP $PY $D/inventory.py dev $R/inv-pid-dev.json > $R/inv-pid-dev.log 2>&1 &
wait
