#!/bin/bash
# go336.sh NEW BASE (sa-port-336, orion, detached): job336.sh on pareto0 under a shared lease, the rows copied back to
# sa-port-336/job-NEW, then the comparisons: cmp329.py (suite by id), ivcmp329.py (iv, off against on).
# End marker: sa-port-336/go-end-NEW.txt, the last line here.
X=~/sa-rust-ids-work/sa-port-336; R0=/home/tilo/sp19/sa-rust-ids-work/sa-port-336; NEW=$1; BASE=$2
machine run pareto0 --shared --wait 4h -r "sa-port-336: witness check (issue 323): suite by id on/off/base, digests, iv on $NEW, about 40 minutes" -- bash $R0/s1/tools/job336.sh $R0 $NEW $BASE > $X/job-$NEW.log 2>&1
rc=$?
ssh pareto0 "tar -c -C $R0 --exclude hyp --exclude .hypothesis job-$NEW" | tar -x -C $X
. ~/sa-rust-ids-work/env.sh
$PY $X/tools/cmp329.py $X/job-$NEW > $X/job-$NEW/suite-cmp.txt 2>&1
$PY $X/tools/ivcmp329.py $X/job-$NEW/iv > $X/job-$NEW/iv-cmp.txt 2>&1
echo "END $rc $(date -u +%FT%TZ)" > $X/go-end-$NEW.txt
