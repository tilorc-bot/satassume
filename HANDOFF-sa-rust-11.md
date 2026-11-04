# Handoff sa-rust-11: slice plan (issue 323, branch rust-slice). Brief unchanged: SLICE-PLAN.md, one comment on 323, no Rust, no PR.

Setup: `. ~/sa-rust-ids-work/env.sh; export PYTHONPATH`, run from ~/dev/sa-rust on orion. Work dir ~/sa-rust-ids-work/slice (cover-dev.json, cover-fuzz.json, out.jsonl, not in git).

## Tools (rust-spike/slice/)
cover.py WL OUT (flags and counters per query; digests match 31cd0945c07f02a6, 173502b6ef285ad6). qtime.py + run-slice.sh on pareto1: quiet lease, bench-container, BENCH_CPU=2, rounds 0-7, /work/slice/out.jsonl, fetched to ~/sa-rust-ids-work/slice/out.jsonl.
analyze.py COVERDIR OUT.jsonl: prints the coverage, part-share and arithmetic tables as markdown. Not yet run when this was written: write to rust-spike/slice/results/coverage.md, read it.
set-iter-audit.md: per-site audit of the 19 sites by a subagent. Spot-check lra.py:614 and any non-SAFE verdict yourself.

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
