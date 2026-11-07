#!/bin/bash
# The ground workload: fresh compare.
G=$B/ground; mkdir -p $G; date -u >$G/start
$PY live.py ground py $G/py.jsonl --check entry --fork >$G/py.tot 2>$G/py.err &
$PY live.py ground rust $G/rust.jsonl --check entry --fork >$G/rust.tot 2>$G/rust.err &
wait
$PY livecmp.py $G/py.jsonl $G/rust.jsonl >$G/fresh.cmp 2>&1
date -u >$G/done
