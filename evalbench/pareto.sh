#!/bin/sh
# evalbench/pareto.sh sync NAME=DIR ...   copy the harness, data, SymPy, satsimp
#                                          and the named trees to pareto1:~/sa-eval-bench
# evalbench/pareto.sh ab OUTNAME NAME ...  the pinned A/B there, under a quiet
#                                          whole-machine lease (machine run --quiet)
# Trees are byte-compiled here first (the container mounts them read-only).
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
host=${SA_EVAL_HOST:-pareto1}
wd=sa-eval-bench
py=$here/.venv/bin/python
cmd=$1; shift
case $cmd in
sync)
    ssh "$host" "mkdir -p $wd/src $wd/image $wd/results"
    for t in "$@"; do
        name=${t%%=*} dir=${t#*=}
        "$py" -m compileall -q -j 4 "$dir/satassume" >/dev/null
        rsync -a --delete --exclude .git "$dir/satassume" "$dir/tests" "$host:$wd/src/$name/"
    done
    "$py" -m compileall -q -j 4 "$here/ext/sympy/sympy" "$here/ext/satsimp/satsimp" "$here/ext/satsimp/satrefine" "$here/ext/satsimp/tests" >/dev/null || true
    ssh "$host" "mkdir -p $wd/image $wd/results"
    rsync -a --delete --exclude __pycache__ --exclude results "$here/evalbench/" "$host:$wd/evalbench/"
    rsync -a "$here/ext/sympy/" "$host:$wd/sympy/"
    rsync -a --delete --exclude .git "$here/ext/satsimp/" "$host:$wd/satsimp/"
    rsync -a /home/tilo/dev/rete-impl/data/ "$host:$wd/data/"
    rsync -a "$here/secret/" "$host:$wd/secret/"
    printf 'FROM reteassume-bench:1\nENV PYTHONPATH=\n' | ssh "$host" "cat > $wd/image/Dockerfile"
    ssh "$host" "cd $wd && ~/bin/bench-container build sa-eval-bench:1 image >/dev/null && docker image inspect sa-eval-bench:1 --format '{{.Id}}'"
    ;;
ab)
    out=$1; shift
    trees=""
    for n in "$@"; do trees="$trees --tree $n=/work/src/$n"; done
    rounds=${ROUNDS:-5} warm=${WARMUP:-1} wls=${WORKLOADS:-dev,ho-stream,ho-battery,ho-fuzz,corpus,fork-battery}
    inner="SA_EVAL_DATA=/work/data SA_EVAL_SYMPY=/work/sympy SA_EVAL_SATSIMP=/work/satsimp SA_EVAL_SECRET=/work/secret SA_EVAL_SHIM=/tmp/shim python -m evalbench.ab $trees --rounds $rounds --warmup $warm --workloads $wls --out /results/$out.jsonl"
    machine run "$host" --quiet -r "sa-eval A/B $out" -- \
        "cd $wd && BENCH_RESULTS_DIR=\$HOME/$wd/results/$out ${BENCH_CPU:+BENCH_CPU=$BENCH_CPU} ~/bin/bench-container run sa-eval-bench:1 \$HOME/$wd -- sh -c '$inner'"
    mkdir -p "$here/bench-results/$out"
    rsync -a "$host:$wd/results/$out/" "$here/bench-results/$out/"
    "$py" -m evalbench.summarize "$here/bench-results/$out/$out.jsonl"
    ;;
esac
