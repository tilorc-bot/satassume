#!/bin/bash
# chain361.sh NEW SOHASH16 (sa-port-361, orion, under setsid; the session hands off without waiting): waits for
# gopre361.sh's end marker (sa-port-361/pre-end.txt), then starts the bar (gobar361.sh NEW SOHASH16) ONLY IF the pre-bar
# checks read clean: the pre job's rc 0; cond3.txt 4 of 4 cells rc 0 (the id at tests/test_noncommutative.py:546 under
# the bar's suite invocation, head and base, both walkers); convdiff/total.txt with inputs, "differences": 0 and
# `exit 0`; its last line `workloads 20; answer rows 60, MATCH 60`. Otherwise no bar.
# ONE end marker for both outcomes, sa-port-361/gobar-end.txt: `NO-BAR reasons` written here (line 18), or gobar361.sh's
# own last line (gobar361.sh:19, `END rc <pareto0 bar-end.txt's first line> | time`) when the bar ran.
X=~/sa-rust-ids-work/sa-port-361; NEW=$1; WANT=$2; T=$X/pre-$NEW/convdiff/total.txt
rm -f $X/gobar-end.txt
until [ -e $X/pre-end.txt ]; do sleep 30; done
why=
grep -q '^END 0 ' $X/pre-end.txt || why="$why; the pre job's rc is not 0"
[ "$(grep -c ': rc 0 | 1 passed' $X/pre-$NEW/cond3.txt 2>/dev/null)" = 4 ] || why="$why; cond3.txt is not 4 of 4 passed"
head -n 1 $T 2>/dev/null | grep -q '"inputs": [1-9][0-9]*, "differences": 0,' || why="$why; total.txt line 1 is not differences 0"
grep -qx 'exit 0' $T 2>/dev/null || why="$why; total.txt has no exit 0"
tail -n 1 $T 2>/dev/null | grep -qx 'workloads 20; answer rows 60, MATCH 60' || why="$why; the answers are not 60 of 60 MATCH"
if [ -n "$why" ]; then echo "NO-BAR$why | $(date -u +%FT%TZ)" > $X/gobar-end.txt; exit 1; fi
echo "pre-bar checks clean $(date -u +%FT%TZ): $(head -n 1 $T | cut -c1-60); starting the bar" > $X/chain.txt
bash $X/tools/gobar361.sh $NEW $WANT > $X/gobar.out 2>&1
