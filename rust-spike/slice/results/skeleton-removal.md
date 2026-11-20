# The converted formula skeleton's removal (issue 323) — (1) readers, (2) side effects, (3) the removal, (4) plants 769 and 771, (5) the gate read, (6) S1, (7) not landed: three rows for the planner

Planner's ruling for sa-port-363 (items 1 to 7) and for sa-port-365 (land-only). Branch port/skeleton-removal from
rust-slice 966268c. **Tested SHA f5c1f3f4** (source c400113 plus tools363's gate scripts; later commits are results/
and HANDOFF only). Python stays the default and the reference; SLICE_CONVERT=rust stays opt-in. No SymPy construction
or evaluation at query time and no float in any decision: the removal adds no code path, it only takes one out.

**State: NOT LANDED and no bar run.** The gate's per-query comparison is equal in all 48 rows, but three rows are not
as the gate wanted them ((7)); under the 365 ruling that is Status: question, so the bar was not started.

.so hashes: f5c1f3f4 x86-64 venv a653fd4179da9161 (pareto0, the gate), bench 4ae7f5cf1dbbca07 (pareto1, S1), orion
aarch64 fcf0524571e0cea9. Base 966268c: venv 0f78ac2962f34b3a, bench 8b8041d3fe6223c2, orion aarch64 4d8921d9c510e99f.

## (1) Readers of the skeleton at 966268c (sa-port-363)

rg patterns, over the whole tree minus *.md, *.txt, *.json, *.log:
- `\[['"]formula['"]\]|\.get\(['"]formula['"]|['"]formula['"]`
- `\.formula\(\)|\.formula\b(?!s)` (pcre2)
- `\.tables\b|tables\[|tables\.(get|items|keys|values)`
- `\bformula\b` in term/table.rs and term/py.rs; `convert\.formula|formula_top|py_formula|_ORIGINAL\[.formula`

