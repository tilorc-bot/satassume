#!/bin/bash
# go363.sh NEW BASE (sa-port-363, orion, under setsid; tools359/go359.sh): stage363.sh, then item 5 on pareto0 under ONE
# shared lease (job363.sh) on the staged trees. The small files are copied back to ~/sa-rust-ids-work/sa-port-363/job-NEW
# (no jsonl rows, no suite or differential inputs). End marker: sa-port-363/go-end.txt, the last line here.
S=sa-port-363; X=~/sa-rust-ids-work/$S; R=/home/tilo/sp19/sa-rust-ids-work/$S; NEW=$1; BASE=$2
bash $X/wt/rust-spike/slice/results/tools363/stage363.sh $NEW $BASE > $X/stage.out 2>&1
grep -q "^END staged $NEW $BASE" $X/stage-$NEW.txt || { echo "END stage-failed $(date -u +%FT%TZ)" > $X/go-end.txt; exit 1; }
machine run pareto0 --shared --wait 4h -r "$S: formula skeleton removal (issue 323): per-query gate against 966268c, differential, suite by id (6 cells) and iv (128 runs) on $NEW, about 2 hours" -- bash $R/s1/tools/job363.sh $R $NEW $BASE > $X/job.log 2>&1
rc=$?
ssh pareto0 "tar -c -C $R --exclude hyp --exclude .hypothesis --exclude '*.jsonl' --exclude 'wl-*' --exclude 'convdiff/suite' --exclude 'convdiff/suite-rows' job-$NEW" | tar -x -C $X
echo "END $rc $(date -u +%FT%TZ)" > $X/go-end.txt
