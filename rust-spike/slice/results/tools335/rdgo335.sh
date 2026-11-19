#!/bin/bash
# rdgo335.sh (sa-port-335, orion): rootof rows of head (f4ce4b2 source, 332's worktree) twice and of base (ec34788, 324's worktree),
# per walker cell. End marker: rd/end.txt, written by the last line.
O=/home/tilo/sa-rust-ids-work/sa-port-335
printf '%s\n' "/home/tilo/sa-rust-ids-work/sa-port-332/wt head1 py rootof" "/home/tilo/sa-rust-ids-work/sa-port-332/wt head2 py rootof" "/home/tilo/sa-rust-ids-work/sa-port-324/wt base1 py rootof" "/home/tilo/sa-rust-ids-work/sa-port-332/wt head1r rust rootof" "/home/tilo/sa-rust-ids-work/sa-port-324/wt base1r rust rootof" "/home/tilo/sa-rust-ids-work/sa-port-324/wt base2 py rootof" | xargs -P 3 -L 1 bash $O/tools/rd335.sh
echo "END $(date -u +%FT%TZ)" > $O/rd/end.txt
