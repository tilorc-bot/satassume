# knowledge/domain.py before a port: what it computes, and what reads it (issue 323, sa-port-364)

**Result: no port was written. Status: question.** The largest result domain.py computes on the Rust path, the
construction level of every converted term, is read by nothing but the shadow check; on the default Python path it is
not computed at all. Taking it out of the two walkers removes about four fifths of domain.py's share, and what is left
is below 2 x the S1 spread on dev and on wiring, so the stop rule holds for the port (planner ruling 364 (c), (d)).

- Tree: rust-slice 966268c, no source change. Counts on orion (aarch64, Python 3.12.14), .so 4d8921d9c510e99f built
  from 966268c by build_solver.sh. Counts only: nothing here is a time. The shares are sa-port-356's profile
  (measured-next.md (1): de88d9b9, pareto1, quiet lease, the C sampler), the ranking 362 carried; no new profile.
- Tools: tools364. `cnt364.py` replaces each function of domain.py by a counting wrapper in every module that holds it
  and charges each call to its caller, per query; `gocnt364.sh` runs dev, fuzz 424242, budget and wiring in three cells
  (**py**: the package alone; **rust-py** and **rust-nat**: the slice with S1's rust-nat switches under SLICE_CONVERT=py
  and =rust); `tab364.py` makes `tab-orion.txt` (the full table and every caller). Per-query rows: orion
  ~/sa-rust-ids-work/sa-port-364/cnt4/WL-CELL.json.
- Answers' digests are equal in the three cells of each workload (dev 31cd0945c07f02a6, 356's; fuzz 173502b6ef285ad6;
  budget 35bc2c4a937bebc0; wiring a0df9fd43e5180c1). Two full runs give the same rows in all 12 cells. Converter
  fallbacks (cv:fallback:depth, :name, cv:patched): 0 in every Rust cell.
- False zeros: the two read counters fire on a planted read after each pass (`Engine().is_(A, 'commutative')` for a
  non-commutative `A`: 1 read through `_construction_level`; one `TermTable.row` call: 1). The row counter's first
  version never fired (a method call reaches sys.monitoring as the unbound descriptor); its zero was not used.

## Computed against read, per result (calls over the pass, and the number of queries with at least one)

| result | workload | py (default path): computed / read | rust-py and rust-nat (equal): computed / read |
|---|---|---|---|
| **level**, `constructed_noncommutative(t)` | dev | 0 / 0 | 4,515 (1,197 q) / 0 |
| | fuzz | 0 / 0 | 28,853 (2,998 q) / 0 |
| | budget | 0 / 0 | 7,472 (28 q) / 0 |
| | wiring | 0 / 0 | 63,184 (6,512 q) / 0 |
| **nc**, `_noncommutative(e)`: the walk on a memo miss / every call | dev | 164 (158 q) / 2,701 (978 q) | 164 (158 q) / 3,895 (1,188 q) |
| | fuzz | 148 (123 q) / 5,560 (2,076 q) | 148 (123 q) / 3,746 (1,680 q) |
| | budget | 42 (13 q) / 323 (28 q) | 42 (13 q) / 318 (28 q) |
| | wiring | 109 (73 q) / 37,139 (5,959 q) | 110 (73 q) / 42,899 (6,512 q) |
| `kept_product(factors)`: every call is read | dev | 38 (16 q) | 0 |
| | wiring | 10 (8 q) | 1 (1 q) |
| | fuzz, budget | 0 | 0 |
| `noncommutative_false()` | all four | 0 calls | 0 calls |

The level is not 0 once in the four workloads (dev: one term at 2, in one query), and no call of `_noncommutative`
returns True on any of them.

What reads each result:

