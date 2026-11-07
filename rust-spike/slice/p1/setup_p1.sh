set -e
R=$HOME/sp19; mkdir -p $R/sa-rust-ids-work $R/dev
cd $R/sa-rust-ids-work
PATH=$HOME/.cargo/bin:$PATH
[ -x venv/bin/python ] || uv venv --python 3.12.14 venv
uv pip install --python venv/bin/python hypothesis==6.170.14 mpmath==1.3.0 pytest==9.2.0 pytest-xdist==3.8.0 sortedcontainers==2.4.0 >/dev/null
cat > env.sh <<'E2'
W=$HOME/sa-rust-ids-work
export SA_EVAL_DATA=$W/data PYTHONHASHSEED=0 PYTHONPATH=$W/sympy:$W/shim
PY=$W/venv/bin/python
E2
venv/bin/python --version; ls; which cargo; cargo --version; rustc --version; uname -m; echo $HOME
