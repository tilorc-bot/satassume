#!/bin/bash
# go352b.sh NEW BASE (sa-port-352, orion, under setsid; tools347/go347.sh): item 3's suite by id and iv on pareto0 under
# ONE shared lease (job352b.sh), on the trees stage352.sh staged; the tools and plugins are synced again from the
# worktree's HEAD first. The rows are copied back to ~/sa-rust-ids-work/sa-port-352/job-NEW and byid352.py reads them.
# End marker: sa-port-352/go-end.txt, the last line here.
WT=~/sa-rust-ids-work/sa-port-350/wt; X=~/sa-rust-ids-work/sa-port-352; R=/home/tilo/sp19/sa-rust-ids-work/sa-port-352; NEW=$1; BASE=$2
rm -rf $X/tools; mkdir -p $X/tools
for d in tools328 tools336 tools352; do git -C $WT archive HEAD:rust-spike/slice/results/$d | tar -x -C $X/tools; done
git -C $WT rev-parse HEAD > $X/tools/TOOLS-SHA; cp $X/tools/wn_seen.py $X/plug/
tar -c -C $X/tools . | ssh pareto0 "tar -x -C $R/s1/tools" && tar -c -C $X/plug --exclude __pycache__ . | ssh pareto0 "tar -x -C $R/s1/plug" || { echo "END sync-failed $(date -u +%FT%TZ)" > $X/go-end.txt; exit 1; }
machine run pareto0 --shared --wait 4h -r "sa-port-352: native witness check (issue 323): suite by id (4 cells) and iv (128 runs) on $NEW, about 60 minutes" -- bash $R/s1/tools/job352b.sh $R $NEW $BASE > $X/job.log 2>&1
rc=$?
ssh pareto0 "tar -c -C $R --exclude hyp --exclude .hypothesis job-$NEW" | tar -x -C $X
. ~/sa-rust-ids-work/env.sh
$PY $X/tools/byid352.py $X/job-$NEW > $X/job-$NEW/byid.txt 2>&1
echo "END $rc $(date -u +%FT%TZ)" > $X/go-end.txt
