# Handoff: sa-port-6 to the next session on component 1a (issue 323)

**Nothing is ported.** No Rust or Python changed, nothing was built, no test or workload was run. The session went on reading and hit its context note at 153k. This file is the whole output. 0 of the 32 runtime modules moved, and none of "What each step is held to" has been attempted. Everything below comes from reading at ccb061d, so treat it as a plan with no run behind it.

Read the brief first: `~/.local/state/agent/briefs/sa-port-6-20261107T073350Z.txt`. Its terms still apply. Same clone (`~/dev/sa-port-6`), same branch (`port/1a`).

**To save context:** the reading cost was `lra.py`, `lra.rs`, `live.py` and `lib.rs` read whole. Use the map below and read only the parts you're changing.

## Proposed design (mine, not a ruling)

1. **One source for the core.** Load `rust-spike/lra/port/src/{lra,rat}.rs` into `slice/solver_rs` with `#[path]`, so the replay binary and the crate share it. Add `num-bigint`, `num-integer`, `num-traits` and pyo3's `num-bigint` feature. All three are in `~/.cargo/registry` (0.4.8, 0.1.47, 0.2.19), along with pyo3 0.30.1. No build has tried this.
2. **A pyclass holding either the Rust core or a real Python `LRATheory`.** It has the same method names as `LRATheory`. Attach it through the existing `PyTheory` hooks first, which needs no solver change.
3. **Python subclass named `LRATheory`, in a new `slice/` module.** `backend.install()` and `rust_plugin.py` patch `lra.LRATheory` and `lra_adapter.LRATheory` to it. It has to be a Python subclass for two reasons: `live.py:174` sets wrappers on the class, and the stream lines hold `cls.__name__` (`live.py:53`, `:204`), so any other name makes every stream differ.
4. **Refusal by state transfer, not replay.** Any payload that isn't plainly rational moves the session to Python before that payload is handled: a non-`Fraction` number after `num()` (an `Element`), a `num()` that raises, a bad literal, a literal registered twice, an odd shape. The core dumps its full state into a new real `LRATheory`, and Python then handles the payload, so its exceptions and partial effects are Python's own. There's no log, so rational sessions pay nothing, and the same dump serves the state comparison. Count these per session, by reason.
   - **Open question for the planner:** the brief says "queries ... stay on Python". This moves a *session* mid-way, so rational work before the move runs on Rust. I think it meets the rule, because answers and state must match either way, but it hasn't been ruled on.
   - The transfer itself is the riskiest new code. Test it by moving at every call index of a session and comparing with Python.
5. **Then measure a native path.** After the suite is green, add a variant in `PyTheory` that calls the core without Python method dispatch. It must not skip a wrapper: `lib.rs:105` says hooks are looked up per call so a wrapped method sees the same calls. Report the cost with and without it, which is what the brief means by the boundary's cost and shape for siblings.

## What `lra.rs` lacks against today's `lra.py`

I read both side by side. Simplex, pivot, branch, concrete, check, propagate and the trail matched as far as I could tell by reading. `_assert_integral` computes its verdict before the push in Rust and after it in Python, which is harmless because the verdict doesn't read `_int_lits`. Missing or different:

| Gap | Where |
|---|---|
| `PySet` for `_dirty`: replace with ascending order (`sorted`, `lra.py:614`) | `lra.rs:131-221`, `:329`, `:1104-1116` |
| **`lra.rs` mutants 6 and 7 are defined against `PySet` (`:1108-1111`).** Mutant 6 becomes the correct behaviour, so both need redefining. These numbers are not the solver mutants of the same number. | `lra.rs:1105-1114` |
| `eager`: Rust is always eager | `lra.rs:578`; `lra.py:348`, `:580` |
| `branched_rational`, set when branching with no constants | `lra.py:988-989`; absent in `lra.rs:777-778` |
| `gave_up`, `undecidable`, `certified`, `certified_with`, `rational_values`, `stats` as a dict with `gave_up` | `lra.py:410-446`; `lra.rs:241` |
| `ValueError` on a non-positive or repeated literal | `lra.py:647-651` |
| `pop_level` on an empty stack panics in Rust; Python raises `IndexError` | `lra.rs:531` |
| **`BRANCH_BUDGET` is a Rust const, and tests patch `lra.BRANCH_BUDGET`** at about 15 sites. Read it from the module per check, or those tests test nothing. | `lra.rs:61`, `:1017`; `tests/test_lra_exhaustion.py:82` on, `tests/test_lra_integers.py:185`, `:237`, `:351` |
| `atoms`, `ints`, `ground`, `slack_of` are `HashMap`s. The dump needs insertion order, so keep it. Never iterate these maps: that's the hash-order rule. | `lra.rs:306-325` |
| The transfer must restore `_ONE` and `_ZERO` by identity for `m is _ONE` | `lra.py:893`, `:936`, `:739` |

**Mapping terms to ids:** hold a Python dict from term to id, so that equality and hash are exactly what `_var_of` uses, and keep the first-seen object for model keys (`lra.py:1174`). Terms get an id in payload order, including zero coefficients (`lra.py:694`). Term ids aren't variable ids once slacks exist.

**Payload shapes:** `(terms, constant, strict, equality)`, with `Negated` wrappers or `Integral(terms, offset)`. `terms` is a dict or an iterable of pairs (`lra.py:652-659`, `:685`). `num` is at `constfield.py:827`.

## `lra_cert.py`: by reading, the engine never reaches it on a rational session

