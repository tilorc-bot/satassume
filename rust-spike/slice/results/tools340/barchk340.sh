#!/bin/bash
# barchk340.sh (sa-port-340, pareto1): the checks of bar.sh's three debts on the pushed branch, by the bar itself.
#  void   a fresh clone with no .so and no build phase: bar.sh must end 3 with done.txt VOID ([148])
#  fired  build, tests, the plain suite, the plants phase and four suite rows: two witness plants, a term plant, the
#         dispatch plant 753, a convert plant and witness:on; the sum must show fired > 0 on the plant rows ([146],
#         [147]), "no counter" on the convert row and 0 on witness:on
# End marker: ~/sp19/sa-rust-ids-work/sa-port-340/barchk-end.txt
export HOME=/home/tilo/sp19; R=$HOME/sa-rust-ids-work/sa-port-340; BR=port/witness-reasons
bash $HOME/bar-sa-port-340.sh sa-port-340-void $BR tests sum > $R/barchk-void.log 2>&1; v=$?
PLANTS="witness:on witness:single witness:skip-own dispatch-nan-arg-on" SUITE_PLANTS="witness:on witness:single witness:integer-half term:mark-wrong-pattern dispatch-nan-arg-on convert:enc-int-no-sign" \
  BASE=$R/s7n0-340-29c5a0db/noplant bash $HOME/bar-sa-port-340.sh sa-port-340-fired $BR build tests suite live plants suiteplants sum > $R/barchk-fired.log 2>&1; f=$?
echo "END void $v fired $f $(date -u +%FT%TZ)" > $R/barchk-end.txt
