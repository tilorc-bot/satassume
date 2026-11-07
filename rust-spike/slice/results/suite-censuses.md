# Suite censuses on source 2d00bea (issue 323)

Both censuses ran on source 2d00bea, which holds PR 328. The older `suite2` ran without it. Census keys are `file|function|line` at 2d00bea; `PORT-INVENTORY.md`'s lines are at c230ee0, so compare by file and function. Outputs are under `~/sa-rust-ids-work/port-census/` (`$C`).

Both are complete by test id: 6,125 of 6,125. Memos stay on, as the tests own them, so counts are floors, and they aren't costs.

## Derived census

`$C/derived-suite`, orion, `-n 6`, 09:13 to 09:38 UTC. `exit=1` is 4 failed tests, not a crash or a timeout: 4 failed, 6,080 passed, 23 skipped, 18 xfailed, in 1,518 s. Every worker wrote its final dump, and the workers' lists hold 6,125 unique ids, the same set as the controller's. `derived_merge.py` labels this "7 workers": 6 plus the controller, which has 0 queries.

282,466 top-level queries. 27,401 touched a derived term at one of the sites, 21,420 at a sort key.

| Site | Calls classed | Derived | Queries touching one | Derived shapes |
|---|---:|---:|---:|---|
| `relations._key` | 506,810 | 126,193 | 21,407 | `0`; two-term sums such as `x/2 + 2*z`, in 7 queries |
| LRA `default_sort_key` | 117,873 | 311 | 39 | Products of input terms: 2 args (`r**2*w`, 28), 3 (`r*w*y**2`, 9), 4 or more (`n*w**2*x*y`, 6) |
| `Session.node` | 3,212,314 | 138,105 | 13,489 | 49 shapes, below |

Shape counts are one per term per query, so they don't add up to queries. Callers: all derived calls at `relations._key` are `relation_atom:524`; LRA's are `<lambda>:324` 134, `interpret:348` 134 and `integer_form:412` 43. None of the sort-key shapes carries a float, an infinity or a non-rational number factor.

**The two `calls` lines:**

- `capture|preorder-stopped-at-top`: **239.** `preorder_traversal` stopped at the top of a term with args this many times. The `.args` walk in `derived_plugin.py` works around it. The cause in SymPy wasn't found.
- `|outside-query`: **`node` 89,167, `sort.relations` 54,902, `sort.lra` 4,375.** Tests driving `Session` or an adapter directly have no captured input, so these calls are counted and not classed. They aren't in the table, and any shape reached only that way is missing from it.

**Against the five workloads (`PORT-INVENTORY.md` section 3):**

- **`relations._key`: same shapes.**
- **LRA sort key: wider.** The five showed only `re(x)*im(x)`. The suite adds products of 3 and 4 or more args, and `Pow` factors. `algebra_check.py` predicted `-t`, `c*t`, `t + c` and `p - q`, so it didn't cover these. Whether Rust's `mul_key` gets them right wasn't checked here: the suite doesn't install component 0's shadow (`port-D0.md`).
- **`Session.node`: deeper shapes now appear,** which section 3 says none of the five showed. Of 53,827 shape counts: `Dummy` atoms 194, `Pow` 52, deeper sums 36, function applications and one `Sum` 28, deeper products 27. Terms holding a float or an infinity: 51. The rest are the known kinds: sums of input or `c*input` terms 29,250, `c*input` 17,161, products of input terms 5,443, numbers 1,636.
- **Where those come from isn't traced, beyond examples.** Many hold a `Dummy` (`gamma(-_k/2 + x + 1/2)`, `f(_x)`), which points to `limits.py`'s `_inner`; that's an inference. Others are closed and hold none (`exp(-1)`, `log(7)/log(2)`, `1/log(2)`).
- **The one derived `Sum`,** `Sum(k, (k, 1, 3))`, fits section 7's claim that these classes are built only at `limits.py:83` from one in the input: `tests/test_notmpl_limits.py:32` has `Sum(k, (k, 1, 3), (n, 1, k))`. By reading; not traced to that query.

