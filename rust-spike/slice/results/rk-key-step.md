# rk_key step (issue 323): (a) lands, (b) read-once caches tried and dropped (sa-port-296/297/298)

Status: landing tree port/rk-key 0bd82e4 (= rust-slice 63d5632 + ded9d0b + test_rk_key_targets.py); its bar is running on
pareto0 (sa-port-298/bar). Landing, probe and knowledge_live rows are added when it ends.

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

## Thread check (d), report only (r2 numbers; r3 above agrees)
ThreadCheckerImpl::ensure inclusive, fuzz s/run: 146 0.046-0.049, 63d5632 0.109-0.110, head 0.100-0.108; thread::current self
~0.05. Owners (prof297.py `tc`): RDict::get_item 0.009, add_clause 0.004, term_in 0.004, Ses::d_get 0.004, compile_loop::flush 0.004,
RDict::set_item 0.004, MembersView/RepView __getitem__ ~0.003 each. Proposed fix: (1) borrow once per entry, passing PyRef/&T down
(term_in's two table.try_borrow, rk_key's l.table.try_borrow, solver_of, flush): ~0.02 s, no unsafe. It is the next small step
after this one and lands only on a gain beyond spread (planner 298 (3)). (2) A GIL-token cell in place of `unsendable`: declined by
the planner (adds unsafe for ~1% of fuzz); it stays here as an option Tilo can ask for.

## Plants and counters used
Plants 621, 668, 669 and counters 703-705 were used by (b) and removed with it, so the ranges are free again in the landed code.
