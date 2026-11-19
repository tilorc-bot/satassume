#!/bin/bash
# gobar336.sh SHA (sa-port-336, orion, detached): the bar on pareto0 under a shared lease. Copies SHA's p1/bar.sh (from the
# commit, not the worktree) as ~/sp19/bar-sa-port-336.sh, job336bar.sh and the pareto1 venv build of SHA's crate, checks
# that origin/bar/witness-check-SHA is SHA (bar.sh tests that branch's head), runs job336bar.sh, and copies back the bar's
# small files (no jsonl rows, no target). End marker: sa-port-336/gobar-end.txt, the last line here.
WT=~/sa-rust-ids-work/sa-port-328/wt; X=~/sa-rust-ids-work/sa-port-336; L=/home/tilo/sp19/sa-rust-ids-work/sa-port-336; SHA=$1
[ "$(git -C $WT ls-remote origin refs/heads/bar/witness-check-$SHA | cut -c1-7)" = "$SHA" ] || { echo "END branch head is not $SHA" > $X/gobar-end.txt; exit 2; }
ssh pareto0 "mkdir -p $L/so; echo $SHA > $L/so/source.txt"
git -C $WT show $SHA:rust-spike/slice/p1/bar.sh | ssh pareto0 "cat > /home/tilo/sp19/bar-sa-port-336.sh"
ssh pareto0 "cat > $L/job336bar.sh" < $X/tools/job336bar.sh
ssh pareto0 "cat > $L/so/sa_solver.so" < $X/so/sa_solver-$SHA.so
ssh pareto0 "cat > $L/so/so.txt" < $X/so/so-$SHA.txt
machine run pareto0 --shared --wait 4h -r "sa-port-336: witness check (issue 323): the full bar on $SHA, about 2 hours" -- bash $L/job336bar.sh > $X/bar-launch.log 2>&1
rc=$?
mkdir -p $X/bar
ssh pareto0 "cd $L && tar -c --exclude '*.jsonl' --exclude target --exclude hyp --exclude .hypothesis --exclude '*.knowledge.json' bar bar-end.txt bar.log env-summary.txt launcher-env.txt" | tar -x -C $X/bar
echo "END $rc $(date -u +%FT%TZ)" > $X/gobar-end.txt
