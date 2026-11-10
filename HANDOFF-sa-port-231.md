# HANDOFF sa-port-231: formula step (issue 323), first part

Branch `port/formula` (from rust-slice 59e9d15). **Unbarred, unlanded.** Report: rust-spike/slice/results/port-formula.md.
Handed off at the context budget, with (iii) not yet landed (rust-slice still 59e9d15 when last fetched, ~09:10 UTC).

## Done
1. File list and inventory (port-formula.md, 23 rows in groups A-E, each with what it waits on). Progress report 4f23d3a.
2. Module-wide probe, before, all 13 workloads plus dev and fuzz at seed 1 (port-formula.md table,
   port-formula-probe-base.txt). Tool in ~/sa-rust-ids-work/sa-port-231/probe/; base tree is the worktree
   ~/sa-rust-ids-work/sa-port-231/base (59e9d15, with its own sa_solver.so; `git worktree remove` it when done).
3. `formula.rs`: the one-pass conversion to Rust nodes with `atoms_of` on the node; counters 630-639, plants 601-606.
   `test_formula_nodes.py`: 15 tests pass (python mode: `PYTEST_N="-n 0" sh rust-spike/slice/run_suite.sh OUT python
   rust-spike/slice/test_formula_nodes.py`; with test_core_derived_args.py and test_knowledge_core_shapes.py, 58 pass).
4. `scaffold:core:kept_product:mismatch` (+ `:unchecked`), plant 600. core: 0. `:none` in ce706d3 was not a mismatch
   count (port-formula.md, KEPT_PRODUCT section).

## Not done
- Nothing is wired: no query reaches formula.rs, so plants 601-606 are void on the workloads and the after-probe equals
  the before-probe.
- No suite, no dev/fuzz comparison, no handler rows, no kept shares. The mismatch counter has run on core only.

## Next, in order
1. `git fetch`; if (iii) has landed (`~/dev/architect/markers/state-relations-iii-landed`), rebase. rows_tpl.rs and
   lib.rs are the only shared files touched.
2. Per-session node cache in `SessionCore`: object identity -> `FNode` (hold the object so the id can't be reused;
   `FNode.source` already does). `to_f` then walks `N`, not the object: per `N::Atom(k)` take `occ(k).pred/expr` and call
   `pred_id`, `nid_in_formula`, `custom_in_formula` in the same order as today, so nids and refusals don't move.
   `convert` returning None keeps today's Python path (`refuse:*`).
3. Replace the `atoms_of` callbacks (inventory B1-B7) with the cached node's `atoms_of`, then C1-C2 (compile the node
   without going through Python), then D (template formulas built as nodes) and E (keys).
4. After-probe, the bar, land after (iii) and state part 3.

## File:line map (at this branch's head)
- formula.rs: `N` :32, `Occ` :51, counters :59, plants :83, `Walk::atom` :133, `Walk::walk` :162, `FNode` :233,
  `FNode::atoms_of` :257 (Rust callers), `convert` :326, pyfunctions from :355.
- session.rs: `to_f` :942-989, `convert` :993-1009, `nid_in_formula` :804, `custom_in_formula` :829, `atom_fields` :933,
  `compile`/`literal` :1560/:1569, `FORMULA_DEPTH` :481, `SessionRules.classes` :520.
- atoms_of callbacks: session_glue.rs:86, :184; compile_loop.rs:327, :372-376; query.rs:271, :287; scope_core.rs:252-261,
  :286-296; budget.rs:61, :91, :115, :199, :374, :465.
- compile by name: compile_loop.rs:182, :344; session_glue.rs:119; query.rs:248; entry.rs:778, :781.
- rows_tpl.rs: `QIds.pending` :1346, `rest` :1458, `check_products` :1495, `check_product` :1506, flush in
  `direct_split` :1589; plant name :91. knowledge_common_live.py:46-47 (plant 600 in PLANTS).
- session_live.py `_core_rules` :34-39 (the nine classes).

## Watch
- `check_product` calls Rust's `mul`, which interns. It runs after the split, but a bar should check answers and state on
  the workloads where the scaffold fires (core, f6, dev, wiring, loop).
- Slice tests that call `K.install` themselves fail under `run_suite.sh ... rust` with "knowledge_live is already
  installed"; run them in python mode.
