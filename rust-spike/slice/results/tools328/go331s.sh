#!/bin/bash
# go331s.sh NEW BASE (sa-port-331, orion, detached): the suite by id for the witness check, on the host the planner's
# ruling allows: pareto0 once no lease or queue entry is on it (two polls a minute apart), or pareto1 once a quiet lease
# of sa-port-327's S1 has been seen there and pareto1 has then had no lease or queue entry for five polls; whichever
# comes first. Stages NEW and BASE (git archive from the worktree plus pareto1's x86-64 sa_solver.so 45f63fdf of
# 5e6e46a: the crate is source-equal on all three, checked here) on both hosts first (file copies, no lease), then runs
# suite331.sh under a shared lease, copies the rows back and compares by id (cmp329.py).
# Progress: sa-port-331/wait.txt. Orion end marker: sa-port-331/gos-end-NEW.txt, the last line here.
WT=~/sa-rust-ids-work/sa-port-328/wt; X=~/sa-rust-ids-work/sa-port-331; P=~/sa-rust-ids-work/sa-port-329; NEW=$1; BASE=$2
R0=/home/tilo/sp19/sa-rust-ids-work/sa-port-331; R1=/home/tilo/sa-rust-ids-work/sa-port-331
for s in $NEW $BASE; do git -C $WT diff --quiet 5e6e46a $s -- rust-spike/slice/solver_rs || { echo "END crate differs $s" > $X/gos-end-$NEW.txt; exit 2; }; done
mkdir -p $X/so; rsync -a pareto1:$P/s1/bench-5e6e46a/tree/rust-spike/slice/sa_solver.so $X/so/sa_solver.so
for hr in pareto0:$R0 pareto1:$R1; do h=${hr%%:*}; r=${hr#*:}   # pareto0 has no rsync: tar and cat over ssh
  for s in $NEW $BASE; do
    ssh $h "mkdir -p $r/s1/bench-$s/tree $r/s1/tools; echo $s > $r/s1/bench-$s/SHA"
    git -C $WT archive $s | ssh $h "tar -x -C $r/s1/bench-$s/tree"
    ssh $h "cat > $r/s1/bench-$s/tree/rust-spike/slice/sa_solver.so" < $X/so/sa_solver.so
  done
  tar -c -C $X/tools . | ssh $h "tar -x -C $r/s1/tools"
  ssh $h "sha256sum $r/s1/bench-*/tree/rust-spike/slice/sa_solver.so" >> $X/staged-so.txt
done
echo "STAGED $(date -u +%FT%TZ)" > $X/wait.txt
st() { ssh -o ConnectTimeout=10 $1 cat .local/state/machine-lease/state.json 2>/dev/null; }
f0=0; f1=0; seen=0; host=; n=0
while [ -z "$host" ]; do
  s0=$(st pareto0); s1=$(st pareto1)
  if [ -n "$s0" ] && [ "$(echo "$s0" | jq '(.leases|length)+(.queue|length)')" = 0 ]; then f0=$((f0+1)); else f0=0; fi
  if [ -n "$s1" ]; then
    echo "$s1" | jq -e '[.leases[],.queue[]] | map(select((.mode=="quiet") and ((.holder|tostring|test("sa-port-327")) or (.reason|tostring|test("may_be_nan|S1"))))) | length > 0' > /dev/null && seen=1
    if [ "$(echo "$s1" | jq '(.leases|length)+(.queue|length)')" = 0 ]; then f1=$((f1+1)); else f1=0; fi
  fi
  echo "$(date -u +%TZ) p0free=$f0 p1free=$f1 seen327quiet=$seen" >> $X/wait.txt
  [ $f0 -ge 2 ] && host=pareto0 && root=$R0
  [ -z "$host" ] && [ $seen = 1 ] && [ $f1 -ge 5 ] && host=pareto1 && root=$R1
  [ -n "$host" ] && break
  n=$((n+1)); [ $n -ge 300 ] && { echo "END timeout $(date -u +%FT%TZ)" > $X/gos-end-$NEW.txt; exit 3; }
  sleep 60
done
echo "HOST $host $(date -u +%FT%TZ)" >> $X/wait.txt
machine run $host --shared --wait 30m -r "sa-port-331: witness check (issue 323): suite by id on/off/base on $NEW, about 15 minutes" -- bash $root/s1/tools/suite331.sh $root $NEW $BASE > $X/suite-$NEW.log 2>&1
rc=$?
ssh $host "tar -c -C $root --exclude hyp --exclude .hypothesis job-$NEW" | tar -x -C $X
. ~/sa-rust-ids-work/env.sh; $PY $X/tools/cmp329.py $X/job-$NEW > $X/job-$NEW/suite-cmp.txt 2>&1
echo "END $rc $host $(date -u +%FT%TZ)" > $X/gos-end-$NEW.txt
