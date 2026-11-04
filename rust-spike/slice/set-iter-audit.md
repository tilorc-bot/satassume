# Set iteration audit for interned ids (19 sites of rust-spike/ids/results/set-iter.txt)

Paths are relative to `satassume/`. Static reading around each site; nothing was run. Five sites are not sets: the finder's Module pass (`set_iter.py:32,36-43`) folds every assignment in a file into one name set, so `out = set()` at rules.py:319 flags every `out` there and `new = c - cone` at engine.py:1775 flags the list at engine.py:647.

| site | elements | order use | reaches answer/record? | verdict |
|---|---|---|---|---|
| sympy_api.py:192 | SymPy Symbol, IndexedBase, Function; ids change order | only adds to set `bad`, sorted at :200 | no answer; see tie in Extras | SAFE |
| sympy_api.py:742 | SymPy Rational; ids change order | `acc.update`, set build; becomes `frozenset` at :800 | contents only, in `_KEYS`; readers :884, :956 use `isdisjoint`, `set(k)` | SAFE |
| relations.py:584 | SymPy AppliedUndef; ids change order | `out.update`, set build; `frozenset` at :587 | contents only, in `_UNDER_APPS`; readers use `\|` and `in` (:613, :651, engine.py:1807-08) | SAFE |
| engine.py:1777 | cone objects (SymPy, P); ids change order | `sum` of weights | no | SAFE |
| engine.py:1767 | cone objects (SymPy, P); ids change order | early return on first None or over budget | answer no; memo `_qcones` yes, unread fields only | FIX-SORT (closest fit; see below) |
| engine.py:647 | not a set: list of slot ints, from `pat.used`, a sorted tuple (`_common.py:276`) | fixed order | no set order involved | SAFE (false positive) |
| engine.py:1713 | cone objects (SymPy, P); ids change order | stack push order; `break` on budget | answer no; memo `_cones` yes, unread fields only | FIX-SORT (closest fit; see below) |
| knowledge/rules.py:264 | `(bool, bool)`; ids do not touch | `any` with pure test | no | SAFE |
| knowledge/rules.py:265 | `(bool, bool)`; ids do not touch | `any` with pure test | no | SAFE |
| knowledge/rules.py:285 | not a set: list of clause tuples | fixed order | no set order involved | SAFE (false positive) |
| knowledge/rules.py:237 | not a set: list of model tuples | fixed order | no set order involved | SAFE (false positive) |
| knowledge/rules.py:280 | not a set: list of clause tuples | fixed order | no set order involved | SAFE (false positive) |
| knowledge/rules.py:282 | not a set: list of clause tuples | fixed order | no set order involved | SAFE (false positive) |
| knowledge/templates/_rows.py:362 | SymPy `f(...)`; ids change order | builds the `xreplace` dict, read by lookup | no | SAFE |
| knowledge/templates/_rows.py:482 | SymPy Symbol/Constant; ids change order | builds the `xreplace` dict, read by lookup | no | SAFE |
| knowledge/templates/_rows.py:603 | SymPy Symbol/Constant; ids change order | `all` with pure test | no | SAFE |
| knowledge/templates/_rows.py:874 | SymPy `f(...)`; ids change order | list filter; two or more nodes raise at :878, so `starred` has one entry | no | SAFE |
| theories/transfer.py:103 | tuple of sides of an `lt` atom; ids change order | any-style loop, `(y, x) in lts`, returns bool | no | SAFE |
| theories/lra/lra.py:614 | plain ints, `v = len(self._key)` (:480); ids do not touch | order-sensitive: emits literals in set order | yes under budget, but ids leave it as is | SAFE for ids (not order-free) |

Counts: SAFE 16 (5 of them false positives), SAFE for ids but order-sensitive 1, FIX-SORT with the caveat below 2, UNSAFE 0.

## Sites not SAFE

**engine.py:1713 (`_cone_info`).** Whether the cone is None is order-free: `over` holds exactly when the closure's weights sum past the budget (weights are non-negative, and a known over-budget sub-cone implies that, :1703, :1717). A cone that fits gets the same `seen`, `total` and `rel` in any order. The order only changes `w` and `rel` of an over-budget entry, stored in `_cones` at :1720-23. Every reader I found ignores those fields when the cone is None (:1703-05, :1769-70, :1812, :1817, :1821, :2004, :2052, :2156), and `rel` is documented as meaningful only when the cone fits (:1681-82). So no answer changes, but the recorded value differs.

A sort would not fix this: the `cones.get(o)` hit at :1700 changes where the loop breaks, so these fields depend on earlier queries already, with or without ids. The fix is to store a constant over-budget value such as `(None, budget + 1, False)`, with no sort key.

