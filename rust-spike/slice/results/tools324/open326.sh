#!/bin/bash
# open326.sh TAG [SODIR]: run open326.py on the head worktree, optionally with another .so directory first on the path.
X=$HOME/sa-rust-ids-work/sa-port-326; T=$HOME/sa-rust-ids-work/sa-port-324/wt; S=$T/rust-spike/slice
. ~/sa-rust-ids-work/env.sh; export SA_EVAL_DATA PYTHONHASHSEED
export PYTHONPATH=${2:+$2:}$S:$T:$W/sympy:$W/shim
cd $X/open && $PY $X/tools/open326.py > $X/open/$1.txt 2>&1; echo "exit $?" >> $X/open/$1.txt
