# HANDOFF sa-port-264: formula step (issue 323), eighth part

Branch `port/formula`, head = this commit, on rust-slice **9151316**. **Unbarred, unlanded.** Handed off at the context
budget, **inside gate step 3 (convert once)**: the commit below is work in progress, builds, and leaves one test failing.
Nothing else in the gate was started. j1 (`~/sa-rust-ids-work/sa-port-260/j1`) had no `end.txt` at 00:32Z 11 Nov: not read.

## Step 3 as it stands (WIP commit)
- New in formula.rs: `Nodes` (a trait: `atoms(f)`), implemented by `Hand` and by `SessionCore`. A `Hand` is what an entry
  holds for the length of its call: each formula is converted the first time something needs it, found by identity
  after that. It is passed as an argument to the scope and cone functions, and `Hand::give(s, needed)` hands each held
  node to a session (the session gets its own references through `FNode::share`: two collector-visited holders must
  not share one `Rc<FNode>`).
- `atoms_nosession` is gone. scope_core.rs and budget.rs take `nodes: &dyn Nodes` and never convert.
- A caller holding nodes calls Rust's own function directly while the Python name is still the installed one
  (`context::patched_method` against `session_live.OURS`; `scope_core::theory_scope_from` against
  `sa_solver.scope_theory_scope`), and calls the patched name with the objects otherwise. Done for `_within_budget`,
  `verdict`, `_context_session`, `theory_scope` from entry.rs and context.rs. `_fresh_session` and the session's methods
  stay by name.
- Counters: `fm:nosession` (644) now means "a scope or cone pyfunction entered while another entry is live" (a by-name
  call dropped the nodes); `fm:twice` (645): an object converted a second time inside one outermost entry; `fm:give`
  (646). Plant 607 `fm-hand-no-give`.
- Numbers, one Rust pass, `--check plain`, before (cb1217b) -> after; answers and every per-query line identical:

| workload | fm:convert | fm:nosession | fm:twice | fm:give |
|---|---|---|---|---|
| scope | 1,763 -> 1,275 | 1,170 -> 133 | 137 | 610 |
| dev | 3,928 -> 1,865 | 2,898 -> 196 | 196 | 1,611 |
| zero | 4,497 -> 1,949 | 3,268 -> 555 | 555 | 1,312 |

  (`~/sa-rust-ids-work/sa-port-264/c0` before, `c1` after; `cnt.sh OUTDIR WL...` writes `WL.counts.json`.)

## Not done in step 3
1. `fm:nosession` and `fm:twice` are **not 0**. Not rewired: session_glue.rs:120 (`theory_scope(f, None, exts)` inside a
   session method: pass the session's core as `nodes`) and relevance.rs:759 (`_theory_scope`; relevance.rs:637
   `eng.verdict(g)`: the `rv_*` entries need a `Hand`). Which site gives which share was not measured. scope's
   `fm:twice` exceeds its `fm:nosession` by 4: another path, not found.
2. **Failing test**: test_formula_nodes.py::test_each_plant_fires_and_is_caught[fm-hand-no-give] (:154 takes every `fm-`
   plant). Plant 607 needs its own kept test (an engine query: `fm:twice` 0 without the plant, above 0 with it) and to
   be left out of that parametrization. Plant 607 has not been shown to fire on anything yet.
3. Slice tests run: test_formula_nodes.py only, 8 passed and the one above failed, then `-x` stopped. test_scope_core,
   test_cones_core, test_context_core, test_entry_core and the rest: **not run**. No suite, no digest.
4. `_noncommutative_atoms` (entry.rs:762, context.rs verdict) still walks the formula in Python (engine.py:174).
5. `ent_is_many` holds one `Hand` for all its predicates, so two sessions converting one template formula tick
   `fm:twice`; whether that should be one `Hand` per predicate was not decided.
6. A refused formula is not kept by the `Hand` (as in the session).

## For the planner (not yet sent as a question)
Ruling (3) on extension facts does not fit the code as read:
- `extensions.facts_for(atom)` (knowledge/extensions.py:175) calls the user's handlers on every call and returns what they
  return; there is no registered fact object and no registration position. Python calls it at three sites per query
  (scope.py:213, engine.py:1658, engine.py:731), so a fact can differ between calls within a query.
- scope_core.rs's `extension_atoms` runs inside `theory_scope`, before the session exists, so a session slot cannot be
  filled there.
What the WIP does instead: the entry's `Hand` holds each returned fact object by identity and gives it to the session, so
an object the handler returns again is converted once per query. This needs the planner's yes or another rule.
Also for the planner: `Hand` is an argument, but it is filled lazily and found by identity; say if that counts as the
"per-query cache" the gate rules out.

## File:line map (at this head)
- formula.rs: counters `NAMES` :61 (`fm:twice` :78), `PLANTS` (607 at :112), `ENTRIES`/`SEEN` :122, `FNode::share` :354,
  `convert_or` :475 (the `fm:twice` tick :496), `Nodes` :529, `Hand` :538 (`enter` :544, `enter_inner` :551, `node` :558,
  `give` :577). Lines after :331 moved down by 14 and after :500 by about 110 against the older map.
- session.rs: `impl Nodes for SessionCore` :998, `fnode` :1318, `take_node` :1335.
- scope_core.rs: `extension_atoms` :241, `theory_scope` :278, `theory_scope_from` :306, `scope_theory_scope` :318.
- budget.rs: `add_kids_of` :61, `struct_` :78, `query_cone` :365, `within_budget` :450, `within` :543, `within_from` :560,
  `cone_info_any` :617.
- context.rs: `patched_method` :66, `context_session_from` :111, `verdict_from` :119, `context_session` :126, `fresh` :196
  (give :200), `build_context` :205, `verdict` :281.
- entry.rs: `ent_is_many`'s hand :620, `theory_scope` :705, is_custom's give :731, `_noncommutative_atoms` :762, `ent_ask`'s
  hand :765 and give :799.
- session_live.py: `OURS` :936 (filled :957, :1151).
- Still to rewire: session_glue.rs:120, relevance.rs:637 and :759.
- Everything else: HANDOFF-sa-port-260.md's map.

## Watch
- Helpers in `~/sa-rust-ids-work/sa-port-264/`: `cnt.sh OUTDIR WL...` (live.py on Rust, `--check plain`, then
  `session_counts()` into `WL.counts.json`; 3 at a time), `run1.sh OUTDIR MODE WL...`, build0-1.log.
- The worktrees HANDOFF-sa-port-260.md lists are still there.
- Plants 600-607 and 660-667 are used; 608-629 and 668-669 are free. Counters 630-646 and 670-672 are used; 647-659 and
  673-679 are free.
