#!/usr/bin/env bash
# Run the phase-2 gates for handlers_identities in parallel and print a compact summary.
#
#   satrefine/tools/refine_gates.sh OUTDIR [BASEDIR]    (tools/refine_gates.sh is a shim for it)
#
# Runs, all with PYTHONHASHSEED=0, JOBS at a time from this run (default 6), and at most
# SLOTS gate jobs machine-wide across concurrent gate runs (default 8; lock files in
# $GATE_SLOTS_DIR, default /tmp/refine-gate-slots; the suite holds 3 slots for its workers):
#   the tests/refine_identities suite (pytest-xdist, SUITE_WORKERS workers, default 3),
#   the battery scoreboard (scoreboard battery) in both SATREFINE_IDENTITIES modes,
#   the differential against handlers_v3 for seeds 2, 3, 7 at 1,500 cases in both modes,
#   the same for seed 2 with SATREFINE_BACKEND=satassume, in both modes,
#   the extended family (--ext: infinities, Piecewise, inverse pairs) for seed 2 at EXT_CASES
#   cases (default 1,000; 20 s per-case timeout, KroneckerDelta at +-oo is slow) and the matrix family (--matrices) for seed 2 at MAT_CASES cases
#   (default 1,500), both in both modes, as sections of their own (the default seeds' case
#   streams are unchanged, so their sections still compare 1:1 with older baselines),
#   the tests behind the opt-in marker `full` (the full fixpoints; SATREFINE_FULL_TESTS=1),
#   the termination tests (B9) with the adversarial-ask fuzz on their own, so the summary shows
#   they ran: small by default (as in the suite, seconds); TERMINATION_FUZZ=N runs N random
#   cases and the whole battery instead (N=150: about 10 minutes on one core).
# Full logs go to OUTDIR; the summary goes to OUTDIR/summary.txt and stdout.
# With BASEDIR (an earlier OUTDIR), prints the lines of the summary that changed, per
# section; a section the baseline lacks (a gate added since) prints "no baseline".
# Re-running into an existing OUTDIR only re-runs the tasks that did not finish with
# exit 0 (the suite: exit 0 or 1), so a run cut short by a timeout can be completed.
# Start it detached and wait in short chunks (agent-reports/...how-work-gets-lost.md, section 6):
#   nohup satrefine/tools/refine_gates.sh /path/out > /path/out.log 2>&1 &
set -u
out=${1:?usage: refine_gates.sh OUTDIR [BASEDIR]}
base=${2:-}
jobs=${JOBS:-6}
workers=${SUITE_WORKERS:-3}
termfuzz=${TERMINATION_FUZZ:-0}
extcases=${EXT_CASES:-1000}
matcases=${MAT_CASES:-1500}
export GATE_SLOTS=${SLOTS:-8} GATE_SLOTS_DIR=${GATE_SLOTS_DIR:-/tmp/refine-gate-slots}
mkdir -p "$GATE_SLOTS_DIR"
mkdir -p "$out"
cd "$(dirname "$0")/../.."
export PYTHONHASHSEED=0 PYTHONPATH=.:${SYMPY_PATH:-/home/tilo/orion/sympy}
uvrun=(uv run --no-project --with pytest --with pytest-xdist --with mpmath --with hypothesis python)

