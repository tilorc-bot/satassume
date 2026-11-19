#!/bin/bash
# go342.sh a|b NEW BASE (sa-port-342, orion, under setsid): a = job342.sh on pareto0, b = jobb342.sh on pareto1, each under
# a shared lease; the small outputs are copied back to ~/sa-rust-ids-work/sa-port-342, then for a the comparisons of
# tools336/go336.sh: cmp329.py (suite by id), ivcmp329.py (iv, off against on).
# End marker: sa-port-342/go-a-end.txt or go-b-end.txt, the last line here.
X=~/sa-rust-ids-work/sa-port-342; R=/home/tilo/sp19/sa-rust-ids-work/sa-port-342; J=$1; NEW=$2; BASE=$3
if [ $J = a ]; then
  machine run pareto0 --shared --wait 4h -r "sa-port-342: witness reasons (issue 323): suite by id on/off/base, digests, iv on $NEW, about 40 minutes" -- bash $R/s1/tools/job342.sh $R $NEW $BASE > $X/job-a.log 2>&1
  rc=$?
  ssh pareto0 "tar -c -C $R --exclude hyp --exclude .hypothesis job-$NEW" | tar -x -C $X
  . ~/sa-rust-ids-work/env.sh
  $PY $X/tools/cmp329.py $X/job-$NEW > $X/job-$NEW/suite-cmp.txt 2>&1
  $PY $X/tools/ivcmp329.py $X/job-$NEW/iv > $X/job-$NEW/iv-cmp.txt 2>&1
else
  machine run pareto1 --shared --wait 4h -r "sa-port-342: witness reasons (issue 323): answers on 20 workloads and fuzz seeds, $NEW against $BASE, about 30 minutes" -- bash $R/s1/tools/jobb342.sh $R $NEW $BASE > $X/job-b.log 2>&1
  rc=$?
  ssh pareto1 "tar -c -C $R --exclude '*.jsonl' --exclude '*.json' jobb-$NEW" | tar -x -C $X
fi
echo "END $rc $(date -u +%FT%TZ)" > $X/go-$J-end.txt
