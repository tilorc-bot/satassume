# rk_key step (issue 323): (a) lands, (b) read-once caches tried and dropped (sa-port-296/297/298)

Status: LANDED on rust-slice by sa-port-299 (12 Nov): the commit carrying this line, on 63d5632; source 0bd82e4 (= rust-slice
63d5632 + ded9d0b + test_rk_key_targets.py). Its bar (below) equals the base on every item except one test file.
KNOWN ROW (planner forward-chain-3b, 12 Nov, on report 61ce097: "yes, land 0bd82e4 as is"):
test_lazy_reads.py::test_stock_term_plant_is_caught[finite-stock_finite] fails 3 of 40 runs on the landing tree and 3 of 40 on
base 1d22f9a, on the same 10 of 60 SymPy assumptions-shuffle seeds (11 15 18 21 25 34 37 50 55 58) on both. It follows SymPy's
random order of assumption checks, not this step. Not fixed here; the test-only fix is owed (new OWED item for the architect).
Probe on the landed source: 21 of 32, every cell equal to base.

## Outcome
- (a) fidelity, LANDS (bar permitting): ded9d0b, GuardMethod/EntMethod `__module__` = the Python method's module, `__reduce__`
  pickles by reference (session_glue.rs, session_live.py). Kept tests: test_guard_method.py `_lookups` (:43), test_entry_frame.py.
