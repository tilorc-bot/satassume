#!/bin/bash
# gonohandler360.sh (sa-port-360, orion, under setsid): nohandler360.sh on pareto0 under one shared lease; the small
# files copied back to ~/sa-rust-ids-work/sa-port-360/nohandler. End marker: sa-port-360/nohandler-end.txt, the last line.
X=~/sa-rust-ids-work/sa-port-360; R=/home/tilo/sp19/sa-rust-ids-work/sa-port-360
ssh pareto0 "mkdir -p $R/tools" && tar -c -C $X/tools . | ssh pareto0 "tar -x -C $R/tools" || { echo "END sync-failed $(date -u +%FT%TZ)" > $X/nohandler-end.txt; exit 1; }
machine run pareto0 --shared --wait 4h -r "sa-port-360: convert.py port (issue 323): the differential's suite pass without the handler_count plugin on 00535462, about 25 minutes" -- bash $R/tools/nohandler360.sh > $X/nohandler-job.log 2>&1
rc=$?
ssh pareto0 "tar -c -C $R --exclude hyp --exclude .hypothesis --exclude suite-rows nohandler" | tar -x -C $X
echo "END $rc $(date -u +%FT%TZ)" > $X/nohandler-end.txt
