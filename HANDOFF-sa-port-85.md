# Handoff, sa-port-85: component 5, step 5b. Joins item done; the link and C2a designed, not written

Head: `port/5b`, on `rust-slice` bfac870. Not landed. Handed off at the context limit (141k), no blocker.

## Done
- **Item 1, joins:** `rust-spike/slice/results/port-5b-joins.md`. 1,041 joins in 19 tests, all `f(x)`-shape. Swing stated.
- Code: `join_log.py`, `join_summary.py`, `JOIN_HOOK`, `log_join` and `set_join_hook` in `session.rs`. They run at a `join` and nowhere else.

## Not done
Items 2 and 3: **no link or C2a code exists.** Everything below is design from reading. None of it has run.

## The link, as designed
**What it maps:** a session node's id to the current query's term id. Nodes live for a session and term ids for a query, and queries nest (`term_live.stack`), so the link can't be a fixed column.

1. **Resolve by the object passed.** `term_of(x)`: `SessionCore`'s node for `x` with no new node and no `join` tick (a quiet version of `known`, `session.rs:259`). If the memo holds `x` itself, hit. Otherwise call Python's `term_live.term_id(q, x, 'link')`, `term_live.py:269`: the one rule, including `type(q.objects[i]) is type(e)` at :274. So a join's second object gets its own answer, and `objs[n]`, which `nid_of` can overwrite at `session.rs:189`, is never what's read.
2. **It must not create a node.** `nid_of` chooses the slot's object, so calling it from the link could change numbering.
3. **Memo:** on the query's table, so it dies with the query: a new field on `PyTermTable` (`term/py.rs:92`), key `(session serial, nid)`, value `(object, TermId)`. Hit only if the object `is` `x`. Positive results only, since a later lazy row could turn a None into an id. `SessionCore` needs a serial; a pointer could alias.
4. **None is an ordinary answer, not a refusal.** No id, a kept query or `_Refused`: that read goes to Python's own function (`relations._is_number`, `euf_adapter.structural`, `getattr`). The link reads no row and no class row, so lazier rows and cached class rows don't touch it, which is the ruling. Row reads stay table calls made after the link.
5. **Counters:** `link:hit`, `link:resolved`, `link:none`, `link:no_table`, `link:second` (memo holds another object), added to `NAMES` at `session.rs:17`. Show each fires.
6. **Term to node:** not needed in C2a, since its methods hold objects. It arrives with C2b, where `_eq_links`' plan has derived ids. So **no plan is deleted in C2a**: `_eq_links` and `_eq_infinity` are called from `process` (`relations.py:917`) and `_interpret` (:1022), and neither moves here. Say so in the report.

**Tests owed:** a runtime plant `link-none`, every resolve returning None: dev and fuzz digests must still MATCH, which is the direct test of the ruling. A join case in both orders, pinning that the second object resolves on its own. Report `link:*` on dev, fuzz and suite, beside `session_live.py`'s header census.

## C2a, as designed
New `solver_rs/src/relations_core.rs`, pyfunctions `rel_*(rel, ...)`, registered at `lib.rs:570`. `session_live.install` (`session_live.py:279`) sets the `Relations` methods and its undo restores them; `SLICE_SESSION=py` leaves Python's. Reach `SessionCore` through `rel.session.table.core`. Make `var`, `emit`, `custom_get` and `shell` `pub(crate)`. Late-bind module attributes each call (`relations.relation_atom`, `_ext_atoms`, `sign`, `_is_number`), because `term_live` and `lra_live` replace them.

Python source, `satassume/relations.py`, in order:
- `_closed_extended_real` :1375: table flag `IS_RATIONAL` and `is_number_term` (`term/table.rs:66`, `term/relations.rs:12`), `Kind::NaN`, `engine.is_` by callback. Keep `v is False` and `v is None` as identity checks.
- `_order_sides` :1387: `s.var` before `s.emit`, as written.
- `_order_infinite` :1405: **`return` on `Undecided` comes after earlier `ensure` and `var` calls, and those effects must stay.** Fraction by `type(c) is Fraction`, `relations.sign` otherwise. Use a real Python set for `seen`, so `==` joins as Python's does.
- `_trichotomy` :1154: `custom_get`, not `.custom` views. `_atom_var`, `_note_sides`, `_atom_selector` and `_add_role` stay callbacks to `rel`.
- `_mention_number` :958 and `_link_integer` :1106: mostly callbacks; `s.var` and `s.emit` direct. `_fresh(inert=True)` takes a kwarg.

**Traps found while reading:**
- `ensure`'s set: `PySet::new` in Python's literal order, since `_discover` may read its order.
- `Session.ensure` and all of discovery stay Python and re-enter: **hold no table or `St` borrow across a callback.** Use `try_borrow` and raise `TermFault` on failure, so it can't become a quiet unknown at `engine.py:1906`.
- Callback exceptions (`Uninterpreted`, budget exceptions) must propagate unchanged, so don't blanket-wrap in `_guarded`. Only Rust's own extraction failures become `TermFault`.
- The `var-off` plant lives on Python's `_var` (`session_live.py:232`), so a direct Rust `var` bypasses it. Use new plants for the bar: one dropped clause each in `_order_sides`, `_order_infinite`, `_trichotomy`.
- `term_discard.py:40` lists journaled methods. Check whether moved methods need entries.

**What compares it:** `test_session_limits.py` shape (`_cases()` and `_ids()`, both needed), plus dev and fuzz digests. Add a `rel:*` counter per method and report reach. Neither dev nor fuzz reaches `compile`'s `Or` arm (5a), so name that again.

## Machines
- Own tree on pareto1: `~/sp19/dev/sa-port-85`, with `~/sp19/job85.sh` (environment) and `~/sp19/build85.sh`. Update the tree with `git fetch` and `reset --hard origin/port/5b`, then rebuild. Copies in `~/sa-rust-ids-work/sa-port-85/`.
- Run: `setsid nohup machine run pareto1 --shared --wait 4h -r WHY -- bash -lc 'cd ~/sp19 && bash job85.sh ~/sp19/JOB.sh'`. Template `joinjob.sh`. The suite takes under 2 minutes at `-n 8` on a quiet pareto1. The tree has no pareto0 copy, and sa-port-86 may hold pareto0.
- Base rows for the by-id comparison: `pareto0:~/sp19/sa-rust-ids-work/sa-port-84/suite`, copied to `~/sa-rust-ids-work/sa-port-85/s84/`.
- Fresh dev and fuzz: `run_live.sh`; see `~/sp19/job84.sh` and its scripts on pareto0.

## Module count
No module newly counts whole. Nothing but the join hook has moved, and `relations.py` stays partial until C2b, C2c and 5c.
