#!/bin/bash
# gorep349.sh (sa-port-349, orion, detached): rep349.sh on pareto0 under a shared lease, its small files copied back.
# End marker: ~/sa-rust-ids-work/sa-port-349/gorep-end.txt, the last line here.
X=~/sa-rust-ids-work/sa-port-349; R=/home/tilo/sp19/sa-rust-ids-work/sa-port-348; L=/home/tilo/sp19/sa-rust-ids-work/sa-port-349
ssh pareto0 "mkdir -p $L/rep" && ssh pareto0 "cat > $L/rep349.sh" < $X/tools/rep349.sh
machine run pareto0 --shared --wait 4h -r "sa-port-349: witness bounds (issue 323): the planted-history repeat check under plant skip-work, 80 short runs" -- bash $L/rep349.sh $R $L/rep > $X/rep-launch.log 2>&1
rc=$?
mkdir -p $X/rep; ssh pareto0 "cd $L/rep && tar -c rep-sum.txt trees.txt rep-source.txt rep-end.txt logs" | tar -x -C $X/rep
echo "END $rc $(ssh pareto0 "cat $L/rep/rep-end.txt") | $(date -u +%FT%TZ)" > $X/gorep-end.txt
