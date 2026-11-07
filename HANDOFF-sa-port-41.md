# Handoff: sa-port-41, component 1b (LRA constants), issue 323

Written 2026-11-07 12:04 UTC, at the context note.

## State

**Nothing is ported. No Rust or Python source changed, nothing was built and nothing was run.** `port/1b` is `origin/rust-slice` 69639da plus this file. None of the bar's 5 items has been started. `_Move` and the transfer are still in place.

This session spent its budget on reading: `constfield.py` and `lra_cert.py` whole, about half of `lra.py`, and part of `lra.rs`. Don't repeat that. The sections below hold what came out of it. Reread a function only when you're porting that function.

Everything under "Design" comes from reading and has never run.

**Lazy reads:** `origin/port/lazy` was at 79e59f4 at 12:04 UTC, 8 commits ahead of rust-slice and not landed. It changes `term/table.rs`, `term/py.rs`, `term/algebra.rs`, `convert.py` and the shadow tools. I read only its log and diffstat. The arithmetic and the core don't depend on it. Only `_from_sympy` on rows does, so check its state again before starting that part.

## Design

1. **`Num` replaces `Rat` in the core.** `enum Num { Q(Rat), E(Rc<Elem>) }`, with fallible arithmetic returning `Result<_, CfErr>`, where `CfErr` is Undecided, TooLarge, ZeroDiv, Arithmetic or Py(PyErr).
2. **`lra.rs` location.** `solver_rs/src/lib.rs:11` includes `rust-spike/lra/port/src/lra.rs` by `#[path]`, and the old `lra-replay` spike crate builds the same file (9 `Rat` sites in its `main.rs`). Recommendation, not yet done: move the file into `solver_rs/src/` and leave the spike its frozen copy, rather than making the spike understand `Num`. `term/rat.rs` also refers to `lra/port`.
3. **Python `Element` stays the format at the boundary for now.** A payload's `Element` is converted on the way in by reading `_n` and `_d`. Models and the dump convert back with `Element._new`. So tests and the adapter keep seeing the same class, and `type(x) is Element` keeps working.
4. **One constant registry until component 4: Python's `_CONSTANTS` (constfield.py:731).** Rust caches rows by index on first sight, so the indices can't diverge. Inventory section 5, item 1 (PORT-INVENTORY.md:172) wants it per query at component 5. Python's is global with history; name that in the report.
5. **Enclosures.** Native in Rust for `pi`, `E` and `("root", r, b)` keys, ported exactly so the integers match (constfield.py:749-820). Only when `_enclose` is still the module's own, since a test can replace it. Anything else calls `Constant.enclose(prec)` (:718), which is R9's permanent callback and also keeps the `lo <= hi` check. A callback's exception isn't Undecided, so it propagates as Python's does.
6. **Limits.** `PREC_START`, `PREC_CAP`, `MAX_*` are module globals and `lra_cert.limits()` says they may change. Plan: reread them from the module at hook entry once a session has constants. Whether tests monkeypatch them wasn't checked: `rg` tests/test_lra_constants.py and tests/test_constfield.py.
7. **Gcd.** Port `_inner_gcd` (:510) with its shortcuts and Euclid (:483). For `_sympy_inner_gcd` (:577) keep `_denominators`' TooLarge first (:537), then a Rust exact gcd, for example a primitive PRS. The monic gcd and the cofactors are unique, so the result should equal SymPy's. Show that by differential test. At install also patch `constfield._sympy_inner_gcd`, so the adapter's Python arithmetic stops importing `sympy.polys`.
8. **`_from_sympy` on rows: open, and may be a question.** `lra_adapter.py:213` calls `from_sympy(Mul(*closed))`, a derived term that isn't in any table, and the adapter stays Python until 4. `backend.py` and `rust_plugin.py` have no conversion call, so no per-query table seems to exist on the engine path (those two files searched, nothing wider). `TermRow` (`term/table.rs:102`) wasn't read. Likely shape: a Rust walker behind a small reader, on the live object until 4 and on rows after that, with `radical` and `_generic` calling Python's so they register in the one registry. If rows can't serve the engine path, say so and name it, or ask the planner. Don't let this block the rest.
9. **`lra_cert`: proposed choice, port all of it.** `CertAtoms` and `certify` (lra_cert.py:102-252) are small and pure, and `values` only adds lines 209-214. So `_branch`, `certified` and `certified_with` can all answer from the same Rust port, with `rational_values` (lra.py, just before `_certificate`) beside them, and no test needs to be kept on Python for this. Keep `_certificate`'s memo key and `except Exception` giving `(False, None)` (lra.py:448-465). Unproven until built. Fall back to the kept-on-Python list only if it turns out large.
10. **Private reads.** Per the ruling, served read-only from the dump with no Python theory behind them. `_view` (lra_backend.py:299) currently builds a real theory object and has to stop doing that. Tests that patch `_certificate` or need a real theory go on the kept-on-Python list.

