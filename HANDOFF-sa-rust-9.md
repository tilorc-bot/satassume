# Handoff sa-rust-9: ids test, items 1-2 done, 3-5 left (issue 323, branch rust-ids)

Brief unchanged (see HANDOFF-sa-rust-8.md for setup, `. ~/sa-rust-ids-work/env.sh`, and the architect's brief): no Rust, no PR, one comment on 323,
RESULT at rust-spike/RESULT-ids.md, every failure gets a class, plain conclusion in one of three forms, say which column of RESULT-k-lra.md applies,
no backend recommendation. Above 100k context, hand off before a wait likely over an hour. Nothing posted yet.

## Item 1 done: every failure classed (rust-spike/ids/results/suite-classes.tsv, per test; suite-rungs.txt, one line per run)
New tools: ids_core install(mode, scope, exempt), IDS_RANDOM=seed (random 61-bit hash per id), suite.sh NAME ENV=..., classify.py, classes.py. XML/logs in ~/sa-rust-ids-work/suite-*.
Base: 12 failed under load (11 plus test_performance_smoke_300_vars, a timing test), same 11 otherwise. Live failure beyond base: serial 103, xdist 107, both 94, union 116.
gen-8's 112 were one more run of that; check below whether all are in the union.
eqonly: 0 beyond base. So == by ids breaks nothing in the suite; all failures are hash.
hashonly: 93 of the union, no new ones.
Classes of the union 116, 0 unexplained:
- 66 artifact, container crosses test/satassume: pass with ids in tests/, tools/, harness/ frames too (scope repo). E.g. test_extended_order KeyError(x): a dict built in satassume is compared with a test's dict.
- 48 artifact, container crosses satassume/SymPy: fail at repo, pass at repo + 3 exempt functions (exempt3.txt), and at all frames. _rows.py bind (row.xreplace of an id-hashed rule dict: SymPy misses, row unchanged, "f(x) is neither the argument..."), _rows.py constant_term (same), limits.py _inner (`v not in inner.free_symbols`, a SymPy-built set asked with an id hash: answer changes, test_bound_variable_context None vs False, and inner.xreplace). sa + those 3 alone (sax3): 54 beyond base, all in the union, no new.
  Repo rungs add failures of their own, not in the union: repo 22, repox3 16 (test frames read SymPy-built sets, eg test_verify_soundness); all clear at all frames.
- 1 artifact, wall-clock limit: test_wide_derived_or_against_or_is_fast 2.35 s vs limit 2, wrappers. Also allser test_wide_or_compiles_in_linear_time 2.59 s vs 1 (not in union).
- 1 REAL: test_add_rows::test_the_pattern_keys_are_legacys fails at live, all, allser, allrand. ('add_bound', 3, 2): code's key holds SymPy Integers (core.py:187; confirm), the test writes ints. Real: hash(Integer(3)) == hash(3) and == holds, so the tuples are one set key; ids: different hash. Mixed int/Integer keys are the named exception. No other tested path hit this: all and allrand fail only this one test.
All frames (all, allser, allrand with random hashes): exactly that test beyond base, plus the wall-clock one in allser. 22 tests flip between serial and xdist under live (rows_shapes 16, relevance 3, others 3). All are in the artifact classes and clear at all frames in both orders. The per-test reason for the flip is NOT shown: say so (candidates: a memo filled by an earlier test).
Warning: saex (exempt.txt, all 19 crossing functions, scope sa) gave 873 failed, 862 beyond base: exempting a whole function makes real-hash containers flow to id-hash readers. So a container needs one hash discipline for its whole life. Half-converting is what breaks, and this is a rule for the result.
Reach: cross.py on workloads found only has and atoms (relations.py:584) from satassume; no xreplace, subs. free_symbols sites reached there only test truthiness (lra_adapter 185, 197; constfield 1386; sympy_api 553; lra_adapter 535), I read them statically; cross.py does not wrap free_symbols. bind and constant_term run at row compile; limits _inner only on Sum/Integral. So YES the suite reaches behaviour the digests can't see. State this.

## Integer(1) == True
Shadow over the whole suite (scope sa; ~/sa-rust-ids-work/shadow-report.*): 0 disagreements at any site, and no bool operand; true cross-type == are One/int 87,468, Zero/int 80,200, f/f 21,735, g/g 3,936 (classes with the same name, one id, agreeing). Shadow returns the real hash, so a True/Integer(1) container collision would call == and be logged too. Workloads: 0 too. So not reached on anything tested; no proof it is unreachable. What a backend must do: True can't have one id, since S.true == True and Integer(1) == True but S.true != Integer(1); so never intern a Python bool: fall back to SymPy's == for a bool operand (a path with 0 calls tested). Same class as int vs Integer: an int needs the Integer's id, a bool must not get it.

## History (partly item 4)
results/history.txt, 32 replays: live with random hashes (6 seeds recorded, 3 random + shuffled, 3 seq + shuffled), base under PYTHONHASHSEED 1-4. Same digest for all: dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6. Suite at all+random: same one failure. So interning order did not move an answer on anything tested. Set order IS history-dependent under ids in a way it is not under real hashes (id depends on first sight): that's a new channel with nothing observed through it. Issue 96 asks for random tests of this; issue 97 (closed) is one session per query with pure memos; read state/memos.py PROCESS keys vs table lifetime for the rest.

## Item 2 done
results/is-count.txt: 968 is/is not: None 627, type/constant 169, object identity 74, bool 68, SymPy singleton 30. Ids change none of them; object-identity ones in a Rust port would need care: `is` is finer than id equality, so keep the address. results/inventory-ne-*.txt: with __ne__ wrapped eq+ne = 3,726 dev, 172,391 fuzz, exactly the ceiling (confirms the gen-8 gap). Not done: a one-line count of sites needing a constant id for an int literal (rows with /int in inventory-ne-*.txt).

## To do, in order
3. Timing (item 3 of HANDOFF-sa-rust-8.md, unchanged): real source edits on a branch copy, P hash/eq first, then top sites; pinned on pareto1. Must keep the container rule above, no id-hashed dict into SymPy. Say how much was converted.
4. Rest of lifetime: table pins objects; unpinned size (ids vs addresses in hand-off 8); clear_cache and Memos.clear; process vs engine ownership.
5. RESULT-ids.md, push, one comment on 323 with link at SHA, agent report, tell the architect. Working conclusion so far, re-check it: "ids hold with named exceptions and rules", the exceptions being int/Integer mixed keys and Python bool; the rules being one hash discipline per container and no id-hashed container crossing into SymPy. Column in RESULT-k-lra.md: decide after item 3.
