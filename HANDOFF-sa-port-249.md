# HANDOFF sa-port-249: state part 3. The landing bar on f252daf is READ and clean; NOT LANDED

Branch port/state-part3, pushed, on origin/rust-slice 0192b35 (unchanged at 22:10Z 10 Nov). Handed off at the context
budget after reading the bar. Left: memo cost, Group D in seconds, the Subs twins runs, landing. No source changed here.
Read this, then HANDOFF-sa-port-247.md for the file:line map.

## The bar (pareto1 ~/sp19/sa-rust-ids-work/sa-port-247/bar-part3; 17:47Z-22:09Z 10 Nov; every phase exit 0; seed1 not run)
Copies on orion: ~/sa-rust-ids-work/sa-port-249/bar/ (sum.txt, tests.txt, live-summary.txt, extra-summary.txt,
plants-pivot.txt = the plant table by workload, counts-all.txt = counters per workload and suite against the base bar,
counts.py = the script that made it, run on pareto1 as /tmp/sa249-counts.py REGEX --base).
- Tested f252daf, .so sha256 e9aaf5052540. Base rows: (iii)'s bar, sa-port-236/bar-iii-b3/suite.
- Suite: 126 failed, 5992 passed, 23 skipped, 18 xfailed; 6159 ids; against base new 0, gone 0, changed outcome 0.
  Passed 5992 = 5991 with no handler firing + 1 with a firing (tests/test_invariants.py::
  test_ci_stream_reports_only_what_replays). Handler rows 39 in 2 tests, multiset same as base (34 `_ok`, 4 `_rb_clauses`,
  1 `Already mutably borrowed` in test_transfer.py::test_protocol_on_fuzz). TermFault 0.
- Tests: 53 files, one process each; not exit 0 only test_cf_diff.py (exit 2, 1 error), test_catch_count.py (3 failed),
  test_handler_count.py (2 failed): the known base failures. test_term_live.py 20 passed, 1 skipped.
  test_install_order.py 198 passed (holds test_engine_first_refused, plant 420); test_session_boundary.py 27 passed;
  test_split_order.py 2 passed and test_moved_digest.py 2 passed (plants 450-453: 450, 451, 453 by the verdict, 452 by the
  guard). The logs have no per-test lines (no -v). direct.txt exit 0.
- Workloads: all 16 MATCH Python against Rust (dev, fuzz, twin, scope, loop, zero, cert, budget, core, f6, opaque,
  rootof, value, wiring, transfer:7:60, transfer2:3:40); Python against Python controls MATCH; dev and fuzz traced
  against untraced MATCH. answer_diff, msg_diff, session_count_diff, end_diff, stream_diff, lra_diff, stats_diff,
  moved_diff, moved_known_diff, moved_native_diff all 0 on every one. answers_sha dev 31cd0945c07f02a6, fuzz
  173502b6ef285ad6, scope 12e06b0586faee40. Known differences inside the verdict are only the _SPLIT/_CACHE rows per engine
  point, equal to known_moved.json's (moved_order_differs = engine points: dev 80, fuzz 120, scope 7, twin 1, loop 17,
  zero 35, cert 3, budget 2, core 66, f6 117, opaque 102, rootof 208, value 150, wiring 261, tr7 3, tr2 2).
  moved_lra_python_only: dev 13, twin 11, 0 elsewhere (not read further; MATCH).
- Handler rows on workloads: 0 on every Python and Rust run of all 16 (base bar: 0 on its 7). So the relevance.rs
  AttributeError change adds no firing. The capture is live: plant runs show rows (dev sb-core-stale 4, sb-solver-fresh 42).
- Kept shares equal base where the base has the workload: out-of-scope dev 24/1985, 0 elsewhere; refused 0. No base rows
  for core, f6, opaque, rootof, value, wiring, twin, tr7, tr2 (refused: f6 13, opaque 7, value 15, wiring 1).

### Plants (22; fired then D = DIFFER, m = MATCH; full table plants-pivot.txt)
Caught on workloads: sb-core-stale 16/16; sb-hold-zero 16; sb-sel-zero 16; sb-solver-fresh 16; sb-verdict-none 16;
sc-demand-drop 16; sc-frontier-drop 16; sc-pending_c-drop 15 (twin fired 0); sc-literals-drop 9 (dev, fuzz, budget, cert,
scope, tr2, tr7, value, zero; 0 fired elsewhere); sc-groups-drop 8 (dev, fuzz, cert, scope, tr2, tr7, twin, zero);
sc-deferred-drop 6 (dev, core, f6, loop, opaque, wiring); **sc-pending-drop 5 (budget 145, core 150, f6 252, loop 598,
wiring 571; 0 fired on dev, fuzz and the rest), so the expected "fires 0 on the workloads" was wrong: no footnote needed**;
sb-link-pending-stale 5 (dev, fuzz, scope, twin, zero; fired but MATCH on the other 11); sc-key-shared (446) 3 (dev, fuzz,
scope; fired but MATCH on 13); rk-class-split (409) on twin (13 fired; 0 elsewhere); th-exhausted-skip and th-first-only
on dev, fuzz, tr7, tr2.
Not caught on any workload, each to name in the report:
- sb-core-unset (447): fired on all 16 (dev 103,122, fuzz 1,572,238), MATCH on all: equal answers by construction; caught
  by sb:core_prop and `_table_get` rising in test_session_boundary.py::test_core_read_without_the_property.
