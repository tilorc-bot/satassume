# HANDOFF sa-port-300: convert.py's `_Walk` to Rust (issue 323, the convert step)

Handed off at the context budget, between item 0 and item 1. Started from rust-slice 899d354.

## State

- **Item 0, done and pushed**: port/convert 8c72dd0, `rust-spike/slice/results/convert-item0.md` (tools in
  `rust-spike/slice/tools300/`). From sa-port-295's samples of 1d22f9a (convert.py and term_live.py are the same
  files on 899d354). Conversion = 39.4% of in-loop samples on dev, 16.3% on fuzz; of its own samples: bytecode
  25.8% / 21.6%, C straight from convert.py 43.7% / 42.6%, SymPy/satassume Python callees 27.2% / 33.4%, Rust
  3.4% / 2.5%. Lazy reads: 1.6% / 4.1% of N. Certain to go (ported methods' bytecode plus the ABC check's frame,
  both roots): dev 11.2%, fuzz 5.8% of N. Expected gain: dev 11% to 19% of loop time (0.085 to 0.145 s of 0.760),
  fuzz 6% to 9% (0.37 to 0.60 s of 6.420), less what the pyo3 calls add.
- **Items 1-5, written and tested together, NOT committed per item, nothing landed**: branch
  `origin/port/convert-wip` d4af871 (one WIP commit on top of 8c72dd0). On it `test_convert_walk.py` gives 12
  passed: each item alone and all five against Python's `_Walk` on 51 inputs, 0 differences (tables by token and
  type, ids by object/id/order, objects, classes, counts, Kept reason and detail, exception type and message,
  every lazy read of every term); plants 670-674 each caught by that comparison, with all items on and with the
  plant's item alone. Not run on it: the suite, the 20 workloads, livecmp, S1, the bar, the probe.
- **The per-item cut failed and is the next thing to do**: `~/sa-rust-ids-work/sa-port-300/mk_commits.py` (orion)
  writes, for item k, walk.rs with the later items' `//@begin X`..`//@end X` blocks and `//@call X` lines stripped
  and `RUST_ITEMS` cut to the first k, builds, runs the test, commits. The stripped item-1 file doesn't compile
  (7 errors, not read: `commits.log` keeps only the tail; run `cargo build --release` on the stripped file to see
  them). Likely the `rsplit` filter on `//@call` lines in mk_commits.py or code left referring to stripped
  functions. The script wrote no commit. Inputs it needs: `walk-final.rs`, `convert-final.py` in that directory
  (equal to d4af871's files). Run it in the worktree on port/convert with the other WIP files checked out from
  port/convert-wip (`git checkout port/convert-wip -- rust-spike/slice`), not on the WIP branch.
- **Item 6, draft only**: `convert_diff.py` on the WIP branch (`install(out)` wraps `convert.convert` and compares
  both walkers per query; `python convert_diff.py DIR...` adds up). It has never run. Still to do: call
  `install` from `convert.from_env` on SLICE_CONVERT_DIFF, make test_convert_walk.py import `diff` from it instead
  of its own copy, run it under the 20 workloads and the suite.
- Not started: S1 on pareto0, bar300.sh, `bar.sh land`, landing, the probe.

## Design, as built

- The state stays `_Walk.__init__`'s: `sa_solver.Walk` fills the same `ids`, `objects`, `classes`, `class_rows`,
  `opaque`, `counts`; `strings`, `string_ids`, `reading` are held by Rust (properties on the Python subclass),
  because `_Walk.read` replaces them. `read`, `power_rows`, `term`, `s` and `convert()` stay Python's.
- `convert.WALK[0]` is the walker class; None is `_Walk`, the default. `SLICE_CONVERT=py|rust|enc,klass,...`
  through `convert.from_env()`, called from `term_live.from_env()`. `SLICE_CONVERT_PLANT=<name>` sets a plant.
- A mask says which items run in Rust; an item that is off is `_Walk`'s method called on the owner.
- Where Rust differs from a literal transcription, with the same output: `walk` uses one `ids.setdefault` for
  `t in ids` plus `ids[t] = n`; `enc` asks `isinstance(v, numbers.Integral)` of the ABC once per class per walk
  (an exact int skips it); `term_row` reads `t.args` once and `Basic._hashable_content` once per walk; `enc`'s
  tuple recursion goes through `Py_EnterRecursiveCall`.
- Known boundary, untested: a nesting right at the recursion limit can be `Kept('too-deep')` under one walker and
  converted under the other, since Rust frames don't count as Python frames.

## Plants and counters

Plants 670 enc-true-as-false, 671 klass-no-is-expr, 672 term-row-no-number, 673 walk-args-unreversed, 674
enc-int-no-sign (walk.rs `PLANT`, numbers 1-5 to `sa_solver.walk_plant`). Next free plant 675. No counters used
(706-719 still free).

## File:line map (port/convert-wip d4af871, rust-spike/slice/)

- solver_rs/src/term/walk.rs (765 lines): PLANT :57, WalkCtx :75 (`new` :116), Walk :179, W (one call's view) :202,
  getattr3 :276, s :281, term :294, dispatchers enc :309 / enc_int :314 / walk :319 / klass :324, is_integral
  :331, enc_native :346, enc_int_native :404, walk_native :432, klass_native :499, term_row_native :629,
  pymethods :721 (entries :752-:756), register :759. Registered in term/mod.rs and lib.rs (after
  `term::dispatch::register`).
- convert.py: RUST_ITEMS :392, WALK :394, rust_walk :398, use_rust :440, WALK_PLANTS :446, from_env :450,
  `w = (WALK[0] or _Walk)()` :543. The reference `_Walk` is unchanged (:123-:388).
- term_live.py:1220 `convert.from_env()`.
- test_convert_walk.py: inputs, `diff`, test_rust_walk_is_pythons, test_plant_is_caught (subprocess, by plant).
- convert_diff.py: item 6's draft.
- Orion scratch ~/sa-rust-ids-work/sa-port-300/: py.sh (runs with this tree's paths), mk_commits.py, commits.log,
  item0/ (split-dev.json, split-fuzz.json).
- Unchanged from the brief: S1 harness sa-port-295 gd (orion and pareto0 ~/sp19/sa-rust-ids-work/sa-port-295/),
  297's go297c.sh; bar: pareto0 ~/sp19/bar298.sh is the newest (copy to bar300.sh); probe pc294.sh / 299's
  pc299.sh, base ~/sp19/sa-rust-ids-work/sa-port-294/pc.
