#!/bin/bash
# gos1336.sh SHA TAG (sa-port-336, orion, detached): S1 for the witness check on pareto1 under ONE quiet lease: 12 rounds,
# dev and fuzz, Python and both Rust switches, off against cap 32 (onlease336.sh, time336.sh), then the rows copied back
# and read by tools328/med329.py. End marker: sa-port-336/gos1-end-TAG.txt, the last line here.
X=~/sa-rust-ids-work/sa-port-336; R1=/home/tilo/sa-rust-ids-work/sa-port-336; SHA=$1; TAG=$2
machine run pareto1 --quiet --wait 1h -r "sa-port-336: witness check (issue 323): S1 on $SHA, 12 rounds pinned, about 15 minutes" -- env SHA=$SHA ARMS="py-off py-on32 rust-off rust-on32" ROUNDS="1 2 3 4 5 6 7 8 9 10 11 12" WLS="dev fuzz" bash $R1/s1/tools/onlease336.sh $TAG > $X/lease-$TAG.log 2>&1
rc=$?
rsync -a pareto1:$R1/s1/timing-$TAG $X/
. ~/sa-rust-ids-work/env.sh; $PY $X/tools/med329.py $X/timing-$TAG > $X/timing-$TAG/med.txt 2>&1
echo "END $rc $(date -u +%FT%TZ)" > $X/gos1-end-$TAG.txt
