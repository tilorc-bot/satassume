# Handoff: sa-port-24, component 6 (issue 323)

Read the brief first: `~/.local/state/agent/briefs/sa-port-24-20261107T095702Z.txt`. Its terms still apply. Clone `~/dev/sa-port-24`, branch `port/6`, based on `rust-slice` at cc3055c. Nothing is on `rust-slice`.

## Standing

**Family: atoms.** `symbol_units` and `constant_units` run from Rust in the real registry; Python's engine takes the pattern. First version only, **not held to the bar yet.**

| What ran | Result |
|---|---|
| Dev census, fresh, seed 0 | 1,985 queries: 1,929 reach an atom template, 1,198 visit only atom nodes; 6,583 of 10,575 node visits are atoms, 6,505 input, 78 derived (all Zero) |
| First 150 dev, shadow against plain | Answers and session digests byte-identical; 184 calls compared, 0 mismatches |
| `CRootOf(x**5 - x + 1, 0)` and `+ 1` | Kept on Python, `complex-unbounded`; `complex()` ran 0 times; answers False and None |

**Running, not a result:** `~/sa-rust-ids-work/sa-port-24/fresh2/`, full dev and fuzz in plain, atoms and shadow, from a snapshot of fe85470 in `fresh2/tree`, so rebuilding the clone can't disturb it. Started about 10:10 UTC, detached. It ends with `fresh2/summary.txt`. Read that, then the `*.counts.json` files for `shadow:mismatch`, `fault`, `kept:*` and `*:derived`. `fresh1-failed-no-harness/` is a dead run (no `harness` package in its snapshot); its "DIFFERS" lines mean nothing.

**Traps already hit:**
- Don't test the refusal with `CRootOf(x**50 - x + 1, 3)`: SymPy's constructor alone ran past 60 s (`rootoftools.py:561`), before any query. So the case in the brief **has not run through the refusal**, only degree 5 has. Build it in a way that doesn't isolate roots, or say it wasn't run.
- `Q.even(2)` calls `complex()` once: every closed term does, including plain integers. Ruling 6 wants its own counter, not yet added.

## Still owed, in order

1. **Read fresh2.** A difference gets its smallest case, never a reclassification.
2. **Quiet handlers, whole `try`.** `engine.py:1906` and `sympy_api.py:1107`. Architect (7 Nov): wrapping `verdict` misses part of the 1107 try. 1a's `catch_count.py` missed `_formula` inside 1107 and `s.assumption_lits()` inside 1906, so its zeros were floors. `~/dev/sa-port-15/rust-spike/slice/handler_count.py` (port/2) uses `sys.monitoring` EXCEPTION_HANDLED filtered by code object, which should see both. **That's a claim to check:** show it firing on a planted raise in each of those two spots before reporting any zero, and say what the zero covers. Do this with Rust conversion able to raise there.
3. **Discarded run.** This family has no mid-run discard: conversion finishes before the engine starts and a template never refuses. That's by reading. Still owed: show that a kept query leaves nothing in Python, including SymPy caches written by conversion's `is_finite` and `complex(t)`. Plain against atoms on the same order, without clearing the SymPy cache, is the direct test; `knowledge_fresh.py` runs `sympy_cache=False`, so it doesn't clear it per query.
4. **Planted bugs**, in a new `mutate_knowledge.py` on `mutate_term.py`'s pattern (scratch copy, `--so`). Say which a comparison caught and which only a crash. Candidates: `closure` sign swap, `expand` dropping dedupe, `sorted_lits` order, `complete` with `rule_free` dropped, `unsubsumed` not stable, `in_vocab` ignoring `commutative`, `const_basis` offset, atom row by wrong id, `_wrap` `used` always `(0,)`. Re-score this boundary: atom rows from conversion to Rust, patterns from Rust to Python. **Run the shadow-off mutants too:** shadow only catches what its comparison sees.
5. **Branches no run is known to reach:** the conflict path in `Rules::units` (`closed` None, literals kept in fact order with duplicates) and the `rest` loop (`antihermitian`). A symbol with `antihermitian=True` should reach `rest`. Compare `Rules::units` against `_common.units` directly over generated fact sets, since workloads may not get there.
6. **Suite by id** against 5,961 / 77 / 46. `rust_plugin.py` needs a small switch to call `knowledge_live.install()` (not added); keep the shared-file change minimal and name it. Expect tests that inspect templates or `_CACHE`. Report `test_performance_smoke_300_vars` either way.
7. **History:** seeds 0, 1, 2, shuffle, on dev, fuzz and corpus. `run_history.sh` and `historycmp.py` exist. Corpus hasn't run at all, and it's where the `complex-unbounded` and derived counts would be most informative.
8. **Counts for the report.** Per query: `default_sort_key` and `decompose_power` constructions beside pure Python's, keys computed against keys used, `complex(t)` with its own counter, conversion's time by site. **The atoms family uses no key,** so every key computed is unused by it. If that's noticeably more work or a large share of query time, it goes to the planner as a question (ruling on component 0, point 6); no lazy path without a ruling. `term_counts.py` is the place to start.
9. **Then** rebase, rerun the suite if others' source came in, push to `rust-slice` without force, and report the SHA, three numbers, what ran and what didn't, and modules of the 32 now running.

