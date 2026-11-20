# HANDOFF sa-port-356 (20 Nov, ~07:10Z): items 1 and 2 done, item 3 (the port of convert.py) not started

Branch port/measured-next, head = this commit (parent f1d851f), from rust-slice de88d9b9. Pushed to the clone's origin.
Worktree ~/sa-rust-ids-work/sa-port-356/wt in clone ~/dev/sa-port-5. No source of satassume, the slice or the crate is
changed so far; nothing is landed. No job of mine is running; no lease is held.

## Done
- Item 1, the profile on de88d9b9 (quiet lease 20fa32a4 on pareto1, .so 0b6f073f5c5a600b, 5 timed rounds, sampler rows):
  rust-spike/slice/results/measured-next.md (1); tables in results/tools356/tab-p1.txt; raw rows in
  ~/sa-rust-ids-work/sa-port-356/s1/p1 (orion) and the same path on pareto1.
- Item 2, the target: **slice/convert.py** (own 5.50% dev, 2.92% fuzz, 2.79% budget, 6.33% wiring; stop rule not
  triggered). Its split, the answer to Tilo's open question 7 ([156]'s read dispatch is 11/26/65/9% of convert.py's own
  time), and the table of who reads each result: measured-next.md (2).

## To do: item 3, the port (then 4 gate, 5 S1, 6 bar and landing, as the ruling numbers them)
What is still Python in convert.py with SLICE_CONVERT=rust, by own time on dev / wiring:
1. Per-query entry, 3.08% / 3.66%: `convert` (convert.py:537), `formula` (:503), `default_engine_settings` (:482),
   `_Walk.__init__` (:125) and `_RustWalk.__init__` (:416), `power_rows` (:307).
2. Per-class callbacks from Rust's klass, 1.38% / 1.34%: `_template_name` (:120), `_structural_class` (:476); Rust holds
   them as WalkCtx fields (walk.rs:164-165) and calls them in `klass_native` (walk.rs:504-610).
3. Walk trampolines, 0.42% / 0.77%: Rust's `walk` calls `self.klass` / `self.term_row` through the Python object
   (walk.rs:112, :170, :331), which are the lambdas at convert.py:426-432, which call back into Rust.
4. Read dispatch, OWED [156](a), 0.59% / 0.54% (1.82% on budget): `read` (:321), `_read_*` (:348-:395), the three
   property lambdas (:421-:423).

Suggested order (my reading, not a ruling): 3 first (when every item of RUST_ITEMS is on, Rust calls its own native
methods directly; smallest change, same behaviour by construction), then 2, then 1 as new items of RUST_ITEMS
(convert.py:391), so the existing switch SLICE_CONVERT (convert.py:450 `from_env`) fits and no new switch is needed;
`SLICE_CONVERT=rust` stays opt-in. 4 last. An item that is off stays `_Walk`'s method, as now.

## File:line map
- rust-spike/slice/convert.py: REASONS :36, READS :53, _PREFIX :81, Kept :87, Converted :97, _Walk :124-395
  (enc :148, term :182, walk :194, klass :219, term_row :269 with `constructed_noncommutative` at :305, power_rows :307,
  read :321), RUST_ITEMS :391, WALK :393, rust_walk :397, use_rust :439, WALK_PLANTS and from_env :445-470,
  _structural_class :476, default_engine_settings :482, formula :503, convert :537.
- rust-spike/slice/solver_rs/src/term/walk.rs: walk_plant :75, WalkCtx :81 (fields from convert.py's module :160-170),
  Walk :183, enc :314, walk :324, klass :329 (through Python :331), enc_int_native :409, klass_native :504,
  term_row_native :634, bind :744, the #[pymethods] :755 on.
- rust-spike/slice/solver_rs/src/term/table.rs: Reads trait :125-131, TermTable's rows :150-160, the table's build :277-355.
- rust-spike/slice/term_live.py: _Query :78-107 (the only reader of Converted: kept :89, classes :92, TermTable :93,
  ids/objects/counts :94, raised :95), _note_query :300-303 (the only reader of counts and raised), the call :309,
  q.ids lookups :327 :444 :513, same_class :416.
- Tests of the converter: rust-spike/slice/test_convert_walk.py, test_convert_once.py, convert_diff.py (the differential,
  p1/convert_diff.sh; bar.sh's `convdiff` phase, bar.sh:18), bar.sh penv :91-129 (how a `convert:NAME` plant row is run).
- The last component port as the pattern: rust-spike/slice/witness_live.py, solver_rs/src/witness.rs, results/witness-native.md.
- Profile tools: results/tools356/goprof356.sh SHA NAME (orion, setsid; stages, takes the lease, analyses),
  onlease356p.sh, pys356.sh, ana356.py, tab356.py DIR [rows], prof356.py. goprof356.sh checks the tree against b7302f83
  and copies 354's .so: for a tree with a changed crate, build the x86-64 .so on pareto1 first (tools327/build327.sh's
  docker line) and change that check.
- Plants from 768 (765-767 are also free), counters from 740.

## Traps met
- git pathspec `rust-spike/slice/*.py` also matches results/tools*/x.py; use `:(glob)rust-spike/slice/*.py`.
- cProfile over the whole pass misleads (Rust entered through a slot is charged to the calling file); a Python signal
  handler does too. Use the C sampler rows.
- An exception inside a Python signal handler during conversion becomes a quiet TermFault (seen in the orion trial).
- orion's .so for this tree: built, e0365239348de148 (aarch64), in the worktree, untracked.
