#!/bin/bash
# go329.sh (sa-port-329, orion, detached): pareto1, first the quiet lease for the check's per-call cost, then the shared
# lease for the suites and the iv history check. Orion end marker: go-end.txt (last line here).
X=~/sa-rust-ids-work/sa-port-329; G=$X/s1
machine run pareto1 --quiet --wait 1h -r "sa-port-329: witness check (issue 323): the check's own time per call, pinned" -- env SHA=5e6e46a ARMS="py-on32 py-on0 rust-on32 rust-on0" ROUNDS="1 2 3" WLS="dev fuzz" bash $G/tools/lease329.sh c1 > $X/lease-c1.log 2>&1
echo "lease rc=$? $(date -u +%FT%TZ)" > $X/lease-c1-end.txt
rsync -a pareto1:$G/timing-c1 $X/
machine run pareto1 --shared --wait 4h -r "sa-port-329: witness check (issue 323): suite by id on/off/base, iv history on/off" -- bash $G/tools/job329.sh 5e6e46a e5db633 > $X/job.log 2>&1
rc=$?
rsync -a --exclude hyp --exclude '.hypothesis' pareto1:$X/job $X/
echo "END $rc $(date -u +%FT%TZ)" > $X/go-end.txt
