#!/bin/bash
# rb334.sh REF TAG (sa-port-334, pareto1): rowbit334.py on the 20 workloads on origin/REF, Python's walker (c=py) and
# Rust's (c=rust), in pc334.sh's clone and target. Rows: $O/c$c/WL.json and $O/exit.txt. End marker: $O/end.txt, by fin().
REF=${1:?ref}; TAG=${2:?tag}
export REAL=/home/tilo CARGO_HOME=/home/tilo/.cargo RUSTUP_HOME=/home/tilo/.rustup PATH=/home/tilo/.cargo/bin:$PATH HOME=/home/tilo/sp19
X=$HOME/sa-rust-ids-work/sa-port-334; O=$X/rb-$TAG; rm -rf $O; mkdir -p $O
H=$HOME/dev/sa-port-334-pc
fin() { echo "END $1 $(date -u +%FT%TZ)" > $O/end.txt; exit; }
git -C $H fetch -q origin && git -C $H checkout -q -f --detach $REF || fin clone-failed
. $HOME/sa-rust-ids-work/env.sh; export PY W SA_EVAL_DATA PYTHONHASHSEED O H X
(cd $H/rust-spike/slice/solver_rs && CARGO_TARGET_DIR=$X/target PYO3_PYTHON=$PY cargo build --release > $O/build.log 2>&1 && cp $X/target/release/libsa_solver.so ../sa_solver.so) || fin build-failed
(git -C $H rev-parse --short HEAD; sha256sum $H/rust-spike/slice/sa_solver.so; echo "seed $PYTHONHASHSEED") > $O/tree.txt
cd $H/rust-spike/slice; export PYTHONPATH=$H:$W/sympy:$W/shim
unset SLICE_CONVERT_PLANT SLICE_SESSION_PLANT SLICE_TERM_PLANT SLICE_TERM_FRAMES
WLS="lra f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls"
one() { n=$(echo $1 | tr -d :); c=$2; d=$O/c$c; mkdir -p $d
  SLICE_CONVERT=$c timeout 14400 $PY $X/rowbit334.py $1 $d/$n.json > $d/$n.out 2>&1; echo "rb c=$c $1 run $? $(date -u +%T)" >> $O/exit.txt; }
export -f one
for c in py rust; do for w in $WLS; do echo "$w $c"; done; done | xargs -P 8 -L 1 bash -c 'one "$@"' _
fin done
