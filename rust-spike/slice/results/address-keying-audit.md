# Address-keying audit (issue 323, sa-port-233)

Read-only audit of `rust-spike/slice` (Rust and Python) and `satassume/` at rust-slice 59e9d15, 10 Nov. No product
edits, no builds, no suite runs, no snippet run.

**Result: 47 sites, 46 SAFE, 1 FLAGGED.** The flagged site is a diagnostic log (`session.rs:850`); it can't move an
answer. Nothing found on rust-slice that keys an answer or state on an address without holding the referent.

## What can go wrong, and what was searched

Only a stored integer address can alias: `id(x)` or `as_ptr() as usize` kept after `x` may have died. An `is` /
`.is()` / `Rc::ptr_eq` compare of two references that are both alive at the compare can't be wrong by reuse, so
those are SAFE by kind once the stored side is shown to be a strong reference.

Searched with rg: `as_ptr`, `ptr::eq`, `ptr_eq`, `.is(`, `*const`, `*mut`, `addr`, `id(`, `weakref`/`Weak`,
`serial`, `__hash__`, `fn hash`, `HashMap<usize|u64|isize` keys (Rust); `id(`, `weak`, `addressof`,
`object.__hash__`, `__hash__ =` (Python). Every stored-address hit was opened. See "Limits" for what was
classified from the grep line alone.

## FLAGGED (1)

**F1. `solver_rs/src/session.rs:850` -> `join_log.py:31` -> `join_summary.py:25`. Diagnostic only.**
`SessionCore::known` passes `self as *const Self as usize` to the join hook. `join_log.py` writes it as `session`
in each row, and `join_summary.py:25` prints `distinct (session, node)` as the size of
`{(worker, session, nid)}`. Rows outlive the sessions, and nothing holds a session for the log's life, so a later
session allocated at a dead one's address in the same worker merges with it when the same node id joins: the
printed count comes out low. Without xdist `worker` is `''`, so two processes can merge too.
It reaches no answer and no state: the hook only reads (`session.rs:1695`), and it's set only by `-p join_log`.
Smallest fix: pass `self.serial` (`session.rs:609`, already unique per session per thread) instead of the address;
`join_summary.py` needs no change. No snippet: showing it needs a built `.so` and two sessions with a join each,
not run here.

## SAFE: stored addresses (Rust)

| # | Site | Keys / caches | Why safe (line that shows it) |
|---|------|---------------|-------------------------------|
| R1 | `adapters.rs:139` (map `:283`) | LRA adapter's per-query memo, `(kind, arg address, flag)` -> result | The value holds `arg` (`:164` `(arg.clone().unbind(), out)`), and the memo dies with the slot (`:137`). `arg` is borrowed alive from `:139` to `:164`, so the insert can't be for another object. Rechecked, agrees with 228. |
| R2 | `relations_core.rs:2638` (map `:2632`) | `SPEC_ROWS`, spec address -> `SpecRow` | The value holds the spec (`:2661` `(spec.clone().unbind(), row)`); entries leave only by a whole `clear()` (`:2659`, `:2675`). Rechecked, agrees with 228 (their `:2673` is the clear). |
| R3 | `procmemo.rs:203` | `_SPLIT` lookup, `(clauses address, hash(want))` | A hit also needs `r[0] is clauses` (`:222`), and the stored tuple `r` holds its `r[0]`, so the compare is between live objects. Rechecked. |
| R4 | `procmemo.rs:232` | `_SPLIT` write, same key | Stores `r` (`:268`, `:270`); a stale key can only miss at `:222`. Rechecked. |

## SAFE: serials and weak references (Rust)

| # | Site | What | Why safe |
|---|------|------|----------|
| R6 | `session.rs:485`, `:609`, `:1350`; `term/py.rs:152-161`; `relations_core.rs:714`, `:736` | The link's memo on the query table, `(session serial, node id)` -> `(object, term id)` | A serial, not an address; `link_get` also needs the held object to be `x` itself (`term/py.rs:154`). Table and session are both `unsendable`, so the thread-local counter is unique where they meet. |
| R7 | `session.rs:605` (called `:766`); made at `session_live.py:128` | The shell, a `weakref.ref(session)` | Dereferenced, never keyed on. |
| R8 | `constfield.rs:1314`, `:2376`, `:2382` | `Elem.pyw`, weak ref to the last `Element` crossing | Read only through `upgrade()` (`:2376`). |
| R9 | `relations_core.rs:2063` | `weakref.proxy(session)`, as `relations.py:800` | A proxy raises on a dead referent; not a key. |

## SAFE: identity compares against a held strong reference (Rust)

