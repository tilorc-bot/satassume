#!/bin/bash
# chain366.sh NEW BASE (sa-port-366, orion, under setsid): stage366.sh (the trees and both builds of NEW on pareto1), then
# gos1366.sh (S1 under one quiet lease, first, so nothing of this session shares the machine with it), then go366.sh (the
# gate under one shared lease; it finds the staging done). Each writes its own end marker; this one's is
# sa-port-366/chain-end.txt, the last line here.
X=~/sa-rust-ids-work/sa-port-366; T=$X/wt/rust-spike/slice/results/tools366; NEW=$1; BASE=$2
bash $T/stage366.sh $NEW $BASE > $X/stage.out 2>&1
grep -q "^END staged $NEW $BASE" $X/stage-$NEW.txt || { echo "END stage-failed $(date -u +%FT%TZ)" > $X/chain-end.txt; exit 1; }
bash $T/gos1366.sh $NEW $BASE > $X/gos1.out 2>&1
bash $T/go366.sh $NEW $BASE > $X/go.out 2>&1
echo "END $(date -u +%FT%TZ) s1: $(cat $X/gos1-end.txt) gate: $(cat $X/go-end.txt)" > $X/chain-end.txt
