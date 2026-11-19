#!/bin/bash
# gobar348.sh SHA SOHASH16 (sa-port-348, orion, detached; tools347/gobar347.sh with the output under sa-port-348): the bar on pareto0
# under a shared lease. Copies SHA's p1/bar.sh (from the commit, not the worktree) as ~/sp19/bar-sa-port-348.sh,
# job348bar.sh and the staged .so, checks that origin/bar/witness-bounds-SHA is SHA (bar.sh tests that branch's head)
# and that the crate is source-equal between 29c5a0db (the .so's source) and SHA, runs job348bar.sh, and copies back the
# bar's small files (no jsonl rows, no target). End marker: sa-port-348/gobar-end.txt, the last line here.
WT=~/sa-rust-ids-work/sa-port-346/wt; X=~/sa-rust-ids-work/sa-port-348; L=/home/tilo/sp19/sa-rust-ids-work/sa-port-348; SHA=$1; WANT=$2
[ "$(git -C $WT ls-remote origin refs/heads/bar/witness-bounds-$SHA | cut -c1-${#SHA})" = "$SHA" ] || { echo "END branch head is not $SHA" > $X/gobar-end.txt; exit 2; }
[ "$(sha256sum $X/so/sa_solver-$SHA.so | cut -c1-16)" = "$WANT" ] || { echo "END staged .so is not $WANT" > $X/gobar-end.txt; exit 2; }
ssh pareto0 "mkdir -p $L/so; echo $SHA > $L/so/source.txt; echo $WANT > $L/so/want.txt"
git -C $WT show $SHA:rust-spike/slice/p1/bar.sh | ssh pareto0 "cat > /home/tilo/sp19/bar-sa-port-348.sh"
ssh pareto0 "cat > $L/job348bar.sh" < $X/tools/job348bar.sh
ssh pareto0 "cat > $L/so/sa_solver.so" < $X/so/sa_solver-$SHA.so
git -C $WT diff --quiet 29c5a0db $SHA -- rust-spike/slice/solver_rs || { echo "END crate of $SHA differs from 29c5a0db" > $X/gobar-end.txt; exit 2; }
ssh pareto0 "cat > $L/so/so.txt" < $X/so/so-$SHA.txt
machine run pareto0 --shared --wait 4h -r "sa-port-348: witness bounds, ruling B (issue 323): the full bar on $SHA, about 90 minutes" -- bash $L/job348bar.sh > $X/bar-launch.log 2>&1
rc=$?
mkdir -p $X/bar
ssh pareto0 "cd $L && tar -c --exclude '*.jsonl' --exclude target --exclude hyp --exclude .hypothesis --exclude '*.knowledge.json' bar bar-end.txt bar.log env-summary.txt launcher-env.txt" | tar -x -C $X/bar
echo "END $rc $(ssh pareto0 "head -n 1 $L/bar-end.txt") | $(date -u +%FT%TZ)" > $X/gobar-end.txt
