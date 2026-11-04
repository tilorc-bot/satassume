# Handoff sa-rust-8: ids stand-in experiment (issue 323, branch rust-ids)

Brief unchanged: no Rust, no PR, one comment on issue 323, RESULT at rust-spike/RESULT-ids.md, don't recommend a backend plan.
Tilo's constraint: "any optimizations need to be things that don't take us further away from sympy using it."
Handed off at budget (~110k of 120k). No comment posted yet; nothing is concluded yet.

## Setup (orion)
`. ~/sa-rust-ids-work/env.sh` gives `$PY` (uv venv, py 3.12, mpmath 1.3.0), PYTHONPATH, SA_EVAL_DATA, PYTHONHASHSEED=0. Data, evalbench, sympy
1.15.0.dev are copied from pareto1:~/sa-rust-bench. Raw answers and mon JSON are in ~/sa-rust-ids-work (not in git). Run from ~/dev/sa-rust.

## Tools (rust-spike/ids/)
inventory.py + inv_table.py (site counts), ids_core.py (table; shadow/eqonly/live by caller frame, no package edits), run.py
(MODE WL recorded|shuffled:N|fork|only), hand.py, cross.py, asks.py, rc_ids.py, ids_plugin.py (`pytest -p ids_plugin`).

## Done, with numbers (results/ has the files)
Step 1. Hash asks inside the boundary reproduce the ceiling exactly: dev 249,497, fuzz 5,048,969. Dynamic hash+eq sites inside: dev 173, fuzz 174
(inventory-*.txt; inventory.py does not wrap __ne__, which is why eq shows 3,376/158,321 against the ceiling's 3,726/172,391, not yet confirmed).
P's generated dataclass hash (`<string>:3`) is one site with 1.82M on fuzz. Largest eq site: EUFAdapter.parse euf_adapter.py:120,122 (Predicate ==, cross type, always False).
Container eq between NegativeOne and Integer is a hash collision: hash(-1) == hash(-2) == -2. Static count of `is` checks not done yet.
Step 2. shadow: 0 disagreements, dev (264,244 hash, 6,082 eq/ne) and fuzz (5,078,682 hash, 179,765 eq/ne); digests match. Only logged items are
true_crosstype: Integer == int (322 dev, 5,950 fuzz), and ids agree there because the int is sympified first. Table audit (same real hash, same str, Numbers pairwise): no == pair with two ids.
Hand pairs (hand-*.json): one disagreement, Integer(1) == True (real True; ids False, because True sympifies to S.true). S.true == True and True == 1 but S.true != Integer(1), so == is not transitive there. In this SymPy,
Integer(1) != Float(1.0) and Float prec 15 != prec 30. Hand-query answers are the same in base, eqonly, live.
Step 3. Digests dev 31cd0945c07f02a6 and fuzz 173502b6ef285ad6 match for eqonly and live in recorded and shuffled:7, live and base in fork-per-query (all queries),
and 120 of 120 sampled queries as real separate processes (60 each, live vs base, not vs digest). Fork is a fork of a parent that has only imported, not exec.
Test suite on orion: base 11 failed, 6072 passed. **Live 123 failed, 5960 passed: 112 fail only under live. NOT CLASSIFIED.**
Hypothesis to test, not a finding: frame-scoped hashing is an artifact when a dict crosses frames (a test file's `{x: ...}` has real hashes, satassume's has ids; `_rows.py` xreplace rule dicts built under ids are read by SymPy with real hashes). Failing files: test_rows_shapes 36, test_relevance 21, test_rows_nary 13, test_registry_versioning 9, test_ref 7, test_extended_order 6.
cross.py: on the workloads, from satassume frames only `has` and `atoms` (relations.py:584) were reached; no xreplace/subs. So the digests are not exposed to that artifact, but the suite is.
Step 4 asks (results/asks.md), mon mode, inside the boundary: dev 282,918 to 32,109; fuzz 5,946,570 to 774,642. Hash 5.05M to 31k, eq 172k to 4k. Read and walk unchanged (fuzz 411k, 186k). Construct goes up (fuzz 20k to 35k) from sympifying ints in the eq stand-in; asks.py's category split differs from the ceiling table on walk/other/construct although totals match, so fix or explain it (likely the partial exec of analyze.py's tables).
Table: dev 1,019 ids, 1,729 addresses; fuzz 7,681 ids, 13,405 addresses. Pinned for the process, never cleared. Live hash and eq are 1:1 with frames, so timing under ids_core is NOT valid (fuzz 19.8 s vs 13.1 s, wrappers).

## To do, in order
1. Classify the 112. First `pytest -p` with eqonly (needs a plugin variant, or ids_core.install read from an env var): if eqonly gives only the base 11, the rest is hash. Then per file: artifact of crossing frames, or real? E.g. give test frames ids too, or make rule dicts crossing into SymPy real. Report any real one with cause. Don't assume the hypothesis.
2. Static `is` count (AST over the moved files) and a `__ne__`-inclusive inventory; which sites a table could replace (all reached hash/eq sites replaceable except int literals needing a constant id; say what about SymPy-built sets).
3. Timing: ids_core can't be timed. Needs real source edits on a branch copy: start with P's hash and eq (cached id via address table, sat/formula.py:13), then top sites. Report the share of asks covered. Pinned on pareto1 per the brief: `machine run pareto1 --quiet`, bench-container sa-eval-bench:1, ~/sa-rust-bench, BENCH_CPU=2, cold process, alternating, medians (style: tools-rust/run.sh, analyze_k.py). src/base-9bafaa5 is main. Keep pareto0 free. Say plainly if only part was converted.
4. Lifetime and issues 96, 97 (not yet read: `gh issue view`): table pins objects; by_addr needs pinning so addresses stay valid; set order under ids depends on interning order (shuffled digests matched, but see the limits); process vs engine ownership in state/memos.py; clear_cache and Memos.clear. Also unpinned variant size: distinct values vs addresses above.
5. rust-spike/RESULT-ids.md (result, method, tables, limits), push, one plain comment on 323 with the link at the commit SHA, `agent report`, tell the architect. Remove this handoff from the tree only if the architect asks.
