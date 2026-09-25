# Agent report: refine capability baseline on main merged with refine-identities

- **Date:** 2026-09-25
- **Status:** measured; nothing merged or pushed from the merge. This is the
  "before" for stage 3 of `2026-09-25-fact-lattice-theory-plan.md` (its
  section 5, item 6).
- **Scope:** a temporary worktree of `main` at `6b935d7` with
  `origin/refine-identities` at `eb106a6` merged on top (merge commit
  `21318c5`, local only, clean merge, worktree deleted afterwards).
  Scripts: `agent-reports/scripts/refine_baseline_plugin.py`,
  `refine_baseline_counts.py`, `refine_battery_time.sh`.
- **Read this if:** you need the numbers any engine change on `main` is
  compared with on the refine side, or you need to reproduce them

## 1. SymPy pin

`refine-identities` is developed against SymPy at `6379c4da69` (its
report `archive/2026-09-25-phase-2-baseline.md`; `tools/refine_gates.sh`
defaults to `/home/tilo/orion/sympy`, which does not exist on this
machine). That commit is not the reasoning pin `ddbb536d7e` that
`/home/tilo/sympy` is at: it is one commit, "Add refine handler for
conjugate", on a base 24 commits older than `ddbb536`. Everything below
uses `6379c4da69`, extracted with `git archive` so the SymPy repository is
untouched. At `ddbb536` the refine suite collects 473 tests instead of 474
and each backend passes one fewer (sympy 462, satassume 416, combined
466); the losses are the same.

## 2. Scoreboard (`tools/refine_scoreboard.py`, suite `tests/refine`, default handlers)

| backend | passed | failed | xfailed | total | suite time |
|---|---:|---:|---:|---:|---:|
| sympy | 463 | 7 | 4 | 474 | 120.9 s |
| satassume | 417 | 55 | 2 | 474 | 23.2 s |
| combined | 467 | 3 | 4 | 474 | 51.2 s |

(Suite times are pytest's own and were taken while a fuzz ran on the
other cores. They are indicative only. The battery times in section 4
were taken on a quiet machine.)

**satassume's losses against sympy:** 52, and none in scope (0 tests
that fail on in-scope queries only). The Pi's stage 0 found the same 52
on `refine-monorepo` with the current engine.

| category | tests | which |
|---|---:|---|
| matrix predicates | 45 | `test_refine_matrix_*` (18), `test_refine_verifier_matrix` (25), `test_matrixelement` in `test_refine` and `test_sympy_refine_suite` (2) |
| relation, ordering against `pi`/`pi/2` (no theory interprets it) | 6 | inverse-trig principal branches (4 in `test_refine_inverse_trig`), `test_atan_rule_at_closed_interval_endpoints`, `test_quoted_rule_outputs` |
| relation, stale expectation | 1 | `test_kronecker_reversed_assumption_order` expects `refine(KroneckerDelta(i, j), Q.eq(i, j))` unchanged; the engine now answers it |

Other sections: 1 satassume win on in-scope queries, 5 tests pass under
satassume only because a handler did not fire, 0 combination-only wins, 3
tests fail under every backend.

**SymPy fallbacks in the combined backend.** On this branch the combined
backend no longer asks SymPy on every satassume `None`
(`satrefine.backend.route`): it asks only when satassume has no model of
the query. From the query log of the combined run:

| | queries | distinct |
|---|---:|---:|
| all queries | 6,816 | 1,459 |
| SymPy asked, matrix predicate | 541 | |
| SymPy asked, relation no theory interprets (`no-theory`) | 124 | |
| SymPy asked, inconsistent assumptions | 1 | |
| **SymPy fallbacks, total** | **666** | 170 |
| satassume `None` that stands (the old combined backend asked SymPy on these) | 2,877 | 655 |

SymPy's answers on the fallbacks: matrix 202 True, 172 False, 167 None;
`no-theory` 56 True, 22 False, 46 None. The 124 `no-theory` fallbacks are
the ones the fact-lattice plan's free-Boolean change (its section 3,
last row) could move to satassume; matrix fallbacks are outside any
scalar design. The Pi's stage 0 counts (3,412 to 3,645 fallbacks) used
the old backend, where every `None` was a fallback; they are not
comparable with 666.

