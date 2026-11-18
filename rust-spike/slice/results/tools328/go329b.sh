#!/bin/bash
# go329b.sh (sa-port-329, orion, detached): after go329.sh has ended, on pareto1 under a shared lease: the 20-workload
# answers gate on the staged 5e6e46a, then the same with plant 751 (skip-own). Orion end marker: gob-end.txt.
X=~/sa-rust-ids-work/sa-port-329; G=$X/s1
while [ ! -e $X/go-end.txt ]; do sleep 20; done
rsync -a --exclude __pycache__ ~/sa-rust-ids-work/sa-port-328/wt/rust-spike/slice/results/tools328/ pareto1:$G/tools/
machine run pareto1 --shared --wait 4h -r "sa-port-329: witness check (issue 323): 20-workload answers gate on/off, then with plant 751" -- bash -c "bash $G/tools/gate329.sh 5e6e46a gate; bash $G/tools/gate329.sh 5e6e46a gate-751 skip-own" > $X/gate.log 2>&1
rc=$?
rsync -a pareto1:$X/job/gate pareto1:$X/job/gate-751 $X/job/
echo "END $rc $(date -u +%FT%TZ)" > $X/gob-end.txt
