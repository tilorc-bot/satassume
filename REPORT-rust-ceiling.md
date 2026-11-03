# Rust ceiling: how much of a pass must stay in Python (issue 323)

Session sa-rust-2. Measured on main `9bafaa5` with outside instrumentation only: no Rust, nothing in
the package changed. Workloads: the dev set (1,985 queries) and fuzz seed 424242 (3,000 queries).

## Result

**The 2x line is cleared, as a ceiling.** Taking the highest estimate of the share S that must stay
in Python as the code stands, S is about 25% on dev and 27% on fuzz. That gives a ceiling of 3.7x to
4.0x, 2.9x to 3.1x if the moved code gets 10x faster, and 3.5x to 3.8x at 50x. The lower estimates
give more (table below).

| whole pass | dev S | 1/S | at 10x | at 50x | fuzz S | 1/S | at 10x | at 50x |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S0: outside the boundary only | 7.8% | 12.9x | 5.88x | 10.39x | 2.6% | 37.9x | 8.08x | 21.80x |
| S1: as the code stands, low | 12.4% | 8.1x | 4.72x | 7.06x | 8.3% | 12.0x | 5.72x | 9.86x |
| S1: as the code stands, high | 25.2% | 4.0x | 3.06x | 3.75x | 26.8% | 3.7x | 2.93x | 3.54x |
| S1 high + 200 ns per SymPy call (assumed) | 35.0% | 2.9x | 2.41x | 2.76x | 41.4% | 2.4x | 2.12x | 2.35x |
| S2: all resolved before the boundary, optimistic | 8.9% | 11.2x | 5.54x | 9.29x | 3.5% | 28.9x | 7.63x | 18.55x |
| S3: resolved, only hash and eq gone | 18.6% | 5.4x | 3.74x | 4.95x | 16.1% | 6.2x | 4.08x | 5.62x |
| S4: the SymPy-reading functions stay in Python whole | 39.6% | 2.5x | 2.19x | 2.45x | 28.1% | 3.6x | 2.83x | 3.38x |

