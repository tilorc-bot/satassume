# Handoff: sa-port-42, component 1b (LRA constants), issue 323

Written 2026-11-07 12:14 UTC, at the context note. Replaces HANDOFF-sa-port-41.md as the place to start; its "What will bite" section is still useful and its Design items 1, 3-8, 10 still stand except as corrected here.

## State

**Nothing is ported in the sense of the brief, and nothing new has compiled or run.** `port/1b` still builds 1a, because `solver_rs/src/lib.rs` still includes `lra/port/src/lra.rs`.

Written, never compiled: `rust-spike/slice/solver_rs/src/lra.rs`, the whole theory over `Num`. It needs `constfield.rs` and `lra_cert.rs`, which don't exist on this branch.

None of the bar's 5 items has started. The transfer (`_Move`, `_move`, `TransferFailed`) is still in place. Nothing suggests it has to outlive 1b.

## The subagent's worktree: check this first

I launched a subagent at about 12:06 UTC for `constfield.rs`, `lra_cert.rs` and `test_cf_diff.py`, in the worktree `~/sa-rust-ids-work/sa-port-42/cf`, local branch `port/1b-cf`, notes meant for `~/sa-rust-ids-work/sa-port-42/cf-out/notes.md`.

**At 12:13 UTC it had no commits, no uncommitted files in that worktree and no `cf-out`. It may or may not survive this session's end, and I have no result from it.** Nothing about that port is known. Run `git -C ~/sa-rust-ids-work/sa-port-42/cf log --oneline -5` and read its notes. If it stopped short, take over its commits or redo that part. Its branch is local to this clone and isn't pushed.

The interface it was told to provide, which `lra.rs` codes against:
`CfErr {Undecided, TooLarge, ZeroDiv, Arithmetic, Py}` with `is_undecided()` and `From<CfErr> for PyErr`; `Num {Q(Rat), E(Rc<Elem>)}` with `zero one add sub mul div neg inverse formally_zero sign nonzero py_eq lt le floor ceil is_integer from_py to_py`, floor and ceil returning an integer `Rat`; structural `Eq + Hash`; `refresh_limits()`; bridges `sa_solver.cf_op`, `sa_solver.cf_inner_gcd`.

## Left to write in lra.rs

`lra.rs` names three things nobody has defined; the subagent wasn't told these names:
- `crate::lra_cert::CertMemo` (`Default`; the field `Theory.cert`, :313): `_cert` and `_cagg`.
- `crate::lra_cert::Y`, and `crate::lra_cert::within(&Num, &Y) -> R<bool>` (:813, :901-907).
- `Theory::certificate(values) -> R<(bool, Option<Y>)>`, not written. Port lra.py:448-473: memo key `(len(atoms), len(ints), len(slack_of), len(key), limits())`, `except Exception` gives `(False, None)`, `certify` over `len(key) - len(rows)`. It needs atoms and ints in `reg_order`. Since it swallows every exception, `cert_skips`' `?` only sees `within`'s.

Also `rational_values` (lra.py:434), and `certified`, `certified_with` answered from it. **The choice proposed, not yet made or shown: port all of `lra_cert`, so no test is kept on Python for this.** Name it in the report.

## Corrections to the earlier design

1. **`_rows`' outer order can move an answer once constants run.** `lra.py:1016` walks `_rows` in dict order and skips only `b > leave`, so the order decides which comparison runs and whether it raises `Undecided`. The old claim in `lra.rs` that only the minimum matters holds for rationals only. Rust now keeps `row_order`: a pivot deletes `b`, then appends `j`. **`state.py:238` (`lra_text`) still sorts this order away: change it to `list(get("_rows").items())`-style, keeping the order, and have `dump` emit `row_order`.** That changes a shared file (name it in the report) and is the first real evidence on `order:_rows`. Until a run shows it, report `order:_rows` as not caught.
2. **Give-up state is read.** `lra_text` reads `_fields`, `gave_up`, `_int_memo` and the partial state at session end (`state.py:221-248`), so writes before a raise must match. That's why `lra.rs` follows Python's order. `_int_memo` is compared too, by repr.
3. **Python builds all six ground truths before indexing** (lra.py:668): any of them can raise, whichever `kind` is. Done in `register_inner`.
4. **`_assert_integral` appends to `_int_lits` before the verdict** (lra.py:862-864), the reverse of the old Rust. Done.
5. **`_simplex`'s entering loop skips `j > enter` before reading `a > 0`** (lra.py:1032-1034), and the leaving loop doesn't stop at the first violation. Done.
6. **One path, not two.** `lra.rs` uses Python's compute-then-commit `_pivot` and `_update` for rationals too. By reading the results are the same as `_pivot_rational`; not shown. Rationals get slower by an unmeasured amount. Timing isn't on the bar.
7. **Unverified assumption:** `lra.rs` writes `a > b` as `b.lt(a)` and `a >= b` as `b.le(a)`, assuming `_cmp` is antisymmetric including which exception it raises. Read `constfield.py:1191`, or use `gt`/`ge` from `Num` if the subagent added them.

## What's left, in order