**How many suite queries these shapes would keep on Python isn't measured.**

## Suite census

Two parts, each id in exactly one.

| Part | Where | Tests in the JSON | How it ended |
|---|---|---:|---|
| `suite3` | orion, `-n 6`, `census_plugin2` | 5,000 | exit 124 at the 7,000 s limit, 09:09 UTC |
| `suite4` | pareto1, `-n 6 --dist worksteal`, shared lease, `census_plugin3` (dumps after every test) | 1,125 | exit 1, 10:17 to 10:37 UTC: 5 failed, 1,110 passed, 5 skipped, 5 xfailed |

**A correction to "5,562 by id, 563 not run":** both numbers are right, but `suite3`'s JSON holds only 5,000 tests. It dumps every 200 tests, so the 562 tests that finished after a worker's last dump are in `done-*.txt` and in no JSON. By worker, finished then in JSON: `gw0` 92, 0; `gw1` 1,452, 1,400; `gw2` 919, 800; `gw3` 1,544, 1,400; `gw4` 671, 600; `gw5` 884, 800. So the rerun took 1,125 ids, not 563: `$C/suite4-ids/{notrun,unsaved,all}.txt`. All 1,125 finished, and none also sits in the 5,000.

**Same code on both machines:** `suite4` ran a `git archive` of 2d00bea, and all 1,568 of SymPy's `.py` files have matching hashes on orion and pareto1. Same Python, pytest, xdist and mpmath versions, hash seed 0. The tests ran in a different mix, so with memos on the call counts aren't what one straight run would give; reach is the reading here. `suite3`'s log has 26 `F` marks and no summary, so those tests aren't named. A test that failed early reached less.

**Reach, merged (`$C/suite-full`, summary `$C/suite-full-summary.txt`):**

| Module | Functions run, `suite2` | Functions run, merged | Calls, `suite2` | Calls, merged |
|---|---:|---:|---:|---:|
| `templates/special.py` | 5 | 5 | 97 | 96 |
| `templates/stats.py` | 2 | 2 | 22 | 22 |
| `templates/rootof.py` | 5 | 5 | 1,415 | 1,415 |
| `templates/physics.py` | 2 | 2 | 18 | 18 |
| `templates/limits.py` | 18 | 18 | 1,953 | 2,611 |
| `templates/functions.py` | 27 | 27 | 8,645 | 9,586 |
| `realroots.py` | 18 | 18 | 47,904 | 47,904 |
| `extensions.py` | 26 | 26 | 107,169 | 110,196 |

Excluding `<module>`, so counts compare with `suite2-summary.txt`. **No module's reach changed,** so what `gw0` lost in `suite2` added no function in these eight. `special.py` shows one call fewer, so the two runs aren't supersets of each other.

**SymPy areas reached directly:** `special` 1 site, 7 calls (`_rows.py:374` to `betainc_regularized.__new__`); `stats` 3 sites, 27 calls; `rootof` 5 sites, 392 calls; `physics` 0 direct sites, with 8,057 constructor calls in SymPy's `physics/` code somewhere below a satassume line (the tool's `^physics/` match; not read further). Enclosures (R9): `lra_bounds.constant_enclosure` 248 calls, `_interval` 3,951; those are calls, and this census doesn't give them per query.

