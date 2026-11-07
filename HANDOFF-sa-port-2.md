# Handoff: sa-port-2 to the next inventory session (issue 323)

**The inventory isn't finished.** I handed off at the context note. `rust-spike/PORT-INVENTORY.md` is pushed to `rust-slice`, still marked partial. Read the brief first: `~/.local/state/agent/briefs/sa-port-2-20261107T055134Z.txt`. Its scope, terms and standing rulings still apply. The file:line map is in `HANDOFF-sa-port-1.md`; its tool paths are stale.

## What's left, in order

Section 8 of the document has the same list.

1. **Real-hash order; this is the one that can change a call.** State differs across hash seeds in 39 of 1,985 dev and 131 of 3,000 fuzz queries; no answer differs. Cause not established. Next: `git archive 68c86b5 | tar -x -C $C/pr328`, run `seed_state.py` with that tree first on `PYTHONPATH` under seeds 0 and 1, compare with `seed_cmp.py`. For a query that still moves, diff `state.dump_py` by field. 68c86b5 is local; `git archive` leaves the clone alone.
2. **Unread modules.** The subagent finished after I handed off: `$C/notes-unread.md`. I saw only its summary and checked none of it, and it did no differential run. Check these before writing them into the document:
   - **`limits.py:92`, possibly a new blocker.** `xreplace` with an assumption-bearing `Dummy` makes SymPy re-evaluate the summand and call `_ask` on compound terms. Dev and fuzz never run it, but `ask` does. Sum, Product and Integral need a decision: stay on Python, or a Rust version that may change answers.
   - **Hidden budget, `limits.py:84`, `engine.py:1245`:** nested queries always use a default engine, whatever the caller's budget.
   - **`limits.py:106`:** `.is_commutative` writes SymPy's cache, against what `domain.py:36-41` says.
   - **More derived terms with symbols:** `functions.py:90-93`, `:315`, `wiring.py:147`, `domain.py:482`, `limits.py:83`, `:172`, `:208`. Compare with section 3's census, which saw none of the suite. `relations.py:1176` also reaches `_affine_strip`.
   - **For a heuristics ruling:** the `PREC_CAP` drop at `relations.py:1423`, and the cost-tuned zero-twin and constant-atom rules. The `except Exception` at `relations.py:1989`, `:2011`, `:2018` shapes the kid sets the budget counts.
3. **Suite census.** `$C/suite2/` and `$C/suite2.log`; it was at about 42% at 06:04 UTC under a 3,000 s limit, started from my session, so it may die with it. Use a new summary of `suite-*.json`, not the log. If it's gone, rerun: `CENSUS_OUT=DIR PYTHONPATH=$PWD:$HOME/sa-rust-ids-work/sympy:$HOME/sa-rust-ids-work/shim:$C $PY -m pytest -q -n 6 -p census_plugin -p no:cacheprovider tests`.
4. **Derived census over the suite:** `-p derived_plugin`, same form. `derived_plugin.py` has never run, so expect a bug. Memos stay on, so counts are floors. Run it after the suite census, not with it; orion's load was 13 on 12 cores.
5. **Finish sections 9 and 10.** Section 8 item 4 lists the format changes. Then remove the partial status, report, and stop.

## Tools

`C=~/sa-rust-ids-work/port-census`, all written by me unless noted. Environment as in `HANDOFF-sa-port-1.md`: `. ~/sa-rust-ids-work/env.sh`, then override `PYTHONPATH`.

- `derived_core.py`, `derived.py`, `derived_plugin.py`, `derived_show.py`: the derived census. Results `derived-*.json`, `derived-others.txt`.
- `algebra_check.py`, `algebra_show.py`: the term algebra check. Results `algebra-*.json`.
- `budget_check.py`, results `budget/`. `seed_state.py`, `seed_cmp.py`, results `seed/`. `is_scan.py`, results `is-scan.tsv`; `is_run.py`.

## Calls so far (mine; sa-port-1's are in its handoff)

- A cone over budget can be a constant in Rust; `rel` there can't change the budget's answer.
- `is` bits are replaced by a refusal: args that are == but not `is` keep the query on Python.
- Sort-key option 1: a small Rust key for the measured shapes, other shapes refused. Not measured on the suite.

**Limit on all of it:** no Rust ran. The algebra check is Python over synthetic combinations.