| # | Site | Stored side |
|---|------|-------------|
| R10 | `adapters.rs:121` patch guard | `live.memoized`, `live.reads[kind]` (held by `LraLive`) |
| R11 | `adapters.rs:132`, `:163` slot's query | `LraQuery.query: Py<PyAny>` (`:278`) |
| R12 | `adapters.rs:45`, `:52` `attach_to` | `_solver: Option<Py<PyAny>>` (`:69`), `theory: Py<PyAny>` (`:67`) |
| R13 | `relations_core.rs:2705` `RULE_MASKS` | `(Py<PyAny>, masks)` (`:2693`) |
| R14 | `constfield.rs:1255` `ENCLOSURES` | `(Py<PyAny>, ..)` per `(index, prec)` (`:185`) |
| R15 | `session.rs:694`, `:708`, `:718`, `:730`, `:757` transfer fields by `rel` | `rel: Py<PyAny>` (`:646`, `:652`) |
| R16 | `session.rs:796`, `:806`, `:835`, `:848`, `:1041`, `:1234` | `objs: Vec<Py<PyAny>>` (`:612`), `custom_exprs` values |
| R17 | `engmemo.rs:92` | entry keys are `Py<PyAny>`; identity is a shortcut before `==` |
| R18 | `procmemo.rs:49`, `:68`, `:213`, `:252` | `PyKeyMap` and `_SPLIT` keys are `Py<PyAny>` (`:35`, `:104`) |
| R19 | `factcache.rs:61`, `:80` | store keys are `Py<PyAny>`; `:206` is plant 200 only |
| R20 | `lib.rs:388`, `:407` attached theories | `obj: Py<PyAny>` (`lib.rs:143`); field type read, methods not opened |
| R21 | `solver.rs:2323`, `:2344`; `constfield.rs:1765` `Rc::ptr_eq` | both `Rc`s alive; `Num`'s hash is by content (`constfield.rs:1774`) |
| R22 | `__hash__`: `formula_py.rs:88`, `scope_core.rs:111`, `payloads.rs:62`, `constfield.rs:2463` | all hash content (a tuple of fields), none an address |
| R23 | the other `.is(` lines: `relevance.rs:158-713`, `relations_core.rs:804-1662`, `:2613-2624`, `scope_core.rs:289`, `entry.rs:271-784`, `budget.rs:230-233`, `query.rs:139`, `:309`, `context.rs:55-198`, `term/dispatch.rs:98-162`, `term/rows_tpl.rs:757-1913`, `term/outer_tpl.rs:242`, `:307`, `term/fn_tpl.rs:201`, `:413`, `memos.rs:219`, `lib.rs:110`, `:283`, `formula_py.rs:99` | compares of an argument with a singleton, a class or another argument, both alive at the compare; nothing stored |
| R24 | `formula_py.rs:46`, `:114`, `:161` `as_ptr` | FFI call arguments, not keys |

## SAFE: `satassume/` (Python)

| # | Site | Keys / caches | Why safe |
|---|------|---------------|----------|
| P1 | `engine.py:2340` | `_SPLIT[(id(clauses), want)]` | Hit needs `r[0] is clauses` (`:2342`); the entry holds the list. |
| P2 | `knowledge/rules.py:334` | `_MASKS[id(clauses)]` | Hit needs `hit[0] is clauses` (`:336`). |
| P3 | `sat/solver.py:367` | `_RULE_TABLES[(id(block), nvars)]` | Hit needs `hit[0] is block` (`:369`). |
| P4 | `sat/solver.py:747`, `:905`, `:967`, `:1003`, read `:2782` | `_cowner[id(problem clause)]` -> owner (provenance) | Each clause is appended to `self._clauses` just before (`:745`, `:903`, `:965`, `:1001`), and nothing removes from or rebinds `_clauses` (every use: `:419`, `:857`, `:942`, `:994`, `:2567`). `_reduce_db` drops only `_learnts`, and `:2780` returns before the lookup for a learnt `Clause`. No copy, deepcopy or pickle of a solver in `satassume/`. A live `reason` can share an id only with itself. |
| P5 | `sat/solver.py:749`, read `:2787` | `_cante[id(owned clause)]` | Same clause, same argument as P4. |
| P6 | `sat/solver.py:2334`, `:2342` | `dead[id(c)] = c` in `_reduce_db` | The dict holds `c` while the watches are filtered. |
| P7 | `knowledge/compile.py:279`, `:313`, `:360` | `srcs[id(part)]` | Every `part` stays in `parts` (`:314`) until after the last lookup; all local to one call. |
| P8 | `knowledge/compile.py:340-342` | `keep = set(map(id, ...))` | Taken and read while `info` holds every item. |
| P9 | `state/memos.py:260-261` | `weakref.ref(obj)`; `id(obj)` in the `Memos` owner label | The label is read only by `__repr__` (`:166`); the getter dereferences the weak ref. |
| P10 | `relations.py:800` | `weakref.proxy(session)` | As R9. |