**Not seen: 50 of 927 functions** (module-level functions and methods, `$C/suite4-ids/not-seen.json`; nested functions aren't in the 927). None of the 50 ran on dev or fuzz either. Mostly `__repr__`, `sat/formula.py`'s operators and `sat/theory.py`'s abstract base. The ones worth a look when their step comes: `Relations._bound`, `LRAAdapter.register_bounds`, `LRAAdapter.to_constraint`, `lra_adapter.constant_enclosure`, `realroots._div`, `Element.__init__`, `Element.__abs__`, `special._register`, `sympy_api.set_default_engine`. This is "not seen in the suite with memos on", and it's a reading of these runs only. Nothing was read to see whether any is dead.

**`gw0`'s two losses:**

- **`suite3`, why there's no file: shown.** It finished 92 tests, under the 200-test dump, and was killed at the limit.
- **`suite3`, why it stopped at 92: not established.** Its last finished test is `test_eq_links.py::test_fuzz_against_models` at 07:38:47 UTC, 5,419 s before the 09:09:06 stop. The log has no crash line. The 563 not run are 6 contiguous blocks, and each starts at the next test in collection order after one worker's last finished test. So each worker was probably on that first test, with the rest queued behind it; xdist doesn't print this. For `gw0` that's `test_shared_subterm_against_models`, with 162 behind it. That test finished in the derived census (`gw2`) and in `suite4` (`gw0`), so it isn't a certain hang. Slow or stuck on orion under the profile hook isn't told apart.
- **`suite2`: not established.** Its plugin writes only at session end and keeps no id list, so `gw0` still running at the 3,000 s kill explains the missing file, and nothing says which test it was on or that it's the same one.
- **Why `gw0` both times: not established.**

## Wall clocks, for the record

The derived census's 4 failures, by their own asserts:

| Test | Measured | Limit | Worker | Census hooks on its path, run alone |
|---|---:|---:|---|---|
| `test_solver.py::test_performance_smoke_300_vars` | 13.27 s | 5.0 s | `gw3` | 0 |
| `test_wide_derived.py::test_wide_or_compiles_in_linear_time[positive]` | 2.35 s | 1.0 s | `gw1` | 0 |
| `test_wide_derived.py::test_wide_derived_or_against_or_is_fast[or-nor]` | 2.84 s | 2.0 s | `gw1` | 2 queries, 2,400 `node` |
| `...or_is_fast[nor-or]` | 2.44 s | 2.0 s | `gw1` | 2 queries, 2,400 `node` |

**What this run shows:**

- 3 of `test_wide_derived.py`'s 72 tests failed, all on `gw1`, inside about 40 s. From `perf_counter` and the uptime offset, that's about 09:31:30 to 09:32:08 UTC. Their neighbours on `gw1` didn't fail: `[nonnegative]`, `[nonzero]`, `[or-or]`, `[nor-nor]`.
- For 2 of the 4 failures the census's hooks aren't on the path: a run of each alone fired none (`$C/derived_plugin.py`, counts only). So the hooks don't account for those two. For the 2 `ask` tests, the hooks are on the path and this run can't separate them from anything else.
- The run records no load. The machine's own record does: `sar`, 12 CPUs, `ldavg-1` 38.33 at 09:30:13 and 27.69 at 09:40:03. So load was high when they failed. **That's coincidence in time, not a shown cause,** and this run has no comparison at another load.

**Beside it:** without the census, same source, `test_wide_derived.py` didn't fail in `pr328-check`'s Python suite run, where the smoke test did (6.11 s). D0 failed `[nor-nor]` at 2.27 s, and step 4's Python run failed `[nor-or]`; the architect's brief also lists EUF, with no report in this tree to cite. So no one parameter is the one that fails. `suite4` failed the smoke test (8.57 s) and all four `or_is_fast` parameters (2.35 to 2.75 s) under `sys.setprofile`, which sits on every call, so it says little about this. Each of the 4 passed once when run alone on orion today, with the census's hooks on; that's pass or fail only, not a timing. Not run: anything on a quiet machine, or at a matched load with and without the census.

## Not run

- A rerun of either census, or of the optional `test_performance_smoke_300_vars` comparison on `$R/pre`.
- A derived census with memos cleared, or per-query reach; both censuses are floors.
- Appendix A wasn't regenerated from the merged census.
- Tracing the deeper `Session.node` shapes to their sites, or running component 0's shadow on the suite.
