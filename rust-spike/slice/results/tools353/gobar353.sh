#!/bin/bash
# gobar353.sh SHA SOHASH16 (sa-port-353, orion, detached; tools347/gobar347.sh for the native witness check): the bar on pareto0
# under a shared lease. Copies SHA's p1/bar.sh (from the commit, not the worktree) as ~/sp19/bar-sa-port-353.sh,
# job353bar.sh and the .so stage352.sh built from SHA (S=sa-port-353), checks that origin/bar/witness-native-SHA is SHA
# (bar.sh tests that branch's head), runs job353bar.sh, and copies back the
# bar's small files (no jsonl rows, no target). End marker: sa-port-353/gobar-end.txt, the last line here.
WT=~/sa-rust-ids-work/sa-port-350/wt; X=~/sa-rust-ids-work/sa-port-353; L=/home/tilo/sp19/sa-rust-ids-work/sa-port-353; SHA=$1; WANT=$2
[ "$(git -C $WT ls-remote origin refs/heads/bar/witness-native-$SHA | cut -c1-${#SHA})" = "$SHA" ] || { echo "END branch head is not $SHA" > $X/gobar-end.txt; exit 2; }
[ "$(sha256sum $X/so/sa_solver-$SHA.so | cut -c1-16)" = "$WANT" ] || { echo "END staged .so is not $WANT" > $X/gobar-end.txt; exit 2; }
ssh pareto0 "mkdir -p $L/so; echo $SHA > $L/so/source.txt; echo $WANT > $L/so/want.txt"
git -C $WT show $SHA:rust-spike/slice/p1/bar.sh | ssh pareto0 "cat > /home/tilo/sp19/bar-sa-port-353.sh"
ssh pareto0 "cat > $L/job353bar.sh" < $X/tools/job353bar.sh
ssh pareto0 "cat > $L/so/sa_solver.so" < $X/so/sa_solver-$SHA.so
ssh pareto0 "cat > $L/so/so.txt" < $X/so/so-$SHA.txt
machine run pareto0 --shared --wait 4h -r "sa-port-353: native witness check (issue 323): the full bar on $SHA, about 90 minutes" -- bash $L/job353bar.sh > $X/bar-launch.log 2>&1
rc=$?
mkdir -p $X/bar
ssh pareto0 "cd $L && tar -c --exclude '*.jsonl' --exclude target --exclude hyp --exclude .hypothesis --exclude '*.knowledge.json' bar bar-end.txt bar.log env-summary.txt launcher-env.txt" | tar -x -C $X/bar
echo "END $rc $(ssh pareto0 "head -n 1 $L/bar-end.txt") | $(date -u +%FT%TZ)" > $X/gobar-end.txt
