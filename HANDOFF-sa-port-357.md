# HANDOFF sa-port-357 (20 Nov, ~09:35Z): item 3 (the port of convert.py) in progress, handed off mid-item at the architect's instruction

Branch port/measured-next, head = this commit (parent 827f0b1), from rust-slice de88d9b9. Pushed to the clone's origin.
Worktree ~/sa-rust-ids-work/sa-port-356/wt in clone ~/dev/sa-port-5. Nothing is landed. No lease is held.
Items 4 (gate), 5 (S1) and 6 (bar, landing) are not started. No x86-64 .so of this tree exists; nothing ran on a pareto.

## What is in the commit (work in progress, not gated)
Under SLICE_CONVERT=rust, four new items of RUST_ITEMS (no new switch, no separate off-switch for them):
`klass_calls` (`_template_name`, `_structural_class`; acts only inside Rust's `klass`), `power_rows`, `read` (`_Walk.read`
and the `_read_*`), `entry` (`convert`, `default_engine_settings`, `formula`, `_rel`, the state of `_Walk.__init__`).
Python's `_Walk` and the body of `convert` stay the default and the reference.
- With every item on, Rust makes the state, no `_RustWalk` exists for the query, and `tables['reads']` is Rust's bound
  method `Walk.read_own`. `counts` and `raised` are the same dict and list shapes, filled by Rust (ported, not removed).
- What stays Python in convert.py on that path, by design: `convert`'s first lines (the dispatch on `WALK[0]`, kept
  because tests and tools replace `convert.convert` and `WALK[0]`); `_read_own_base` (`Mul(2, t)`, the input layer's
  construction, ruling 5; counter 745); `Kept.__init__` and `Converted.__init__` (called as classes).