The None / definite split is in [Tables by answer](#tables-by-answer). None and definite answers are
close on dev. On fuzz, definite answers have the higher S: 33.7% against 25.4% at S1 high.

Three limits on this result:

- **The 10x and 50x are the issue's assumptions.** Nothing here measures them. With S1 high, reaching
  2x overall needs the moved code to be at least 3.0x to 3.2x faster. For scale, and only as
  arithmetic: the issue's 1.37x from the typed Cython solver corresponds to about 1.5x to 1.6x on the
  moved code at these S values, but that build was not this split.
- **The real risk is the number of calls into SymPy, not conversion.** The code behind the boundary
  asks SymPy 283 thousand times on dev and 5.9 million times on fuzz, about 2,000 times per query on
  fuzz. Crossing costs were not measured because there is no Rust. At an assumed 200 ns per call, fuzz
  falls to 2.12x at 10x and definite fuzz answers to 1.80x, below the line. So the design has to
  replace most of these calls with integer ids; a callback per hash is the shape to avoid.
- **Conversion is small, and it is already memoized.** Conversion is 1.6% of dev and 0.8% of fuzz.
  Query preparation is not a thin SymPy step: `Session.prepare_query` is session work, 16% and 26% of
  the pass all-in, and it belongs behind the boundary.

**Recommendation:** do not stop on the ceiling. If this goes further, measure next what this report
could not: k on the moved code and the cost per crossing, and treat integer ids for hash and equality
as part of the design. Maintaining two engines and shipping wheels are costs this measurement does
not weigh. The next step is the architect's to decide; no prototype was started.

## The boundary

The issue's shape: the whole session behind the boundary. Function names are from `9bafaa5`.

**Stays in Python, before the call** (`satassume/sympy_api.py`): `ask` (418), `check_strict` (178),
`out_of_scope` (300), `relation_parts` (316), `_relation_formula` (339), `to_formula` (354), `_formula`
(496), `is_constant_proposition` (530), `_ask` (560), `_ask_general` (576), `_keys`, `_keys_rel` and
their helpers (693-860), `_Split` (864), `_relevant` (929), `_part_consistent` (1076), `_consistent`
(1088), `_engine_ask` (1111); the answer memo `eng.answers` and the conversion memo `_FORMULAS`.

**Moves** (`satassume/engine.py` and below): `Engine.ask` (2172), `Engine.is_` (1986),
`Engine.is_many` (2026), `Engine.verdict` (1922), and everything under them: `Session`, the SAT solver,
`Relations`, the LRA and EUF cores, transfer, `EqualitySharing`.

**Behind the boundary but reading or building SymPy** (the "fn groups", listed in full in
`tools-rust/coarse.py`):

- templates: `TemplateRegistry.clauses_for`, `closed_units`.
- lra_read (reading linear forms): `lra_adapter` readers, `constfield.from_sympy`.
- euf_read: `EUFAdapter.parse` and friends, `structural`.
- relation_read: `relations.py` readers such as `_is_number`, `_key`, `sympy_atom`, `relation_atom`.
- struct: `Engine._struct`, `_cone_info`, `_query_cone`, `_union`, `_within_budget`, the noncommutative
  checks, `theory_scope`, `transfer_wanted`.

The boundary timers wrap the outermost entry to any of the four `Engine` methods. The issue's
assumption of one call per query is close: 0.56 calls per query on dev (ask 776, is_ 275, verdict 64)
and 1.10 on fuzz (ask 2,812, is_ 169, verdict 315). Answers from the memo make no call; consistency
checks and the relevance layer make extra ones.

## What the boundary still asks of SymPy

Outermost SymPy entries from inside the boundary, grouped by what they do. The interval is raw, the
calibrated column subtracts the monitoring cost. The map from function to category is `cat_of` in
`tools-rust/analyze.py`; "other" is near zero, so nothing large is unclassified.

**dev**

| asked inside | calls | interval s | calibrated s | share of base |
|---|---:|---:|---:|---:|
| hash | 249,497 | 0.090 | 0.036 | 6.3% |
| eq | 3,726 | 0.004 | 0.003 | 0.5% |
| read | 14,596 | 0.007 | 0.003 | 0.6% |
| walk | 9,759 | 0.058 | 0.030 | 5.2% |
| construct | 1,215 | 0.010 | 0.007 | 1.2% |
| evaluate | 2,112 | 0.006 | 0.004 | 0.6% |
| order | 2,004 | 0.015 | 0.011 | 1.9% |
| other | 9 | 0.000 | 0.000 | 0.0% |

**fuzz 424242**

| asked inside | calls | interval s | calibrated s | share of base |
|---|---:|---:|---:|---:|
| hash | 5,048,969 | 1.804 | 0.709 | 8.7% |
| eq | 172,391 | 0.352 | 0.195 | 2.4% |
| read | 410,716 | 0.155 | 0.066 | 0.8% |
| walk | 230,997 | 1.064 | 0.539 | 6.6% |
| construct | 20,607 | 0.289 | 0.207 | 2.5% |
| evaluate | 10,764 | 0.016 | 0.011 | 0.1% |
| order | 52,126 | 0.275 | 0.210 | 2.6% |
| other | 0 | 0.000 | 0.000 | 0.0% |

- **Hashing** is most of the count. 1.79 million of fuzz's 5.05 million and 86 thousand of dev's 249
  thousand come through `P.__hash__`, the formula atom hashing its expression. Those would disappear
  with integer ids.
- **Construction** does happen at query time, against what the issue asks for, but it is small: 1.2% of
  dev and 2.5% of fuzz. Counted at any depth, `__new__` calls inside the boundary are, on fuzz,
  `Basic.__new__` 9,457, `AppliedPredicate.__new__` 2,908, `AssocOp.__new__` 1,829; on dev 431, 214, 26.
- **Walks** (`free_symbols`, `is_number`, `Basic.has`, `atoms`) are the largest non-hash item: 5.2% and
  6.6%. Each is a pure function of the expression, so it can be resolved before the boundary.
- **Callbacks into registered user code** (`Extensions.facts_for`, `node_facts`): 24 and 0 on dev, 0
  and 0 on fuzz. This corrects the earlier counter: `Session._custom` also takes relation atoms (1,507
  and 36,397) and is not a callback count. These workloads barely exercise custom predicates, so they
  say little about that hard part of the issue.

### Is the calibrated SymPy time too high?

Yes, probably. Monitoring costs more on real code than on the no-op used for calibration: the model
explains 0.375 s of the real 0.633 s slowdown on dev, and 7.32 s of 11.75 s on fuzz (ratios 1.69 and
1.60). Four estimates of SymPy time inside the boundary, as a share of the base pass:

| estimate | dev | fuzz |
|---|---:|---:|
| Sampler, corrected for safepoint bias (thin calls undercounted) | 3.7% | 5.3% |
| Monitoring with the charge scaled by the ratio above | 5.7% | 9.3% |
| Sampler, raw (thin calls overcounted) | 8.6% | 12.4% |
| Monitoring, calibrated on the no-op (the "S1 high" row) | 16.5% | 23.7% |

The "S1 high" row is therefore conservative, and it is the one used for the 2x test. Using the scaled
or raw figures, S1 is about 14% to 17% on dev and 12% to 15% on fuzz, or 3.9x to 4.6x at 10x. These four
disagree by a factor of about 4.5, so this report gives S1 as a range and not as one number.

The thin-call floor: a hot `hash(e)` costs 36 ns net of `hash(int)`, so hashing is at least 0.009 s on
dev and 0.183 s on fuzz, against 0.036 s and 0.709 s calibrated. An extra Python layer on the hash
methods, with no monitoring, costs 33 ns per call on dev and 11 ns on fuzz; the fuzz difference (59 ms)
is smaller than the base run's range, so that one is weak.

## Items the issue names

Outside the boundary, exclusive times, boundary time excluded:

**dev**

| outside the boundary | calls | None s | definite s | share of pass |
|---|---:|---:|---:|---:|
| conversion | 2,004 | 0.0061 | 0.0035 | 1.63% |
| relevance | 989 | 0.0042 | 0.0051 | 1.56% |
| consistency | 106 | 0.0001 | 0.0002 | 0.06% |
| precheck | 1,221 | 0.0029 | 0.0032 | 1.03% |
| rest (ask, memo lookups, replay loop) | | | | 4.59% |
| total outside | | | | 8.86% |

**fuzz 424242**

| outside the boundary | calls | None s | definite s | share of pass |
|---|---:|---:|---:|---:|
| conversion | 6,068 | 0.0521 | 0.0143 | 0.81% |
| relevance | 2,938 | 0.0471 | 0.0139 | 0.75% |
| consistency | 315 | 0.0007 | 0.0003 | 0.01% |
| precheck | 2,998 | 0.0225 | 0.0055 | 0.34% |
| rest (ask, memo lookups, replay loop) | | | | 1.05% |
| total outside | | | | 2.97% |

"Rest" is `ask`'s own code, the memo lookups, the replay loop and any lazy imports on first use.

Behind the boundary, outermost timers on the groups:

**dev**

| group behind the boundary | calls (outermost) | None s | definite s | share of pass |
|---|---:|---:|---:|---:|
| templates | 4,964 | 0.002 | 0.001 | 0.5% |
| lra_read | 4,340 | 0.002 | 0.001 | 0.5% |
| euf_read | 3,595 | 0.005 | 0.004 | 1.6% |
| relation_read | 10,113 | 0.009 | 0.008 | 2.9% |
| struct | 3,515 | 0.089 | 0.038 | 21.0% |
| total | | 0.106 | 0.053 | 26.4% |

**fuzz 424242**

| group behind the boundary | calls (outermost) | None s | definite s | share of pass |
|---|---:|---:|---:|---:|
| templates | 33,074 | 0.017 | 0.003 | 0.2% |
| lra_read | 105,863 | 0.047 | 0.011 | 0.7% |
| euf_read | 93,889 | 0.245 | 0.047 | 3.4% |
| relation_read | 215,896 | 0.318 | 0.071 | 4.5% |
| struct | 19,107 | 0.663 | 0.182 | 9.7% |
| total | | 1.290 | 0.314 | 18.5% |

Query preparation (`Session.prepare_query`) all-in: 16.2% of dev, 26.1% of fuzz. It overlaps the groups
and is session work, so it is not added to S. Linear forms (lra_read) are 0.5% and 0.7%.

`struct` is the largest group, 21.0% of dev and 9.7% of fuzz. Reading the code, its outermost timer
holds the first visit's template instantiation (`_struct` calls `clause_templates`) and `atoms_of`, as
well as the cone and budget walks. So a template read as data would reduce it, or, if it stays in
Python, it is most of the S4 row. By the calibrated (high) estimate, SymPy frames are most of the groups' time on fuzz (1.418 s
of 1.60 s) and under half on dev (0.070 s of 0.159 s). S4 adds only the SymPy frames outside the groups (27% on dev, 28%
on fuzz), so nothing is counted twice.