tasks=()
tasks+=("suite|timeout 2400 ${uvrun[*]} -m pytest -q -p no:cacheprovider -n $workers tests/refine_identities")
tasks+=("full|env SATREFINE_FULL_TESTS=1 timeout 2400 ${uvrun[*]} -m pytest -q -p no:cacheprovider -n 3 -m full tests/refine_identities")
for m in generated live; do
  tasks+=("score-$m|env SATREFINE_IDENTITIES=$m timeout 3000 ${uvrun[*]} -m satrefine.tools.scoreboard battery")
  for s in 2 3 7; do
    tasks+=("diff-$m-$s|env SATREFINE_IDENTITIES=$m timeout 3600 ${uvrun[*]} -m satrefine.tools.refine_differential --summary --seed $s --cases 1500")
  done
  tasks+=("diffsa-$m-2|env SATREFINE_BACKEND=satassume SATREFINE_IDENTITIES=$m timeout 3600 ${uvrun[*]} -m satrefine.tools.refine_differential --summary --seed 2 --cases 1500")
  tasks+=("diffext-$m-2|env SATREFINE_IDENTITIES=$m timeout 3600 ${uvrun[*]} -m satrefine.tools.refine_differential --summary --ext --timeout 20 --seed 2 --cases $extcases")
  tasks+=("diffmat-$m-2|env SATREFINE_IDENTITIES=$m timeout 3600 ${uvrun[*]} -m satrefine.tools.refine_differential --summary --matrices --seed 2 --cases $matcases")
done
tasks+=("termination|env SATREFINE_TERMINATION_FUZZ=$termfuzz timeout 3000 ${uvrun[*]} -m pytest -q -s -p no:cacheprovider tests/refine_identities/test_engine_termination.py")

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
    grep -E '^ +[0-9]+  ' "$out/score-$m.log" | tail -10
    sed -n '/^open differences/,/^$/p; /^stale accepted/,/^$/p' "$out/score-$m.log" | sed '/^$/d'
  done
  for m in generated live; do for s in 2 3 7; do
    echo "== differential $m seed $s (exit $(cat "$out/diff-$m-$s.exit"))"
    tail -15 "$out/diff-$m-$s.log"
  done; done
  for m in generated live; do
    echo "== differential satassume $m seed 2 (exit $(cat "$out/diffsa-$m-2.exit"))"
    tail -15 "$out/diffsa-$m-2.log"
  done
  for m in generated live; do
    echo "== differential ext $m seed 2, $extcases cases (exit $(cat "$out/diffext-$m-2.exit"))"
    tail -15 "$out/diffext-$m-2.log"
  done
  for m in generated live; do
    echo "== differential matrices $m seed 2, $matcases cases (exit $(cat "$out/diffmat-$m-2.exit"))"
    tail -15 "$out/diffmat-$m-2.log"
  done
  echo "== full fixpoint tests, marker full (exit $(cat "$out/full.exit"))"
  grep -E '[0-9]+ (passed|failed|skipped)|^FAILED' "$out/full.log" | sed 's/ - .*//' | tail -8
  echo "== termination tests, fuzz size ${termfuzz} (exit $(cat "$out/termination.exit"))"
  grep -E '^termination fuzz:|[0-9]+ (passed|failed)|^FAILED' "$out/termination.log" | sed 's/ - .*//' | tail -12
} > "$out/summary.txt"
cat "$out/summary.txt"
if [ -n "$base" ] && [ -f "$base/summary.txt" ]; then
  # compare section by section ("== ..." headers), so a
  # baseline made before a gate existed says "no baseline" for that gate only
  echo "== changed against $base"
  split_sections() {   # summary -> directory of one file per section
    mkdir -p "$2"
    awk -v d="$2" '/^== /{f=$0; sub(/ \(exit [^)]*\)$/, "", f); gsub(/[^A-Za-z0-9]+/, "_", f); print f > (d "/.order"); f=d "/" f}
                   f {print > f}' "$1"
  }
  tmp=$(mktemp -d)
  split_sections "$base/summary.txt" "$tmp/base"
  split_sections "$out/summary.txt" "$tmp/new"
  changed=0
  for f in $(cat "$tmp/new/.order"); do
    if [ ! -f "$tmp/base/$f" ]; then
      echo "$(head -1 "$tmp/new/$f"): no baseline"
    elif ! cmp -s "$tmp/base/$f" "$tmp/new/$f"; then
      changed=1; echo "$(head -1 "$tmp/new/$f")"
      diff "$tmp/base/$f" "$tmp/new/$f"
    fi
  done
  [ $changed = 0 ] && echo "(no change in the sections the baseline has)"
  rm -rf "$tmp"
fi
