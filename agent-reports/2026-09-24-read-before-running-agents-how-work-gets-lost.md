# Agent report: read this before running or coordinating agents — how work gets lost, and how to prevent it

- **Date:** 2026-09-24 (section 6 added 2026-09-25)
- **Status:** lessons from a multi-agent run on the `refine-identities`
  branch (one coordinator, up to four subagents in parallel on separate
  worktrees). Every failure described below happened in that run; the
  prevention rules are what would have stopped it.
- **Read this if:** you are about to spawn subagents, run long test or
  generation jobs, coordinate parallel work in this repository, or trust a
  fuzzer's "0 unsound", or you are paying for agent runs (section 6).
- **Stale after:** never entirely; revise items as the tooling changes.
- **TL;DR:** a subagent waited for hours on its own background job and
  stopped without committing, and its coordinator kept reporting it as
  "still running" because it trusted the agent's last message. Separately,
  three orphaned pytest processes had burned two cores for 36 hours, and a
  fuzzer had silently skipped a third of its cases. The fixes are cheap:
  time-box every long run, commit before waiting, judge liveness from the
  branch rather than from messages, and make every test tool count what it
  could not check. And (section 6, from the phase-2 run): keep every
  single tool call under about 4 minutes, because a subagent that blocks
  longer loses its prompt cache and pays to rewrite its whole context;
  that was about $80 of a $141 bill.

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
   not stop a hung test. Run it detached and wait for it in short
   foreground chunks (section 6), not as one long blocking call.
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

## 6. Cost: keep every tool call under about 4 minutes

What happened: in the phase-2 run (2026-09-25; one coordinator, five Opus
subagents) the session's usage read 18.5M cache-write tokens against 179.5M
cache reads, $141 in total. The transcripts
(`~/.claude/projects/<project>/<session>/subagents/*.jsonl`, field
`message.usage`) showed why:

- Subagents write their prompt cache with a **5-minute lifetime**
  (`usage.cache_creation.ephemeral_5m_input_tokens`); the main
  conversation on a subscription gets 1 hour. This is Claude Code's
  documented default
  (https://code.claude.com/docs/en/prompt-caching#subagents-and-the-cache).
- The agents ran scoreboards, differentials and suites as single
  foreground commands of up to 10 minutes (the Bash tool's maximum
  timeout). After each one the cache had expired, and the next turn
  rewrote the agent's whole 200-300k-token context at the write price.
- Measured over 637 subagent requests: after a gap under 4 minutes, 2
  full-context rewrites in 543 requests; after 4-5 minutes, 0 in 5; after
  5-6 minutes, 3 in 12; after 6 minutes or more, **76 in 77**. The 81
  rewrites were 16.2M of the 17.5M written tokens, about $80 at Opus 5.5
  prices ($5/M for 5-minute writes, $0.20/M for reads). The same waits as
  warm-cache check-ins would have cost about $0.05 each instead of about
  $1.25.

Rules to put in every agent prompt:

1. **No single tool call longer than about 4 minutes.** The cache
   lifetime runs from the *start* of one model request to the start of the
   next, so it has to cover the model's own generation time (seconds to
   over a minute for a long turn) as well as the tool call. A 4-minute cap
   leaves about a minute of margin; 4.5 minutes leaves 30 seconds, which a
   long turn can use up (the 5-6 minute band above already loses a quarter
   of its caches).
2. **Start long jobs detached and wait in chunks, in the foreground:**
   ```bash
   nohup env PYTHONHASHSEED=0 timeout 3000 uv run ... > /path/run.log 2>&1 & echo $!
   timeout 200 tail --pid=<PID> -f /dev/null; tail -3 /path/run.log   # repeat until the process is gone
   ```
   This keeps section 1's rule (the agent never ends its turn to wait for
   a notification, so it cannot stall) while every check-in lands on a
   warm cache.
3. **Keep tool output small.** Redirect full output to files and print
   summaries (`tail -25`, a grep for FAILED/unsound/crash, totals). Every
   token in the context is paid once as a write and again as a read on
   every later turn.
4. **Start a fresh agent for each new assignment** and hand over through
   the previous agent's written report, instead of sending the next task to
   a finished agent: a continued agent carries its whole history (here
   200-300k tokens) into work that needs none of it.

No job needs a tool call longer than 4 minutes: however long the job,
the agent runs it detached (rule 2) and only ever blocks on a check-in
under 4 minutes. With the rules followed, the 5-minute cache never
expires.

Not recommended by default: the setting `subagentPromptCacheTtl: "1h"` (or
`CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL=1h`, Claude Code 2.1.242 or later)
gives subagents the 1-hour lifetime, but one-hour writes cost 2x the input
price instead of 1.25x, so every write costs 60% more to protect only
against broken rules. Use it only if agents keep blocking despite the
rules.
