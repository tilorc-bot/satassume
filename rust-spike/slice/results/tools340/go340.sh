#!/bin/bash
# go340.sh JOB HOST SHA WHY (sa-port-340, orion; run under setsid): run tools340/JOB on HOST's staged tree of SHA under a
# shared lease; the job writes its own end marker on HOST; this copies the small outputs back and writes
# ~/sa-rust-ids-work/sa-port-340/JOB-end.txt.
J=$1; HOST=$2; SHA=$3; WHY=$4; X=~/sa-rust-ids-work/sa-port-340; R=/home/tilo/sp19/sa-rust-ids-work/sa-port-340
n=${J%.sh}
machine run $HOST --shared --wait 4h -r "sa-port-340: witness reasons (issue 323): $WHY" -- bash $R/tools/$J $R/tree-$SHA $R/$n-$SHA > $X/$n-job.log 2>&1
rc=$?
ssh $HOST "tar -c -C $R --exclude hyp --exclude .hypothesis --exclude '*.jsonl' $n-$SHA" | tar -x -C $X
echo "END $rc $(date -u +%FT%TZ)" > $X/$n-end.txt