## Cost of what crosses the boundary

Measured in Python: a flat integer table, built and turned into bytes at each boundary call
(`tools-rust/encode.py`).

**dev**

| encode what | s | share of base | per boundary call us | bytes per call | nodes per call |
|---|---:|---:|---:|---:|---:|
| q | 0.0053 | 0.92% | 4.8 | 132 | 3.1 |
| intern | 0.0029 | 0.51% | 2.6 | 57 | 0.2 |
| cl | 0.0067 | 1.16% | 6.0 | 121 | 4.0 |

**fuzz 424242**

| encode what | s | share of base | per boundary call us | bytes per call | nodes per call |
|---|---:|---:|---:|---:|---:|
| q | 0.0320 | 0.39% | 9.7 | 267 | 6.4 |
| intern | 0.0155 | 0.19% | 4.7 | 118 | 0.8 |
| cl | 0.0665 | 0.82% | 20.2 | 538 | 15.7 |

- `q`: the query's own formulas, with a fresh table. `intern`: the same with one process-wide table.
  `cl`: every node and atom the call's sessions actually touched.
- `cl` is a lower bound for full resolution: it holds what lazy search reached, and it has no patterns
  or linear forms. An eager enumeration of the cone would be larger. As a sensitivity, ten times `cl`
  would take S2 to about 19% on dev and 11% on fuzz, still above 3x at 10x.
