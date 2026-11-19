#!/bin/bash
# gobar337.sh SHA SOHASH16 (sa-port-337, orion, detached): the bar on pareto0 under a shared lease, rerun because
# sa-port-336's bar had no .so (see job337bar.sh). Copies SHA's p1/bar.sh (from the commit, not the worktree) as
# ~/sp19/bar-sa-port-337.sh, job337bar.sh and the pareto1 venv build of SHA's crate, checks that
# origin/bar/witness-check-SHA is SHA (bar.sh tests that branch's head), runs job337bar.sh, and copies back the bar's
# small files (no jsonl rows, no target). End marker: sa-port-337/gobar-end.txt, the last line here.
WT=~/sa-rust-ids-work/sa-port-328/wt; X=~/sa-rust-ids-work/sa-port-337; L=/home/tilo/sp19/sa-rust-ids-work/sa-port-337; SHA=$1; WANT=$2
[ "$(git -C $WT ls-remote origin refs/heads/bar/witness-check-$SHA | cut -c1-7)" = "$SHA" ] || { echo "END branch head is not $SHA" > $X/gobar-end.txt; exit 2; }
[ "$(sha256sum $X/so/sa_solver-$SHA.so | cut -c1-16)" = "$WANT" ] || { echo "END staged .so is not $WANT" > $X/gobar-end.txt; exit 2; }
ssh pareto0 "mkdir -p $L/so; echo $SHA > $L/so/source.txt; echo $WANT > $L/so/want.txt"
git -C $WT show $SHA:rust-spike/slice/p1/bar.sh | ssh pareto0 "cat > /home/tilo/sp19/bar-sa-port-337.sh"
ssh pareto0 "cat > $L/job337bar.sh" < $X/tools/job337bar.sh
ssh pareto0 "cat > $L/so/sa_solver.so" < $X/so/sa_solver-$SHA.so
ssh pareto0 "cat > $L/so/so.txt" < $X/so/so-$SHA.txt
machine run pareto0 --shared --wait 4h -r "sa-port-337: witness check (issue 323): the full bar on $SHA again (336's had no .so), about 2 hours" -- bash $L/job337bar.sh > $X/bar-launch.log 2>&1
rc=$?
mkdir -p $X/bar
ssh pareto0 "cd $L && tar -c --exclude '*.jsonl' --exclude target --exclude hyp --exclude .hypothesis --exclude '*.knowledge.json' bar bar-end.txt bar.log env-summary.txt launcher-env.txt" | tar -x -C $X/bar
echo "END $rc $(ssh pareto0 "head -n 1 $L/bar-end.txt") | $(date -u +%FT%TZ)" > $X/gobar-end.txt
