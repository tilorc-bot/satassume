# HANDOFF sa-port-166 (step 5c8, issue 323)

Branch port/5c8 from rust-slice 17442af. The code is written, builds, and passes a quick check. No bar has run yet.

## Done
- `rust-spike/slice/solver_rs/src/relevance.rs` (new, about 820 lines): all 16 rows ported in the 5c7 style (PyO3 over the
  Python objects, callbacks counted). Map:
  - `DEPTH` :42 (deeper Booleans go to Python's `_keys_rel`, `rv:py_deep`, the same precedent as session.rs FORMULA_DEPTH).
  - `Ctx` holds sympy_api's globals, read once per key walk. Its methods are `const_base`, `const_free`, `closed_keys`,
    `expr_keys`, `arg_keys`, `bool_keys` :276 and `sides_keys`.
  - `keys_rel` :377 (`_KEYS`/`_CONST` stay Python's PROCESS tables, worked through their methods).
  - `Split` pyclass :419 (fields are Rust's; it lives in Python's `Engine.splits` AnswerMemo). `part_of` is `_Split.part`.
  - `vocab_blocks` :542, `handler_row` :578, `caller_hint` :589, `consistent_body` :597, `consistent` :627 (the
    `except Exception` mirror: catches only `PyException`; BaseException goes on up), `part_consistent` :644, `relevant` :663.
  - The pyfunctions `rv_*` and `Split` are in `register` at the end. lib.rs registers the module.
- Counters, session.rs: `rv:relevant` 179 .. `rv:sympy_and` 199 (NAMES/COUNTS 200). Slots 170-178 are "rsv:170".."rsv:178",
  held for sa-port-162's Element._new; replace them on its rebase.
- Plants, relations_core.rs :183-198, numbers 124-139 (118-123 held for sa-port-162): const-base-no-pow, const-free-no-mul,
  closed-keys-no-undef, expr-keys-closed-skip, arg-keys-no-closed, keys-empty, keys-rel-no-flag, bool-keys-opaque-in,
  sides-keys-first-only, split-no-merge, split-part-first, relevant-assume-consistent, vocab-no-derived, part-consistent-true,
  **consistent-fault** (the raising plant: raises a TermFault through `session_live._fault` inside `_consistent`'s body), and
  consistent-ignore-verdict. They're in `rel_plant`'s match.
- session_live.py: `PY_RELEVANCE` :760, `_RELEVANCE_NAMES`, `_RELEVANCE_PLANTS`, `_install_relevance` :770, the install :899
  (`SLICE_RELEVANCE=py` puts Python's back), and from_env takes the plants.
- handler_count.py: `install` takes Python's `_consistent` code from `PY_RELEVANCE` when the module name is Rust's.
  `rust_handled` :53 writes the same row under site `_consistent` and skips `Uninterpreted`, as `_fired` does.
- catch_count.py: `NEXT_CALLER`/`_take_hint` :15. Rust names `_consistent` as the caller of `_formula`/`verdict`, so the
  per-id `caught` rows stay `verdict<_consistent` / `formula<_consistent`.

## Checked
- `cargo build --release` and `sh rust-spike/slice/build_solver.sh` OK (orion).
- Quick suite (rust_plugin + handler_count, -n 4): test_relevance, test_memos, test_registry_versioning, test_scope and
  test_unrelated_relation give 211 passed (~/sa-rust-ids-work/sa-port-166/quick). Its 3 handler rows were `Uninterpreted`,
  written before the filter fix, so rerun it.
- A direct `_relevant` call fires rv:relevant, split_new, keys_rel, part_consistent, consistent, cb_formula, cb_verdict,
  cb_theory_scope, cb_category, cb_memo and br_parts.
- The `consistent-fault` plant comes out loud (TermFault), not as a quiet False.
- **Open:** a first probe through the public `sympy.ask(...)` showed every rv: counter at 0. Find out why: maybe that path
  doesn't reach `_ask_general` with `eng.relevance`, or `session_counts` reads another thread or engine. This matters for
  "reached by which workload".

## Left (the brief's steps 1, 5 and 6)
1. Classify each row and trace which run per query on dev, fuzz, loop, scope, zero and cert, with Rust callbacks vs Python
   callers.
2. State decisions, all "stays", from sa-port-147 INVENTORY-state.md:
   - `splits` row :193: last reader 5c9 (`_drop_set_memos`), so it stays to 5c9c.
   - `stats` row :199: never moved by a planned step (sympy_api conversion writes it), so it stays.
   - `_KEYS`/`_CONST` (the relevance memo): no inventory row (:169 lists them with "no Rust worker"), so the inventory
     doesn't put its last engine reader in 5c8 and it stays. Name its readers: tests test_memos.py:136-143,
     test_relevance.py, tools/relevance_fuzz.py, and term_live `_Mark`.
   - The `_Split` values are Rust objects inside the Python container. No digest switch is needed, since no container moved.
     Say so.
3. Run the plants. Find which are void, and bring a workload for any with 0 reach on dev and fuzz.
4. Then the bar (`PUSH=1 sh rust-spike/slice/p1/bar.sh land TESTED_SHA`, base rows pareto1
   ~/sp19/sa-rust-ids-work/sa-port-158/bar-5c7b/suite), the report results/port-5c8.md in port-5c7.md's form, and the
   updates to port-ownership.md and the TSV (rows 539-554).
5. Check the module count against ~/dev/architect/STATUS.md "Counted modules" (13 of 32 before).
6. knowledge_quiet.py:104 reads `A._consistent.__code__`, which is a builtin under Rust. Check that tool before using it.
