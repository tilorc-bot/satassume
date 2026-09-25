#!/usr/bin/env bash
# Run the phase-2 gates for handlers_identities in parallel and print a compact summary.
#
#   tools/refine_gates.sh OUTDIR [BASEDIR]
#
# Runs, all with PYTHONHASHSEED=0, JOBS at a time from this run (default 6), and at most
# SLOTS gate jobs machine-wide across concurrent gate runs (default 8; lock files in
# $GATE_SLOTS_DIR, default /tmp/refine-gate-slots; the suite holds 3 slots for its workers):
#   the tests/refine_identities suite (pytest-xdist, SUITE_WORKERS workers, default 3),
#   the battery scoreboard in both SATREFINE_IDENTITIES modes,
#   the differential against handlers_v3 for seeds 2, 3, 7 at 1,500 cases in both modes.
# Full logs go to OUTDIR; the summary goes to OUTDIR/summary.txt and stdout.
# With BASEDIR (an earlier OUTDIR), prints the lines of the summary that changed.
# Re-running into an existing OUTDIR only re-runs the tasks that did not finish with
# exit 0 (the suite: exit 0 or 1), so a run cut short by a timeout can be completed.
# Start it detached and wait in short chunks (agent-reports/...how-work-gets-lost.md, section 6):
#   nohup tools/refine_gates.sh /path/out > /path/out.log 2>&1 &
set -u
out=${1:?usage: refine_gates.sh OUTDIR [BASEDIR]}
base=${2:-}
jobs=${JOBS:-6}
workers=${SUITE_WORKERS:-3}
export GATE_SLOTS=${SLOTS:-8} GATE_SLOTS_DIR=${GATE_SLOTS_DIR:-/tmp/refine-gate-slots}
mkdir -p "$GATE_SLOTS_DIR"
mkdir -p "$out"
cd "$(dirname "$0")/.."
export PYTHONHASHSEED=0 PYTHONPATH=.:${SYMPY_PATH:-/home/tilo/orion/sympy}
uvrun=(uv run --no-project --with pytest --with pytest-xdist --with mpmath --with hypothesis python)

tasks=()
tasks+=("suite|timeout 2400 ${uvrun[*]} -m pytest -q -p no:cacheprovider -n $workers tests/refine_identities")
for m in generated live; do
  tasks+=("score-$m|env SATREFINE_IDENTITIES=$m timeout 3000 ${uvrun[*]} tools/refine_identity_scoreboard.py")
  for s in 2 3 7; do
    tasks+=("diff-$m-$s|env SATREFINE_IDENTITIES=$m timeout 3600 ${uvrun[*]} tools/refine_differential.py --summary --seed $s --cases 1500")
  done
done

start=$(date +%s)
printf '%s\n' "${tasks[@]}" | xargs -P "$jobs" -I{} bash -c '
  name=${1%%|*}; cmd=${1#*|}
  if [ -f "$2/$name.exit" ]; then
    e=$(cat "$2/$name.exit"); [ "$e" = 0 ] && exit 0; [ "$name" = suite ] && [ "$e" = 1 ] && exit 0
  fi
  need=1; [ "$name" = suite ] && need=3
  # take $need slots machine-wide (slot i is lock file $GATE_SLOTS_DIR/i)
  while :; do
    fds=(); got=0
    for i in $(seq 1 "$GATE_SLOTS"); do
      exec {fd}>"$GATE_SLOTS_DIR/$i"
      if flock -n "$fd"; then fds+=("$fd"); got=$((got+1)); [ $got -ge $need ] && break
      else exec {fd}>&-; fi
    done
    [ $got -ge $need ] && break
    for fd in "${fds[@]}"; do exec {fd}>&-; done
    sleep 10
  done
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
