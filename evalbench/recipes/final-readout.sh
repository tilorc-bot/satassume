#!/bin/sh
# RECIPE (as run for FINAL-READOUT.md, 10:55Z): sync -> pareto1 C builds (shared lease) -> .so load check -> 6-arm A/B;
# orion: judge --skip-ab --build per C tree.  Copy, edit the tree names, set S to your scratchpad.
# FINAL readout: 6-arm A/B on pareto1 (now) + C gates on orion (after combo.sh).
S=${S:-/tmp/sa-eval-recipe}; mkdir -p $S
cd ~/dev/sa-eval
F2=final-321-3a7b03a F3=final-320C-276dab1 F4=final-merge321-320C-a300007 F5=final-lra-320C-03ddfb0 F6=sa-cy-3C-e61e024
APP=tests.test_engine::test_contextual_queries_build_and_discard
BUILD="SATASSUME_CYTHON=1 /home/tilo/dev/sa-cy/.bvenv/bin/python setup.py build_ext --inplace -j 8"
date -u
evalbench/pareto.sh sync $F2=cands/$F2 $F3=cands/$F3 $F4=cands/$F4 $F5=cands/$F5 $F6=cands/$F6 >/dev/null 2>&1 || { echo SYNC FAILED; exit 1; }
(
  set -x
  for t in $F3 $F4 $F5 $F6; do
    X=""; [ $t = $F6 ] && X="-e CPPFLAGS=-DCYTHON_USE_TYPE_SPECS=1"
    rsync -a cands/$t/setup.py cands/$t/pyproject.toml cands/$t/README.md pareto1:sa-eval-bench/src/$t/
    machine run pareto1 --shared -r "sa-eval-3 cython build $t" -- 'cd sa-eval-bench/src/'$t' && docker run --rm --user $(id -u):$(id -g) -e HOME=/tmp -e SATASSUME_CYTHON=1 '"$X"' -v $PWD:/w -w /w sa-cy-build:1 python setup.py build_ext --inplace --force -j 8 >/tmp/sa-eval3-cybuild-'$t'.log 2>&1; tail -1 /tmp/sa-eval3-cybuild-'$t'.log; find satassume -name "*.so" | wc -l'
  done
  for t in $F2 $F3 $F4 $F5 $F6; do
    ssh pareto1 "docker run --rm -v \$HOME/sa-eval-bench:/work:ro -e PYTHONPATH=/work/src/$t:/work/sympy sa-eval-bench:1 python -c \"import importlib; print('$t', [importlib.import_module(m).__file__.rsplit('/',1)[1] for m in ['satassume.sat.solver','satassume.engine','satassume.sympy_api']])\""
  done
  ROUNDS=7 WORKLOADS=dev,ho-stream,ho-battery,final-fuzz,ho-fuzz,corpus,fork-battery evalbench/pareto.sh ab ab-final base $F2 $F3 $F4 $F5 $F6 > $S/final-ab.log 2>&1
  echo "A/B exit $?"; date -u
  .venv/bin/python -m evalbench.summarize bench-results/ab-final/ab-final.jsonl
) > $S/final-pareto.log 2>&1 &
: # (originally waited here for an earlier chain)
date -u; echo "combo gates done; final gates start"
for spec in "final-merge321-320C /home/tilo/dev/sa-eval a300007 --approved-test $APP" "final-320C /home/tilo/dev/sa-eval 276dab1" \
            "final-lra-320C /home/tilo/dev/sa-eval 03ddfb0" "sa-cy-3C /home/tilo/dev/sa-cy e61e024"; do
  set -- $spec; tag=$1; shift
  B="$BUILD"; [ $tag = sa-cy-3C ] && B="CPPFLAGS=-DCYTHON_USE_TYPE_SPECS=1 SATASSUME_CYTHON=1 /home/tilo/dev/sa-cy/.bvenv/bin/python setup.py build_ext --inplace --force -j 8"
  .venv/bin/python -m evalbench.judge $tag "$@" --skip-ab --build "$B" --check-modules satassume.sat.solver,satassume.engine --note "final readout, gates only (C built)" > $S/judge-$tag.log 2>&1
  date -u; echo $tag; tail -1 $S/judge-$tag.log
done
wait
echo ALL DONE; date -u