| result | computed at | read by |
|---|---|---|
| level, on demand | `engine._construction_level`, engine.py:165 | `_noncommutative_answer`, engine.py:2044, :2091; entry.rs:579 into `noncomm_answer` :623, :685. Only when `_noncommutative(node)` is True, so it is already computed on its read. No workload reaches it: sympy_api.py:282 keeps such a term out of scope first. Tests reach it (tests/test_noncommutative.py:632). |
| level, per term | `term_row`: convert.py:305, walk.rs:865 (the callback `constructed_nc`, :165, :271), once for every term of every converted query | The token goes to `TermRow.level` (table.rs:143, :338); its one exposer is `TermTable.row` (py.rs:349), index 5. `row`'s callers: term_live.py:490 `scaffold` (row[0], row[1]; 24 calls on dev, 204 on fuzz), term_history.py:78, :83 (row[4], row[:5]), term_shadow.py (index 5 at :128, checked at :167 against the same function). **No Rust code and no query-time Python reads it; the shadow check is its only reader.** No plant sits on it. |
| nc | domain.py:431, memo `_NONCOMM` (4096 rows, cleared when full) | sympy_api.py:282 `_applied_category` (the scope check; under the slice also called from convert.py:543, walk.rs:1136 and relevance.rs:326, which is why the Rust cells show more Python calls), engine.py:173, :2043, :2083; entry.rs:546 reads the memo itself and calls the function on a miss. Every call branches on the result. |
| `kept_product` | domain.py:474 | templates/core.py:96, :342, :430; lra_adapter.py:208. Rust has its own (lra_read.rs:245, rows_tpl.rs:1473), so the slice calls Python's once on wiring. No sample in the profile. |
| `noncommutative_false` | domain.py:388, once per process | engine.py:161, entry.rs:586, at level 2 only. |
| `_fixed_noncommutative` (helper) | domain.py:35 | `constructed_noncommutative` for a symbol (2,016 / 5,750 / 7,307 / 44,880 calls on dev / fuzz / budget / wiring under the slice, 0 on py) and the nc walk (816 / 831 / 3,865 / 893, the same on py). |
| `SWEPT_UNARY` | domain.py:150 | `_swept_unary`, and the offline tools (tools/sweep_unary_functions.py, gen_offline_data.py:138). |

## Where domain.py's share is (356's profile, rust-nat, own share of in-loop samples)

| function | dev | fuzz | budget | wiring |
|---|---|---|---|---|
| `constructed_noncommutative` | 1.22 | 1.29 | 2.82 | 3.04 |
| `_fixed_noncommutative` | 0.29 | 0.10 | 1.05 | 0.51 |
| `_noncommutative` | 0.24 | 0.05 | 0.36 | 0.11 |
| `_is_matrix`, `_holds_matrix`, `_matrix_to_scalar` | 0.05 | 0.01 | 0.24 | 0.00 |
| domain.py own / inclusive | 1.80 / 2.0 | 1.45 / 1.5 | 4.47 / 4.6 | 3.66 / 3.7 |
| **goes with the per-term level** (its own, plus `_fixed_noncommutative` split by the call counts above) | **1.43** | **1.38** | **3.51** | **3.54** |
| left in domain.py (the nc walk and its helpers) | 0.37 | 0.07 | 0.96 | 0.12 |
| 2 x the S1 spread (356's 5 rounds; 354's 12 rounds gave 0.8% for wiring) | 1.2 | | | 3.0 (1.6) |

The split of `_fixed_noncommutative` is by calls, so the bold row is an estimate to about 0.1 point; the Rust-to-Python
call per term is outside domain.py's own share and goes too.

## Under the ruling

- **(a)** The table above. The read count of the per-term level is 0 on every query of the four workloads, against
  4,515 to 63,184 computed.
- **(b)** Nothing on the default path is computed before its read: Python computes the level only inside the branch
  that reads it, and the nc walk only on a memo miss of a call that branches on it. There is no Python change to make
  first, and the default path gains nothing from this file.
- **(d)** The per-term level is a result nothing reads: it is removed, not ported, as the formula skeleton was. That
  is a change to both walkers, the table, `TermTable.row` and the shadow check, the same files as sa-port-363's
  removal, so it goes on top of that landing. Computing it lazily in the table instead would add a read with no
  reader.
- **(c) and the 2 x stop** What is left to port after (d) is 0.37% of dev and 0.12% of wiring, less than 2 x the spread
  on both, even if a port removed all of it, which it cannot (the walk reads SymPy's classes and objects through the C
  API either way). So no port of domain.py; the removal is where the time is.
- Not done here: the removal itself, its gate, S1 and bar. HANDOFF-sa-port-364.md has the file:line map.
