# HANDOFF sa-port-134 (5c6, issue 323)

Done:
- Step 0 reported (journal 7be9784): every scope.py function 0 Python calls per query outside kept paths on dev, fuzz, loop,
  scope; affine_pair 9/pass on dev, all kept:out-of-scope. Probe ~/sa-rust-ids-work/sa-port-134/scope_count.py (not committed),
  output ~/sa-rust-ids-work/sa-port-134/step0/.
- 5c6 code, port/5c6 50fb678 (pushed; base rust-slice 803d073): the eight Session rows on Rust. Slice tests on orion
  (test_query_core, test_discovery_core, test_session_limits, test_scope_core): 273 passed. Nothing else run yet.
- Bar running: pareto1, OUT=/home/tilo/sp19/sa-rust-ids-work/sa-port-134/bar-5c6 (done.txt at end), launcher log
  orion ~/sa-rust-ids-work/sa-port-134/bar-5c6.launch.txt, machine-run PID in bar-5c6.pid. Started 04:04Z on 50fb678.
  PLANTS = the 7 below, WLS="loop scope", SUITE_PLANTS=zero, TESTS = bar-scope2's list, BASE = bar-scope2/suite.

File:line map (port/5c6 50fb678):
- rust-spike/slice/solver_rs/src/session_glue.rs: init :30, assume_formula :81 (emit closure adds -sel), link_set :134,
  assumption_lits :152, set_glue :246, group_sel :330, glue_of :388; pyfunctions ses_* :420-456.
- query.rs :274 and :308: `_glue_of` is now a direct Rust call (was call_method1).
- session.rs :182-188: counters ses:init .. ses:glue_of (133-139), NAMES has 140.
- relations_core.rs :148-154, :261-267: plants init-no-relations, af-drop-relations, link-set-skip, al-drop-delta,
  set-glue-no-emit, group-sel-no-impl, glue-of-plain (97-103).
- session_live.py :668 PY_GLUE, :698 _GLUE_PLANTS, :702 _install_glue (copies __init__'s scope=EMPTY default), :830 install,
  SLICE_GLUE=py switch. Shells: `_ses_init` falls back to Python when engine.VarTable is not TableView; others on TableView.
- engine.py on 803d073: Session :304, __init__ :305, assume_formula :936, link_set :972, assumption_lits :982, _set_glue :1072,
  _group_sel :1119, _glue_of :1182. Python callers left: Engine._build_context (link_set, assumption_lits at :1906 try,
  assume_formula), all 5c10's.

Left: read the bar (five items), trace which Session methods run per query (ses:* counters from the live phase's
session report, by workload), report in results/port-5c6.md (port-5c5.md's form), update port-ownership.md :41 row and the
TSV rows 19-20, 43-47, 50 (owner landed 5c6 SHA, today Rust), `bar.sh land` without PUSH first, read the incoming diff
(6d and adapters C run beside), then PUSH=1. Notes for item 5: Session's methods are now session_live shells into Rust;
under the count rule a shell is Python per query, so Session (a class row group) isn't "whole" until 5c10 removes the
shells with engine.py; engine.py counts at 5c10.
