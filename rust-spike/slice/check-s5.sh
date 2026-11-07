#!/bin/sh
# Not timed. /work = sa-rust-bench read-only, /o writable. live.py --check raw: answers and each solver's end state, Python and both x86 modules.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export SA_EVAL_DATA=/work/data PYTHONHASHSEED=0 PYTHONPATH=/work/src/slice-c230ee0:/work/sympy:/tmp/shim
cd /work/slice5
for wl in dev fuzz; do
  python live.py $wl py /o/$wl-py.jsonl --check raw > /o/$wl-py.tot 2>&1 &
  for b in full abi3; do
    python live.py $wl rust /o/$wl-$b.jsonl --check raw --so /work/slice5/$b > /o/$wl-$b.tot 2>&1 &
  done
done
wait
for wl in dev fuzz; do for b in full abi3; do
  echo "== $wl py vs $b"; python livecmp.py /o/$wl-py.jsonl /o/$wl-$b.jsonl --end-only; echo "exit $?"
done; done
