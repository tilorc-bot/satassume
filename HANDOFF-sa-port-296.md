# HANDOFF sa-port-296 (rk_key step, issue 323), between items (b) and (c)

Branch port/rk-key, head = the commit adding this file (Rust source as at 1b41dce). Worktree ~/sa-rust-ids-work/sa-port-296/wt
(from ~/dev/sa-port-7). Base origin/rust-slice 63d5632. Env: `. ~/sa-rust-ids-work/sa-port-296/env296.sh` (sets PYTHONPATH to the wt).

## DONE
(a) ded9d0b: GuardMethod/EntMethod `__module__` = the Python method's module (getter named `__module__`, which PyType_FromSpec
doesn't overwrite; the class repr is unchanged; `GuardMethod.__module__` on the class reads a member descriptor) and
`__reduce__` returns `__qualname__` (pickle by reference -> the class's attribute, the same object). Kept test:
test_guard_method.py `_lookups` (+ `__module__` in the look rows) and test_entry_frame.py (class_looks over all 4 attrs + lookups,
bare_module control). Control: dropping the module argument in session_live fails both look-alike tests. Relations._eq_links skipped for
pickle (its Python method is a `<locals>` function, which Python can't pickle either).
(b) 1b41dce: rk_key reads the innermost query and the isinstance result once per query.
- Writers: term_live stack = one list per thread made by `stack()` (term_live.py:150), never replaced; push/pop by `_ask`
  term_live.py:1094/1099 and :1117/:1124 (_Refused), plus hand-opened queries in tests/tools (relations_direct.py:117/141).
  Queries nest -> a push/pop inside an outer query are the mid-query writes. `_Query.kept`/`.table` written only in `__init__`
  (term_live.py:89/91/93, :107). isinstance input = type(x): targets' metaclass is `type` (checked), no `__class__` override
  (checked via _PyType_Lookup), any MRO write changes tp_version_tag.
- Refresh: keyed by the stack top's identity via a weakref (`_Query.__weakref__` added); re-read when the top is another object/none;
  type results kept per (type held, tag), cleared when the top changes. term_of unchanged for other callers; rk_key uses term_of_in.
- Counters 703 rk:top_read, 704 rk:type_read, 705 link:in_query. Dev on orion: rk:top_read 198 (= relations sessions),
  rk:type_read 1574, link:calls 13950 = cross_current 4979 + in_query; answers_sha 31cd0945c07f02a6 = base bar's dev (rust and py).
- Plants: 621 rk-top-once (caught by test_rk_key.py path rows: converted/nested/after-pop lose term keys and outlive);
  668 rk-type-once (caught by test_rk_key.py joins: x, Integer(2), 2 -> 3 members vs Python's 2). Both wired in session_live _SB_PLANTS.
- Note: a stale top value can only change the path (term id vs hash), never an answer: the dict path is exact, and term_of_in resolves
  in the given table with the serial check. 621 is a path plant by the gate's request (gate (b)); 668 is the wrong-value one.
- Tests passing on orion: test_rk_key, test_rs_core, test_rl_core, test_rd_core, test_relations_core (crossing identity updated),
  test_term_ids, test_entry_frame, test_guard_method, test_ses_keys, test_session_boundary (344+ passed). A one-process
  `pytest test_*.py` exited 3 "no tests ran" (collection; use the bar's TESTS_SPLIT=1).

## NEXT: (c) S1, (d), bar, land, probe
- S1 harness to copy: ~/sa-rust-ids-work/sa-port-295/gd (go295.sh / go295b.sh, tools/stage285.sh, tools/job195.sh builds the .so in
  sa-cy-build:1 + pysample runs, tools280/onlease285.sh + time285.sh pinned rounds, med285.py, tools/prof292.py per function).
  Its paths say sa-port-295 and pareto1: change to sa-port-296 and pareto0 (stage285 stages onto pareto1 by ssh; point it at pareto0;
  job195 needs docker+cargo images on the host: check pareto0 has sa-cy-build:1, else build on pareto1 --shared and copy).
  Three arms on pareto0 in ONE quiet lease, interleaved, >=5 rounds: 63d5632 (Rust = 1d22f9a's), this head, 146 = 1401d1f.
  Per-function inclusive (prof292) for rk_key, innermost, basic_key, term_of_in, rd_get/rd_set/rs_contains on all three arms, same lease.
- pareto1: SHARED by train-test-1, and a stale quiet request "sa-port-295: S1 pinned timing" is still queued there (from go295.sh;
  295 is done): tell the architect.
- (d) report only: ThreadCheckerImpl::ensure + thread::current 0.048 -> 0.110 s fuzz (group-d-gap.md line 85): every borrow of an
  `unsendable` pyclass (SessionCore relkeys RefCell borrows go via the pyclass borrow; PyTermTable `try_borrow`, factcache, adapters).
  Proposed fix to write up: mark the hot pyclasses (TermTable, the RDict/RSet holders) `frozen` + interior RefCell, or not
  `unsendable` with a Send-safe interior, so pyo3 skips the per-borrow thread check; or borrow once per entry call.
- Bar: copy ~/sp19/bar294.sh (pareto0) to bar296.sh, PLANTS += rk-top-once rk-type-once, TESTS=all TESTS_SPLIT=1, .so built on
  pareto1 (bar.sh build) or in sa-cy-build:1. Then bar.sh land, PUSH=1, probe pc294.sh -> 21/32 compare (base pareto0
  ~/sp19/sa-rust-ids-work/sa-port-294/pc). knowledge_live per workload from the bar's live/*.knowledge.json vs 294's.
