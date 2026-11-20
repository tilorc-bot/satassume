#!/bin/bash
# readrows.sh: reads passes.sh's and plantrows.sh's output by id. Wanted: nothing only on rust against py; against base
# nothing only on rust (what base's Rust walker already fails is listed by id); each plant row with ids only it fails.
O=${1:-~/sa-rust-ids-work/sa-port-358}
ids() { grep -E '^(FAILED|ERROR) ' $1/pytest.log | cut -d' ' -f2 | LC_ALL=C sort -u; }
for k in py rust base; do echo "$k: $(cat $O/k-$k/exit.txt) | deep: $(cat $O/k-$k-deep.rc) | .so $(head -n 1 $O/k-$k.so.txt | cut -c1-16) tree $(tail -n 1 $O/k-$k.so.txt | cut -c1-8)"; done
echo "only on rust against py: $(LC_ALL=C comm -13 <(ids $O/k-py) <(ids $O/k-rust) | wc -l); only on py: $(LC_ALL=C comm -23 <(ids $O/k-py) <(ids $O/k-rust) | wc -l)"
echo "only on rust against base: $(LC_ALL=C comm -13 <(ids $O/k-base) <(ids $O/k-rust) | wc -l); only on base's Rust walker:"
LC_ALL=C comm -23 <(ids $O/k-base) <(ids $O/k-rust) | sed 's/^/  /'
echo "failing on py, rust and base alike:"; LC_ALL=C comm -12 <(ids $O/k-py) <(ids $O/k-base) | sed 's/^/  /'
for d in $O/p-*/; do pl=$(basename $d); pl=${pl#p-}
  LC_ALL=C comm -13 <(ids $O/k-rust) <(ids $O/p-$pl) > $O/p-$pl.only.txt
  echo "convert:$pl: $(cut -d' ' -f2- $O/p-$pl/exit.txt | cut -c1-60); failing only under the plant: $(wc -l < $O/p-$pl.only.txt); passing only under it: $(LC_ALL=C comm -23 <(ids $O/k-rust) <(ids $O/p-$pl) | tr '\n' ' ')"
done