Not traced: :1713's order picks which `_struct(x)` runs first, and that runs templates. `_struct`'s docstring says kids are a function of the object, registry and settings; I did not check that re-entrant queries (:1998) cannot make kids depend on visit order. If they can, this site reaches the discovery budget and so an answer.

**engine.py:1767 (`_union`).** Same result: None-ness, a fitting cone, its weight and `rel` are order-free, because weight is the sum over the union (the :1777 shortcut equals that sum). The first None or budget return leaves `w` and `rel` order-dependent, and `_query_cone` stores them in `_qcones` (:1753-56). The one reader is :1795-1810, where a partial `rel` can flip `link`. The boolean stays False, because linked `objs` are a superset of unlinked ones, so a None cone stays None and :1813 or :1818 returns False. Flipping `link` can still add a `_qcones` entry and fill `_glue_adapters`; I did not read whether that memo stays pure. The same constant value fixes this. If an order is still wanted, `objs` can be `dict.fromkeys` over `atoms_of(f)`, already first-seen order (`sat/formula.py:126`), with `link_objects` (relations.py:1970) returning a dict too.

**theories/lra/lra.py:614 (`_dirty`), confirmed.** The set holds LRA variable indexes, allocated per theory by `_new_var` (:480) and added at :679, :743, :811, :826. They are not derived from a SymPy hash, and an int's hash is the int, so ids do not touch the table.

The order is used: :614 sets the order of `out` (:628, :638), the solver implies in that order (`sat/solver.py:1976-77`), and that should set the order of later `assert_lit` calls (:1970; trail in between not traced), then bounds, pivots and basis. The module docstring (:102-112) says budget exhaustion depends on this path: `BRANCH_BUDGET` = 16 (:224), and giving up with undecidable constants unless certified. Real simplex finds conflicts with no budget. Evidence: first-added order changed results on 1 dev and 8 fuzz recorded calls (`RESULT-k-lra.md:62`, mutant 7); ascending order was not caught, on small ids (mutant 6, :63-65).

Ids would change it only through variable numbering or the add sequence. Within an atom, terms are sorted with `default_sort_key` (`lra_adapter.py:323-24`, :348, :412) and by var at lra.py:710. Not traced: the order atoms get registered across a session, which sets numbering. A one-line rg found no direct loop over `linked`, `_xcand` or similar in relations.py, which is not a proof. `sorted(self._dirty)` is a history-free int key, if the order is ever made language-defined.

## Process-lifetime memos

Yes, for two sites, and neither passes an order into an answer as far as I read. engine.py:1713: `k` is the stored set object in `Engine._kids` (:1621-39, :1673), which lives as long as the engine, and `default_engine` is process-lifetime (sympy_api.py:206-10). Under ids its iteration order is frozen when first built, so it comes from earlier queries. engine.py:1777: `c` and `cone` come from `_cones`; only a sum reads them.

Three others are fresh sets whose results are memoized by value: :1767 (`_qcones`), relations.py:584 (`_UNDER_APPS`), sympy_api.py:742 (`_KEYS`). Contents are functions of the input; frozenset iteration order can vary, and I saw no order-sensitive reader. rules.py:264-65 feeds `_DEF_IMPL`, values only. An insertion-ordered kid dict would be history-free even in `_kids`, because it is built from one object's templates, not from a query.

## Extras the finder misses (not hunted)

- sympy_api.py:200: `sorted(bad, key=(str(s), isinstance(s, type)))` ties for two symbols with the same name and different assumptions, so set order shows in `AssumptionSymbolError.symbols` and its message, though the docstring says "in a fixed order" (:159). Error text only, not an answer. Adding `_declared(s)` to the key breaks that tie; equal Dummies would still tie.
- engine.py:1708 `for x in kc` (memoized frozenset, no break inside) and engine.py:1827 `sum(... for x in ca ...)`: order-free.
- engine.py:1632, :1749: `glue_objects`, `link_objects` return sets (relations.py:1994, :1970) that flow into :1713 and :1767. Internals not read beyond the first lines.
- lra.py:838, :846, :1064, :1072: `_cols[...]` is `set[int]` of row indexes, so ids do not touch them. Lines seen by rg only; mutant 8 (column reversed in a pivot) was expected to change nothing and was not caught.

## Sort keys nearby

Existing: `default_sort_key` at `lra_adapter.py:324`, :348, :412 and relations.py:465-66 (used at :523); `(str, bool)` at sympy_api.py:200; plain ints or strings at engine.py:1098, :1149, lra.py:710, rules.py:400, `_rows.py:419-20`; `dict.fromkeys` for first-seen order at engine.py:1806. None of the three sites above needs `default_sort_key` or `str`, both history-free but slow (your note; not measured here). That matters for :1713 and :1767, which run per cone object.
