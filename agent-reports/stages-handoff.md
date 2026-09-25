# Handoff: agent "stages" (plan step 4), 2026-09-25

Read `agent-reports/2026-09-25-stages-report.md` first (the numbers
behind everything here). Worktree `/home/tilo/fable-rewrite/.claude/worktrees/ri-stages`,
branch `ri/stages`, head 04b9b1e plus this note. It is pushed and clean,
and no processes are running.

## Done

- **Go/no-go (report section 1): go, with a smaller headline.**
  complex_parts goes from 45 to 32 stated rows. Of its 27 base rows:
  - 9 never fired: SymPy evaluates their left sides when the node is built.
  - 6 derive from 2 definitions: `Abs(z) = z/sign(z)` and
    `arg(z) = -I*log(sign(z))`.
  - 2 follow from `ask`.
  - 10 stay stated.

  Definitions through `conjugate` were measured and rejected: they are
  unsound at infinity and lose facts about whole products.
- **Stage manifest and fixpoint** (`_stages.py`, `refine_specialize.py
  --write`). On the old tables it reproduced all four generated tables
  exactly, in 2 rounds (1,461 s).
- **Tables installed between stages** (`_dispatch.tables`, `live_for`).
  Derivation records are written as comments in the generated modules,
  with round, source row, rows fired and asks.
- **Regenerated tables at b44342b.** complex_parts has 4 new derived
  rules, and power_exp_log's bare `log(x)` row now comes last (the
  `n*log(-x) + I*pi` open item is closed).
- **Range rows.** `_simple.BOUNDS` is now `RANGES` rows in complex_parts
  and inverse.
- **Needs tests fixed and moved:** `render_one_symbol`,
  `case_split_zero_point`, `checker2_firing_cap_on_wide_input` (cap per
  chain) and `checker2_eq_of_equal_infinities`. The last needed identity
  rows to support `unless`, which the KroneckerDelta definition uses.
- **Gates at b44342b:** `/home/tilo/fable-rewrite/.claude/gates/stages-b44342b`
  (base `int-f686dcc`). They pass: suite 0 failed, live scoreboard
  identical, generated power_exp_log +2 same, 0 wrong, 0 crash, and the
  differential has no new unsound or numerically different result.

## In flight / not verified

Commits after b44342b have **not** been through a gate run:
- 6ae3602: a round skips a family unless a table at a key it looked up
  changed; compact imports.
- c8dab08: the merge of `origin/refine-identities` 4810c71.
- 04b9b1e: the firing cap per chain, the same-infinity proof of `eq`,
  and `unless` on identity rows.

Their targeted tests pass (engine, conditions, minmax_deltas, ablate:
172 passed). I stopped a fixpoint rerun of 04b9b1e (round 1 had
finished integer_funcs) at the handoff request. It never wrote anything.

## Next steps, in order

1. Rerun the fixpoint on the head, detached. It takes about 15 to 25
   minutes and writes `generated/*.py`:
   `nohup env PYTHONHASHSEED=0 PYTHONUNBUFFERED=1 PYTHONPATH=.:/home/tilo/orion/sympy timeout 3000 uv run --no-project --with mpmath python tools/refine_specialize.py --write --quiet > LOG 2>&1 &`
   Then:
   - Compare the rule rows with b44342b:
     `diff <(git show b44342b:satrefine/handlers_identities/generated/F.py | grep '^    (') <(grep '^    (' .../generated/F.py)`.
     The same-infinity `eq` proof or the chain cap could change a row;
     if one does, check it.
   - Record round 2's time. With 6ae3602 round 2 should regenerate only
     the families whose looked-up tables changed; I expect complex_parts
     alone, about 230 s against about 680 s.
   - Commit.
2. Run the gates on the new head against `int-f686dcc`, or against a
   newer shared baseline if the coordinator made one:
   `nohup tools/refine_gates.sh $G/stages-<head> $G/int-f686dcc > $G/stages-<head>.log 2>&1 &`,
   with `G=/home/tilo/fable-rewrite/.claude/gates`. **Do not edit the
   code while gates run**: jobs start later and import the worktree.
3. Update section 5 (gates) and section 6 (metrics) of the report with
   the new numbers. Recount rows with the scoreboard's `count_rows()`
   and lines with `--lines`.
4. Optional, and the least certain: stage 4 (report section 4). Trig
   definitions for `tan`, `cot`, `sec` and `csc` over `sin`/`cos` with a
   top-down fold save about 6 rows but move 6 to 14 trig cases to "other
   form". Hyperbolic through trig would fire where v3 expects unchanged.
   The prototype is `trigdef.py` in the old session scratchpad, which may
   be gone. I did not land it; it is a judgment call for the coordinator
   or user.

## Pitfalls

- `from sympy import *` after `from satrefine import refine` replaces
  `refine` with SymPy's own. In scripts, import
  `satrefine.handlers_identities._dispatch.refine` after the star import.
- `ruff check --fix --select I001` spreads parenthesized imports to one
  name per line, which inflates the code-line metric. Keep the compact
  style.
- Moving the last file out of `tests/refine_identities/needs/` makes git's
  directory-rename detection put new needs tests from later merges in the
  wrong directory. Check `git status` after a merge.
- Generation is slow: 25 to 320 s per family per round at load 10 to 15.
  Installing tables did not speed it up (report section 2).
- `BASE` in complex_parts no longer exists: the base layer is the
  `DEFINITIONS` plus the "Abs, re, im under sign facts" and linearity rows.
- Identity rows can now be 4-tuples (`unless`). Code that unpacks
  `for lhs, rhs, dom in rows` over family tables must slice `row[:3]`.
