# Handoff: sa-port-65, component 4 slice B (issue 323)

**State: a first version runs on `port/4b` at 776151d or the commit adding this file. Nothing is on `rust-slice`. Not landed, and no landing item is met.** Stopped on the context note, not on a blocker.

## What exists

Rust answers these on ids, in rust mode, with `SLICE_TERM=terms` now the default (`from_env`):

- `relation_atom`'s eq and ne branch, with `_is_number`, `_affine_strip` and the sort by Rust's key.
- `_termwise`, and `_eq_links`'s `p - q`.
- Python's clauses in `_eq_links` are kept line for line, and they still go through `session.var` on SymPy objects.

A derived term Rust returns is rebuilt with SymPy's constructors as scaffolding, form-checked, and refuses on a mismatch. A term with no id stays on Python for that one call and is counted. At the sort sites Python still computes its key, so Rust's key must match it or refuse, including derived products.

## Map

| What | Where |
|---|---|
| Rust: `is_number_term`, `rational_head`, `affine_strip`, `eq_sides`, `closed_finite`, `wise_terms`, `termwise`, `eq_diff` | `rust-spike/slice/solver_rs/src/term/relations.rs` |
| Python bindings | `solver_rs/src/term/py.rs`, the block above `n_input` |
| Plants and check flags | `term_live.py:241` `PLANT`, `:245` `CHECK` |
| Term to id, id to term | `term_live.py:259` `term_id`, `:297` `scaffold` |
| Consumers | `term_live.py:361` `_relation_atom`, `:396` `_termwise`, `:425` `_eq_links`, `:494` `_key_match`, `:472` `_same_key` |
| Wiring | `term_live.py:549` `_install`, `:636` `from_env`, `:626` `report` |
| Python's originals | `satassume/relations.py:465` `_key` (only caller `:524`), `:511` `relation_atom`, `:673` `_termwise`, `:1325` `_eq_links` |
| Not moved, stays for C | `relations.py:2008` glue's `d = p - q`, which only reaches `_termwise` |
| Env | `SLICE_TERM_CHECK=1`, `SLICE_TERM_PLANT=<name>`, `SLICE_TERM_COUNTS=<path>` |
| Join counts | `term_ids_counts.py FILE...`; the suite's `term.PID.json` has the same form |
| Tests | `rust-spike/slice/test_term_ids.py` |
| Output | `~/sa-rust-ids-work/sa-port-65/d1`, `d2` (orion) |

## What ran, all on orion, aarch64, on unlanded source

| Run | Result |
|---|---|
| Dev, `d1`, no check | MATCH: 0 answers, 0 digests, 0 session counts differ, answers 31cd0945c07f02a6. This tree predates the check flag |
| Dev, `d2`, `SLICE_TERM_CHECK=1` | MATCH. `relation_atom` 709 calls, `_eq_links` 34, `_termwise` 10. `check:differs` 0 at all three. Rebuilt 32. Refused 0, key mismatches 0 |
| Fuzz, `d2` | **Unread, still running at 14:43 UTC.** `d2/fuzz-cmp.txt`, `d2/fuzz-rust.json`, end marker `d2/END`. Wait for END before rebuilding: `build_solver.sh` copies over the .so that job has loaded |
| 11 hand-built queries | Ran with 2 refusals, `x + 1.5` and `x + oo`, reason `algebra: holds an infinity, nan or Float`. Answers not compared with Python here |
| `test_term_ids.py` | **48 of 56 fail** |

On `d2`'s `key:*` counts: `key:asked:relations._key` 1,418 (394 derived) exists only because check mode runs Python's `relation_atom`. Don't quote it as the consumer's reach. `key:asked:lra_adapter` 594 (7 derived) is the real site.

## The failing tests

- **39: my helper.** `table_for` converts `And(Q.positive(...))`, and conversion keeps that as `out-of-scope`, so these say nothing about Rust yet. It needs a query form conversion accepts.
- **At least 7: probably an answer memo.** The fixture doesn't do `A.set_default_engine(E.Engine())` as `test_term_live.py:43` `fresh` does. That's a reading, not tested. This includes both refusal plants and `test_every_relation...`.
- **`test_a_termwise_plant_moves_an_answer`: don't assume it's the memo too.** The plant may not move this answer, since the query can be decided another way. If it's still True on a fresh engine, pick another query.
- **Remaining failures, not read:** `test_an_unknown_term...`, `test_nan_goes_last...`, `test_scaffold_rejects...`.
- **`test_a_shape_the_algebra_refuses...` passes and proves nothing:** it asserts `>= 0`, and its inner `install` can't change the mode. Rewrite it to compare with a Python answer.

## Things to check in my code

1. **`converted` on dev is 1,197 plus kept 24; slice A's table says 1,935 plus 50.** Same workload name, cause not looked at. It may be the harness behind that table, or something I changed. Settle this before quoting reach.
2. **`_same_key`'s tagged-tuple clause isn't the shadow's `_tagged` test.** I approximated it. Use the shadow's rule or show they agree. A loose compare here would hide a wrong key.
3. **`scaffold` doesn't count a rebuilt Rational** in `scaffold:rebuilt`, only Add and Mul. The ruling says count, so fix this.
4. **`rational_head` refuses a non-plain class before knowing a strip is possible,** so a non-Expr side refuses where Python returns it unchanged. Safe, but measure it on the suite.
5. **`sub` refuses anything holding Float, infinity or nan, and non-commutative terms,** so any such eq atom with non-number sides now discards its run. Dev had 0; the suite's count is unknown and could be large.
6. **`relation_atom`'s lt, le, gt and ge stay Python's.** They do no term work, but say so in the report rather than claim the whole function.
7. **Reach is thin on dev,** at 34 and 10 calls. Read fuzz, and add a workload or direct comparison if `_termwise` stays this low.

## Left for the landing bar, none of it done

Suite by id with three numbers and handler firings (pareto, x86-64 .so). Fresh dev and fuzz with no check flag on the landing source, Python against Rust. A plant caught by that comparison: `SLICE_TERM_PLANT=swap` or `termwise-false` through `live.py`, untried. Rebase on `origin/rust-slice`, then land without force.

## Owed in the report, not answered yet

- Exp-factor product refusals: 0 on dev so far, fuzz and suite unread. Whether derived products reach Rust's key at the LRA sites is shown only on dev, 7 derived.
- The refusal path on real terms: only the 2 hand-built queries above; no workload has refused yet.
- Whether suite count noise (args-eq-not-is, `converted`) now moves an answer.
- A discarded run leaving nothing in Python, on real refusals, and the count at `engine.py:1906`.
- `read_raised` on real reads.
- How many of the 32 modules run whole: expected 0, not checked.