- sb-truncated-stale: fired on all 16, MATCH on all 16; caught only by test_session_boundary.py (trunc case). No
  workload has a truncated session whose stale flag changes an answer. Not in the suite-plant runs (it fired on dev).
- sb-neg-shared-stale: fired 0 on 14, tr2 8 and tr7 10 with MATCH; suite: fired 26,194, 24 ids changed (caught).
- sb-fwd-skip-link (437): fired 0 on all 16; suite: fired 87,333, 216 ids changed (caught). **Cause of the zero, found
  here: the bar's workload runs have the digest on, and moved_digest.py:137 replaces Relations._interpret and _link with
  its trackers, so Rust calls them by name (session.rs `named`, sb:fwd_named) and the plant, which sits on the direct
  branch (relations_core.rs:2380), can't fire.** A digest-off run with this plant on dev was not done.
- th-gave-up-skip (428): MATCH on all 16; suite: 6 ids changed (caught); also test_theory_flags.py. The bar prints
  fired 0 for all three th-* plants because theory_flags.rs's own `th_plant` doesn't feed plant_fired: that 0 is
  unmeasured, not a zero (th-exhausted-skip and th-first-only DIFFER with "fired 0"). The read is reached (th:gave_up dev
  523, fuzz 7,996) but no workload has a theory that gave up. Gaps ruling: suite-only, needs a footnote or a workload.
Suite under plants (against this run's plain suite, handler multiset same as base in each): rk-class-split 132 failed
(6 changed, fired 681); sb-fwd-skip-link 330 failed (216, fired 87,333); sb-neg-shared-stale 150 (24, fired 26,194);
sc-pending-drop 185 (59, fired 456); th-exhausted-skip 128 (2); th-first-only 131 (5); th-gave-up-skip 132 (6).
tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence goes passed -> failed in
several plant suites: the known id()-reuse test; it passed in the plain suite, as on base.

### Counters (Rust runs; counts-all.txt has every row and the base's)
| wl | sc:key_hash | sc:key_eq | sc:core | sb:fwd_direct | sb:fwd_named (digest on) | rk:intern:engine |
|---|---|---|---|---|---|---|
| dev | 28,951 | 0 | 66,462 | 2,758 | 1,876 | 4,067 |
| fuzz | 478,541 | 1,193 | 908,133 | 21,427 | 45,802 | 93,286 |
| budget | 46,412 | 0 | 53,922 | 1,961 | 0 | 0 |
| cert | 6,513 | 0 | 12,904 | 243 | 455 | 902 |
| core | 31,346 | 333 | 92,847 | 6,365 | 0 | 0 |
| f6 | 56,852 | 0 | 156,933 | 11,575 | 0 | 0 |
| loop | 14,880 | 16 | 36,879 | 2,284 | 0 | 0 |
| opaque | 13,385 | 0 | 39,380 | 3,007 | 0 | 0 |
| rootof | 32,384 | 0 | 76,703 | 5,520 | 0 | 0 |
| scope | 10,220 | 0 | 22,079 | 502 | 875 | 1,953 |
| transfer2:3:40 | 11,680 | 17 | 21,289 | 1,032 | 957 | 2,080 |
| transfer:7:60 | 14,752 | 2 | 26,844 | 1,069 | 1,114 | 2,476 |
| twin | 140 | 1 | 300 | 12 | 26 | 56 |
| value | 25,145 | 0 | 59,710 | 4,358 | 197 | 1,183 |
| wiring | 283,608 | 67 | 601,128 | 48,945 | 0 | 0 |
| zero | 73,045 | 0 | 145,552 | 4,832 | 8,011 | 18,338 |
| suite (7 xdist files summed) | 10,005,845 | 27,692 | 20,782,325 | 1,657,074 | 0 | 992,243 (base 994,158) |
- sb:attr, sb:core_prop, sc:view, sc:record, sb:scalar_record, th:py_helper, rk:outlive, rk:migrate, xf:record,
  bud:py_fallback: 0 on all 16 and in the suite. sb:scalar_view: 0 on workloads, 23 in the suite.
- **sb:fwd_named is NOT 0 in the bar's workload runs** (earlier links reported 0 from digest-off probes, --check plain,
  seven workloads at fd0fabb). It is the digest's own wrapper, see sb-fwd-skip-link above; in the suite (no digest) it is
  0. Say both in the report. rk:intern:engine and rk:intern:input equal the base on its seven workloads.
