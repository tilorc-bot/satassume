# env346.sh: sa-port-346's environment on orion, own tree first (ENV TRAP: env.sh puts ~/dev/sa-rust on PYTHONPATH)
W=$HOME/sa-rust-ids-work
. $W/env.sh
T=$W/sa-port-346/wt
export SLICE_DIR=$T/rust-spike/slice PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$T:$W/sympy:$W/shim
