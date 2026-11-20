#!/bin/bash
# rows353.sh OUT (sa-port-353, orion, detached; not a timing and not the bar): item 4's rows before the bar, with bar.sh's own
# penv and its plants phase's command: on dev and fuzz the row wnative:on and the five plants wnative:NAME (760-764), each
# against this run's Python under SLICE_WITNESS=1 (livecmp.py) -> OUT/plant-WL-ROW.*, OUT/rows.txt: per row the fired
# counts (session report: plant_fired, rel:plant_fired, witness_plant_fired), livecmp's last line and the wall seconds.
# End marker: OUT/end.txt, the last line here.
T=$(cd "$(dirname "$0")/../../../.." && pwd); export L=$1; mkdir -p $L
. ~/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONPATH=$T:$W/sympy:$W/shim
cd $T/rust-spike/slice; eval "$(sed -n '/^penv() {/p' p1/bar.sh)"; export -f penv
ROWS="on wn-integer-half wn-work-one wn-skip-patched wn-int-side wn-skip-own"
for wl in dev fuzz; do ( SLICE_WITNESS=1 $PY live.py $wl py $L/$wl-pywit.jsonl --check entry > $L/$wl-pywit.tot 2> $L/$wl-pywit.err ) & done
for wl in dev fuzz; do for pl in $ROWS; do echo "$wl wnative:$pl"; done; done | xargs -P 4 -L 1 bash -c 'wl=$0; pl=$1; f=$L/plant-$wl-$pl
  env $(penv $pl) SESSION_REPORT=$f.session.json SLICE_TERM_COUNTS=$f.term.json $PY live.py $wl rust $f.jsonl --check entry > $f.tot 2> $f.err; echo $SECONDS > $f.wall'
wait
for wl in dev fuzz; do for pl in $ROWS; do f=$L/plant-$wl-wnative:$pl
  echo "$wl $pl | fired $($PY -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('plant_fired'), d['counts'].get('rel:plant_fired'), d.get('witness_plant_fired'))" $f.session.json 2>&1 | tail -1) | $($PY livecmp.py $L/$wl-pywit.jsonl $f.jsonl 2>&1 | tail -1 | cut -c1-300) | wall $(cat $f.wall)"
done; done > $L/rows.txt
echo "END $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)" > $L/end.txt