## SAFE: `rust-spike/slice` (Python)

| # | Site | Keys / caches | Why safe |
|---|------|---------------|----------|
| S1 | `term_live.py:151` | `_Mark.tables[id(t)]` | Value holds `t`; the held `last` key is compared by `is` (`:183`). |
| S2 | `term_live.py:157`, `:161` | `_Mark.engines[id(eng)]` | Value holds `eng`. |
| S3 | `term_live.py:163-164` | `_Mark.facts[id(c)]` | Value holds `c`. |
| S4 | `audit.py:28`, `:30` | `S.dig[id(solver)]` | Value's last item is the solver. |
| S5 | `knowledge_leak.py:51` | `seen` ids in `walk` | Every seen object is appended to `out`, alive for the walk. |
| S6 | `knowledge_plants.py:17` | same `walk` | Same. |
| S7 | `core_trace.py:51` | `seen` ids of code objects | Held by their functions and parents' `co_consts`. |
| S8 | `transfer_fuzz.py:98-99` | id lists of Python's and Rust's results compared | `a1`, `a2`, `sets` and both `shared` lists are alive at the compare. |
| S9 | `test_lra_identity.py:38`, `:46` | ids of the kept keys, compared after the theory is gone | The keys are `x1..y2`, held by the test's locals. |
| S10 | `join_log.py:21` | `id(type)` written into each row | `join_summary.py` doesn't read it; inside one row both classes are alive. Comparing it across rows would be F1 again. |
| S11 | `rust_plugin.py:63`, `backend.py:80`, `live.py:117` | `weakref.finalize(.., _gone)` | Counts drops; no key. |
| S12 | `boundary.py:95`, `:141` | weak refs to solvers and theories | Dereferenced to count the living. |
| S13 | `test_xfer_core.py:66`, `:79`; `test_lazy_reads.py:366`; `transfer_fuzz.py:512`, `:544` | tests that the classes take weak refs | Dereferenced only. |

## `ad:cbm_noid` (OWED [111]): does it key on a flagged site?

No. The tick is `adapters.rs:158`, reached when `Reader::id` (`adapters.rs:316-326`) has no id for a side. That
reads `q.ids` (a dict on the term's own hash and `==`), then `term_live.term_id` (`term_live.py:286`), which reads
`q.ids`, `q.derived` and `q.rev`, all keyed by content. The one address key on the path is R1, and it is SAFE.

Two pointers for the cause read, neither checked here:
- R1 stores only successes (`:164`), so an argument with no id ticks on every call. The count is then the number
  of calls, which follows whatever decides how often the adapter is asked, not the number of distinct arguments.
- `adapters.rs:321` and `term_live.py:292`, `:300` take a row only if `type(row object) is type(e)`. That is an
  identity compare of two live classes, so reuse can't touch it, but for two `==` terms of distinct class objects
  it depends on which object the process handed back, so it can follow test order and the xdist split.

## Not on rust-slice (seen in the added lines of in-flight branches, not counted)

- `port/state-relations-iii` (742ba6b): fix 0576370 keys RelKeys' table by `PyTermTable::serial()` (a process-wide
  `AtomicU64`, `term/py.rs`), and RelKeys' keys index `objs`, which holds strong refs. SAFE as written. One stale
  sentence: `RelKeys`' doc comment in `session.rs` still says "`table` is the address of the one query table",
  two lines above the field's own "never its address".
- `port/state-part3` (55ca91a): a test script's `replaced[id(before[k])] = before[k]` holds the object. SAFE.
- `port/formula` (ebd73f1): no added line matches.

## Limits

- Outside the two directories, listed and not read: `tests/test_public_incremental.py:194`
  (`key = (id(self), proposition)`, sa-port-185's known case, still there), `tests/test_relations.py:208`,
  `tests/test_memos.py:109`, `tests/_sympy_trap.py:142-148`, `tests/test_layering.py:340`,
  `harness/state.py:323-330`, `tools/totality.py:120-150`, `:250`, `tools/check_sympy_boundary.py:92-101`.
- R23's lines were classified from the grep line; of them only `relations_core.rs:984`, `:1564`, `:1662`,
  `scope_core.rs:289`, `entry.rs:271`, `budget.rs:233`, `relevance.rs:713`, `query.rs:309` and
  `term/rows_tpl.rs:769` were opened. R20's methods were not opened.
- Python `is` compares in `satassume/` were not swept line by line (too many); the sweep was for stored `id()`
  and weak references, which is the only form reuse can break.
- `LraLive`'s field types (R10) were inferred from `clone_ref`, not read.
- Nothing was run: no counter, plant or snippet backs a verdict here. Each is from reading the lines named.
