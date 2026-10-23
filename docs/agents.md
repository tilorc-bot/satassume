# Working with coding agents

Rules for coding agents working on this repository, and for the sessions
that coordinate them. Each rule exists because breaking it once lost work,
money or a correct result. The machine rules (shared host, benchmarks
through `~/bin/bench-container`) are in the host's own README; what to
run to check a change is in [testing.md](testing.md).

## Long-running commands

1. Wrap every command that can run long in `timeout` with an explicit
   budget. pytest's `-o faulthandler_timeout=N` only dumps stacks; it does
   not stop a hung test.
2. Keep every single tool call under about 4 minutes. A subagent's prompt
   cache (5 minutes by default; check the session's setting) lives from the
   start of one request to the next, and
   after a longer wait the whole context is written again at the write
   price: in one run, 76 of 77 waits of 6 minutes or more did that, about
   $80 of a $141 bill.
3. Start long jobs detached and wait in short foreground chunks, on the
   PID:

   ```bash
   nohup env PYTHONHASHSEED=0 timeout 3000 uv run ... > run.log 2>&1 & echo $!
   timeout 200 tail --pid=<PID> -f /dev/null; tail -3 run.log   # repeat until the process is gone
   ```

   Never end a turn to wait for a notification, and never wait for or
   kill processes with `pgrep -f`/`pkill -f`: the pattern also matches the
   waiting shell.
4. Split long runs by file, family or seed range. Do not start a job
   whose cost is unmeasured over everything at once.
5. Redirect full output to files and print summaries (`tail`, a grep for
   `FAILED`, totals). Every token in the context is paid again on every
   later turn.
6. Commit and push before waiting on anything. Work-in-progress commits on
   the agent's own branch are fine; uncommitted work is lost when the
   agent stalls.
7. Always end with a report, even when out of time: what is finished,
   what is not, what was pushed.

## Shared machine and shared checkouts

1. One worktree and one branch per agent. No two agents edit the same
   checkout. `git fetch` before touching a shared branch; leave other
   sessions' branches and worktrees alone.
2. Before diagnosing slowness or timing anything, look for orphans:
   `ps -eo pid,ppid,etime,pcpu,cmd --sort=-etime | grep python` (long
   `etime` with parent 1). Find the owner with `readlink /proc/<pid>/cwd`
   and kill only processes of finished work.
3. Size parallelism to the machine as it is (`nproc`, `uptime`, other
   sessions' load). Correctness gates need no pinned cores; timings do.

## Gating

1. Gate from a clean checkout of the branch as pushed. Before gating,
   `git status --ignored` must list no source files: `.gitignore` has
   `build/`, and a directory of that name once kept five modules out of a
   merge whose gates had passed in the agent's worktree.
2. pytest skips directories named `build` (its default `norecursedirs`);
   do not put tests there, or collect them explicitly.
3. Compute the baseline once, on a clean worktree of the base commit, and
   share it. Do not merge unrelated work into a branch while its gates
   run.
4. Run independent checks in parallel: the suite under pytest-xdist,
   separate fuzz seeds and gate runs as separate processes.
5. Every checker counts what it could not check and prints that count
   next to the pass count. A fuzzer once skipped a third of its cases
   (relations it could not evaluate) and reported them as sound.
6. Wrap each case of a scoreboard or fuzz run so that one exception is
   counted, not fatal, and print partial results before a risky section.
7. Comparisons across packages or versions run in fresh processes:
   importing one package's test module can re-register its handlers over
   another's.

## The truth standard

1. SymPy's evaluation (`doit()`, automatic evaluation, `subs`/`xreplace`
   values) and its `is_*` answers are candidates, never the truth
   (docs/spec.md, "Truth standard"; #247). A report or review finding
   that calls an answer wrong states a mathematical argument: a
   definition, a limit, a theorem, or a convention of the spec. "SymPy
   evaluates it to X" alone is filed as a candidate.
2. Every review brief and every brief for a held-out test writer states
   this rule, and their oracles derive expected answers from the spec.

## Coordinating agents

1. An interim "still running" message is not progress. Judge liveness from
   the branch and worktree (`git log -1`, `ls -lt`); no change for longer
   than the job should take is a stall.
2. Give each phase a deadline. When an agent dies, commit its worktree as
   a WIP commit, push it, and start the replacement from that commit with
   the full context in its prompt.
3. Assign file ownership in each prompt. An agent that needs a change in
   code it does not own commits the smallest failing test for it and
   reports it; the owner makes it pass.
4. Start a fresh agent for each new assignment and hand over through the
   previous agent's written report, instead of sending more work to a
   finished agent that carries its whole history.
5. Merge finished branches in order and bring the other agents' worktrees
   up to date before their next phase.

## GitHub

1. Several sessions post as the same account, `tilorc-bot`. Start every
   issue comment and PR body that is not obviously yours alone by saying
   which session or role wrote it, and do not assume you wrote the earlier
   comments. On issue #7 two sessions answered each other's comments as
   the same user and had to correct each other's premises.
2. The push token lacks the `workflow` scope, so GitHub refuses any change
   under `.github/workflows/`. Stage such a file elsewhere (#55 used
   `harness/ci/`), say in the PR that it must be moved, and let the owner
   move it (the owner did, in `fb1c039`).
3. `gh pr edit` fails with the installed `gh` 2.46; edit a PR with
   `gh api -X PATCH repos/tilorc-bot/satassume/pulls/N -F body=@file`.

## The `needs-human` label

A PR with the `needs-human` label waits for a human decision. Agents
never merge a labelled PR and never remove the label; only a human does.
Apply it when any of these holds:

1. It changes what counts as a correct answer: a convention for `nan`,
   `oo`/`zoo`, non-commutative terms or special values, or what answers
   are checked against (#245 judged non-commutative levels by `doit()`).
2. It gives up definite answers (True/False to None) that SymPy's tests
   or users rely on (#225 sent `test_hermitian` back to the xfail list).
3. It weakens a check: a soundness oracle, gate or fuzzer, a new xfail
   entry or an xfail pin (sympy-satassume#5 added three entries).
4. It changes a semantic section of [spec.md](spec.md) or
   [design.md](design.md) (#250 adds a truth standard to both).
5. It trips the satperf flag: any case over 2x or any view over 10%
   (#192, 2.59x on one query in #212).
6. It is a release, a public API change or a dependency pin in another
   repository (#123, release v0.0.2).

No label is needed for mechanical changes against the stated spec: crash
fixes, a missing rule that follows from the spec, refactors with
identical answers, speedups with no changed answers, new tests, and docs
that only describe. When unsure, apply it.

The PR description says why, one visible "**Needs your decision:**" line
per decision, near the top (the description style is #255). Next to it, a
labelled PR must carry a short "**Why a human:**" justification: (a) which
of the criteria above it meets, by number, and (b) why it is worth a
human's time, that is, what goes wrong or is lost if it is not reviewed
or not merged. For example:

> **Why a human:** criterion 2: three queries go from True to None.
> Unreviewed, SymPy code that relies on those answers could break
> silently; unmerged, the three wrong True answers stay.

The label is a convention: nothing enforces it. A required status check
that fails while the label is present would block the merge, but the
owner has to add that workflow (see "GitHub", item 2).

## Reporting a PR

The house style of the merged PRs (#51, #54, #61) as a checklist:

- [ ] First line: what it fixes or closes (`Fixes #N`), and what it is
      stacked on, if anything.
- [ ] A before/after table of queries: query, assumptions, `main`, branch,
      and SymPy's `ask` where it helps.
- [ ] Cause, then the fix, then a soundness argument for every new or
      changed rule (why it holds for every value, including `0`, `oo`,
      `zoo`, `nan` and non-commutative values where relevant).
- [ ] Alternatives measured and dropped, with the number that decided.
- [ ] Gates, each with its baseline named (a clean worktree of
      `origin/main` at a hash) and the SymPy version:
      - suite: passed / skipped / xfailed for base and branch, new tests
        counted, known failures named;
      - `tools/gate2.py`: records, changed, more definite;
      - `tools/compare.py --in-scope-only` and `--relations-only` when
        rules, templates or relations change;
      - stream answers: queries, changed answers by kind;
      - timing: machine or `bench-container` CPU, rounds, interleaving,
        medians and the per-round change.
- [ ] Every changed answer listed and explained: more definite ones
      checked correct, any less definite one traced to its cause.
- [ ] A mutation check where a test guards a fix: reverting the change
      fails N tests.
- [ ] What was not run, and why.
- [ ] "Not in this PR" (related gaps left for later) and "Where this
      could conflict" (open PRs touching the same files).
- [ ] Undated, plain prose; measurements with the commit they were taken
      at.