- Fallbacks to Python, each counted: `formula` nested past 100 connectives goes to Python's `formula` from the top
  (743; Python's recursion limit then decides 'too-deep'; `formula` only reads, so it is read twice in that case);
  a template whose class has its own metaclass goes to Python's `_template_name` (744); a replaced definition (746, below).
- Replaced definitions (P1): kept tests and the instrument lazy_reads.py replace `_Walk.read`, `_read_key`, `term_row`,
  `term`. `WalkEntry` compares `_Walk`'s methods and the module's ported functions with `convert._ORIGINAL` per query;
  a replaced one turns its item off for that query (`term`, `s`, `__init__`: every item), so it is called by name.
  This guard was added after the first run of the kept tests under the suite plugin showed 12 failures only the Rust
  walker had; whether it removes all 12 is NOT yet known (see "The running job").
- Counters 740-746 (`sa_solver.walk_counts()`, `walk_counts_reset()`): cv:entry, cv:formula, cv:read,
  cv:fallback:depth, cv:fallback:name, cv:py:own_base, cv:patched. Plants 768-773 (SLICE_CONVERT_PLANT; walk_plant
  9-14): calls-structural-not, power-rows-drop-last, read-commutative-not, entry-no-assumptions, formula-and-as-or,
  entry-skip-replaced. Next free: plants 774, counters 747.
- Shared files changed: none outside the converter (convert.py, solver_rs/src/term/walk.rs, test_convert_walk.py).
  No new crate dependency.

## What was run, and what was not
- Run on orion, before the replaced-definition guard, standalone pytest (no suite plugin): test_convert_walk.py 30 tests,
  28 passed, then the 2 failures fixed and the new ones rerun, 18 passed (-k 'template or plant or deep or entry'):
  each new item alone and all items against Python's walker (differential, counts and raised included), plants 768-772
  caught with all items and with the item alone, deep formulas 90/130/700, template names. Logs: ~/sa-rust-ids-work/sa-port-357/t1..t3.log.
- NOT run: anything since the guard was built, except what the running job does. `test_a_replaced_definition_is_called`
  (test_convert_walk.py:319) has never been run. Plant 773 and its Rust line (walk.rs:126, :1186) are in the source but
  NOT in the built .so: the worktree's sa_solver.so (aarch64, b6845b493e458a4f, untracked) was built with the guard and
  without plant 773. Rebuild (`sh rust-spike/slice/build_solver.sh`) only when no test of this tree is running.
- t4-py.log / t4-rust.log (290 passed each) prove nothing about the Rust walker: without `-p rust_plugin` nothing reads
  SLICE_CONVERT. Use run_suite.sh, as the running job does.

## The running job (started 08:49Z; NOT detached: it is a background shell of my session and may die with it)
Command, from the worktree root, O=~/sa-rust-ids-work/sa-port-357, F = the six files test_lazy_reads.py,
test_convert_once.py, test_term_live.py, test_term_ids.py, test_knowledge_lazy.py, test_convert_walk.py (all under rust-spike/slice/):
`for m in py rust; do rm -rf $O/k-$m; SLICE_CONVERT=$m SLICE_TERM_FRAMES=rust PYTEST_N="-n 4" sh rust-spike/slice/run_suite.sh $O/k-$m rust $F -W ignore; done`
then the same with SLICE_CONVERT=rust from $O/base (my own worktree of clone -5 at de88d9b9, its .so built) into $O/k-base.
- State at 09:31Z: still in the first pass (py). $O/k-py/pytest.log was last written at 08:49Z, at about 95% of the
  tests; one xdist worker (pid 194891) has been at 100% CPU for 41 minutes. Not diagnosed. It is a test of this tree
  under the plugin with the Python walker; the same file standalone took 35 s. The rust and base passes have not started.
- $O/k-rust/exit.txt and pytest.log are STALE (the run before the guard: 22 failed against 10 for py, 12 only on Rust,
  in test_lazy_reads.py and test_term_live.py). They are replaced only when the rust pass starts.
- Reading it: each pass writes exit.txt last. Compare failures by id:
  `diff <(rg '^FAILED|^ERROR' $O/k-A/pytest.log | cut -d' ' -f2 | sort) <(rg ... $O/k-rust/pytest.log ...)` for A = py and base.
  Wanted: nothing only on rust against py; against base, only what base's Rust walker already failed (base rows by id).
  If the py pass never ends, find the spinning test first (py-spy or rerun the six files one at a time), then rerun.

## To do
3. Finish the port: read the job (or rerun), rebuild with plant 773, run test_convert_walk.py and the kept tests under
   run_suite.sh in both modes; add bar rows `convert:NAME` for 768-773 (bar.sh penv :102 already routes them);
   results/measured-next.md (3) with what moved, what stays Python and why, the fallbacks, the plants.
4. Gate; 5. S1, 12 rounds against Rust at de88d9b9; 6. bar, bar.sh land, guard, PUSH=1 (planner's ruling for 356/357).
Open points for the report, mine and not ruled: the depth bound of 100 and its double read; `convert`'s remaining
dispatch frame; whether lazy_reads.py's replaced `_Walk.read` (READ off under that instrument, cv:patched per query)
is acceptable or needs P1's "instruments register".

## File:line map
- rust-spike/slice/convert.py: RUST_ITEMS :394, rust_walk :400 (new lambdas :439-:445, ENTRY :445), _walk_class :450,
  use_rust :457, WALK_PLANTS :465, from_env :470, default_engine_settings :502, formula :523, convert :557 (dispatch
  first, `walk=` for the hand-back), _ORIGINAL :606.
- rust-spike/slice/solver_rs/src/term/walk.rs: item bits :26-:42, DEPTH :45, counters :48-:85, plants :115-:126,
  WalkCtx :140 (originals read at :235), Walk :330, W.owner :427, template_name :890, structural_class :932,
  power_rows_native :948, read_value :981, read_native :1041, rel_parts :1089, formula :1104, replaced :1183,
  formula_top :1199, engine_settings :1215, WalkEntry :1250 and its __call__ :1262, Walk::bare :1397, fresh :1417.
- rust-spike/slice/test_convert_walk.py: ALL_PLANTS :37, PLANTS :43, nested :213, counted :222, the new tests :229,
  :264, :276, :319, test_plant_is_caught :378.
- Kept tests that replace `_Walk` methods: test_lazy_reads.py:116-122, :313-320; test_term_live.py:296, :313;
  lazy_reads.py:134-142. Everything else: HANDOFF-sa-port-356.md "File:line map".
