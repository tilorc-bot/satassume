#!/bin/bash
# rbgo334.sh (sa-port-334, pareto1; launched detached from orion under `machine run pareto1 --shared`): the head half of
# the row-bytes check and its comparison. The base half is rb-base (ec34788, END done 05:23:19Z 19 Nov).
# End marker: $P/rb-all-end.txt, written by the last line of this script (rb-head/end.txt is rb334.sh's own, by fin()).
P=/home/tilo/sp19/sa-rust-ids-work/sa-port-334; rm -f $P/rb-all-end.txt
bash $P/rb334.sh f4ce4b2 head
cd $P; /home/tilo/sp19/sa-rust-ids-work/venv/bin/python rbcmp334.py rb-base rb-head > rbcmp.txt 2>&1
echo "ALLEND $? $(date -u +%FT%TZ) base-not-0 $(grep -vc 'run 0 ' rb-base/exit.txt) head-not-0 $(grep -vc 'run 0 ' rb-head/exit.txt)" > $P/rb-all-end.txt
