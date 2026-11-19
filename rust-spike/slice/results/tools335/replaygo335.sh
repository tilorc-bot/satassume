#!/bin/sh
# replaygo335.sh: the four replays, two at a time. End marker: order/end.txt, written by the last line.
O=$HOME/sa-rust-ids-work/sa-port-335; H=$HOME/sa-rust-ids-work/sa-port-332/wt; B=$HOME/sa-rust-ids-work/sa-port-324/wt
printf '%s\n' "$H head-tree.order334 $O/order/sa-port-334.ids enc-int-no-sign" "$B base-tree.order334 $O/order/sa-port-334.ids enc-int-no-sign" "$H head-tree.order326 $O/order/sa-port-326.ids enc-int-no-sign" "$B base-tree.order326 $O/order/sa-port-326.ids enc-int-no-sign" | xargs -P 4 -L 1 sh $O/tools/replay335.sh
echo "END $(date -u +%FT%TZ)" > $O/order/end.txt