- ad:cbm_noid: 0 on 15 workloads, twin 25 (two equal Function classes, as (iii) reported for twin11); suite 293 (base bar
  94; it varies between runs of one source; formula's). ad:lra_not_expr scope 4 = base. gl:plain = base on the seven.
- The digest's own view reads on a Rust run: memo:native_items dev 560, fuzz 840, scope 49 (base 0: no digest there);
  xf:session_view dev 918, fuzz 3,133; xf:rel_view dev 594, fuzz 9,054 (all in counts-all.txt).
- ctx:caught 0 on workloads, 1 in the suite (= base); ctx:fallback suite 37 (= base); rv:consistent_caught suite 45 (= base).
- Not read: scaffold:core:kept_product:mismatch (RULINGS 7; not in session.json's counts, look in *-rust.knowledge.json
  or the .tot files), registry:python / rows:python per workload (RULINGS 11).

## The planner's landing conditions, as read
Verdict clean with exact known differences: yes. Handler multiset equals base, suite and workloads: yes. Plants 409,
439-446, 450-453 caught: yes (409 on twin and in the suite; 439-445 each on 5 to 16 workloads; 446 on dev, fuzz, scope;
450-453 in test_split_order.py and test_moved_digest.py). sc:key_hash / sc:key_eq in the suite: 10,005,845 / 27,692.
STILL OPEN before landing: the Subs twins rows (below), [91] and the budget gate at landing time, memo cost, Group D.

## Running (detached; read the end marker)
Group D samples, sa-port-146's method (pysampler, dev 10 runs, fuzz 3, plus one unsampled time row each for Rust and
Python), started 22:14Z under shared leases on pareto1 for f252daf and for the base 0192b35:
orion ~/sa-rust-ids-work/sa-port-249/gd/run-f252daf.log and run-0192b35.log ("END exit N" is the last line); output
pareto1 ~/sa-rust-ids-work/sa-port-249/gd/run-SHA/DONE-JOB. Tools: orion ~/sa-rust-ids-work/sa-port-249/gd/tools, copied
from sa-port-225's with the paths changed (go195.sh, job195.sh, post195.sh). After DONE-JOB: `bash post195.sh SHA` on
orion (copies the run back, writes SUMMARY.md), then `python3 sum202.py RUN > SUMMARY-rel.md` as sa-port-225 did (check
its usage line; sum202's (a) does not count relkeys.rs or ses_cont.rs: add them by hand, as results/
port-state-relations.md :646 did). These give SHARES. Not checked after launch beyond "running under shared lease".

## Not done
1. Group D in SECONDS: seconds = D share x a timed median of the workload (146 used 034e6bc's medians, dev 0.767 s, fuzz
   6.802 s; REPORT at orion ~/sa-rust-ids-work/sa-port-143/REPORT-sa-port-146.md, Method). The medians must be timed
   pinned on pareto1 with ~/bin/bench-container (read ~/bin/README.md) under a quiet lease, for f252daf and 0192b35, Rust
   mode, dev and fuzz (job195.sh's "time" rows run in a plain --cpus 1 container: not pinned, context only). Compare with
   0.158 s dev / 1.990 s fuzz.
2. Memo cost (OWED [108]: what moving cross-query memos under per-query ids costs, in time): not measured. My plan was
   the same pinned timing, Rust mode against Python, base against f252daf, per workload; check with the architect if the
   planner wants a different comparison.
3. Subs twins (RULINGS 13; the gate's last block): 8 runs (oo:lra, one:lra x ORDER 12, 21 x MODE python, rust) on base
   0192b35 and on f252daf: copy ~/sa-rust-ids-work/sa-port-255/repro.py and py.sh, point them at a tree of each SHA with
   its own built .so (repro.py line 4, py.sh TREE). Expected rows are in the brief. A change from base blocks the landing.
4. Land: `sh rust-spike/slice/p1/bar.sh land f252daf` in the clone (no PUSH; read the incoming diff; rust-slice was still
   0192b35 at 22:10Z), then PUSH=1; [91]; tell the architect at once. Then results/port-state-part3.md (bar section, "Not
   run" rewritten) and the report with every MUST STAY item.
5. Optional, cheap: one digest-off dev run with SLICE_SESSION_PLANT=sb-fwd-skip-link to show plant 437 fires and is
   caught on a workload without the digest's wrapper.

## FILE:LINE MAP (additions; the rest is HANDOFF-sa-port-247.md's)
- rust-spike/slice/moved_digest.py:137: the digest replaces Relations.__init__, _interpret, _link
- rust-spike/slice/solver_rs/src/session.rs:845 `named` (:852 SB_FWD_DIRECT, :856 SB_FWD_NAMED); relations_core.rs:2380
  the sb-fwd-skip-link site; theory_flags.rs `th_plant` (not counted in plant_fired)
- rust-spike/slice/p1/bar.sh :114-133 live, plants and extra commands (live.py WL rust OUT --check entry)
- rust-spike/slice/results/port-state-relations.md :554 fallbacks and kept shares as (iii) reported them, :638 Group D
- bar-part3/sum.txt: :7 tests, :15 suite, :30 live, :81 extra, :209 plants, :564 suite plants, :787 kept reasons
