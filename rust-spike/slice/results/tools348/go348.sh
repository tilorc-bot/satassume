#!/bin/bash
# go348.sh NEW BASE JBASE (sa-port-348, orion, under setsid; tools347/go347.sh without the arm at 8400, output under sa-port-348): the gate of NEW on pareto0 under ONE
# shared lease: job347.sh (the suite by id on/off on NEW and base on BASE, the digests and test_witness.py under every
# plant, iv), then jobb348.sh (the 20 workloads at the default bound, budget's stats rows, the fuzz seeds;
# JBASE's rows are sa-port-343's on pareto0, copied first). The small outputs are copied back to
# ~/sa-rust-ids-work/sa-port-348 and the suite and iv comparisons run on orion.
# End marker: sa-port-348/go-end.txt, the last line here.
X=~/sa-rust-ids-work/sa-port-348; R=/home/tilo/sp19/sa-rust-ids-work/sa-port-348; NEW=$1; BASE=$2; JBASE=$3
OLD=/home/tilo/sp19/sa-rust-ids-work/sa-port-343/jobb-$JBASE
ssh pareto0 "set -e; mkdir -p $R/jobb-$NEW/fz; cp -a $OLD/gate-$JBASE $R/jobb-$NEW/; cp -a $OLD/fz/$JBASE-* $R/jobb-$NEW/fz/" || { echo "END copy-failed $(date -u +%FT%TZ)" > $X/go-end.txt; exit 1; }
machine run pareto0 --shared --wait 4h -r "sa-port-348: witness bounds (issue 323): suite by id, digests, iv, 20 workloads and fuzz seeds on $NEW (ruling B), about 70 minutes" -- bash -c "bash $R/s1/tools/job347.sh $R $NEW $BASE; bash $R/s1/tools/jobb348.sh $R $NEW $JBASE" > $X/job.log 2>&1
rc=$?
ssh pareto0 "tar -c -C $R --exclude hyp --exclude .hypothesis job-$NEW" | tar -x -C $X
ssh pareto0 "tar -c -C $R --exclude '*.jsonl' --exclude '*.json' jobb-$NEW" | tar -x -C $X
. ~/sa-rust-ids-work/env.sh
$PY $X/tools/cmp329.py $X/job-$NEW > $X/job-$NEW/suite-cmp.txt 2>&1
$PY $X/tools/ivcmp329.py $X/job-$NEW/iv > $X/job-$NEW/iv-cmp.txt 2>&1
echo "END $rc $(date -u +%FT%TZ)" > $X/go-end.txt
