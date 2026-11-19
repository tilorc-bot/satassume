#!/bin/bash
# go338.sh NEW BASE (sa-port-338, orion, detached): job338.sh on pareto1 under a shared lease, the rows copied back to
# sa-port-338/job-NEW, then cmp329.py (suite by id). End marker: sa-port-338/go-end-NEW.txt, the last line here.
X=~/sa-rust-ids-work/sa-port-338; R=/home/tilo/sp19/sa-rust-ids-work/sa-port-338; NEW=$1; BASE=$2
machine run pareto1 --shared --wait 4h -r "sa-port-338: witness check (issue 323): suite by id on/off/base and 24 one-process order runs on $NEW, about 15 minutes" -- bash $R/s1/tools/job338.sh $R $NEW $BASE > $X/job-$NEW.log 2>&1
rc=$?
ssh pareto1 "tar -c -C $R --exclude hyp --exclude .hypothesis job-$NEW" | tar -x -C $X
. ~/sa-rust-ids-work/env.sh
$PY $X/tools/cmp329.py $X/job-$NEW > $X/job-$NEW/suite-cmp.txt 2>&1
echo "END $rc $(date -u +%FT%TZ)" > $X/go-end-$NEW.txt
