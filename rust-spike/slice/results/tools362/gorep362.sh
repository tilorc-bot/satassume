#!/bin/bash
# gorep362.sh (sa-port-362, orion, detached): rep362.sh on pareto0 under a shared lease, on the bar's tree of 5b20d1f2,
# its small files copied back. End marker: ~/sa-rust-ids-work/sa-port-362/gorep-end.txt, the last line here.
WT=~/sa-rust-ids-work/sa-port-356/wt; X=~/sa-rust-ids-work/sa-port-362; L=/home/tilo/sp19/sa-rust-ids-work/sa-port-362
ssh pareto0 "mkdir -p $L/rep $L/plug" && ssh pareto0 "cat > $L/rep362.sh" < $WT/rust-spike/slice/results/tools362/rep362.sh
ssh pareto0 "cat > $L/plug/test_keepalive185.py" < ~/sa-rust-ids-work/sa-port-354/plug/test_keepalive185.py
machine run pareto0 --shared --wait 4h -r "sa-port-362: convert.py port landing (issue 323): the planted-history repeat check on the bar's tree, 160 short runs" -- bash $L/rep362.sh /home/tilo/sp19/dev/sa-port-361 $L/plug $L/rep > $X/rep-launch.log 2>&1
rc=$?
mkdir -p $X/rep; ssh pareto0 "cd $L/rep && tar -c rep-sum.txt trees.txt rep-source.txt rep-end.txt logs" | tar -x -C $X/rep
echo "END $rc $(ssh pareto0 "cat $L/rep/rep-end.txt") | $(date -u +%FT%TZ)" > $X/gorep-end.txt