Every reader:
1. term/py.rs:292 (TermTable's constructor required the table) -> term/table.rs:346 parsed it -> term/py.rs:311
   `TermTable.formula()`, whose one caller was term_shadow.py:623 `check_formula` (with `rebuild` :249). A check.
2. Two generic readers of every table that name none: convert_diff.py:131-136 (the differential compares each table
   of the two walkers) and term_history.py:69 (a sha256 of all tables but `reads`). Neither needs the table.

No reader answers a query.

## (2) Side effects (sa-port-363; the per-query proof is (5))

- **Refusals: kept.** `convert.formula` raising `Unsupported` is what makes `convert` return `Kept('out-of-scope')`
  (convert.py:579; walk.rs's entry likewise). So the walk stays as a scope check that builds nothing.
- **It builds no formula node and no skeleton object** (the planner's condition): Python's `_rel` (convert.py:513)
  and `formula` (:522) return nothing, and `_CONNECTIVE` (:519) is the classes alone; Rust's `rel_parts`
  (walk.rs:1076), `formula` (:1091) and `formula_top` (:1171) return `PyResult<()>`, called from the entry's
  `in_scope` closure (:1257). `tables` has no `formula` entry and nothing is encoded for one.
- 'too-deep': RecursionError comes at the same nesting as before, converted at 496 and too-deep at 497, for the
  proposition and for the assumptions, both walkers, base and head (deep363.py; the two outputs are byte-equal).
- Counters: 741 cv:formula and 743 cv:fallback:depth count the scope check, so both stay (743 is not skeleton-only).
  744 is `_template_name`'s and is untouched.
- Encoding the skeleton added only strings to `strings`, so string ids inside `terms` and `settings` shift; counts,
  raised, ids, objects and the number of terms cannot, and (5) shows per query that they did not.

## (3) The removal: c400113, 6 files, 72 lines added, 123 removed

convert.py, solver_rs/src/term/walk.rs, term/table.rs (the field and its parse), term/py.rs (the requirement and the
getter), term_shadow.py (`rebuild`, `check_formula`, `_outcome` gone; `check_scope` :600 is what is left) and
test_convert_walk.py. Shared files changed: none outside the convert component.

Seen and not touched: cargo warns that term/table.rs's `settings` field is never read by Rust (:152). Not traced
further (whether Python reads `tables['settings']`, whether base warned).

## (4) Plants

| plant | state | caught by |
|---|---|---|
| 772 formula-and-as-or | **removed**, with its kept test test_plant_is_caught[772] | (its site is gone) |
| 771 entry-no-assumptions | **kept**, with test_plant_is_caught[771] | the kept test only; see below |
| 769 power-rows-drop-last | kept | its kept test and the differential's forced reads |
| 768, 770, 773 | untouched | as in measured-next.md (7) |

**771 was kept although the ruling listed it to go.** The ruling took the whole walk to be unread; its site is now the
assumptions' scope check, which stays ((2)). What it plants: the Rust walker does not scope-check the assumptions
(walk.rs:1259, as if they were True). Independent check: test_plant_is_caught[771], input `(Q.positive(x), 5)`,
'out-of-scope' against 'non-basic' (passed, kept.log: 33 passed). **The differential no longer catches it** ((7) row 2).

**769 stays** (the planner accepted this). Its site, `_Walk.power_rows` (convert.py:307), lists the terms whose
`as_base_exp` can split; table.rs sets `has_power` from it and `TermTable::power_of` is read by algebra.rs's key of
a derived Add, which can answer. P2 line: `power` is `[0, 0]` in all 48 rows of cmp.txt (24 workloads, both
walkers): no query of any workload asks a power row, so no workload builds a derived Add whose key needs a factor's
power split, and only the kept test and the differential's forced reads reach one. Whether unreached code with a
reader stays is the planner's.

## (5) The gate on f5c1f3f4 against 966268c (pareto0, venv .so; read by sa-port-365)

End line: GATE-DIFF rows 48, **EQUAL 42**, walk-EQUAL 24/24, rc0 96/96; GATE-LIVE rows 60, MATCH 60, rc0 40/40;
convdiff exit 0, answer rows 60, MATCH 60; 771 differences 0, exit 0.

| check | result |
|---|---|
| per query, 24 workloads (dev, fuzz 424242, seeds 0/1/2/42, the 20) x SLICE_CONVERT=py and =rust: answers, Engine.stats, last_budget_limited, conversions, refusals (kept, reason and detail), counts, raised, number of terms | **0 differences in all 48 rows**; answer digests equal in all 48 |
| refusals | dev 24 out-of-scope, cls 6 args-eq-not-is, both walkers, base and head; none elsewhere |
| raised | 0 in all 48 rows; term_live RAISED 0 |
| pass totals (walker, counters 740-746, term_live counts, RAISED, digest, environment) | equal in all 48 |
| pass total `life` | **differs in 6 rows, in `alive` only** ((7) row 1) |
| head, Python's walker against Rust's (cmp-walk.txt) | 24 of 24 EQUAL |
| live.py --check entry (answers, sessions, Engine.stats, moved ids), cells py, cpy, crust, 20 workloads | 60 of 60 MATCH |
| the differential of the two walkers, 20 workloads and the suite | 69,527 inputs, 1,783,835 terms, 0 differences; outcomes: 66,795 Converted, 2,492 out-of-scope, 190 non-default-registry, 42 sum-product-integral, 8 args-eq-not-is |
| the differential under plant 771 (dev and fuzz) | 4,219 inputs, **0 differences** ((7) row 2) |
| kept file test_convert_walk.py | 33 passed ([700-too-deep], [771] among them) |
| suite by id, cells rust, py, off, head against base | one id differs in rust and py: the planted-history test ((7) row 3); off: equal |
| iv, 128 runs, SLICE_CONVERT=rust against =py | 64 of 64 pairs equal |

Known rows by id. Suite: 127 failed on head (rust, py, off) and on base off, 126 on base rust and py; the one id is
`tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` [1]. iv: the Rust
backend fails `tests/test_transfer.py::test_models_respect_transfer` and `::test_protocol_on_fuzz` in the 5-file
orders, 16 of 32 runs under each walker (known: witness-bounds.md:149); Python 0 of 64.

[1] The planted-history test, footnoted by id ([137e]): it fails at test_public_incremental.py:204 with
`assert 0 == 2`; a28c548's method was run on the gate's tree of f5c1f3f4 (tools362/rep362.sh unchanged, pareto0,
.so a653fd4179da9161, 20 fresh processes a cell):

| cell | the test, passed | asserts | keep-alive variant, passed |
|---|---|---|---|
| rust, switches off | 0 of 20 | 14 x `0 == 2`, 6 x `1 == 2` | 20 of 20 |
| rust, SLICE_CONVERT=rust | 1 of 20 | 11 x `0 == 2`, 8 x `1 == 2` | 20 of 20 |
| rust, native witness environment | 1 of 20 | 14 x `0 == 2`, 5 x `1 == 2` | 20 of 20 |
| python, switches off | 20 of 20 | | 20 of 20 |

Plain fails some runs and keep-alive passes 20 of 20 in every cell, so it has [137e]'s signature (the id()-reuse
artifact). Python's rate here is 20 of 20 (362 measured 17 of 20 on 5b20d1f2, tools362/rep-sum.txt).

Not counted in this step: the quiet catches at engine.py's `except Exception` around the complete check, and R5
(term_discard's rows); both come from the bar, which did not run.

## (6) S1 (pareto1, quiet lease a877854a, 29 min, bench-container CPU 2, 12 rounds; bench .so)

NEW f5c1f3f4 against BASE 966268c, medians in seconds, same mode and switches; all 12 arms gave the reference digests
(dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6, budget 35bc2c4a937bebc0, wiring a0df9fd43e5180c1).

| arm | dev | fuzz | budget | wiring | sum |
|---|---|---|---|---|---|
| py-on32 (control, no slice walker) | +0.1% | +0.1% | +0.1% | -0.3% | -0.1% |
| cpy-off (slice, Python's walker) | -1.4% | -0.6% | -0.3% | **-2.0%** | **-1.2%** |
| cpy-on32 | -1.1% | -0.4% | -0.3% | **-1.7%** | -1.1% |
| rust-off | -0.7% | -0.4% | -0.3% | **-1.5%** | -0.7% |
| rust-on32 | -0.5% | -0.1% | -0.3% | **-1.2%** | -0.5% |
| rust-nat | -0.5% | -0.0% | -0.5% | -1.1% | -0.6% |

**No workload is worse beyond the spread in any arm** (the landing rule is met). Bold is faster beyond the spread
(med363.py, med342's rule): wiring in four arms, and the sum under Python's walker with the cache off. The rest is
within the spread.

## (7) Three rows that are not as the gate wanted: Status: question (sa-port-365)

**Row 1: 6 of 48 cmp.txt rows say DIFFER, on the pass total `life.alive` alone.** Rows: lra py, lra rust, f6 py,
f6 rust, wiring py, value rust. `alive` (tools359/diff359.py:97) sums, after each query, the walkers still alive
once the query's results are dropped, with no gc run; `walks`, `weakrefs` (0), `types` and `alive_gc` are equal in
all 48 rows.

| row | base `alive` | head `alive` |
|---|---|---|
| lra py | 15,726 | 15,925 |
| lra rust | 14,892 | 15,182 |
| f6 py | 1,886 | 293 |
| f6 rust | 985 | 370 |
| wiring py | 5 | 10 |
| value rust | 3,970 | 3,973 |

The number is not reproducible on one tree: the gate's own command repeated on orion (aarch64 .so, PYTHONHASHSEED 0,
~/sa-rust-ids-work/sa-port-365/rep/rep.txt) gave, for f6 under Python's walker on the head, 1,966 then 1,886; and
f6 under Rust's walker on base gave 370 twice on orion against 985 on pareto0. It reads as the cyclic collector's
timing (walkers in a cycle wait for the next automatic collection), which I did not prove. It is nonzero on base as
on head, and `alive_gc` (after one collection) is 0 or 1 in every row, equal to base. cmp363.py:39 compares the
whole `life` dict, `alive` included; cmp-walk.txt (Python's walker against Rust's, cmp359.py) does not compare it.

**Row 2: the differential under plant 771 finds 0 differences** (4,219 inputs of dev and fuzz; on base it found
4,195, the skeleton's). With the skeleton gone the plant changes an outcome only for an input whose proposition is
in scope and whose assumptions are not. **No workload has such an input**: the tested tree's own
p1/convert_diff.sh, unchanged, under the plant with PLANT_WLS set to all 20 workloads (pareto0, .so a653fd4179da9161,
~/sa-rust-ids-work/sa-port-365/gocd771-end.txt) gave 29,361 inputs, 0 differences, outcomes 29,331 Converted, 24
out-of-scope, 6 args-eq-not-is, as without the plant. The suite's inputs were not run under the plant (the script's
plant mode runs workloads only). That the plant is on in this .so is shown by its kept test alone, which passes on
the same tree; the differential's 0 has no counter of its own behind it. So 771 is now a kept-test catch (P2: one
line why no workload reaches it, above), where it was a differential catch on base. Whether that is enough, or the
plant goes (a source change, so a new tested SHA and gate), is the planner's.

**Row 3: the planted-history test** fails on the head and passes on base in the suite's rust and py cells (it fails
on both in off). The repeat check ((5), [1]) shows [137e]'s signature, so by the rule it is the known id()-reuse
row, not a DIFFER. Listed here because it is a new-against-base difference by id.

## Not done

- The bar (a tools363 copy of tools361's job361bar.sh, gobar361.sh, chain361.sh, with the plant list without
  formula-and-as-or), the probe count against 21 of 32 (tools361/gopc361.sh), R5 and "nothing kept across queries"
  (R1, H2) as the bar's rows show them, the quiet-catch count, bar.sh land, the guard, PUSH=1, rule [91].
- The bar's plant list depends on the ruling on row 2: job361bar.sh's CONVERT_PLANTS runs the differential per plant
  and 771 would now show 0 differences there.