1. Settle `constfield.rs`, `lra_cert.rs` and the differential test, with a planted bug firing.
2. Add the certificate glue above. In `lib.rs` add the `mod`s and replace the `#[path]` `lra` with `mod lra;` (keep `rat`'s `#[path]`; `lra/port` keeps its frozen copy of `lra.rs`). Compile. Remember `lra.rs:10-11` imports both.
3. `lra_py.rs` (`rat_of` :11, `pairs_of` :22, `frac` :53, hooks :106-168, `dump` :208): `Num::from_py`, `to_py`; hooks return `PyResult` via `CfErr`, `check` returns None when gave up; `gave_up` no-ops in push and pop *before* the IndexError check (lra.py:750, :756); add getter `gave_up`, method `give_up()`, `set_fields()`, `touch(pairs) -> bool` (it now takes pairs and runs `_lin`); stats `gave_up` real (today hard-wired at :201); dump adds `fields`, `gave_up`, `int_memo`, `row_order` order for `rows`, and `forms_order` replaces the `forms.sort_by` at :298. `refresh_limits()` at hook entry when `t.fields`.
4. `lra_backend.py`, delete: `TransferFailed` :33, `moves` and `counts["moved"]` :38-40, `_Move` :43, `_once` and `_Replay` :47-65, `rebuilt`, the raises :191, :207, :238, `_move` :307, `_view`, and every `core is None` branch :103-175.
   - `register_atom`: `if core.gave_up: return` first (lra.py:546), then the literal checks, all in `try ... except Undecided: core.give_up()`.
   - `_pairs`: `core.set_fields()` when `type(c) is not Fraction`, in order, before any later raise. A raising constant: `if core.touch(ids): raise`, else return, because `_lin` gave up first.
   - `_state`'s `fast` must guard by type: `type(m) is Fraction and m == 1 and type(k) is Fraction and not k`. An Element's `==` can raise.
   - `gave_up` becomes a property. `__getattr__` serves `_STATE` plus `_fields`, `_int_memo` read-only from `_state()`, with no theory behind it (a test-plugin shim; keep naming it). `_certificate`, `certified`, `certified_with`, `rational_values` go to the core. `_fields` etc. leave `__init__`. Tests that patch `_certificate` or need a real theory go on the kept-on-Python list.
5. Transfer's other users: `rust_plugin.py:134-136, :161-162` (`lb.moves`, `lb.counts`), `test_lra_raises.py:164-197`, `move_every_call.py`, `identity_rule.py`'s moves, `dump_mutants.py:168,193`, `except_probe.py:59-62`, `port_mutants.py:63-68`, `p1/p1_move.sh`, `p1/p1_landing.sh:27-33`, `p1/p1_ground.sh:9,17`, `p1/p1_fresh.sh:19`. Not all were read: `rg '_Move|_move\b|\.moves|TransferFailed|move_every_call' rust-spike tests`. Keep their results (below) in the report.
6. At install patch `constfield._sympy_inner_gcd` with the Rust one.
7. `_from_sympy`, per sa-port-41's Design item 8: still open, may be a question. `lra_adapter.py:213, :243, :262` call `from_sympy` on derived terms, and no per-query table exists on the engine path as far as read. Check lazy reads first: `origin/port/lazy` was 1724b7e at 12:13 UTC, not landed; `origin/rust-slice` was 69639da.
8. The bar on pareto0 or pareto1, detached. Rebase first; rerun if rust-slice moved source. Push without force. Report.

## File map

| What | Where |
|---|---|
| New core | `solver_rs/src/lra.rs`: helpers `t_*` :~80, `Theory` :~255, `lin` :~450, `register_inner` :~496, `int_verdict` :749, `branch` :809, `cert_skips` :901, `simplex` :911, `pivot` :1018, `check` :1144, `propagate` :1237, `implied` at the end |
| Frozen rational copy | `rust-spike/lra/port/src/lra.rs`, left as is; `rat.rs` still shared |
| Binding | `solver_rs/src/lra_py.rs`, map above |
| Python theory | `satassume/theories/lra/lra.py`: helpers :287-326, certificate :417-473, hooks :545-644, `_register_atom` :646, `_branch` :917, `_simplex` :1010, `_pivot` :1110, `_check` :1176, `_implied` :1234 |
| constfield | `constfield.py`: outline by `rg -n '^(def\|class) \|^    def '`; `num` :827, `Element` :906, `__eq__` :1209, `_cmp` :1191 |
| State text | `rust-spike/slice/state.py:221-248` |
| Transfer | `rust-spike/slice/lra_backend.py`, map above |
| 1a's report | `rust-spike/slice/results/port-1a.md`: the object rule :54-61, sessions and moves :21-35 |
| Inventory | `rust-spike/PORT-INVENTORY.md`: port order :371-396, 1b row :382, registry :172, R9 :143 |

## Must stay in every report

THE DROP, PLANTED PORT BUGS, QUIET COUNTER, `order:_rows` not caught and 1a's not-run list: in the brief under CARRY FROM 1a, unchanged and not rerun here.

The transfer's results, to keep once it's gone: dev 113 Rust / 109 moved, fuzz 2,569 / 623, suite 42,661 / 2,697 moved in 239 tests, all natural moves at level 0; `identity_rule.py` 14,424 sequences, 344,304 answers, 0 differ (hook level, plain Fractions, moves at level 0). The object rule is `port-1a.md:54-61`.