- S2 and S3 charge the encoding but not the time to enumerate the cone in Python, which is not
  measured.
- The crossing itself is not measured, since there is no Rust. With about one call per query it is
  negligible beside these costs. The cost per SymPy ask from inside is what matters, shown as the
  50 ns and 200 ns rows.

## Definitions

Share = time / pass, speedup = 1 / (S + (1 - S) / k), ceiling = 1 / S, k for 2x = (1 - S) / (0.5 - S).

- **S0**: pass minus boundary timers (mode `bdry`).
- **S1 high**: S0 + calibrated SymPy frames inside (`mon`) + encoding the query (`enc q`).
- **S1 low**: the same with the corrected sampler share (`samp`). The raw sampler is also tabled.
- **S2**: S0 + `enc cl`, with every ask inside free.
- **S3**: S2 + calibrated asks other than hash and eq, run once per query in Python. The non-hash share
  is whole-pass, applied to each class.
- **S4**: S0 + fn groups + SymPy frames outside them + `enc q`. The groups stay in Python and are
  called from Rust; the crossing charge for that is not included.

## Method

Pinned on pareto1 (`machine run --quiet`, `bench-container`, `BENCH_CPU=2`, image `sa-eval-bench:1`),
Python 3.12. Cold process per run, one pass per process, `PYTHONHASHSEED=0`, `gc.freeze()` before the
pass as in REPORT-lzr.md. Seven rounds, round 0 a warmup, medians over rounds 1 to 6. Modes rotate one
place each round. Run `tools-rust/run.sh`, then a second batch `run2.sh` (`base` and `out` alternating,
then `moncall`). Counts come from deterministic single runs. Raw output is in `tools-rust/results/`,
and `tools-rust/analyze.py results/pinned.jsonl results/pinned2.jsonl` rebuilds `results/tables.md`.

**Answers.** All 134 runs, in every mode, gave 9bafaa5's digests: dev `31cd0945c07f02a6`, fuzz
`173502b6ef285ad6`.

**Overhead**, each mode against `base` in the same round:

**dev**

| mode | median s | vs base, paired | range s |
|---|---:|---:|---|
| base | 0.578 | +0.0% | 0.576-0.587 |
| bdry | 0.583 | +1.2% | 0.578-0.588 |
| fn | 0.603 | +4.2% | 0.600-0.605 |
| enc | 0.606 | +5.0% | 0.604-0.612 |
| dbl | 0.588 | +1.6% | 0.582-0.591 |
| samp | 0.613 | +6.2% | 0.612-0.618 |
| mon | 1.210 | +109.7% | 1.204-1.238 |

**fuzz 424242**

| mode | median s | vs base, paired | range s |
|---|---:|---:|---|
| base | 8.133 | +0.0% | 8.045-8.324 |
| bdry | 8.126 | -0.2% | 8.055-8.168 |
| fn | 8.665 | +6.6% | 8.572-8.696 |
| enc | 8.302 | +1.8% | 8.196-8.378 |
| dbl | 8.206 | +0.7% | 8.166-8.380 |
| samp | 8.551 | +5.4% | 8.428-8.615 |
| mon | 19.883 | +144.6% | 19.689-20.020 |

`out` was +2.9% on dev and +1.3% on fuzz in the second batch. Shares use the mode's own pass for the
timer modes. Times that the mode itself adds (encoding, calibrated SymPy time) are shares of `base`.