`_certificate` is called from `_branch` only under `if fields` (`lra.py:943-945`, `:953-955`). The engine's reads of the theory are `gave_up` and `exhausted` (`engine.py:2270-2285`), plus `undecidable` in `ref.py:516-518`. Only tests read `certified` (`test_lra.py`, `test_lra_exhaustion.py`, `test_lra_fuzz.py`, `test_switched_glue.py`, `test_unrelated_relation.py`).

So on the rational core this port adds no engine reach for `lra_cert`, and **the report must say that** rather than count the module as running on Rust. My suggestion is a Rust port of the rational path of `certify` (`lra_cert.py:125-185`, `:188-252`, big ints, limits read from `limits()` per call), tested against Python on random rational theories. Until then, answer `certified` from a transferred Python copy. I didn't read `constfield.pi_laurent`, which `update` calls on `m` and `k` (`:156`); check what it gives for a `Fraction`.

## Traps in the tests and tools

- **Private reads in tests.** `_rows`, `_vq`, `_vd`, `_cols`, `_lo`, `_up`, `_lo_r`, `_up_r`, `_trail`, `_int_lits`: `test_lra.py:511`, `:525`; `test_lra_integers.py:165`, `:252`, `:254`; `test_lra_constant_coefficients.py:268-270`. Choose between a read-only view from the dump and adding them to kept-on-Python. Either changes what the numbers mean, so name it in the report like the `_n_conflicts` shim.
- **`t.exhausted = False`** at `test_lra_exhaustion.py:64` needs a setter.
- **`monkeypatch.setattr(LRATheory, "_certificate", ...)`** at `test_lra_exhaustion.py:282` patches a private method on whichever class the name holds. Check it still does what the test intends.
- **`theory_models`** has no reader in `satassume/` other than its own definition, by rg: tests only (`test_lra_adapter.py:390`, `test_lra_fuzz.py:188`, `test_transfer.py:192`). A lazy model is possible later. But `state.py`'s dump and `live.py`'s `show` render it, so it must be a dict of real `Fraction`s when read. Build plain dicts first.
- **`live.py` compares solver state only.** "State matches" for this step needs an added theory dump per session: a canonical form of `_key`, bounds, values, rows in insertion order, atoms, `_dirty`. `_rows`' outer order and `_cols`' order have no effect (`lra.rs:4-8`), so compare those as sets, or sorted.
- **ENV TRAP in the brief:** `run5_harness.sh`, `run-audit.sh`, `run6_counts.sh` still use the old path. Fix them before use.

## Planted bugs

- **The brief's 2, 5, 6, 7, 9 are the solver mutants** in `slice/mutate_slice.py` (`M`, near the top), not `LRA_MUT` in `lra.rs`. Rerun them through `slice/mutate_live.py` with LRA on Rust.
- **The 10 boundary mutants with no real-engine catch** (`results/step4-gate.md`, "Mutants"): 11, 26, 33, 34 (API only); 27, 29, 31 (nested only); 17, 18, 32 (API and nested). The tool is `slice/mutate_boundary.py`, and `--suite` is the column never run.
- **Plant new ones in the port's own boundary too:** payload conversion, the transfer, term ids, model rendering.

## Order I'd follow

1. Core gaps above, with a test of `_dirty` order, then build.
2. Pyclass, transfer, Python subclass, patch points.
3. `tests/test_lra*.py`, then `real_theory_fuzz` and `test_solver_real_theories`.
4. Theory dump in `live.py`; `run_live.sh` on dev and fuzz.
5. `run_suite.sh` with `PYTEST_N="-n 4"` or less, compared by test id with 5,961 / 77 / 46.
6. History and hash-seed runs (`run_history.sh`, `historycmp.py`).
7. Mutants, then native path and timing on a quiet pareto1 lease.
8. Rebase, push to `rust-slice` without force, report.

## File:line map

| Topic | Where |
|---|---|
| Theory trait | `slice/solver_rs/src/theory.rs` |
| Hooks over a Python object | `solver_rs/src/lib.rs:107` struct, `:138` impl, `:105` lookup note |
| Solver pyclass, attach, register, GC | `lib.rs:207`, `:358`, `:370`, `:221` |
| Solver's theory calls | `solver_rs/src/solver.rs:1369` attach, `:1407` register, `:1441` sync, `:1601` check |
| Rational core | `lra/port/src/lra.rs:303` struct, `:471` register, `:556` assert, `:730` branch, `:800` simplex, `:1013` check, `:1091` propagate |
| Rationals | `lra/port/src/rat.rs:11` |
| Replay binary that shares the core | `lra/port/src/main.rs` |
| Python theory | `theories/lra/lra.py:339` class, `:348` state, `:545` register, `:553` assert, `:599` propagate, `:917` branch, `:1176` check |
| Certificate | `theories/lra/lra_cert.py:102`, `:188` |
| Adapter, stays Python | `lra_adapter.py:125` import, `:467` construct, `:486`, `:518`, `:543` register; `relations.py:445` |
| Engine reads | `engine.py:2270-2285`; `ref.py:516-518` |
| Patch points | `slice/backend.py:34`; `slice/rust_plugin.py:45-65` |
| Comparison | `slice/live.py:174` hooks, `:42` show; `slice/livecmp.py`; `slice/state.py`; `slice/run_live.sh`; `slice/run_suite.sh`; `slice/boundary.py` |
| Last checks | `slice/results/pr328-check.md`; `slice/results/step4-gate.md:83` |
| Earlier map | `HANDOFF-sa-port-1.md` |
