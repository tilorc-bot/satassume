#!/bin/bash
# chain336.sh SHA (sa-port-336, orion, detached): waits for go336.sh's end marker (the suite, digest and iv job on
# pareto0), then runs gobar336.sh SHA (the bar, on pareto0). End marker: gobar336.sh's sa-port-336/gobar-end.txt.
X=~/sa-rust-ids-work/sa-port-336
until [ -e $X/go-end-$1.txt ]; do sleep 30; done
bash $X/tools/gobar336.sh $1 > $X/gobar.out 2>&1
