# Component 4, slice B: term work through ids (issue 323)

**Tested source `cd79c64`, on `rust-slice` 9009865 (pyset-order), on pareto1 (x86-64). Landed as the commit that adds this report, whose only change from the tested source is this file.** Output: `/home/tilo/sa-rust-ids-work/sa-port-66/l2` on pareto1. Base rows: `pareto1:~/sa-rust-ids-work/sa-port-64/l1/suite`.

**Modules that now run whole because of this: 0 of 32**, as the planner expected. `relations.py` keeps its processing for slice C, and every moved function keeps its Python path for a term with no id.

## What moved

Rust's algebra and key now answer these, in rust mode:

- `relation_atom`'s eq and ne branch, with `_is_number`, `_affine_strip` and the sort by Rust's key. **lt, le, gt and ge stay Python's**, so this isn't the whole function. They do no term work beyond identity tests against nan and the infinities.
- `_termwise`, and `_eq_links`'s difference.
- `_key`: its only caller is `relation_atom`, which no longer calls it on this path.

**What still doesn't come from Rust:**

- `_eq_links`'s clauses are Python's line for line, through `session.var` on SymPy objects.
- The glue's `d = p - q` (`relations.py:2008`) is still built by Python, and Rust's difference must equal it or the run refuses.
- At the LRA sort sites Python still computes the key and uses it. Rust's key must match or the run refuses, so Rust's key decides order only at `eq_sides`.

**Shared files touched:** `rust_plugin.py` (the default mode), `fresh.py` (`--term terms`, `--term-plant`), `term_discard.py` (two more sites). Crate: `term/relations.rs` is new, plus `term/py.rs` and `term/mod.rs`. `lra_backend.py` and `constfield` are untouched.

## The bar

| # | What | Result |
|---|---|---|
| 1 | Suite by id, Rust, `-n 8` | **5,960 / 77 / 46, plus the 1 failure from 1b.** 124 failed, 23 skipped, 18 xfailed. 6,125 ids, none added or gone, **0 outcomes changed** against the base. Three runs, each 0 changed: this one, a repeat, and one with `SLICE_TERM_CHECK=1` |
| 2 | Fresh dev 1,985 and fuzz 3,000 | **MATCH.** Python against Rust with terms: 0 answers, 0 digests, 0 session counts differ. Live: 8 of 8 MATCH |
| 3 | Planted bugs through that comparison | **Caught, 3 of 4 plants, below.** `termwise-true` is not caught |
| 4 | Quiet firings on Rust, that suite run | **39 rows, 2 tests, both already named.** 0 findings |
| 5 | Known differences | None in answers or read state on these comparisons. Limits below |

