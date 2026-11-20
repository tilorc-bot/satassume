#!/bin/bash
# gopre361.sh NEW BASE (sa-port-361, orion): pre361.sh on pareto0 under one shared lease; the small files copied back to
# ~/sa-rust-ids-work/sa-port-361/pre-NEW. End marker: sa-port-361/pre-end.txt, the last line here.
X=~/sa-rust-ids-work/sa-port-361; R=/home/tilo/sp19/sa-rust-ids-work/sa-port-361; NEW=$1; BASE=$2
machine run pareto0 --shared --wait 4h -r "sa-port-361: convert.py port (issue 323): one test id in 8 cells, then the differential on $NEW, about 40 minutes" -- bash $R/s1/tools/pre361.sh $NEW $BASE > $X/pre-job.log 2>&1
rc=$?
ssh pareto0 "tar -c -C $R --exclude hyp --exclude .hypothesis --exclude '*.jsonl' --exclude 'wl-*' --exclude 'convdiff/suite' --exclude suite-rows pre-$NEW" | tar -x -C $X
echo "END $rc $(date -u +%FT%TZ) | $(ssh pareto0 "cat $R/pre-$NEW/end.txt")" > $X/pre-end.txt