`base` here was 0.578 s on dev and 8.133 s on fuzz, against 0.525 s and 7.992 s in REPORT-lzr.md on the
same machine. The cause was not investigated. This report uses shares from runs alternating in one
invocation, so compare only within it.

**What this does not cover:**

- Collector time is not separated. A pass is charged to whichever side triggered it.
- One fresh process per query was not timed; both memos are in-stream here and warm up during the pass.
  `import` is outside the pass.
- `refine` was not measured.
- Direct C-level reads of SymPy objects (`type(e)`, `isinstance`, `_args`) are not in the SymPy frames.
  They are in 1 - S, and in a port they become C-API reads or id lookups. S4 is the bound that holds
  them in Python.
- Only these two workloads, no held-out data.

## Step 4: the conversion memo

Not triggered: the estimates sit well above 2x, and the rows that come near it (the assumed crossing
charge, S4) are not about conversion. For scale: `_formula` already memoizes conversion in-stream, and
removing all remaining conversion time would move S1 high by 1.6 points on dev (3.06x to about 3.2x at
10x) and 0.8 on fuzz (2.93x to about 3.0x). The fresh-process case was not bounded.

## Tables by answer

**dev, whole pass**

| row | S | ceiling 1/S | at 10x | at 50x | k for 2x |
|---|---:|---:|---:|---:|---:|
| S0 outside the boundary only | 7.8% | 12.9x | 5.88x | 10.39x | 2.2 |
| S1 as it stands, low (sampler corrected) | 12.4% | 8.1x | 4.72x | 7.06x | 2.3 |
| S1 as it stands, sampler raw | 17.3% | 5.8x | 3.91x | 5.28x | 2.5 |
| S1 as it stands, high (calibrated) | 25.2% | 4.0x | 3.06x | 3.75x | 3.0 |
| S1 high + 50 ns per ask | 27.6% | 3.6x | 2.87x | 3.44x | 3.2 |
| S1 high + 200 ns per ask | 35.0% | 2.9x | 2.41x | 2.76x | 4.3 |
| S2 resolved, all asks free | 8.9% | 11.2x | 5.54x | 9.29x | 2.2 |
| S3 resolved, non-hash asks stay | 18.6% | 5.4x | 3.74x | 4.95x | 2.6 |
| S4 fn groups stay in Python | 39.6% | 2.5x | 2.19x | 2.45x | 5.8 |

**dev, None answers**

| row | S | ceiling 1/S | at 10x | at 50x | k for 2x |
|---|---:|---:|---:|---:|---:|
| S0 outside the boundary only | 8.3% | 12.1x | 5.73x | 9.89x | 2.2 |
| S1 as it stands, low (sampler corrected) | 12.1% | 8.3x | 4.78x | 7.21x | 2.3 |
| S1 as it stands, sampler raw | 16.5% | 6.1x | 4.02x | 5.50x | 2.5 |
| S1 as it stands, high (calibrated) | 23.8% | 4.2x | 3.18x | 3.95x | 2.9 |
| S1 high + 50 ns per ask | 25.9% | 3.9x | 3.00x | 3.65x | 3.1 |
| S1 high + 200 ns per ask | 32.1% | 3.1x | 2.57x | 2.99x | 3.8 |
| S2 resolved, all asks free | 9.3% | 10.7x | 5.44x | 8.98x | 2.2 |
| S3 resolved, non-hash asks stay | 18.0% | 5.6x | 3.82x | 5.10x | 2.6 |
| S4 fn groups stay in Python | 41.9% | 2.4x | 2.10x | 2.32x | 7.2 |

**dev, definite answers**

| row | S | ceiling 1/S | at 10x | at 50x | k for 2x |
|---|---:|---:|---:|---:|---:|
| S0 outside the boundary only | 6.7% | 15.0x | 6.25x | 11.71x | 2.2 |
| S1 as it stands, low (sampler corrected) | 12.6% | 8.0x | 4.70x | 6.99x | 2.3 |
| S1 as it stands, sampler raw | 18.1% | 5.5x | 3.80x | 5.05x | 2.6 |
| S1 as it stands, high (calibrated) | 27.2% | 3.7x | 2.90x | 3.49x | 3.2 |
| S1 high + 50 ns per ask | 30.3% | 3.3x | 2.68x | 3.16x | 3.5 |
| S1 high + 200 ns per ask | 39.5% | 2.5x | 2.20x | 2.46x | 5.7 |
| S2 resolved, all asks free | 8.0% | 12.5x | 5.81x | 10.14x | 2.2 |
| S3 resolved, non-hash asks stay | 19.3% | 5.2x | 3.65x | 4.77x | 2.6 |
| S4 fn groups stay in Python | 35.8% | 2.8x | 2.37x | 2.70x | 4.5 |

