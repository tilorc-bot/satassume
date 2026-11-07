# Handoff: sa-port-111 to the next 6f session (functions, special, rootof, nodes, physics, stats; issue 323)

**State (date -u: see the commit):** port/6f head 3001337 (pushed), on rust-slice 2540ca7. The Rust port is written and wired
under `knowledge_live.install()`. Checked so far: `cargo test tf6` (2 pass), f6 workload's first 300 queries in shadow mode, 0
mismatches, `f6:_pi_trig_rules` 236. Not run yet: full shadow runs, plain vs install MATCH, plants, suite, bar, landing.
Handed off at about 140k context.

## Running when I left (detached, orion)
`~/sa-rust-ids-work/sa-port-111/short/{f6,value,rootof,core}-shadow.tsv` (+ `.counts.json`, `.log`). PIDs are in `pids.txt`;
a finished tsv ends in `END`. Read: `mismatches` (want []), `counts` keys `f6:*`, `fault`, `scaffold:mismatch`,
`scaffold:rebuilt:f6`, `f6:refuse`, `f6:derived:*`, `realroots:root_facts`. Runner: `~/sa-rust-ids-work/sa-port-111/run.sh WL
MODE OUT [--limit N] [--plant ..]` (MODE plain|atoms|shadow; atoms = install without shadow).

## What was done (3001337)
- `rust-spike/slice/solver_rs/src/term/tf6.rs`: `pi_trig_rules`, `cosh_shift_rules`, `parts_of_round_rules`,
  `genocchi_half_rules`, `unit_interval_units`, `accum_rules`, `multigamma_rules`, `rootof_facts` (calls
  `crate::realroots::root_facts`, made `pub(crate)`), `randomsymbol_units`, `const_units`; on TermTable
  `f6_cosh_shift_split`, `f6_shifted`, `f6_doubled` (they use `algebra.rs` `add`/`mul`/`raw_add`/`raw_mul`, and the
  `Counter` rebuild check is a sorted-id compare). Bindings `f6_*` in `term/py.rs`, just before `pub fn register`.
- `rust-spike/slice/knowledge_f6_live.py`: `install(shadow, counts, fault_cls, mismatch)`. Wrappers: `appending` (rules
  added to R), `pure`, `multigamma_rules`, `unit_interval_units` (Float: named callback `f6:unit_interval:float`),
  `rootof_facts`, `multigamma_value` (named callback `f6:multigamma_value:python`), splits `cosh_shift_split`, `shifted`,
  `doubled` (derived terms through `term_live.scaffold(q, i, 'f6')`). `shifted` is swapped in every
  `satassume.knowledge.*` module that binds it by value, at install time. Plants: `PLANTS` list, picked with
  `SA_F6_PLANT=f6-...` or the bar's `SLICE_SESSION_PLANT`; each counts through `knowledge_live._fired`.
- `knowledge_live.py`: `undo_f6 = knowledge_f6_live.install(...)` right after core's (:460), undone before core's.
- satassume (pure refactors, behaviour unchanged): functions.py `_unit_interval_units(kind, c, expr)` and
  `_genocchi_half_rules(R, h)` (module level, called from the closures), special.py `_multigamma_value`, nodes.py
  `_idx_facts`, physics.py `_quantity_facts`, stats.py `_random_units(positive, integer, real)` (conversion reads stay in
  `randomsymbol_units`). `offline_data.json` regenerated: body byte-identical, only `sources_sha256` changed.

## What's left (in order)
1. Read the four shadow runs. Fix any mismatch. Check that every swapped name's counter is nonzero on some workload
   (compare with port-6f-trace.md's table; `shifted` should be close to trace's 2321 on value; if a family module imports
   later than install, its `shifted` is missed, so check `f6:shifted`).
2. Plain vs atoms on dev, fuzz, f6, value, rootof, core: answers and state MATCH (6e: `results/port-6e.md` line 5).
3. Plants: each of `PLANTS` fires and is caught (plain vs atoms differ) on some workload; a void one gets a direct test, as
   in test_knowledge_core_shapes.py. Rust source mutants for tf6.rs in `mutate_knowledge.py`, as 6e did. **Footnotes
   (reclass ruling):** a realroots Rust-side plant caught on the rootof workload (crootof → `f6_rootof_facts` →
   `root_facts`) removes the realroots footnote; a `value_units` plant caught through multigamma on the value workload
   removes that one. Each footnote goes only with its own caught plant.
4. The suite column: `pytest -p f6_trace` with F6_TRACE_OUT, then the bar with `rust-spike/slice/p1/bar.sh` on pareto1
   (default path), quiet-handler firings listed, `engine.py:1906` catches counted. Check `origin/rust-slice` for
   sa-port-109's 5c2/5c3 first; apply the rebase rule; `bar.sh land`.
5. Docs: port-ownership.tsv/.md rows for the six modules, PORT-INVENTORY.md rows, and results/port-6f.md (model:
   port-6e.md). Reclasses per ~/dev/architect/briefs/addenda/sa-port-6f-reclass-ruling.txt: `special._register` not port
   (dead; removal goes in a separate held Python PR, not the port), `rootof._coefficients` conversion,
   `randomsymbol_units` conversion for its reads, with `_random_units` ported (template work stayed, so it was ported).
   `_value_units` offline.

## Ownership counts (for the report)
Before (port-ownership.tsv on 2540ca7): 27 rows: functions 14 (13 `port` + `_value_units` offline), nodes 3, physics 1,
rootof 3, special 4, stats 1; 26 `port`, all Python, owned by 6f. After: work it out from step 5. Template shells
(`_unary`, `nary`, `_pi_trig`, `_exp_ipi`, `_cosh_shift`, `parts_of_round_templates`, `multigamma_templates`,
`accumbounds_templates`, `*_units`) stay Python: what's left in them is the arity check, `_common` (6d) and the rows'
`gen` (6g). Say so plainly in the report (don't count them as moved Rust code). `_exp_ipi` and `_pi_trig` already reached
Rust through core's swapped `_pi_split`/`ipi_rules`.

## Risks to check
- `_cosh_shift_split`'s rebuild check compares ids, but SymPy's `Counter` uses `==`, which joins Float and Integer. Shadow
  shows this if it happens.
- A raw (unevaluated) Add/Mul from `shifted`/`_doubled` on a sum that doesn't rebuild: `scaffold` rebuilds it evaluated, so
  the form check refuses it (`scaffold:mismatch`). The query then refuses. Count these.
