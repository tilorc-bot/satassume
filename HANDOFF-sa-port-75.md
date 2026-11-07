# Handoff, sa-port-75: component 5, step 5a, first version

Head: `port/5a`, on `rust-slice` d29e94b. Not landed. Output: `~/sa-rust-ids-work/sa-port-75/first/`, on orion (aarch64).

## File map
- `rust-spike/slice/solver_rs/src/compile.rs`: `compile.py` over ids, no PyO3. `Cx` :46 is the old `table`, `emit`, `dv`. `def_of` :132 (`_def`, abs tie at `set_order`), `compile` :176, `or_cnf` :329, `literal` :460.
- `rust-spike/slice/solver_rs/src/session.rs`: `SessionRules`, `St` (`VarTable`, `base`, `defvars`, `_dv`, `_dv_node`), `SessionCore`. Crossing counters at `NAMES`. Read with rg; line numbers here are not exact.
- `rust-spike/slice/session_live.py`: the shell. Views `_Custom`, `_BaseOf`, `_Base`, `_Slots`, `TableView`; `_node`, `_core_visit`, `_var`; `_compile_formula` reads `assume_formula`'s selector from the closure (`__closure__[0]`, fragile, name it); `PLANT`; `SESSION_REPORT`; `from_env`.
- Wiring: `live.py` and `rust_plugin.py` call `session_live.from_env()` after `lra_live`. `SLICE_SESSION=py` keeps it off.
- Python side still in use: `engine.py:572-811` discovery, `:1155` `literal_of` body, `:506` `query_lit`, `:539` `emit`, `:614-662` patterns (through views), `rules.def_implications` (callback, memoized in Rust).

## Limits to check, each could move an answer
1. Formula depth: Python raises `RecursionError` near its frame limit, and the quiet handlers can read that as unknown. Rust converts to depth 3000 and has no matching limit. No test run.
2. Errors move earlier: an unhashable `expr` or a non-string `pred` raises at conversion, before clauses Python would have emitted first.
3. `objs[nid]` is the first object seen at the boundary, and Python's slots hold the first passed to `node_base`. They differ only for objects `==` across classes. `join` counts that: 0 on dev.
4. `rs:def_implications` and `rs:neg_shared` are 0 on dev, so `_link`'s implication clauses and the `*unit` needs had no comparison there. Fuzz reach was not read. `tests/test_wide_derived.py` targets these.
5. `Cx::true_var` uses an unsafe pointer into the `RefCell`; replace it.