**A subagent was planned and not launched:** `constfield.rs` plus `lra_cert.rs` plus a differential test against Python is self-contained and suits one, in its own worktree so the builds don't collide. Bridge: `sa_solver.cf_op(name, a, b)` taking and returning Python numbers. Compare `(n, d)` structurally and the exception type. Plant a bug to show the test fires. It would save your context, since those two files are the bulk of the reading.

## What will bite

- **Partial state on give-up.** lra.py's comment says state after Undecided is never read again, but the state comparison may read it at session end. Check that first. If it does, Rust has to raise at the same point with the same writes done. `_update` shows the shape: with `_fields` on it computes everything, then writes (lra.py:837-851). The note at `_pivot` says the same.
- **Tuple comparison on bounds** (`up <= b`, `lo == up == (c, _ZERO)`): first `is`/`==` element by element, then the order test on the first difference. `==` can raise Undecided or answer False without evaluating (constfield.py:1209-1224). Formal equality returns True without raising, which covers the `is` shortcut.
- **Fraction with Element is reflected:** `F - e` is `(-e) + F` (:1039), `F / e` is `e._inverse() * F` (:1098). `e - F` is `e + (-F)`.
- **`x / x`** still checks the divisor (:1093). `_inverse` checks too (:1074).
- **`_nonzero` skips evaluation for one transcendental constant** (:1141) and differs from `sign` (:1150).
- **Identity on `m is _ONE and k is _ZERO`:** lra.py:739-740, :893, :936. `lra_backend._state`'s `fast` maps it today.
- **`propagate` skips an Undecided per implication and goes on** (lra.py:621-626, :632-635); every other path gives up.
- **`math.floor(k)` failing in `_register_integral` is swallowed** (lra.py:735-738). The atom stays with the raw offset.
- **`_fields` is set in `_lin` even if that coefficient later cancels,** and in `_register_atom` for the constant (lra.py:662-663, :690-691, :722-723).
- **`engine.py:1906`** turns any exception from Rust in a complete check into a quiet unknown. Count such catches. `TransferFailed` was a BaseException for this reason and goes with the transfer.
- **`gave_up` is hard-wired off today:** lra_backend.py:74 and :89, lra_py.rs:201 (`"gave_up", 0`).

## File map

| What | Where |
|---|---|
| Transfer to delete | `lra_backend.py`: `TransferFailed` :33, `counts`/`moves` :38-40, `_Move` :43, `_once`/`_Replay` :47-65, raises :191, :207, :238, `_move` :307, every `core is None` branch :103-175, `_state` :259 stays for the dump. Then `move_every_call.py`, `identity_rule.py`'s moves. Users not searched: `rg '_Move\|_move\|moves\|TransferFailed' rust-spike/slice` |
| Binding | `solver_rs/src/lra_py.rs`: `rat_of` :11, `pairs_of` :22, `frac` :53, hooks :106-168, `dump` :208 |
| Rust core | `rust-spike/lra/port/src/lra.rs`: types :97-170, `Theory` :234. **:330-1141 not read** |
| `Rat` API | `rust-spike/lra/port/src/rat.rs`: `S(i64,i64)`/`B`, `norm_big` :89, ops :137-280, `Ord` :281, `Hash` :303 |
| Python theory | `lra.py`: `_is_int`, `_floor` from :287, `_within_cert` :324, certificate :417-475, `_slack` :517, hooks :547-644, `_register_atom` :646, `_lin` :681, `_var_of_form` :701, `_register_integral` :719, levels :749, asserts :781-851, integrality :857-915, `_branch` :917. **:975-1270 not read** |
| constfield | polys :198-657, `_ieval` :671, `Constant` :694, enclosures :749-820, `_make` :854, `Element` :906 (arithmetic :1004-1116, signs :1134-1207, `==` :1209, floor :1249, `is_integer` :1261), `pi_laurent` :1325, `_from_sympy` :1375, `_generic` :1415 |
| Inventory | port order :371-396, 1b row :382, registry :172, R9 :143 |

## Next steps, in order

1. Check state after give-up in the comparison (`slice/state.py`, `harness/state.py`), and `rg` tests for limit monkeypatching.
2. `constfield.rs` and `lra_cert.rs` with the differential test. Subagent recommended.
3. `Num` through `lra.rs` after reading :330-1141 against lra.py:975-1270. Add give-up, `_fields`, the memo, the certificate.
4. Binding: payload and dump conversion, stats' `gave_up`. Delete the transfer, and tell the planner and architect first if anything suggests it must outlive 1b.
5. `_from_sympy`, per design item 8.
6. The bar on pareto0 or pareto1, detached. Rebase first; rerun if rust-slice moved source. Then push without force and report.

## Must stay in every report

THE DROP, PLANTED PORT BUGS, QUIET COUNTER, the moved suite sessions and what now covers them, `order:_rows` not caught, and 1a's not-run list: all in the brief under CARRY FROM 1a, unchanged and not rerun here. Keep the object rule and the transfer's results from `results/port-1a.md`.
