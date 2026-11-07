# Handoff, sa-port-99: port/wire (issue 323), at the 140k note, 7 Nov 22:25 UTC

## State
- Branch `port/wire` on origin, from rust-slice 653d932 (5c1 landed). Commits: 56f3be3 the wiring (tested source), 4dd9984 doc only (step 2, done), then this handoff (doc only).
- Bar running on pareto1 under `bar.sh` (shared lease df7b40c1), all phases but seed1: rows `~/sp19/sa-rust-ids-work/sa-port-99/` (`phases.txt`, `sum.txt`, `done.txt` when finished). Local log `~/sa-rust-ids-work/sa-port-99/bar-run.log`; the `machine run` wrapper's subshell is orion PID 510945 (stop by that PID only). Env: BASE=sa-port-96/suite (5c1's rows), PLANTS="knowledge-pattern-drop knowledge-rows-kept-raise", SUITE_PLANTS=zero, TESTS=the 6 test_knowledge_* files plus test_session_limits.py and test_discovery_core.py.
- Done so far in that run: build; tests 364 passed; suite 5,959 passed / 125 failed / 23 skipped / 18 xfailed (base 5c1: 5,959/125/23/18). Suite knowledge counts, summed over workers' term counts: common:pattern 23,712, common:resolve 41,253, realroots root_facts 133 (+ real_root_counts 5, imaginary_root_count 4, squarefree 1), rows:constant_value 4,796, rows:gen 1,378, symbol:input 2,395, constant:input 209, value:* 0, fault 0, common:kept 212, rows:kept 50.
- Orion short check (dev first 400, `~/sa-rust-ids-work/sa-port-99/short/`): py against rust MATCH; plant pattern-drop: 6 answers and 76 end/stream states differ; plant rows-kept-raise: KnowledgeFault at the first rows use, run aborts (loud).

## Map
- `rust-spike/slice/knowledge_live.py:61` PLANTS, `:159` installed(), `:163` _fired() (also bumps session_live.PLANT_FIRED so bar.sh's `fired` sees it), `:171` from_env() (SLICE_KNOWLEDGE rust|atoms|shadow|py; off if term_live isn't installed; with SESSION_REPORT writes `<base>.knowledge.json` with COUNTS), `:310` pattern-drop plant, `:355` rows_kept under KnowledgeFault (the owed guard; 6e doesn't repeat it), `:469` second install raises.
- `rust_plugin.py:101-102`, `live.py:346-347`: one from_env() call each (shared files). `knowledge_suite.py:19,29`: no second install; records `installed`.
- `test_knowledge_wire.py`: 6 tests (default installs and a real ask reaches common:pattern, py off, no table means off, undo, rows_kept plant loud, others' plants ignored).
- Live counts per module on dev/fuzz: `~/sp19/sa-rust-ids-work/sa-port-99/live/{dev,fuzz}-rust.knowledge.json`.

## Left
1. When done.txt exists: read `sum.txt` (bar items 1-5), the live cmp files (dev/fuzz MATCH), plant cmps, quiet firings (expect base's 39 rows in 2 tests), and `value:*` in the live knowledge.json (value_units is reached only via functions/special; if 0 everywhere, say atoms.py's value_units is wired but unexercised).
2. Write `rust-spike/slice/results/port-wire.md` (<4 KB report body): module count before 5 of 32 (solver, euf, lra, transfer, lra_cert) plus 2 ported but not wired (realroots.py, atoms.py); after: 7 of 32 if the counts above hold (realroots.py and atoms.py run on the default backend); `_rows_runtime.py` and `_common.py` run on default but stay partial. Shared files: rust_plugin.py, live.py, knowledge_suite.py. Backend PR list item to name: Rust raises NotImplementedError on `BlockOwner`/`provenance`/`root_step` (a contract difference). Not run: seed1, plus the "moved to before any backend PR" list.
3. `sh rust-spike/slice/p1/bar.sh land 56f3be3`, check the incoming diff (rebase rule; 6e sa-port-98 ~/dev/sa-port-5 port/6e hadn't landed at 22:25), then PUSH=1. `agent report`, SendMessage the architect.