- isinstance targets, LANDS: relkeys.rs is_basic (:42) and is_joinable (:55) test Basic, Number, BooleanAtom, Tuple; all have
  metaclass `type` (no ABC, no own `__instancecheck__`, and the metaclass can't be reassigned). Kept test test_rk_key_targets.py
  (0bd82e4): the metaclass rows, relkeys.rs names exactly these four (two is_instance calls), and a key whose `__class__` answers
  per instance (own `__getattribute__`) is kept per instance, as a Python set does. With no cache, the `__class__` fallback is
  PyObject_IsInstance's own, so the tp_getattro guard (86845aa, relkeys.rs:279 there) is no longer needed and went with (b).
- (b) speed only, DROPPED (planner 298 gate (2)): reverted by 2b600f0 (1b41dce, 1e7a4db, 86845aa). Its plants 621 rk-top-once,
  668 rk-type-once, 669 rk-getattr-cached, counters 703-705 and test_rk_key.py go with it. Net size of (b): +271/-17 lines of
  Rust/Python (net +254: relkeys.rs +216/-7, relations_core.rs +29/-5, session.rs +22/-3, session_live.py and term_live.py
  +2/-1 each) plus +257 lines of tests. The tried code stays reachable at 86845aa (port/rk-key history).
- Target "most of rk_key's 0.127 s fuzz self time": NOT MET. r3 cut rk_key's inclusive time by 0.056 s/run (0.303 -> 0.247)
  and relkeys' Group D by 0.041 s (0.119 -> 0.078), about a third of 0.127 s; fuzz wall fell 0.058 s (median), within spread.

## S1 r3 (pareto0, one quiet lease 32733198, 01:22-01:28Z 12 Nov; bench-container CPU 2; 7 interleaved rounds; load ~1)
Arms: 146 tree 1401d1f, 63d5632's slice source 1d22f9a, head 86845aa ((a)+(b)). All from the same machine and lease; the bar
ran afterwards as a separate --shared run. Digests: 42 rows, 0 mismatches (dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6).

| workload | 146 1401d1f | 63d5632 src 1d22f9a | head 86845aa | head vs 63d5632 | head vs 146 |
|---|---|---|---|---|---|
| dev, Rust median s (min-max) | 0.751 (0.745-0.756) | 0.760 (0.751-0.766) | 0.757 (0.750-0.762) | -0.4% (paired median -0.001, 4/7 faster) | +0.8% |
| fuzz, Rust median s (min-max) | 6.679 (6.614-6.728) | 6.391 (6.346-6.450) | 6.333 (6.299-6.372) | -0.9% (paired median -0.042, 7/7 faster, min -0.026) | -5.2% |

Why it's within spread: the median gain (0.058 s) is smaller than either arm's own min-max range (0.104 s, 0.073 s; the ranges
overlap at 6.346-6.372), and the median paired gain, 0.042 s, equals r2's 6.401 -> 6.359 (0.7%) that the gate names as within
spread. Head was faster in all 7 paired rounds (a sign test would give p of about 0.008), so the gain is likely real but small.
The gate's measure is the spread, so (b) is dropped. Tilo or the planner can overrule; the code is at 86845aa.

Per-function inclusive / self s per run (pysample, fn297.py; 146 has no relkeys):
| function | dev 1d22f9a | dev 86845aa | fuzz 1401d1f | fuzz 1d22f9a | fuzz 86845aa |
|---|---|---|---|---|---|
| rk_key | 0.012 / 0.000 | 0.010 / 0.000 | - | 0.303 / 0.009 | 0.247 / 0.024 |
| term_of | 0.003 / 0.000 | 0.004 / 0.000 | 0.074 / 0.004 | 0.132 / 0.004 | 0.071 / 0.002 |
| rd_get (caller) | 0.007 | 0.006 | - | 0.187 / 0.005 | 0.146 / 0.012 |
| rd_set (caller) | 0.004 | 0.004 | - | 0.122 / 0.005 | 0.092 / 0.004 |
| rs_contains (caller) | 0.001 | 0.001 | - | 0.040 / 0.001 | 0.031 / 0.001 |
| RDict::get_item | 0.008 | 0.006 | - | 0.200 / 0.003 | 0.159 / 0.003 |
| relkeys module | 0.018 | 0.013 | - | 0.415 | 0.362 |
| ThreadCheckerImpl::ensure | 0.006 / 0.003 | 0.005 / 0.002 | 0.049 / 0.023 | 0.110 / 0.058 | 0.100 / 0.049 |
| thread::current | 0.003 / 0.002 | 0.003 / 0.002 | 0.029 / 0.026 | 0.055 / 0.049 | 0.054 / 0.047 |

Group D s (all-D share x median): dev 0.160 / 0.215 / 0.191, fuzz 1.941 / 2.210 / 2.198 (146 / 1d22f9a / 86845aa); relkeys D
fuzz 0.119 -> 0.078. Source: ~/sa-rust-ids-work/sa-port-297/gd/med-r3.md, timing-r3/time.jsonl, prof-*-SHA.json.
r1 void (own --shared bar inside the quiet lease); r2 (1e7a4db, with the tuple regression) in gd/aborted-r2-1e7a4db/med-r2.md.

## (b) as tried: writers and refresh (kept for the record)
- term_live stack: one list per thread from `stack()` (term_live.py:150), never replaced; push/pop by `_ask` (term_live.py:1094/1099,
  :1117/:1124 for _Refused) and by hand-opened queries (relations_direct.py:117/141). Nested queries are the mid-query writes.
  `_Query.kept`/`.table` are written only in `__init__` (term_live.py:89/91/93, :107). The isinstance input is type(x): any MRO
  write bumps tp_version_tag; `__class__` per instance was guarded by tp_getattro (86845aa).
- Refresh: keyed by the stack top's identity through a weakref, re-read when the top changes; type results per (type, tag),
  cleared with the top.
- Plants: 621 path plant, caught by test_rk_key.py path rows; 668 wrong value, caught by test_rk_key.py joins (3 members vs 2);
  669 caught by test_rk_key_targets.py's per-instance row (8 reads). All three MATCH on every workload in the 6b8a5c2 bar
  (kept-test catches: no workload has a fake-`__class__` key type, and 621/668 never change an answer there).
- Fuzz counters (orion, 86845aa): rk:type_read 27,256, rk:top_read 2,860, rk:term 217,752, rk:dict:hit 584,041.

## Bar on 6b8a5c2 (code 86845aa, (a)+(b); pareto0 --shared, 01:28-05:01Z): read, superseded for landing
Tests 71 files all exit 0, relations_direct.py exit 0. Suite 126 failed / 5992 passed (ids 6159): new 0, gone 0, changed 1, the
planted-history test failed -> passed (known id()-reuse failure, a28c548, flips both ways). Quiet failures: suite 39 rows in 2 tests,
multiset equal to base; live/extra handler files 0 rows. Live dev/fuzz and 15 extra workloads: all MATCH (answers_sha dev
31cd0945c07f02a6, fuzz 173502b6ef285ad6). Kept reasons equal to base on every workload. fm rows 20 workloads, 0 differ; fm plants
caught (4 and 3 differ). Since (b) is dropped, the landing code differs, so the bar is rerun on 0bd82e4 (architect note on (1)).

## Bar on bfe7a87 (source 0bd82e4, .so f7e18b93 built on pareto1; pareto0 --shared, 05:10-08:27Z 12 Nov, END 0; base sa-port-294/bar)
1. Tests: 70 files, 69 exit 0. NOT exit 0: test_lazy_reads.py (1 failed, 73 passed, 5 skipped), the next section.
   relations_direct.py exit 0. This step's kept tests: test_rk_key_targets.py 3 passed, test_guard_method.py 3, test_entry_frame.py 4.
2. Suite: 127 failed / 5991 passed (ids 6159); against base new 0, gone 0, changed outcome 0 (the planted-history test fails in
   both runs). TermFault 0.
3. Live: dev and fuzz, Python vs Python, Python vs Rust, traced vs untraced: all 8 MATCH (dev answers_sha 31cd0945c07f02a6, fuzz
   173502b6ef285ad6; Rust makes 0 Python solvers). Extra workloads (15): 30 of 30 comparisons MATCH (the same 30 as 294's bar).
4. Quiet failures: suite 39 rows in 2 tests, multiset equal to base (34 + 4 + 1, ids differing 0); live and extra handler files
   0 rows each; probe 0 rows.
5. Kept reasons: every live/extra share equal to base (dev kept:out-of-scope 24/1985; cls kept:args-eq-not-is 6/72; refused
   f6 13, opaque 7, value 15, wiring 1).
- fm rows: 20 workloads, 0 differ; fm-args-drop-last caught (4 differ), fm-atoms-merge-pred caught (3 differ).
- Plant table: 425 rows (25 plants x 17 workloads); plant, workload, fired count and verdict equal 294's bar on every row
  (102 DIFFER, 323 MATCH). No rk plants: they went with (b).
- Suite plants: each run new 0, gone 0. Changed outcomes as 294's bar (fm-implies-swap 70, nc-memo-true-false 12, fm-ite-swap 1
  test_xor_and_ite, term:mark-wrong-pattern 1) apart from two things that vary between bars: the planted-history test flipping
  (failed -> passed under dispatch-keeps-memo, sb-join-address and term:mark-skips-native here), and class-is (changed outcome 6,
  fired 1242; bars 288/291/294/297 had 6/7/10/8: caught every time). Fired counts move a little between bars (sb-join-address
  33, as 297's bar; 294's had 65).
- knowledge_live: the bar's 442 live/extra *.knowledge.json files are byte-equal to 294's bar.

## The test_lazy_reads.py failure: SymPy's assumption-check order, same on base (known row by the planner's ruling; not fixed)
test_lazy_reads.py::test_stock_term_plant_is_caught[finite-stock_finite], test_lazy_reads.py:237: with the eager `t.is_finite`
read planted back, the test asserts that some evaluation counter fires; all three read 0 (`assert 0 > 0`). The file passed in
the bars of 288, 291, 294 and 297.
- Repeat, as the bar runs it (one_test.sh, PYTHONHASHSEED=0, 40 processes per tree, pareto0; lz299.sh): landing tree bfe7a87
  3 of 40 fail; base 1d22f9a (rust-slice 63d5632's source, .so 2cc2e09f) 3 of 40; 6b8a5c2 (86845aa, .so 82440e6e) 8 of 40.
  Always this test id and this assertion; no other test in the file fails.
- Cause: SymPy's `_ask` shuffles the facts it checks with a generator that isn't seeded (sympy/core/assumptions.py:596,
  sympy/core/random.py:45 `_assumptions_rng`). Seeding it before the test (seeds 0-59, each run twice, landing and base trees;
  lzseed299.sh): seeds 11 15 18 21 25 34 37 50 55 58 fail both times on both trees, the other 50 pass both times. So the
  outcome is a function of SymPy's order alone and doesn't depend on this step's code.
- At about 7% a run, four passing bars in a row are unsurprising (about 3 in 4).
- Not edited (the 299 ruling: fix nothing). A fix would be the test's: pin the order (seed `_assumptions_rng`) or assert over
  several seeds. The eager-finite plant then has a kept test only on the orders that evaluate. Owner: the planner's call.
- Rows: pareto0 ~/sp19/sa-rust-ids-work/sa-port-299/lz/sum.txt and lzseed/sum.txt.

## Module-wide probe on the candidate (pc299.sh = pc294.sh on clone sa-port-298 bfe7a87, .so f7e18b93; pareto0, 08:34Z)
- 40 jobs exit 0. 180 cells (20 workloads x 9 files, all and converted calls) against sa-port-294/pc: 0 differ; per function
  and state, 0 keys differ (pccmp299.py). session_live.py's `__module__` argument adds no per-query call.
- knowledge_live.py per workload, all (converted), unchanged: lra 4326 (34), f6 328 (22), wiring 125 (80), scope 42 (12),
  dev 160 (50), fuzz 46 (16), ground 40 (10), port 48 (18), loop 70 (22), zero 63 (18), cert 38 (8), budget 930 (900),
  core 88 (16), opaque 140 (6), rootof 32 (2), value 952 (794), twin 38 (8), transfer760 65 (20), transfer2340 73 (28),
  cls 42 (12).
- Count: **21 of 32, unchanged.** session_live.py still makes 623,262 converted-query calls on the 20 workloads; over the 20,
  engine.py 132,056 and formula.py 142,816 converted calls, as base.
- The probe ran on the candidate source (bfe7a87) before the landing; the landed SHA adds results/HANDOFF files only.

## Thread check (d), report only (r2 numbers; r3 above agrees)
ThreadCheckerImpl::ensure inclusive, fuzz s/run: 146 0.046-0.049, 63d5632 0.109-0.110, head 0.100-0.108; thread::current self
~0.05. Owners (prof297.py `tc`): RDict::get_item 0.009, add_clause 0.004, term_in 0.004, Ses::d_get 0.004, compile_loop::flush 0.004,
RDict::set_item 0.004, MembersView/RepView __getitem__ ~0.003 each. Proposed fix: (1) borrow once per entry, passing PyRef/&T down
(term_in's two table.try_borrow, rk_key's l.table.try_borrow, solver_of, flush): ~0.02 s, no unsafe. It is the next small step
after this one and lands only on a gain beyond spread (planner 298 (3)). (2) A GIL-token cell in place of `unsendable`: declined by
the planner (adds unsafe for ~1% of fuzz); it stays here as an option Tilo can ask for.

## Plants and counters used
Plants 621, 668, 669 and counters 703-705 were used by (b) and removed with it, so the ranges are free again in the landed code.
