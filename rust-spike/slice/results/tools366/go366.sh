#!/bin/bash
# go366.sh NEW BASE (sa-port-366, orion, under setsid; tools359/go359.sh): stage366.sh, then item 5 on pareto1 under ONE
# shared lease (job366.sh) on the staged trees. The small files are copied back to ~/sa-rust-ids-work/sa-port-366/job-NEW
# (no jsonl rows, no suite or differential inputs). End marker: sa-port-366/go-end.txt, the last line here.
S=sa-port-366; X=~/sa-rust-ids-work/$S; R=/home/tilo/sp19/sa-rust-ids-work/$S; NEW=$1; BASE=$2
grep -qs "^END staged $NEW $BASE" $X/stage-$NEW.txt || bash $X/wt/rust-spike/slice/results/tools366/stage366.sh $NEW $BASE > $X/stage.out 2>&1
grep -q "^END staged $NEW $BASE" $X/stage-$NEW.txt || { echo "END stage-failed $(date -u +%FT%TZ)" > $X/go-end.txt; exit 1; }
machine run pareto1 --shared --wait 4h -r "$S: per-term level removal (issue 323): per-query gate against $BASE, the level calls counted on $BASE, differential, suite by id (6 cells) and iv (128 runs) on $NEW, about 2 hours" -- bash $R/s1/tools/job366.sh $R $NEW $BASE > $X/job.log 2>&1
rc=$?
ssh pareto1 "tar -c -C $R --exclude hyp --exclude .hypothesis --exclude '*.jsonl' --exclude 'wl-*' --exclude 'convdiff/suite' --exclude 'convdiff/suite-rows' job-$NEW" | tar -x -C $X
echo "END $rc $(date -u +%FT%TZ)" > $X/go-end.txt
