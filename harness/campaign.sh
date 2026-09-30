#!/usr/bin/env bash
# The nightly history-independence campaign, one shard per call
# (the workflow .github/workflows/history-fuzz.yml runs the four shards
# in parallel).
#
#   harness/campaign.sh tests|base|profiles|audit|all
#
# Run from the repository root.  Size and seeds come from the environment:
#
#   SEEDS=8         random seeds per (profile, configuration) cell
#   SEED_OFFSET=0   first seed; the workflow moves it every night so that
#                   successive runs cover new streams (a run's seeds are
#                   printed and every discrepancy file carries its seed)
#   QUERIES=300     queries per base stream (profiles use half)
#   OUT=harness-results/campaign   where logs and shrunk repros go
#   PYTHON=python
#
# At SEEDS=8 a shard takes 3-20 minutes (base is the longest); the cost
# is linear in SEEDS.  Exit status 1 if a discrepancy of an undocumented
# family was found (--fail-on unknown); discrepancies of the known
# families are written as repros but do not fail.
set -u
SHARD=${1:-all}
SEEDS=${SEEDS:-8}
SEED_OFFSET=${SEED_OFFSET:-0}
QUERIES=${QUERIES:-300}
OUT=${OUT:-harness-results/campaign}
PYTHON=${PYTHON:-python}
export PYTHONHASHSEED=0
R="$SEED_OFFSET-$((SEED_OFFSET + SEEDS - 1))"
HALF=$((QUERIES / 2))
mkdir -p "$OUT/logs"
status=0
echo "shard $SHARD: seeds $R, $QUERIES queries per base stream, results in $OUT"

run() {   # run NAME ARGS...: one harness invocation, JSON lines to logs/NAME.jsonl
    local name=$1; shift
    echo "::group::$name: python -m harness $*"
    local t0=$SECONDS
    "$PYTHON" -m harness "$@" --out "$OUT/$name" --quiet --fail-on unknown \
        > "$OUT/logs/$name.jsonl" 2> "$OUT/logs/$name.err"
    local rc=$?
    cat "$OUT/logs/$name.err"
    echo "::endgroup::"
    echo "$name: exit $rc, $((SECONDS - t0)) s"
    [ $rc -ne 0 ] && status=1
    return 0
}

if [ "$SHARD" = tests ] || [ "$SHARD" = all ]; then
    # the slow pytest part, with more seeds and Hypothesis examples
    echo "::group::pytest -m slow tests/test_history.py"
    HISTORY_SLOW=1 HISTORY_SEEDS=6 HISTORY_EXAMPLES=200 \
        "$PYTHON" -m pytest -q -p no:cacheprovider -m slow tests/test_history.py \
        2>&1 | tee "$OUT/logs/pytest-slow.txt"
    [ "${PIPESTATUS[0]}" -ne 0 ] && status=1
    echo "::endgroup::"
    mkdir -p "$OUT/pytest" && cp -r harness-results/pytest/. "$OUT/pytest/" 2>/dev/null
fi

if [ "$SHARD" = base ] || [ "$SHARD" = all ]; then
    run fuzz-base   fuzz --seeds "$R" --queries "$QUERIES" --sets 6 --config default,tight,reuse,cone
    run fuzz-custom fuzz --seeds "$R" --queries "$QUERIES" --sets 6 --config default --custom
    run fuzz-lazy   fuzz --seeds "$R" --queries "$QUERIES" --sets 6 --config default --lazy 0.2
fi

if [ "$SHARD" = profiles ] || [ "$SHARD" = all ]; then
    run profiles       fuzz --profile all --seeds "$R" --queries "$HALF" --sets 4 --config default --custom
    run profiles-lazy  fuzz --profile links,transfer,lazy --seeds "$R" --queries "$HALF" --sets 4 \
                            --config whole,reuse
fi

if [ "$SHARD" = audit ] || [ "$SHARD" = all ]; then
    run audit      audit --profile base,related,declared,deep --seeds "$R" --queries 200 --sets 5
    run hashseed   hashseed --seeds "$SEED_OFFSET-$((SEED_OFFSET + 3))" --hashseeds 0,1,2,42 \
                            --queries 200 --config default
    run hashseed-links hashseed --profile links --seeds "$SEED_OFFSET-$((SEED_OFFSET + 3))" \
                            --hashseeds 0,1,2,42 --queries "$HALF" --sets 4 --config default
fi

# a summary: families per run (markdown, for $GITHUB_STEP_SUMMARY)
"$PYTHON" - "$OUT/logs" > "$OUT/summary.md" <<'EOF'
import glob, json, os, sys
from collections import Counter
from harness.checker import is_known_family
print("| run | streams | queries | family hits (per stream) | families |")
print("|---|---|---|---|---|")
for path in sorted(glob.glob(os.path.join(sys.argv[1], "*.jsonl"))):
    n = q = 0
    fams = Counter()
    for line in open(path):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        n += 1
        q += d.get("queries") or 0
        fams.update(d.get("families") or [])
        fams.update("cross-seed" for _ in range(d.get("cross_seed_disagreements") or 0))
    audit = "audit" in os.path.basename(path)
    cell = ", ".join(f"{f}{'' if is_known_family(f, audit=audit) else ' (NEW)'} x{c}"
                     for f, c in sorted(fams.items()))
    print(f"| {os.path.basename(path)[:-6]} | {n} | {q} | {sum(fams.values())} | {cell or '-'} |")
EOF
cat "$OUT/summary.md"
[ -n "${GITHUB_STEP_SUMMARY:-}" ] && { echo "### History campaign: $SHARD (seeds $R)"; cat "$OUT/summary.md"; } >> "$GITHUB_STEP_SUMMARY"
exit $status
