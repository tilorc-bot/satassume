# Step 5b, first item: what the joins are (issue 323)

One suite run with `join_log.py` on, source 5179361 (rust-slice bfac870 plus the hook), pareto1, x86-64, `-n 8`, `PYTHONHASHSEED=0`. 5,960 passed, 124 failed, 23 skipped, 18 xfailed: the same totals as 5a. Not compared by id, and its handler rows weren't read, since this run only logs joins. Rows: pareto1 `~/sp19/sa-rust-ids-work/sa-port-85/joinlog`, copied to orion `~/sa-rust-ids-work/sa-port-85/joinlog-rows`.

## Result
- **1,041 joins in 19 tests, 143 distinct (session, node). All 1,041 are one shape:** the same text under two `UndefinedFunction` classes with the same name, same `_kwargs` and same hash. Text: `f(x)` 825, `f(z)` 184, `g(y)` 21, `g(0)` 6, `f(0)` 3, `f(xr)` 2. None is any other shape, so sa-port-81's reading holds on this run.
- The logged rows and the `join` counter agree, 1,041 each, so the log missed none.
- **Control:** the hook fires on a planted `f(x)` join and on `1` against `1.0` (`control.py`, 3 rows, summary names 2 as not `f(x)`), so "none of another shape" isn't a false zero.

## The swing
| run | joins | tests | largest |
|---|--:|--:|---|
| this, 5179361 | 1,041 | 19 | `test_transfer_against_explicit_clauses[4-lra]` 517 |
| sa-port-84, 55cb00d | 769 | 18 | `test_split_relational_answer_is_the_part_answer` 184 |
| `suite-cea574c` | 76 | 12 | `test_zero_in_the_proposition_is_an_equality` 15 |

38 tests have a join in at least one of these runs and 1 has one in all three. In this run 1,038 of the 1,041 were on one worker (gw3), 3 on gw0, 0 on the other six. So the count follows what a worker ran earlier, which fits sa-port-81's account of a cached `f(x)` from an earlier `Function('f')`. **Stated, not fully explained:** I didn't fix a worker order and show the count repeats.

## What this means for the link
No join of another shape, so nothing to bring to the planner on shape. Whether a join's first-object choice can decide something the link reads depends on the link, and that isn't built. The design in `HANDOFF-sa-port-85.md` resolves the object passed and never the node's first object, so by reading it can't. That is to be pinned by test, not assumed.
