#!/bin/bash
# disc352.sh OUT (sa-port-352, orion, detached, 3 at once; not a timing): R5 with the native witness check on
# (SLICE_WITNESS=1 SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust SLICE_WITNESS_RUST=1), fresh.py --term terms --lra --full on
# dev, lra and fuzz: plain; --discard (term_discard.py: a planted refusal in each query's run, all of Python's state
# and every native store compared after the rollback with a copy taken as the run started); and on dev's first 300
# --discard --no-rollback, the plant that shows the comparison can fail. cmp plain against discard: answers, digests.
# End marker: OUT/end.txt, the last line here.
T=$(cd "$(dirname "$0")/../../../.." && pwd); S=$T/rust-spike/slice; OUT=$1; mkdir -p $OUT
. ~/sa-rust-ids-work/env.sh
export PYTHONPATH=$T:$W/sympy:$W/shim SLICE_WITNESS=1 SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust SLICE_WITNESS_RUST=1 PY OUT
cd $S
{ for wl in dev lra fuzz; do echo "$wl plain"; echo "$wl disc --discard"; done; echo "dev noroll --discard --no-rollback --first 300"; } > $OUT/todo.txt
xargs -P 3 -L 1 bash -c 'wl=$0; n=$1; shift; f=$OUT/$wl-$n
  $PY fresh.py $wl rust $f.tsv --term terms --lra --full --term-out $f.json "$@" > $f.out 2> $f.err; echo "$? $wl $n" >> $OUT/rc.txt' < $OUT/todo.txt
for wl in dev lra fuzz; do cmp $OUT/$wl-plain.tsv $OUT/$wl-disc.tsv > $OUT/$wl-cmp.txt 2>&1; echo "cmp rc $? lines $(wc -l < $OUT/$wl-plain.tsv) $(wc -l < $OUT/$wl-disc.tsv)" >> $OUT/$wl-cmp.txt; done
echo "END $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)" > $OUT/end.txt
