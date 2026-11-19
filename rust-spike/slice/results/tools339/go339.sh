#!/bin/bash
# go339.sh (sa-port-339, orion): plants339.sh on pareto1's staged frozen tree of 81e6561e (338's stage, .so cad764d4)
# under a shared lease, python and rust, with the repeat check; output copied back. End marker: p1-end.txt here.
X=~/sa-rust-ids-work/sa-port-339; R=/home/tilo/sp19/sa-rust-ids-work/sa-port-339
machine run pareto1 --shared --wait 4h -r "sa-port-339: witness check (issue 323): test_witness.py under plants 749-752 and 754 and the planted-history repeat check on 81e6561e, about 10 minutes" -- env HOME=/home/tilo/sp19 bash $R/tools/plants339.sh /home/tilo/sp19/sa-rust-ids-work/sa-port-338/s1/bench-81e6561e/tree $R/p1 "python rust" $R/plug > $X/p1-job.log 2>&1
rc=$?
ssh pareto1 "tar -c -C $R --exclude hyp --exclude .hypothesis p1" | tar -x -C $X
echo "END $rc $(date -u +%FT%TZ)" > $X/p1-end.txt