Long runs: **not mbp2015** (no environment, Python 3.13). pareto1 with `~/sp19/p1_job.sh` under `machine run pareto1 --shared` (that path is on pareto1, not orion; I haven't used it), or orion at `-n 4`.

## Gaps to name in the report

- **Derived atoms:** Python reads the facts off the node and Rust only closes them. A callback in spirit, counted as `*:derived`. Native rational facts in Rust (`is_prime` needs care) are unbuilt.
- **Not ported in this family:** `value_units` on a non-atom node (`special.py:109`, `functions.py:409`) and `closed_units` (`relations.py:411`) still call Python's `units`.
- **A direct `Engine` caller** with no query on the stack stays on Python, `py:no-query`.
- **Conversion's reads:** rows cover `_CONST_BASIS`, not section 9's "whole vocabulary". Enough for this family; a later family may need the rest.
- **`complex-unbounded` covers `ComplexRootOf` only.** Other closed terms may also be slow in `complex(t)`; nothing measured that. Planner's ruling is pending.
- **Unbounded memo growth is unchecked:** each atom gets a new `Pattern` per query, so `engine._SPLIT`, keyed by clause-list id, sees more entries than under Python's shared `_CACHE`.
- **Shadow mode calls Python's template,** which fills `_CACHE`. The `atoms` mode is the real one.

## File:line map

| Topic | Where |
|---|---|
| Rust family | `rust-spike/slice/solver_rs/src/term/knowledge.rs`: `Rules::load`, `closure`, `expand`, `units`, `sorted_lits`, `unsubsumed` |
| Rust bindings | `term/py.rs`: `PyKnowledge`, `pattern`, `atom_units`, `units` |
| Atom rows | `term/table.rs`: `AtomRow`, `read_atoms`; `convert.py`: `_Walk.atom_rows`, `_CONSTANT` |
| Refusal | `convert.py`: `complex-unbounded` in `REASONS`, the check in `convert()` and in `closed()` |
| Wiring | `rust-spike/slice/knowledge_live.py`: `install`, `rust_units`, `_ask`, `_wrap`, `_compare`, `KnowledgeFault`, `COUNTS` |
| Compare driver | `rust-spike/slice/knowledge_fresh.py` (`--mode plain, atoms, shadow`) |
| Python source of truth | `knowledge/templates/atoms.py:35`, `:47`, `:51`; `_common.py:83` `const_value`, `:224` `Pattern`, `:340` `units`, `:185` `_unsubsumed`; `knowledge/rules.py:207`, `:270`, `:355`, `:383` |
| Seam in the engine | `engine.py:577` `clause_templates`, `:588` `complete`, `:626-650` pattern reads, `:2311` `_split`; `templates/registry.py:226` `clauses_for`; `sympy_api.py:480` `_ask` |
| Env | `. ~/sa-rust-ids-work/env.sh; export PYTHONPATH=$PWD:$W/sympy:$W/shim` from the clone root, then `cd rust-spike/slice` |
| Earlier map | `HANDOFF-sa-port-1.md` |

`.so` for fe85470: sha in `fresh2/so.sha`. Build: `sh rust-spike/slice/build_solver.sh`. The crate's offline format is unchanged; `convert.py` adds `atoms` and `n_atoms`, additive, and `PyTermTable` accepts tables without them. `complex-unbounded` is new in `REASONS` and also applies under the term shadow, so a corpus shadow run will now keep those queries.