## 3. Answers per backend (same suite, from the query logs)

| backend | queries | True | False | None |
|---|---:|---:|---:|---:|
| sympy | 6,708 | 2,347 | 1,240 | 3,121 |
| satassume | 6,632 | 2,080 | 1,190 | 3,362 |
| combined | 6,816 | 2,340 | 1,386 | 3,090 |

Query counts differ because handlers take different paths on different
answers.

## 4. The battery (`tools/refine_identity_scoreboard.py`, `battery_v3.py`, 1,736 cases, `handlers_identities`)

Wall time of the whole command (start-up, row counting and the battery),
interleaved, two rounds, unpinned, on a quiet machine (load under 1):

| backend | round 1 | round 2 | best |
|---|---:|---:|---:|
| satassume | 95.3 s | 91.5 s | **91.5 s** |
| combined | 106.4 s | 106.8 s | **106.4 s** |
| sympy | 226.1 s | 226.1 s | **226.1 s** |

Outcomes (identical in both rounds):

| backend | same as v3 | other form | miss | unchanged as expected | extra | numerically wrong | unchecked |
|---|---:|---:|---:|---:|---:|---:|---:|
| satassume | 982 | 42 | 62 | 639 | 11 | 0 | 134 |
| combined | 1,032 | 41 | 13 | 639 | 11 | 0 | 183 |
| sympy | 1,021 | 41 | 20 | 641 | 9 | 4 | |

satassume's battery misses against combined are the matrix family (52
misses against 3) plus one inverse case in another form. SymPy alone
misses 7 more than combined (combinatorial, integer functions) and has 4
numerically wrong outputs (1 complex parts, 3 power/exp/log). The
refine-identities reports quote 14.8 s for the battery under satassume on
their machine: that figure is the battery alone on one pinned fast core,
not this command's wall time.

## 5. Recipe

```bash
cd /home/tilo/satassume
git worktree add --detach /tmp/claude-1000/ri-merge main          # main at 6b935d7
git -C /tmp/claude-1000/ri-merge merge --no-edit origin/refine-identities   # eb106a6, clean
mkdir -p /tmp/claude-1000/sympy-6379
git -C /home/tilo/sympy archive 6379c4da69 | tar -x -C /tmp/claude-1000/sympy-6379
cd /tmp/claude-1000/ri-merge
S=/tmp/claude-1000/sympy-6379; O=/tmp/claude-1000/ri-sb; P=/home/tilo/satassume/agent-reports/scripts
# one backend per command (each about 25 to 125 s), then combine
for b in sympy satassume combined; do
  PYTHONHASHSEED=0 PYTHONPATH=$P:.:$S PYTEST_ADDOPTS="-p refine_baseline_plugin" \
    REFINE_BASELINE_QLOG=$O/q-$b.jsonl timeout 265 /home/tilo/satassume/.venv/bin/python \
    tools/refine_scoreboard.py --backends $b --junit-dir $O > $O/run-$b.txt
done
PYTHONPATH=.:$S /home/tilo/satassume/.venv/bin/python tools/refine_scoreboard.py --reuse $O
/home/tilo/satassume/.venv/bin/python $P/refine_baseline_counts.py $O
# battery, interleaved, one round per command (sympy alone takes about 226 s)
$P/refine_battery_time.sh $S $O 1 satassume combined
$P/refine_battery_time.sh $S $O 1 sympy
$P/refine_battery_time.sh $S $O 2 combined satassume
$P/refine_battery_time.sh $S $O 2 sympy
cd /home/tilo/satassume && git worktree remove --force /tmp/claude-1000/ri-merge
```

`pytest-xdist` is not installed in the venv, so the refine-identities
suite (`tests/refine_identities`, run with `-n 3` and a 2,400 s timeout by
`refine_gates.sh`) was not run here; the battery covers the
`handlers_identities` package.

## 6. What stage 3 compares against

- Scoreboard losses: 52 (45 matrix, 6 relation against `pi`, 1 stale
  expectation).
- Combined backend: 666 SymPy fallbacks (124 `no-theory`), 2,877
  standing `None` answers.
- Battery: satassume 62 misses, combined 13; best wall times 91.5 s,
  106.4 s, 226.1 s.
