# Handoff, sa-port-81: component 5, step 5a, join fixed, landing runs owed again on the new source

Head: `port/5a` cb77f38 plus this file, on `rust-slice` d29e94b. Not landed. The evaluator hasn't been asked for. `HANDOFF-sa-port-79.md` has the setup, traps and cea574c's numbers, `HANDOFF-sa-port-77.md` the named differences, `HANDOFF-sa-port-75.md` the base map.

**cb77f38 changes `session.rs` and `test_session_limits.py`, so cea574c's suite, dev, fuzz and plant results don't carry over to landing.** On cb77f38 only `test_session_limits.py` ran, on orion, aarch64: 199 passed.

## Join: found, fixed, no answer shown to move
- **Platform or order: order.** The suite's joins are all `f(x)` with `f(x)`, same class name and repr, different class objects, because each `Function('f')` makes a new class and SymPy's cache hands back either. Two suite runs (`suite-cea574c` 76 in 12 tests, `joinlog` 1,025 in 11) share only `test_inconsistent_under_equality`. A cache clear between two `Function('f')` calls joins on orion, aarch64 (`joincase.py`). Not done: the 12 tests alone on pareto1, so "not platform" rests on the aarch64 case. The `test_zero_glue` pairs weren't logged, since they didn't join in the logged run; `f(x)` is inferred for those, and `g` is that module's function.
- **The object kept could differ.** On cea574c, 5 of 600 random formulas kept another class than Python's slot, all 5 through `compile_formula` directly (`joindiff.py`, 1,563 joins). Rust took the first object seen in conversion, Python the first passed to `node_base`. `assume_formula` and `literal_of` run `_ensure_atoms` first, so they never differed; `engine.py:684,732` (template and custom formulas) don't.
- **What reads it.** `wiring.py:209`, `kind == 'same'`: `a is not args[j]`, used by `_compiled_rows.py:1382`, `x**x`. I read the other `type(..) is` sites by rg: `wiring.py:207` needs `a == s[1]` against a constant, `_rows.py` is table time, `lra_bounds.py:251` is mpmath. That rg was on `type(x) is` forms; my wider `is` search hit docstrings and I didn't finish it, so this list may be incomplete.
- **No answer moved on cea574c.** `samediff.py` 500 formulas and `termdiff.py` 300 template-path terms with `Pow(a,a)` and `Pow(a,b)`: 0 differences in answers, clauses or kept objects. That's not a proof, so I fixed the mechanism.
- **Fix, cb77f38.** `nid_in_formula`: a second non-identical object for a node with no slot refuses the conversion before anything is emitted, and Python's compiler runs over the same table (`refuse:object`). `nid_of`: direct entries take the newest object until `node_base`. `nid_of_atom`: custom atoms don't choose it. `known` is unchanged.
- **Shown:** the 122 new `kept:` cases, on the old build 9 of 199 tests failed (8 `kept:` cases, 6 formula plus `kept:two-steps` and `kept:then-node-base`, and `test_counters_fired` by `KeyError`, since the old build has no `refuse:object`); on the new one, none. `joindiff.py` on the new build: 0 of 600.
- **Stands:** named difference 1, `mine(True)` for `mine(1.0)`. A custom atom shows `objs[nid]`, and Python keeps the atom's own `expr`. It reaches a registered custom function's `atom.expr` only for objects `==` across classes. Backend PR list unless the evaluator shows otherwise.
- **Not measured:** how often `refuse:object` fires on dev, fuzz and suite. Report it. It costs speed, not answers, but templates that build `==` terms twice could make it common.

Scripts: `~/sa-rust-ids-work/sa-port-81/join-scripts/`. Run from the clone with `PYTHONPATH=$PWD:$W/sympy:$W/shim:$PWD/rust-spike/slice`.

## Plant runs, read 17:18 UTC, on cea574c
Still running then, no `ALL.DONE` (the brief said it had ended). pareto1 `~/sp19/sa-rust-ids-work/sa-port-79/plant-runs/`, order s466, s425, c166, c393, c444. Leave it to finish; `compile.rs` is unchanged by cb77f38, so its fire counts stand as reach.

| plant | dev | fuzz | suite |
|---|---|---|---|
| s425-have | fired 1,694, DIFFER | fired 65,376, DIFFER | fired 1,089,934, 0 changed by id |
| s466-impl | fired 0, MATCH | fired 0, MATCH | fired 796,489, **25 changed** |
| c166-tie | 0, MATCH | 0, MATCH | not finished |
| c393-key | 0, MATCH | 0, MATCH | not finished |
| c444-true | 0, MATCH | 0, MATCH | not finished |

- **`session.rs`: caught.** s425-have's DIFFER is on the stream and end state only: dev `answer_diff` 0, `end_diff` 172, `stream_diff` 173. The suite doesn't notice this plant at all.
- **`compile.rs`: nothing fired on dev or fuzz, so bar 3 isn't met there.** All three plants are on lines those workloads don't reach. **Write a plant on a line dev reaches**, as `mkplants.py` does, with a fire log, and show it caught. The suite columns only give reach.
- **`_link`: caught by the suite, no comparison.** s466-impl changes 25 ids, `test_wide_derived.py` 13 and `test_stress_wide.py` 12, so no direct test is owed by the brief's condition. Name the gap: dev and fuzz never reach `_link`'s implication clauses, so nothing compares them Python-against-Rust; only the suite's own assertions do.
- **PR 334's tie:** 0 fires on dev and fuzz. Read `c166-tie-suite.fired` when it ends.
- `NAME-suite.session.json` read all zeros for s466-impl while its fire log has 796,489. Per-test crossings are in the rows, so don't read counts from that file.

## Found, not fixed
`table.slots[v]` past the end panics on Rust (`PanicException`, a BaseException) where Python raises `IndexError`. `_Slots.__getitem__`, session_live.py:117. `relations.py:1788` reads by cursor and I didn't read whether it can pass the end. Give the evaluator the code, not this conclusion; backend PR list unless it can move an answer.

## Open, in order
1. Sync cb77f38 to pareto0 and pareto1 under your own tree, with your own job script copied from `~/sp19/job79.sh`, and build x86-64. Mind the `git archive` trap in `HANDOFF-sa-port-79.md`.
2. Suite by id against `suite-cea574c` and `pr328-check/suite-rust`, then dev and fuzz. Report `refuse:object`, `join` and handlers. The join count will vary run to run; it depends on worker order.
3. Plants on cb77f38 through `--so`: s425-have and a new reached `compile.rs` plant, on dev and fuzz. Rerun s466-impl's suite column only if you keep citing it for landing.
4. `var-off`, not started: `_var`, session_live.py:232, is global. Add `var-off:PRED` beside it, with `SLICE_SESSION_PLANT` at :307, and see which predicates reach and which go uncaught. If that doesn't settle it, say it's still unexplained. Code in `session_live.py` is on the run's path, so do this before item 2 if you do it at all.
5. Status: progress with the one-line SendMessage for the evaluator (brief's step 5), then `results/port-5a.md`, rebase, land, report. Quiet-lease timing after landing. Sizing of 5b and 5c if not yet reported.
6. Report also: sa-port-79's two errors, `rust_plugin.py` 3 lines, `compile.py` and `run_live.sh` changed, crossings, what wasn't run, the named differences.

## Errors of mine
None in the tree. My first `kept:` run looked like a pass only because `_ids()` is a fixed list and the new cases weren't in it; I caught that before relying on it. Any new case in `_cases()` has to go in `_ids()` too.
