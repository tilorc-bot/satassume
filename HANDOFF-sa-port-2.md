# Handoff: sa-port-2 to the next inventory session (issue 323)

**The inventory isn't finished.** I handed off at the context note. `rust-spike/PORT-INVENTORY.md` is pushed to `rust-slice`, still marked partial. Read the brief first: `~/.local/state/agent/briefs/sa-port-2-20261107T055134Z.txt`. Its scope, terms and standing rulings still apply. The file:line map is in `HANDOFF-sa-port-1.md`; its tool paths are stale.

## What's left, in order

Section 8 of the document has the same list.

1. **Real-hash order; this is the one that can change a call.** State differs across hash seeds in 39 of 1,985 dev and 131 of 3,000 fuzz queries; no answer differs. Cause not established. Next: `git archive 68c86b5 | tar -x -C $C/pr328`, run `seed_state.py` with that tree first on `PYTHONPATH` under seeds 0 and 1, compare with `seed_cmp.py`. For a query that still moves, diff `state.dump_py` by field. 68c86b5 is local; `git archive` leaves the clone alone.
2. **Unread modules.** A subagent was reading them when I handed off. If `$C/notes-unread.md` exists and looks complete, use it, treating it as a report to check rather than fact; I never saw it. If not, read them or spawn again (notes to a file, at most 2k back).
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
