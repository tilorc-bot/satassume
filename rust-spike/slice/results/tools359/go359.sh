#!/bin/bash
# go359.sh NEW BASE (sa-port-359, orion, under setsid; tools352/go352b.sh): item 4 on pareto0 under ONE shared lease
# (job359.sh), on the trees stage359.sh staged; the tools and plugins are synced again from the worktree first. The
# small files are copied back to ~/sa-rust-ids-work/sa-port-359/job-NEW (no jsonl rows but the gate's last lines) and
# byid359.py reads them. End marker: sa-port-359/go-end.txt, the last line here.
WT=~/sa-rust-ids-work/sa-port-356/wt; S=sa-port-359; X=~/sa-rust-ids-work/$S; R=/home/tilo/sp19/sa-rust-ids-work/$S; NEW=$1; BASE=$2
rm -rf $X/tools; mkdir -p $X/tools
for d in tools328 tools336 tools342 tools352 tools354 tools359; do cp $WT/rust-spike/slice/results/$d/*.sh $WT/rust-spike/slice/results/$d/*.py $X/tools/ 2>/dev/null; done
{ git -C $WT rev-parse HEAD; git -C $WT status --short rust-spike/slice/results; } > $X/tools/TOOLS-SHA; cp $X/tools/cv_seen.py $X/plug/
tar -c -C $X/tools . | ssh pareto0 "tar -x -C $R/s1/tools" && tar -c -C $X/plug --exclude __pycache__ . | ssh pareto0 "tar -x -C $R/s1/plug" || { echo "END sync-failed $(date -u +%FT%TZ)" > $X/go-end.txt; exit 1; }
machine run pareto0 --shared --wait 4h -r "$S: convert.py port (issue 323): per-query gate, differential, suite by id (5 cells) and iv (128 runs) on $NEW, about 90 minutes" -- bash $R/s1/tools/job359.sh $R $NEW $BASE > $X/job.log 2>&1
rc=$?
ssh pareto0 "tar -c -C $R --exclude hyp --exclude .hypothesis --exclude '*-py.jsonl' --exclude '*-rust.jsonl' --exclude '*-nat.jsonl' --exclude '*-rust-cpy.jsonl' --exclude '*-rust-crust.jsonl' --exclude 'wl-*' --exclude 'convdiff/suite' job-$NEW" | tar -x -C $X
. ~/sa-rust-ids-work/env.sh
$PY $X/tools/byid359.py $X/job-$NEW > $X/job-$NEW/byid.txt 2>&1
echo "END $rc $(date -u +%FT%TZ)" > $X/go-end.txt
