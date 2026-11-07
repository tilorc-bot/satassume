#!/bin/bash
# On orion, detached: sync, build under a shared lease, then the quiet lease with retries until DEADLINE (epoch seconds). Fetches the results.
C=$(cd "$(dirname "$0")/../../.." && pwd); O=~/sa-rust-ids-work/sa-port-80/raw/floor; mkdir -p $O; DEADLINE=$1; NAME=floor1
cd $C; H=$(git rev-parse HEAD)
ssh pareto1 'mkdir -p ~/sa-rust-ids-work/sa-port-80/bench/tree ~/sa-rust-ids-work/sa-port-80/bench/tools; rm -rf ~/sa-rust-ids-work/sa-port-80/bench/tree/*'
git archive HEAD | ssh pareto1 'tar -x -C ~/sa-rust-ids-work/sa-port-80/bench/tree'
ssh pareto1 "echo $H > ~/sa-rust-ids-work/sa-port-80/bench/TREESHA"
scp -q rust-spike/slice/conv_floor/{prep80.sh,onlease80.sh,run_floor.sh} pareto1:sa-rust-ids-work/sa-port-80/bench/tools/
machine run pareto1 --shared --wait 1h -r "sa-port-80 build conv-floor prototype" -- bash sa-rust-ids-work/sa-port-80/bench/tools/prep80.sh > $O/prep.log 2>&1 || { echo "prep failed"; tail -3 $O/prep.log; exit 2; }
tail -1 $O/prep.log
rc=1
while [ $(date +%s) -lt $DEADLINE ]; do
  machine run pareto1 --quiet -r "sa-port-80 conversion floor, 6 rounds of 6 arms" -- bash sa-rust-ids-work/sa-port-80/bench/tools/onlease80.sh $NAME > $O/lease.log 2>&1; rc=$?
  ssh pareto1 "test -e ~/sa-rust-ids-work/sa-port-80/bench/results/$NAME/progress" && break
  ssh pareto1 "test -d ~/sa-rust-ids-work/sa-port-80/bench/results/$NAME && rm -rf ~/sa-rust-ids-work/sa-port-80/bench/results/$NAME"
  sleep 300
done
scp -q -r pareto1:sa-rust-ids-work/sa-port-80/bench/results/$NAME/. $O/ 2>/dev/null
echo "lease rc=$rc; $(tail -1 $O/progress 2>/dev/null); $(wc -l < $O/floor.jsonl 2>/dev/null) rows"
