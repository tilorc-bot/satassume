# HANDOFF sa-port-170 (step 5c8, issue 323)

Branch port/5c8 rebased onto origin/port/stack-c2-elemnew **f1e4a74** (the stack's tested source, as the landing order
says). **Tested source fece4c7** = the two 5c8 commits + `pycalls.py`. The commit carrying this file adds only results/
and this handoff, which aren't guarded. rust-slice was still 17442af at 11:35Z. Not landed.

## Bar running (pareto1)
`~/sp19/sa-rust-ids-work/sa-port-170/bar-5c8/` (bar.out, phases.txt, done.txt when finished; it's written on pareto1 by
bar.sh). Launched 11:35Z by `machine run pareto1 --shared --wait 4h -- setsid bash ~/sp19/job-sa-port-170.sh` (the
config is in that file: PLANTS = the 16 except consistent-fault, WLS="loop zero cert", TESTS = 5c7's 12 +
test_elem_pyclass.py + test_relevance_core.py, DIRECT "relations_direct.py 300 0", N=6). **BASE=5c7b's suite**
(sa-port-158/bar-5c7b/suite). Once S1 lands, rerun only the sum phase against S1's rows:
`ssh pareto1` then `$PY ~/sp19/dev/sa-port-170/rust-spike/slice/p1/bar_sum.py OUT ~/sp19/sa-rust-ids-work/sa-port-167/bar-S1/suite`
(env from ~/sp19/sa-rust-ids-work/env.sh). Against 5c7b, the stack's own suite changes show up as diffs: explain them from S1's sum.
The orion-side machine run (the lease renewer) was in sa-port-170's shell. If it died with that shell, the lease lapses but
the pareto1 job carries on.

## Rebase onto f1e4a74
The only conflicts were relations_core.rs's plant consts/rel_plant and session.rs's NAMES/consts/COUNTS (179 -> 200).
Both sides kept: Element._new's 118-123 and 170-178 replace the 5c8 "held"/rsv lines. Built on orion. 72 passed
(test_relevance_core.py, test_elem_pyclass.py, test_knowledge_core_shapes.py), and cert answers 6a09c059eb266747.

## Count ruling (addenda/sa-port-5c8-count-ruling.txt; carry it in NEXT's ruling-file list)
**Condition 2 holds.** `pycalls.py` (sys.monitoring PY_START on sympy_api.py code objects, classed by PORT-INVENTORY's
sympy_api lists) on fece4c7, Rust, --check plain, `~/sa-rust-ids-work/sa-port-170/pyc/` (orion). Outside conversion:
only `<module>` 1 and `_Split` 1 (class body), both at import, so **0 per query** on dev, fuzz, zero, loop, scope, budget
and cert. Answers equal 5c7's hashes. Python conversion calls per query: dev 13.3, fuzz 29.8, zero 22.5, loop 14.6,
scope 19.0, budget 51.5, cert 26.7.
Conditions 1 (bar clean) and 3 (5c8 handler conditions: same catches, fault plant loud, `_consistent` firings Rust next to
Python from the bar's handler rows) are still to be read off the bar. If all three hold, it's 14 of 32 with the ruling's
footnote word for word. Otherwise it's 13 and you name the failed condition.

## Plant state screen (sa-port-168 pe/, --check entry, done 11:37Z): fired / verdict
| plant | dev | fuzz | loop | scope | zero | cert |
|---|---|---|---|---|---|---|
| const-base-no-pow | 1 M | 0 | 0 | 0 | 0 | 0 |
| const-free-no-mul | 6 M | 1 **D** (end 5, stream 5) | 0 | 0 | 1 M | 11 M |
| expr-keys-closed-skip | 579 M | 11093 M | 1 M | 2 M | 185 **D** (end 9) | 10 M |
| keys-empty | 0 | 0 | 0 | 0 | 0 | 0 |
| keys-rel-no-flag | 53 M | 2744 M | 0 | 4 M | 28 M | 82 M |
| bool-keys-opaque-in | 6 **D** (session count 1 query) | 0 | 0 | 0 | 0 | 0 |
| vocab-no-derived | 0 | 0 | 230 M | 0 | 0 | 0 |
| part-consistent-true | 104 **D** (end 19, stream 28) | 0 | 0 | 0 | 25 **D** | 0 |
So part-consistent-true is caught by state on dev and zero, and no new workload is needed for it. Still void, with reasons
(not yet probed):
- **keys-empty**: `rv_keys` has test-only callers (test_memos, test_relevance, test_relevance_core). The engine never calls it.
- **keys-rel-no-flag**: `rel` feeds `_Split.relational`. Under the default `RELATIONAL = "components"` (sympy_api :1070)
  that only picks whole-set `_consistent` against per-component checks, and `prel` is read only by the "whole" ablation (:960).
  Components share no key, and the glue case goes to the whole set anyway (:987), so the verdicts agree.
- **vocab-no-derived**: it skips `_DERIVED_CLASSES` (Add/Mul/Pow). It changes an answer only if a vocabulary class is
  registered for one of those, or a base of one, while no subterm is an instance. loop registers none like that.
- **const-base-no-pow**: owed as a workload. `ask(Q.positive(x), Q.gt(x, sqrt(2)) & Q.gt(y, sqrt(2)))` should merge
  components under the plant (sqrt(2) becomes a key), so state should differ. Not added, because adding it now would
  change guarded source under the running bar.
The full fired/D table across the bar comes from bar sum. sa-port-168's pl/ has the answer-only screen (7 caught,
consistent-fault loud: a TermFault ends the run).

## Done in results/ (this commit)
port-ownership.tsv 539-554 -> "landed 5c8 (port-5c8.md)", Rust, with left/runs. New state rows 821-824: Engine.splits (5c9),
Engine.stats (never by a planned step), _KEYS, _CONST (stay). port-ownership.md :99 updated (it was :97 before the
stack). No container moved, so no digest switch. Scripts: ~/sa-rust-ids-work/sa-port-170/../scratchpad tsv.py are gone. The edits are in the commit.

## Next
1. When bar-5c8/done.txt exists, read sum.txt. State the five items. Handler multiset against base, with `_consistent`'s
   rows (Rust's catches come through handler_count's hook, handler_count.py:40-54) next to Python's 34+4.
2. Landing: if S1 lands f1e4a74 unchanged (sa-port-169), `sh rust-spike/slice/p1/bar.sh land fece4c7` without PUSH,
   read the incoming diff, then `PUSH=1`. If anything else landed, rebase, and rerun the bar if the diff touches guarded source.
   Never land before the stack. Tell the architect when rust-slice moves.
3. Write results/port-5c8.md in port-5c7.md's form (sections: What moved, SHAs, The bar, Plants, Reached [the handoff-168
   rv table + pycalls], Kept reasons, State [splits/stats/_KEYS/_CONST rows 821-824], Module count, Owed, Not run). Then
   `agent report` and push.
