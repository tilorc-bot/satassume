#!/bin/bash
# go343.sh NEW BASE (sa-port-343, orion, under setsid): the gate of NEW against BASE on pareto0 under ONE shared lease:
# tools342/job342.sh (the suite by id on/off/base, the digests and test_witness.py under every plant, iv), then
# jobb343.sh (the 20 workloads and the fuzz seeds on NEW; BASE's rows are sa-port-342's from pareto1, copied here first).
# The small outputs are copied back to ~/sa-rust-ids-work/sa-port-343 and the suite and iv comparisons run on orion.
# End marker: sa-port-343/go-end.txt, the last line here.
X=~/sa-rust-ids-work/sa-port-343; R=/home/tilo/sp19/sa-rust-ids-work/sa-port-343; NEW=$1; BASE=$2
OLD=/home/tilo/sp19/sa-rust-ids-work/sa-port-342/jobb-dfb544e6
ssh pareto0 "mkdir -p $R/jobb-$NEW/fz" && ssh pareto1 "tar -c -C $OLD gate-$BASE \$(cd $OLD && ls fz | grep ^$BASE- | sed s,^,fz/,)" | ssh pareto0 "tar -x -C $R/jobb-$NEW" || { echo "END copy-failed $(date -u +%FT%TZ)" > $X/go-end.txt; exit 1; }
machine run pareto0 --shared --wait 4h -r "sa-port-343: witness reasons (issue 323): suite by id, digests, iv, 20 workloads and fuzz seeds on $NEW, about 70 minutes" -- bash -c "bash $R/s1/tools/job342.sh $R $NEW $BASE; bash $R/s1/tools/jobb343.sh $R $NEW $BASE" > $X/job.log 2>&1
rc=$?
ssh pareto0 "tar -c -C $R --exclude hyp --exclude .hypothesis job-$NEW" | tar -x -C $X
ssh pareto0 "tar -c -C $R --exclude '*.jsonl' --exclude '*.json' jobb-$NEW" | tar -x -C $X
. ~/sa-rust-ids-work/env.sh
$PY $X/tools/cmp329.py $X/job-$NEW > $X/job-$NEW/suite-cmp.txt 2>&1
$PY $X/tools/ivcmp329.py $X/job-$NEW/iv > $X/job-$NEW/iv-cmp.txt 2>&1
echo "END $rc $(date -u +%FT%TZ)" > $X/go-end.txt
