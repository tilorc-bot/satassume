#!/usr/bin/env bash
# Run the phase-2 gates for handlers_identities in parallel and print a compact summary.
#
#   tools/refine_gates.sh OUTDIR [BASEDIR]
#
# Runs, all with PYTHONHASHSEED=0 and JOBS parallel processes (default 6):
#   the tests/refine_identities suite (pytest-xdist, SUITE_WORKERS workers, default 4),
#   the battery scoreboard in both SATREFINE_IDENTITIES modes,
#   the differential against handlers_v3 for seeds 2, 3, 7 at 1,500 cases in both modes.
# Full logs go to OUTDIR; the summary goes to OUTDIR/summary.txt and stdout.
# With BASEDIR (an earlier OUTDIR), prints the lines of the summary that changed.
# Start it detached and wait in short chunks (agent-reports/...how-work-gets-lost.md, section 6):
#   nohup tools/refine_gates.sh /path/out > /path/out.log 2>&1 &
set -u
out=${1:?usage: refine_gates.sh OUTDIR [BASEDIR]}
base=${2:-}
jobs=${JOBS:-6}
workers=${SUITE_WORKERS:-4}
mkdir -p "$out"
cd "$(dirname "$0")/.."
export PYTHONHASHSEED=0 PYTHONPATH=.:${SYMPY_PATH:-/home/tilo/orion/sympy}
uvrun=(uv run --no-project --with pytest --with pytest-xdist --with mpmath --with hypothesis python)

tasks=()
tasks+=("suite|timeout 2400 ${uvrun[*]} -m pytest -q -p no:cacheprovider -n $workers tests/refine_identities")
for m in generated live; do
  tasks+=("score-$m|env SATREFINE_IDENTITIES=$m timeout 3000 ${uvrun[*]} tools/refine_identity_scoreboard.py")
  for s in 2 3 7; do
    tasks+=("diff-$m-$s|env SATREFINE_IDENTITIES=$m timeout 1800 ${uvrun[*]} tools/refine_differential.py --summary --seed $s --cases 1500")
  done
done

start=$(date +%s)
printf '%s\n' "${tasks[@]}" | xargs -P "$jobs" -I{} bash -c '
  name=${1%%|*}; cmd=${1#*|}
  $cmd > "$2/$name.log" 2>&1; echo "$?" > "$2/$name.exit"' _ {} "$out"

{
  echo "gates: $(git rev-parse --short HEAD) in $(( $(date +%s) - start )) s, jobs=$jobs"
  echo "== suite (exit $(cat "$out/suite.exit"))"
  grep -E '^FAILED|^ERROR|[0-9]+ (passed|failed)' "$out/suite.log" | sed 's/ - .*//' | tail -30
  for m in generated live; do
    echo "== scoreboard $m (exit $(cat "$out/score-$m.exit"))"
    grep -E '^  (family|[a-z_]+) +[0-9]|^  family' "$out/score-$m.log" | tail -12
    grep -E '^ +[0-9]+  ' "$out/score-$m.log" | tail -8
  done
  for m in generated live; do for s in 2 3 7; do
    echo "== differential $m seed $s (exit $(cat "$out/diff-$m-$s.exit"))"
    tail -15 "$out/diff-$m-$s.log"
  done; done
} > "$out/summary.txt"
cat "$out/summary.txt"
if [ -n "$base" ] && [ -f "$base/summary.txt" ]; then
  echo "== changed against $base"
  diff <(grep -v '^gates:' "$base/summary.txt") <(grep -v '^gates:' "$out/summary.txt") && echo "(no change)"
fi
