#!/bin/sh
cd $HOME/sa-rust-ids-work/sa-port-318/runs/$1
for b in python rust; do for k in orig keep; do for f in plain frames; do
  n=$(ls $b.$k.$f.*.log | wc -l); p=$(grep -l "^EXIT 0" $b.$k.$f.*.log | wc -l)
  echo "$b $k $f: $p/$n pass"; done; done; done
echo "assertion lines in failures:"; for f in $(grep -L "^EXIT 0" *.log); do grep -h -E 'assert|Error' $f | head -2; done | sort | uniq -c
echo "trees:"; grep -h "^TREE" *.log | sort | uniq -c
