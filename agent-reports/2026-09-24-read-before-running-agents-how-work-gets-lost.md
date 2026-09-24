# Agent report: read this before running or coordinating agents — how work gets lost, and how to prevent it

- **Date:** 2026-09-24
- **Status:** lessons from a multi-agent run on the `refine-identities`
  branch (one coordinator, up to four subagents in parallel on separate
  worktrees). Every failure described below happened in that run; the
  prevention rules are what would have stopped it.
- **Read this if:** you are about to spawn subagents, run long test or
  generation jobs, coordinate parallel work in this repository, or trust a
  fuzzer's "0 unsound".
- **Stale after:** never entirely; revise items as the tooling changes.
- **TL;DR:** a subagent waited for hours on its own background job and
  stopped without committing, and its coordinator kept reporting it as
  "still running" because it trusted the agent's last message. Separately,
  three orphaned pytest processes had burned two cores for 36 hours, and a
  fuzzer had silently skipped a third of its cases. The fixes are cheap:
  time-box every long run, commit before waiting, judge liveness from the
  branch rather than from messages, and make every test tool count what it
  could not check.

## 1. Subagents: never lose work to a stall

What happened: an agent started a long background run (test suite,
generator, scoreboard), said it was waiting for the run to notify it, and
never resumed. Hours of edits across five modules existed only as
uncommitted files in its worktree. They were recovered only because a
human asked why the branch was empty.

Rules to put in every agent prompt:

1. **Wrap every long command in `timeout`** with an explicit budget (for
   example `timeout 1200 ...`). A hung run must fail, not block. Note that
   pytest's `-o faulthandler_timeout=N` only dumps stack traces; it does
   not stop a hung test.
2. **Split long runs.** One family, one test file, one generator target
   per run. A job whose cost you have not measured should not be started
   over everything at once. (Here, generating one small rule family took
   3.5 minutes after an engine change; generating five larger ones in one
   run was the likely hang.)
3. **Commit and push before waiting on anything.** Work-in-progress commits
   on the agent's own branch are fine. Uncommitted work is lost work.
4. **Always end with a report, even when out of time,** stating what is
   finished, what is not, and what was pushed.

## 2. Coordinators: judge liveness from the branch, not from messages

What happened: the coordinator relayed the stalled agent's interim
"waiting on a background run" messages for hours without checking progress.

1. **An interim "waiting" message is not evidence of progress.** At each
   one, check the agent's branch for new commits and its worktree for
   recently modified files (`git log -1`, `ls -lt`). No change for longer
   than the run should take means a stall.
2. **Set a staleness alert** when agents run unattended: a background
   check every few minutes that flags any active worktree with no new
   commit or file change for a set period (for example 45 minutes).
3. **Give each phase a deadline.** Past it, inspect the worktree, then
   message or replace the agent.
4. **When an agent dies, first commit its worktree as a WIP commit and
   push it,** then start a replacement from that commit with the full
   context in its prompt. Do not start the replacement from a clean
   branch.

## 3. Orphaned processes skew everything else

What happened: three `pytest` processes from an earlier, finished task sat
at about 65% CPU each for 36 hours, parented to init. Nothing was waiting
for them.

1. **Before benchmarking or diagnosing slowness, check for orphans:**
   `ps -eo pid,ppid,etime,pcpu,cmd --sort=-etime | grep python`. Long
   `etime` with `ppid` 1 is the signature. Find the owner with
   `readlink /proc/<pid>/cwd`.
2. **Kill them only after confirming they belong to finished work.** Other
   agents share this machine.
3. The `timeout` rule in section 1 is what prevents these from existing.

## 4. Parallel agents: separate worktrees, file ownership, requests as failing tests

This part worked and is worth copying.

1. **One worktree and one branch per agent**, merged by the coordinator into
   an integration branch. No two agents edit the same checkout.
2. **Assign file ownership explicitly in each prompt.** When two agents
   would need the same files, give one of them a report-only deliverable
   (for example "a measured list of proposed removals") and apply it after
   the other lands.
3. **Cross-owner requests as failing tests.** An agent that needs a change
   in code it does not own commits the smallest failing test under a
   `needs/` directory and reports it. The owner makes it pass. Fourteen such
   requests were filed and implemented this way; because each request was
   executable, none needed clarification.
4. **Merge often, and fast-forward the other agents' worktrees** to the
   integration branch before they start their next phase.

## 5. Test tools that pass silently

Each of these made a tool report success on work it had not done.

1. **A fuzzer skipped every case with a relation assumption.**
   `tools/refine_fuzz.py` decided `Q.lt(-3, 0)` with `.doit()`, which SymPy
   leaves unevaluated, so no sample ever satisfied a relation and 353 of
   1,485 cases were checked at zero points and counted as sound. Fixed on
   `refine-identities` (`b8f47a6`) by deciding relations numerically.
   Rule: **every checker must count the cases it could not check and print
   that count next to the pass count.** "0 unsound" means nothing without
   "N unchecked".
2. **Importing one package's test module replaced another package's
   handlers.** Test modules that import a handler package at load time
   re-register its handlers, so running package A's suite against package
   B partly measures A. Cross-package runs must restore the selected
   package's handlers before each test, or run in a fresh process.
3. **One bad case aborted a whole scoreboard run.** A sampler raised on a
   relation assumption with a complex sample point, and another handler
   returned a Python `int`; both killed the run. Wrap each case, count
   exceptions as a category, and print partial results before the risky
   section.
4. **A numeric verifier found what tests did not.** Verifying every
   generated rule numerically, with edge points 0, 1, -1, I, -I and
   branch-cut points always included, surfaced a wrong answer in SymPy's
   own `ask` (`Q.zero(b**2)` under `Q.imaginary(b)` returns `True`). Random
   sampling alone missed points like these in earlier work.