**The 3 numbers:** `suite_report.py` was run with no Python rows on pareto1 (`pr328-check/suite-python` isn't there), so its "passing on Python 1" isn't from this run. By id that 1 is unchanged from the base: `test_lra_exhaustion.py::test_split_beyond_the_certificate_bound_counts_as_exhausted`, 1b's, as `port-4a.md` names it.

**S's standing:** S's gate is met except for the 46 named stub failures, one cause. They stay listed in number 3, and the crate is unchanged for them. The `_n_conflicts` view in `rust_plugin.py` isn't a port: it's a test-plugin shim, with the 64 tests it moved.

**Passed, split per the planner's rule: 5,959 with no firing, 1 with a firing on Rust,** of 5,960. Python's counter wasn't run on this source, so "doesn't fire on Python" for that 1 comes from earlier reports.

## Quiet firings

| Handler | Test | Type | Rows | Status |
|---|---|---|---:|---|
| `_consistent` | `test_invariants.py::test_ci_stream_reports_only_what_replays` | AttributeError, `_ok` 34 and `_rb_clauses` 4 | 38 | Named needs-internals case, passed |
| `Engine._build_context` | `test_transfer.py::test_protocol_on_fuzz` | RuntimeError, "Already mutably borrowed" | 1 | Named 46-stub cause, `tests/theory_harness.py:242`, failed |

- **`engine.py:1906` (`_complete_check`): 0 catches** on the suite, and fresh dev and fuzz recorded 0 at any handler on Rust.
- **The counter fires:** `quiet_fire.py` and `lazy_fire.py` both exit 0 on this source.
- **`handler_count` covers 2 of the 7 handlers.** `TermRefuse` can't be caught at the other 5, but an ordinary Rust `Exception` there would be quiet and isn't counted. `_guarded` turns one raised inside slice B's consumers into a `TermFault`, which isn't quiet: `fault` is 0 on the suite.

## Planted bugs

| Plant | Dev | Fuzz | Direct |
|---|---|---|---|
| `termwise-false` | **Caught:** 1 answer, 15 digests | Not run | - |
| `swap` | **Caught:** 210 digests, 0 answers | Not run | **Caught**, 483 of 500 |
| `no-strip` | **Not caught**, 0 digests | **Caught:** 84 digests, 0 answers | - |
| `termwise-true` | **Not caught** | **Not caught** | **Caught as `wise`**, 339 of 500 |
| No rollback, discard | **Caught:** 489 digests, 1,985 of 1,985 left state, 0 answers | Not run | - |

**`termwise-true` is a real limit:** a wrong True at `_termwise`, the glue's site, moves nothing on dev or fuzz. The evidence for that arm is the direct comparison and check mode, not the fresh comparison. I didn't look into why. Note `_eq_links` reads `eq_diff`, not this plant.

Direct's `key` plant is caught at 440 product keys and 337 difference keys, and `sub` at 341. `test_term_ids.py` also shows the check catching `swap`, and a key and a scaffold plant refusing and answering on Python.

## Reach

| Calls on Rust | `relation_atom` | `_eq_links` | `_termwise` | LRA key asked | of those derived | Refused | Rebuilt |
|---|---:|---:|---:|---:|---:|---:|---:|
| Fresh dev | 1,381 | 40 | 30 | 4,055 | 7 | 0 | 0 |
| Fresh fuzz | 27,626 | 888 | 1,576 | 117,684 | not read | 0 | 100 |
| Suite | 161,654 | 21,028 | 2,614 | 101,724 | 302 | 38 | 18,969 |

**Check mode on the suite**, Python's own function beside each answer from Rust, read after the run: `relation_atom` 160,939 same, `_eq_links` 32,152 same, `_termwise` 2,559 same, **0 differ**. Check mode builds in SymPy, so these are evidence and not numbers to quote for speed.

**Direct comparison, `term_ids_direct.py`, new, 20,000 random pairs, 19,352 converted: 0 differ.** `eq_sides` answered 19,351. `sub` with its form, `_termwise` and `eq_diff` answered 13,341. Product keys answered 18,717. 648 pairs were kept out of scope, and it refuses on the rest as counted in its output.

**The handoff's dev question:** slice A's `converted` of 1,935 and sa-port-65's 1,197 are both right. 1,935 comes from `fresh.py`, which clears memos per query. 1,197 comes from `live.py`, which keeps them, and `keys` mode gives 1,197 there too, so slice B didn't cause it. Fresh dev on this source reads 1,935 and 50 kept.

**Still on Python, by call:** `term:no-table` on the suite is `relation_atom` 80,011, `_eq_links` 12,089, `_termwise` 15,026. These run where no table is live, in a Kept query or outside a run. I didn't split them by caller, so about a third of `relation_atom`'s suite calls aren't this port's reach. `term:py:relation_atom`, a term with no id inside a run, is 21. `term:unknown` is 0 on all three suite runs, because that count is only written by a class with no row; these 21 are Add or Mul with an arg with no id.

## Refusals, now on real terms

**38 on the suite, the same count and the same reasons in all three runs,** of about 34,727 converted. Fresh dev and fuzz: 0. This is the first time the refusal path has run on real terms outside hand-built tests.

| Reason | Count | Distinct queries | Example |
|---|---:|---:|---|
| `mul: class has its own as_base_exp` | 19 | 6 | `Q.eq(exp(f(g(0))), y)` |
| `algebra: holds an infinity, nan or Float` | 9 | 6 | `Q.eq(f(nan), f(nan))` |
| `compare: types Python's < doesn't order` | 8 | 7 | `Q.eq(0.1, 1/10)` |
| `mul: a coefficient beside a numeric-base power` | 2 | 1 | a long disjunction with `sqrt(2)` |

- **Exp factors, the planner's follow-up:** 19 suite refusals on 6 distinct queries, half of all refusals. It isn't the key: it's `mul` in `sub`, negating a factor whose class has its own `as_base_exp`, so `Q.eq(exp(t), y)` discards its run. No `key:` reason appears on the suite. By count on the suite this isn't worth porting yet. The direct comparison refuses this reason on 854 of 19,352 random pairs, which says what shape it is and not how often real use reaches it.
- **Derived products at the LRA sort sites:** 302 asked on the suite, 0 mismatches, 0 refusals. Direct: 18,717 product keys matched, 633 refused, 612 of them `a Mul with a Number head that isn't rational`.
- **Handoff items 4 and 5, measured on the suite:** `rational_head`'s `strip:` refusal 0. `sub`'s refusals are the 9 and the 2 above at most, since those reasons aren't only reached through `sub`.
- **`read_raised` on real reads, first consumer's count:** 0 on the suite, and `read_term_missing` 0.
- **`Kept('too-deep')`:** 0.

**A discarded run leaves nothing in Python, shown on planted refusals at real sites, now including slice B's:**

| Column | Queries | Left something | Reached: `relation_atom` / `_eq_links` / `_termwise` / LRA key |
|---|---:|---:|---|
| Dev, Rust | 1,985 | 0 | 22 / 6 / 3 / 25 |
| Fuzz, Rust | 3,000 | 0 | 307 / 62 / 66 / 288 |
| Dev, Python's solver | 1,985 | 0 | not read |

Answers and digests are identical to Python on each.

**Limit:** the state check ran on planted refusals, not on the suite's 38 real ones. For those the evidence is 0 suite outcomes changed, and `test_term_ids.py` comparing the answer with Python on 3 such shapes. The rollback ran on them: `rollback:cleared` 32, `rollback:restamped` 36.

## Count noise, owed from slice A

**The counts still move between runs of one source, and they now move which path answers, but no answer has moved.**

| | Run 1 | Run 2 | Check run |
|---|---:|---:|---:|
| `converted` | 34,727 | 34,717 | 34,727 |
| `args-eq-not-is` | 2 | 12 | 1 |
| `term:py:relation_atom` | 21 | 8 | 0 |
| `scaffold:rebuilt:relation_atom` | 9 | 5 | 0 |
| `term:rust:relation_atom` | 161,654 | 162,239 | 160,947 |
| Refused | 38 | 38 | 38 |
| Outcomes changed | 0 | 0 | 0 |

A query taking the Kept route answers wholly on Python, so these move between Rust's path and Python's. **Cause still untested.** It's a reason not to read a suite count as exact. The check run also adds its own calls, so its column isn't a clean third sample.

## Scaffolding, must reach zero before any backend PR

| | Rebuilt | At `_eq_links` | At `relation_atom` | Mismatches |
|---|---:|---:|---:|---:|
| Fresh dev | 0 | 0 | 0 | 0 |
| Fresh fuzz | 100 | 0 | 100 | 0 |
| Suite | 18,969 | 18,960 | 9 | 0 |

**Fresh dev's 0 isn't "no construction":** on a fresh engine the glue's Python `p - q` has already built the difference. `_eq_links` rebuilds only where a memo from an earlier query saved that work, as in the suite. Moving the glue in slice C moves this count. Rebuilt Rationals are counted now; they weren't in the first version. No speed is reported, since timing is on the backend PR list.

## What I changed from the first version

- `_same_key` now follows the shadow's `_tagged` rule. The first version's clause was an approximation that could have hidden a wrong key.
- `test_term_ids.py`: 48 of 56 failed, on three test bugs. `table_for` passed `None` as assumptions, which conversion keeps as out of scope. The fixture kept an answer memo. Two spies sat outside the run, where no table is live. The test that asserted `>= 0` now compares with Python's answer and its reason.
- No change to Rust's term code came out of this.

## Tests

- `test_term_ids.py` and the others on Python's solver: 148 passed, 6 skipped (`test_term_ids.py`, `test_term_live.py`, `test_lazy_reads.py`).
- On Rust's solver: `test_term_ids.py` 56 passed, `test_term_live.py` 19 passed.

## Not run

Moved to "before any backend PR" by the landing bar:

- The mutant 2, 5, 6, 7, 9 rerun and mutlive's control. Those mutants rest on the API fuzzer alone.
- The boundary rescore and suite column. 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run. These boundaries moved in this slice.
- The final drop score and its lost rows.
- The suite split with Python's counter.
- `order:_rows`' evidence: not caught meanwhile.
- The `_forms` guard test.
- History and seed reruns, forced moves, the native path, and timing.
- A public-API version of `test_incremental_matches_fresh`: due during the engine port at the latest.

Also not run:

- The component 0 shadow on this source.
- `termwise-false`, `swap` and no-rollback on fuzz.
- Any study of the count noise's cause, or of `term:no-table`'s callers.

`test_performance_smoke_300_vars`' outcome is unchanged from the base. I didn't chase it.