**fuzz 424242, whole pass**

| row | S | ceiling 1/S | at 10x | at 50x | k for 2x |
|---|---:|---:|---:|---:|---:|
| S0 outside the boundary only | 2.6% | 37.9x | 8.08x | 21.80x | 2.1 |
| S1 as it stands, low (sampler corrected) | 8.3% | 12.0x | 5.72x | 9.86x | 2.2 |
| S1 as it stands, sampler raw | 15.4% | 6.5x | 4.19x | 5.84x | 2.4 |
| S1 as it stands, high (calibrated) | 26.8% | 3.7x | 2.93x | 3.54x | 3.2 |
| S1 high + 50 ns per ask | 30.4% | 3.3x | 2.67x | 3.14x | 3.6 |
| S1 high + 200 ns per ask | 41.4% | 2.4x | 2.12x | 2.35x | 6.8 |
| S2 resolved, all asks free | 3.5% | 28.9x | 7.63x | 18.55x | 2.1 |
| S3 resolved, non-hash asks stay | 16.1% | 6.2x | 4.08x | 5.62x | 2.5 |
| S4 fn groups stay in Python | 28.1% | 3.6x | 2.83x | 3.38x | 3.3 |

**fuzz 424242, None answers**

| row | S | ceiling 1/S | at 10x | at 50x | k for 2x |
|---|---:|---:|---:|---:|---:|
| S0 outside the boundary only | 2.2% | 45.1x | 8.34x | 23.96x | 2.0 |
| S1 as it stands, low (sampler corrected) | 7.7% | 13.1x | 5.92x | 10.53x | 2.2 |
| S1 as it stands, sampler raw | 14.6% | 6.9x | 4.33x | 6.14x | 2.4 |
| S1 as it stands, high (calibrated) | 25.4% | 3.9x | 3.04x | 3.72x | 3.0 |
| S1 high + 50 ns per ask | 28.9% | 3.5x | 2.77x | 3.29x | 3.4 |
| S1 high + 200 ns per ask | 39.6% | 2.5x | 2.19x | 2.45x | 5.8 |
| S2 resolved, all asks free | 3.0% | 33.1x | 7.86x | 20.16x | 2.1 |
| S3 resolved, non-hash asks stay | 15.2% | 6.6x | 4.23x | 5.92x | 2.4 |
| S4 fn groups stay in Python | 26.8% | 3.7x | 2.93x | 3.54x | 3.2 |

**fuzz 424242, definite answers**

| row | S | ceiling 1/S | at 10x | at 50x | k for 2x |
|---|---:|---:|---:|---:|---:|
| S0 outside the boundary only | 4.7% | 21.4x | 7.04x | 15.19x | 2.1 |
| S1 as it stands, low (sampler corrected) | 11.5% | 8.7x | 4.91x | 7.52x | 2.3 |
| S1 as it stands, sampler raw | 19.6% | 5.1x | 3.62x | 4.71x | 2.6 |
| S1 as it stands, high (calibrated) | 33.7% | 3.0x | 2.48x | 2.86x | 4.1 |
| S1 high + 50 ns per ask | 37.9% | 2.6x | 2.27x | 2.55x | 5.1 |
| S1 high + 200 ns per ask | 50.6% | 2.0x | 1.80x | 1.94x | inf |
| S2 resolved, all asks free | 5.6% | 18.0x | 6.66x | 13.42x | 2.1 |
| S3 resolved, non-hash asks stay | 20.7% | 4.8x | 3.49x | 4.48x | 2.7 |
| S4 fn groups stay in Python | 34.7% | 2.9x | 2.43x | 2.78x | 4.3 |

## Corrections to the issue and to earlier notes

- "Query preparation" is behind the boundary, not SymPy-facing work that must stay.
- The issue's "about 2-4x" on `ask` holds at 10x to 50x on S1 high (2.9x to 3.8x), given its assumptions.
- `session_custom_calls` was not a callback count. It is now `session_custom_atoms`, with
  `ext_facts_for` and `ext_node_facts` counted separately.
- The `n_nested` output was polluted by the calibration loop in the first version of `rc.py`; it now
  copies the counts before calibrating.
