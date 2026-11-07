# Handoff: sa-port-1 to the next inventory session (issue 323)

**The inventory isn't finished.** `rust-spike/PORT-INVENTORY.md` is pushed to `rust-slice`, marked partial. I handed off at the context note. Read the brief first: `~/.local/state/agent/briefs/sa-port-1-20261107T053950Z.txt`. Its scope and terms still apply: only `~/dev/sa-port`, touch only the document, no PR, no timing, no Python source change.

## What's left, in order

Section 8 of the document has the same list.

1. **Derived-term census (start here; it sizes the main risk).** Patch `Session.node` (`engine.py:545`), `relations._key` (`relations.py:466`) and the sort calls at `lra_adapter.py:324`, `:348`, `:412`. For each query, compute the preorder set of the input terms. Count the terms not in that set, by shape (class, arg count). The question: which derived shapes reach a sort key? It chooses between the options at the end of section 3.
2. **`_within_budget`** (`engine.py:1783`) and the `_cone_info` over-budget doubt (`engine.py:1676`, section 5). Does anything read `w` or `rel` when the cone is None? If so, `_cones` isn't pure and dropping it can change an answer.
3. **`is` on compound terms.** Known so far: `wiring.py:210`, `:310`; `(x + 1) is Add(x, 1)` is False [run]. Decide what derived terms answer. rg `\bis\b` over the runtime modules, excluding `None`, `True` and `False`.
4. **Real-hash set iteration.** `rust-spike/slice/set-iter-audit.md`, `rust-spike/ids/results/set-iter.txt`, `engine.py:1713`, `:1767`. Rust's first-seen order won't copy these, so each needs "doesn't reach state" or an order.
5. **Unread:** `knowledge/domain.py`, `knowledge/extensions.py`, `templates/functions.py`, `templates/limits.py`, `relations.py` outside the listed sites, `engine.py:813` (`escalate`). Check that `lra_bounds._interval` constructs nothing past its head (`lra_bounds.py:150`), and read `constfield.py:1284-1297`.
6. **Suite census.** The result wasn't read. It reaches sites dev and fuzz don't.
7. **Finish sections 9 and 10,** both drafts. Then remove the partial status, report, and stop.

## Tools (scratchpad, may vanish)

`/tmp/claude-1000/-home-tilo-dev-satassume/e90be846-787d-47b3-882a-a4db9f047348/scratchpad`:

- `census_core.py`, `census_run.py`, `census_plugin.py`: the hook, the driver and the pytest plugin.
- `census-dev.json`, `census-fuzz.json`: results. `suite/suite-*.json`: suite run, possibly incomplete; only `suite-main.json` existed at last look, and a run was still going under a 1,500 s limit.
- `report.py`, `report_build.py`, `show.py`, `static.py`, `static.json`, `appendix.py`, `defs.py`, `defs.tsv`: reports. `appendix.py` wrote appendices A and B. If you change a call, regenerate them.

**Rebuilding the hook:** `sys.setprofile`, on `call`. If the frame's code is under `sa-port/satassume`, count it as ran. If it's under `/sympy/`, count (`f_back` code, `f_back` line, callee) when `f_back` is satassume. For callee names `__new__`, `_from_args`, `__xnew__`, `_new_rawargs`, `_new`, `__call__`, walk up to the nearest satassume frame and count that as a build.

**Environment:** `. ~/sa-rust-ids-work/env.sh`, **then override** `PYTHONPATH=$PWD:$HOME/sa-rust-ids-work/sympy:$HOME/sa-rust-ids-work/shim`, because env.sh points at `~/dev/sa-rust`. dev took 7 s under the hook, fuzz about 2 minutes.

**Suite rerun:** `CENSUS_OUT=DIR PYTHONPATH=...:SCRATCH $PY -m pytest -q -n 4 -p census_plugin -p no:cacheprovider tests`.

## File:line map

| Topic | Where |
|---|---|
| Query entry, answer memo | `sympy_api.py:418` |
| Formula conversion | `sympy_api.py:354`, `:496`; `_FORMULAS` :493 |
| Relevance | `sympy_api.py:864`, `:929`, `:1009`, `:1088`; verdict call :1106; "conservatism" :632 |
| Engine memos | `engine.py:101`; cones :1609, :1676, :1726, :1759; budget :1783; `verdict` :1922; `is_` :1986; `ask` :2172; process memos :2263-2307 |
| Session | `engine.py:304`; `node` :545; `escalate` :813 |
| Relation atoms | `relations.py:466` key, :496 strip, :523 sort, :555 `sympy_atom`, :563 `_is_number`, :584 `_under_apps`, :672 `_termwise` |
| Glue | `relations.py:1366` eq links, :1374 closed side, :1586 share, :1632 congruent, :1733 transfer terms, :1801 `has(nan)`, :2008 `glue_objects` |
| LRA adapter | `lra_adapter.py:155` relation, :179 `_lin`, :213 `Mul(*closed)`, :239 `_closed`, :293 `_linear`, :324 sort, :348 `interpret`, :369 `_side`, :406 `integer_form`, :434 memo |
| Constants | `constfield.py:142` registry note, :577 gcd, :731-746 registry, :1375 `_from_sympy`, :1415 `_generic`, :1431 enclose; `lra_bounds.py:26`, :32, :85, :150; `harness/state.py:262-269` |
| EUF adapter | `euf_adapter.py:85` structural, :116 parse, :202-210 `_intern`, :243 shared terms |
| Templates | `_common.py:83` `const_value` (reads :87-99), :320 `_CACHE`; `wiring.py:94`, :151, :196, :210, :275, :303, :307, :310, :372, :378, :453, :464; `core.py:79`, :84, :173, :339, :419, :528; `functions.py:93`; `atoms.py:36`; `_rows_runtime.py:32`, :47, :91; `domain.py:482` |
| SymPy `sort_key` | `sympy/core/expr.py:168`, :1179, :1226, :1242 |
| PR 328's order | `lra.py:614`; `relations.py:1586-1587`; `euf_adapter.py:243`; `lra_adapter.py:547` |

## Calls so far

All are in the document, each marked **Call**. The ones most likely to be challenged:

- Ids are per top-level query, not per session.
- Term-keyed memos are dropped; `answers` stays in Python.
- The reference for state comparison is Python with memos cleared per query, compared by keyed session.
- A shape the term algebra can't handle keeps that query on Python, and never uses a callback that constructs.
- A non-default registry keeps the query on Python.
- Generic-constant enclosures are a long-lived read-only callback.
- A component 0 (term table, conversion, algebra) is added to the port order.

**Limit on all of it:** no code was ported, and no answer run tested any of these.
