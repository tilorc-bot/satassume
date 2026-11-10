# HANDOFF sa-port-262: state part 3 LANDED (rust-slice 9151316, tested f252daf); the count probe is left

rust-slice 0192b35 -> 9151316 at 22:32:40Z 10 Nov. Source under satassume/ and rust-spike/slice/ equals tested f252daf
(incoming diff empty, push guard clean); the commits after f252daf are HANDOFF files and results/port-state-part3.md.
Landed on the planner's ruling of ~22:35Z (on report 93774a0): pinned timing is not a landing-bar item. No source changed
in this link. Everything measured is in results/port-state-part3.md, section "The landing bar".

## Done here (all on f252daf's source)
- Digest-off run (`--check plain`) of all 16 workloads, Python against Rust, the bar's tree and .so (e9aaf5052540):
  16/16 MATCH, answer_diff 0, 0 handler rows; sb:fwd_named 0 on all 16 (digest on: dev 1,876, fuzz 45,802, zero 8,011,
  transfer:7:60 1,114, transfer2:3:40 957, scope 875, cert 455, value 197, twin 26, 0 on the other seven); plant 437 fires
  and is caught on dev, fuzz, twin, scope, zero, cert, transfer:7:60, transfer2:3:40. pareto1
  `~/sp19/sa-rust-ids-work/sa-port-262/dgoff` (job.sh, summary.txt, tab.py), copy on orion `~/sa-rust-ids-work/sa-port-262/dgoff`.
- Subs twins: rows equal on base 0192b35 and f252daf (orion `~/sa-rust-ids-work/sa-port-262/tw`: worktrees base and step,
  each with its own .so, run.sh, rows-{base,step}.txt). The worktrees are registered in the clone (`git worktree list`);
  remove them with `git worktree remove` when no longer wanted.
- scaffold:core:kept_product:mismatch 0 on 16 workloads; registry:python / rows:python per workload, equal to the base on
  its seven (pareto1 `~/sp19/sa-rust-ids-work/sa-port-262/kc.py`). Not in the suite's counts files.
- Group D shares for both trees (orion `~/sa-rust-ids-work/sa-port-249/gd/run-{0192b35,f252daf}/SUMMARY{,-rel}.md`;
  `~/sa-rust-ids-work/sa-port-262/gdt/dmods.py` adds relkeys and ses_cont).

## Owed, not mine any more (planner: formula's bar; to go on OWED)
Group D in seconds and the memo cost ([108]), pinned on pareto1 under a quiet lease. My quiet request waited 9 minutes
behind another project's shared lease and was withdrawn on the architect's word. Ready to run: pareto1
`~/sa-rust-ids-work/sa-port-262/gdt/onlease262.sh` (bench-container, CPU 2, sa-eval-bench:1; refuses if gdt/results exists)
running `~/sa-rust-ids-work/sa-port-249/gd/tools262/time262.sh` over gd/bench-0192b35 and gd/bench-f252daf; then on orion
`python3 ~/sa-rust-ids-work/sa-port-262/gdt/med262.py time.jsonl ~/sa-rust-ids-work/sa-port-262/gdt/dmods.json`.
med262.py has not been run on real rows. Unpinned context rows: dev Rust 2.23 s (f252daf), 2.68 s (base), Python 1.01 s.

## Left: the count step for session_live / ses_cont (planner, ~22:35Z: "No count change without it")
The module-wide probe on the landed SHA, every function in session_live.py, all workloads plus the suite, every nonzero
function listed, with sc:key_hash listed (RULINGS 1).
- Workload half STARTED detached on orion at 22:35Z: `~/sa-rust-ids-work/sa-port-262/pyc/probe.sh landed 9151316`
  (sa-port-247's probe.sh on 16 workloads, 3 at a time; tree `pyc/tree-landed` at 9151316, .so a10068f4febd = f252daf's
  aarch64 build). End marker `pyc/landed/end.txt`; `pyc/landed/exits.txt` one line per workload; read with `pyc/sum.py`
  (247's, check its paths). NOT read; only source.txt and build.txt were checked after launch.
- Suite half: not started. No recipe found here for pycalls.py over the suite; look at how (iii) did its module-wide
  probe on the landed source (results/port-state-relations.md, rg "module-wide") and run it on pareto0 or pareto1 under a
  shared lease.

## FILE:LINE MAP (additions; the rest is HANDOFF-sa-port-249.md's and HANDOFF-sa-port-247.md's)
- rust-spike/slice/results/port-state-part3.md: rg "^## The landing bar" (digest-off table, Subs twins, plants, counters,
  fallbacks, Group D shares, the timing owed), "^## Not run"
- rust-spike/slice/pycalls.py (PYCALLS_FILE=rust-spike/slice/session_live.py); live.py :409-413 (the digest is off under
  `--check plain`); moved_digest.py:137
- ~/dev/architect/RULINGS.md lines 1 (count), 12 (Group D), 14 (instrumentation)
