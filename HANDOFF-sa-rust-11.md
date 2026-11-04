# Handoff sa-rust-11: slice plan (issue 323, branch rust-slice). Brief unchanged: SLICE-PLAN.md, one comment on 323, no Rust, no PR.

Setup: `. ~/sa-rust-ids-work/env.sh; export PYTHONPATH`, run from ~/dev/sa-rust on orion. Work dir ~/sa-rust-ids-work/slice (cover-dev.json, cover-fuzz.json, out.jsonl, not in git).

## Tools (rust-spike/slice/)
cover.py WL OUT (flags and counters per query; digests match 31cd0945c07f02a6, 173502b6ef285ad6). qtime.py + run-slice.sh on pareto1: quiet lease, bench-container, BENCH_CPU=2, rounds 0-7, /work/slice/out.jsonl, fetched to ~/sa-rust-ids-work/slice/out.jsonl.
analyze.py COVERDIR OUT.jsonl: prints the coverage, part-share and arithmetic tables as markdown. Done: rust-spike/slice/results/coverage.md (committed; digests matched on all pinned rounds). Read it first.
set-iter-audit.md: per-site audit by a subagent, NOT yet spot-checked by me. Check engine.py:1713, 1767, lra.py:614 yourself. Its result: SAFE 16 (5 finder false positives on lists), order-sensitive but untouched by ids 1 (_dirty: per-theory ints), FIX-SORT-like 2 (1713, 1767, fields of over-budget cone entries; fix is a constant entry, not a sort), UNSAFE 0. Not traced: re-entrant template queries (engine.py:1998) making _struct kids depend on visit order, which could reach an answer via the discovery budget; LRA atom registration order across a session; _glue_adapters purity.

## Found so far (raw counters; time shares come from analyze.py)
- Sessions: dev 918 in 1985 queries, 1118 queries need no session at all. fuzz 3133 in 3000, 63 need none. 1 to 3 per query, so the unit is one call per session, not per query.
- Session theory kinds. dev: none 720; euf+glue+lra_const 108; euf+glue+lra_rat 55; +transfer 35. fuzz: euf+glue+lra_rat 1676; +transfer 739; euf+glue+lra_const 424; +transfer 172; none 115; glue+lra_rat 7.
  **So rational LRA without EUF is 0 sessions on dev and 7 on fuzz. The plan as written (session, solver, rational LRA) runs only no-theory sessions, nearly nothing on fuzz.** Every glue session attaches EUF.
- No Session, Relations or adapter frame entered while a solver entry is on the stack (no *_in_search key in either workload). Search calls back only into the theories, so a solver boundary needs callbacks only for theories, not for knowledge.
- Theory calls: fuzz lra 1,533,444, euf 728,883, transfer 402,262, sharing 8,009; dev lra 52,206, euf 21,847, transfer 5,091, sharing 506. fuzz register_atom 94,780, add_clause 316,135, _compile_patterns 16,537, escalate 3,622, discover 58,720.
- session._custom is relation atoms, not custom predicates; engine._is_custom reached 2 dev, 45 fuzz. Not yet checked: whether any registered custom predicate exists on the workloads.

## Alternative to propose (Q, solver boundary)
Rust holds solver and rational LRA. Session, Relations, adapters and knowledge stay in Python. Clause and atom additions are batched; each solver entry is one crossing (fuzz solver_top 26,404). EUF, transfer and constant LRA are live callbacks from Rust to the unchanged Python, no fallback at all. Callback cost by table (b) in rust-spike/results/tables-cross.md, 17-37 ns plus args; about 1.1M calls on fuzz is roughly 0.05-0.1 s of 8 s, against 100% of a query's time for fallback. It measures live crossing. It can't settle Session, Relations or knowledge gains; those stay extrapolated.

## Left
1. Run analyze.py, get moved shares, max speedup, k_rest for 2x (brief item 2). Do not count a removed ask as saved (sa-rust-10).
2. History design (item 3): read set-iter-audit.md. Candidate: ids only inside one session, table built per session in Rust, dropped with it; first sight then comes from the query alone, so it is history free by #97's one-session-per-query; no process table, no clearing, no pinning. Q holds no ids across sessions. Python's _FORMULAS and memos keep real SymPy hash. Payload crossing maps term to session id via SymPy hash and == in Python, as LRATheory._var_of does and as the k_lra replay did (per-session ids). Bool and float: not interned; a raw Python value reaching a key means fallback to the Python theory for that session, count it (0 reached so far). int and Integer: sympify ints at the crossing, so int shares the Integer's id. Set order: per-session first sight is a function of the query given insertion order; must still be tested: fork-per-query vs recorded vs shuffled digests plus a same-query-twice-in-one-process check.
3. Build steps (item 4), each under a 120k session, with checks. Identical-answers check must be more than digests: earlier replays missed 5 of 10 and 2 of 9 mutants (rust-spike/mutate.py); use state compare on every session (trail, conflicts, per-call theory results) between Rust and Python in lockstep, plus mutants.
4. Write rust-spike/SLICE-PLAN.md (result first), push, one comment on 323 at the SHA, agent report, tell the architect.

## Measured, read before writing (rust-spike/slice/results/coverage.md). Pass 0.527 s dev, 8.033 s fuzz.
| slice, crossings free | dev queries / time % / max whole, None, def / k_rest 2x | fuzz same |
|---|---|---|
| P, plan as written | 669 / 38.9 / 1.18, 1.23, 1.12 / 1.82 to 2.04 | 84 / 0.2 / 1.00, 1.00, 1.00 / 2.05 to 2.41 |
| Q, solver boundary | 867 / 99.1 / 1.62, 1.67, 1.57 / 1.29 to 1.37 | 2937 / 100 / 1.90, 1.95, 1.70 / 1.06 to 1.08 |
P+ and P++ rows are in the file. k_rest range: stays = outside only, then outside plus SymPy on the stack. Moved shares for Q: SAT 37.4 and 37.3, rational LRA 4.2 and 13.2. Constant-session queries are 36.8% of dev time, 21.8% of fuzz.
Theories mostly do speak: of fuzz's rational+EUF 1549 queries, LRA said something in 1443, EUF in 84; so EUF is usually idle, but it can't be skipped without predicting that.
Limits to state: shares are from a sampler biased to thin callees (SAT 31-46% by other timers); k and k_lra are whole-workload values applied to every class; `custom.facts_for` in analyze.py is never wrapped, so its 0 means nothing: registered custom predicates are still unchecked; the max assumes zero crossing cost and no added Python.
Not done: spot-check of the audit, items 2-4 of "Left" apart from these numbers, SLICE-PLAN.md, the comment. Nothing posted to GitHub.
