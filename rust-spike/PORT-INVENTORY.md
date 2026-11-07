# Port inventory: what moves to Rust, what is converted, what stays offline (issue 323)

**Status: complete, by sa-port-3, 7 Nov. Sections 9 and 10 are final. No code was ported, and no Rust ran for anything here.** One census wasn't run and one is partial; section 8 says which, and what rests on them. Line numbers are of `rust-slice` at c230ee0. PR 328 (head 68c86b5, open, needs-human) was run as a separate tree for this document, and has since been applied to `rust-slice` as 2d00bea, unmerged (`slice/results/pr328-check.md`).

**Where it stands:**

- **Hard blockers:** none. Section 7 has the 4 items closest to one. This is a clearance from reading and Python runs, not from a port.
- **Needs a ruling:** `Sum`, `Product`, `Integral`. A Rust version can't match Python's answers without SymPy's evaluation: 158 of 1,800 queries chosen to break it lost an answer, while 0 of 2,592 plain ones did. **Call:** they stay on Python. Section 7 has the options.
- **Real-hash order: cause found.** PR 328's sites account for all of it: 39, 131 and 13 queries on dev, fuzz and corpus go to 0 with its tree. The reference for state comparison is `rust-slice` plus PR 328 (section 5).
- **History independence:** per-query ids hold up on reading, and they're stronger than Python's own position (section 5). No answer run tested this, because nothing is built yet.
- **Hardest part: derived terms, sized on five workloads, not on the suite.** Only small shapes reach a sort key there, and a Python check computed form, arg order and key without building the term, with 0 mismatches over synthetic combinations (section 3).

## 1. Target and method

**Target (forward-chain-3b, 7 Nov):** "SymPy input stays as it is. A thin Python layer converts it at run time into a format Rust owns, and everything from there on runs in Rust: session build, relations, theories (LRA including constants, EUF, transfer), solver, and the runtime part of knowledge. Offline stuff isn't ported; Rust reads what it produces as data."

**Evidence tags used below:**

- **[census]:** a `sys.setprofile` hook on dev (1,985 queries) and fuzz 424242 (3,000 queries, 207 of them raising). It recorded each satassume function that ran, each SymPy Python function a satassume line called directly, and each line under which a SymPy `__new__`, `_from_args`, `_new_rawargs` or `__call__` ran. It can't see C-level reads (`isinstance`, a plain class attribute such as `is_Add`, `.p`). Counts are for one pass with memos on, so they're floors for reach and not costs.
- **[static]:** an AST scan of attribute, method, `isinstance` and constructor sites. It works by name, so it over-reports (`.args` of a `Formula`, `.expr` of a `P`).
- **[read]:** I read the function.
- **[doc]:** taken from a docstring or comment only, not checked against the code.
- **[run]:** a direct check in this SymPy (1.15.0.dev).

**Suite reach:** the suite-wide census is partial (section 8). It shows that `special`, `stats`, `rootof`, `physics` and `limits` all run, but the sites in them are otherwise [static] or [read]. `limits` was measured directly (section 7).

## 2. Classification

Appendix A lists every function. These are the module-level calls; a function's row is the module's class unless the appendix says otherwise.

| Module | Class | Basis and note |
|---|---|---|
| `sat/solver.py`, `sat/theory.py`, `sat/formula.py` | port | Solver already ported (`slice/solver_rs`). `EqualitySharing` and `P` not yet |
| `theories/lra/lra.py`, `lra_cert.py` | port | `lra/port/src/lra.rs` covers the rational core, as a replay binary |
| `theories/lra/constfield.py` | port | No port yet. `_from_sympy` (:1375) becomes reading the term table. `_sympy_inner_gcd` (:577) uses SymPy's `dmp_inner_gcd`: polys, no `Expr`; replace it with a Rust gcd |
| `theories/lra/lra_adapter.py` | port, except `relation` (:155) | **Call:** `relation` reads predicate heads, so it's conversion. `_lin`, `_side`, `_closed`, `_constraint`, `interpret`, `integer_form` are term work and move |
| `theories/lra/lra_bounds.py` | **callback, stays Python** | **Call**, section 4 row R9 |
| `theories/euf/euf.py`, `theories/transfer.py` | port | `transfer.py` reads only `P.expr` [static] |
| `theories/euf/euf_adapter.py` | port, except `parse` (:116 on) | **Call:** the head tests in `parse` are conversion. `structural` (:85) reads class facts, so conversion supplies the bit |
| `relations.py`, `engine.py`, `scope.py`, `knowledge/compile.py` | port | **Call on `compile.py`:** it's runtime, not offline. `VarTable` and `compile_formula` run per session, and its `.args` reads are of `Formula` objects, not SymPy [static] |
| `sympy_api.py` | **split** | `ask` and the answer memo (:418), `to_formula` (:354), `_applied_category` (:257), `check_strict` (:178), `out_of_scope` (:300) and matrix tests are conversion. **Call:** the relevance layer (`_keys_rel`, `_Split` :864, `_relevant` :929, `_consistent` :1088) is port, because it calls `Engine.verdict` and its inputs are terms |
| `knowledge/rules.py` | **split** | Import-time compile is offline, output read as data. `cnf_of` (:207), `expand_clause` (:270), `closure_mask` (:355), `unit_propagate` (:383) and others that ran at query time are port. Appendix A marks each by [census] |
| `knowledge/domain.py` | conversion, except `kept_product` | `constructed_noncommutative` (:58) becomes a level per node, 0, 1 or 2, not a bit (`engine.py:165`, `_noncommutative_answer`). `kept_product` builds a `Mul` (:482): port, section 3 |
| `knowledge/extensions.py` | **stays Python** | User functions take SymPy arguments. Section 7, item 2 |
| `knowledge/realroots.py` | port | Plain Python over `int` and `Fraction` [doc]; polynomial data comes from conversion |
| `templates/_rows.py` | **offline** | **Call:** language and compiler. `wiring.py:42` says a query doesn't need it, and `_rows_runtime.py` holds what a query does |
| `templates/_compiled_rows.py` | **offline, data** | **Call:** generated by `tools/compile_rows.py`. Rust reads it, so a generator writes a Rust-readable form of `FAMILIES` |
| `tools/compile_rows.py`, family modules (`add`, `mul`, `power`, `trig`, ... the names of `ROW_FAMILIES`, `__init__.py`) | **offline** | They state `RULES` only [doc], and `wiring.load` doesn't import them (:151-157) |
| `templates/_rows_runtime.py` | port | **Call:** `from_text` (:32) and `constant_value` (:47) parse the row texts into SymPy numbers. Rust parses the same texts into its own numbers. `generator` (:91) becomes the data reader |
| `templates/wiring.py` | **split** | **Call:** `functions` (:87) is offline. `load` (:151) and `template` (:94) become one offline step, a table from function name to template kind, resolved against classes by conversion. Per-node code (`matches` :196, the `template` closure in `power` :275, `expand` :381, `_instances` :453, `rules_for` :596, `product`, `addition`, `any_arity`) is port. The data tables (`PI_MULTIPLE` :53 and on) move by name |
| `templates/_common.py`, `table.py`, `core.py`, `functions.py`, `atoms.py`, `nodes.py`, `rootof.py`, `special.py`, `stats.py`, `physics.py` | port | Runtime templates. `core`'s module-level tables are built at import, so they're data. `functions.py:404` (`_value_units`) evaluates six functions at a constant: **call,** an offline table for its range, section 3 |
| `templates/limits.py` | **stays Python, pending a ruling** | **Call,** section 7 item 4. `Sum`, `Product` and `Integral` keep the whole query on Python |
| `templates/registry.py` | **split** | **Call:** the class walk and `_redefines` (:67) read classes, so conversion resolves them. User `register` stays on Python (section 7, item 2) |
| `state/memos.py`, `state/epoch.py` | port (thin) | Section 5 |
| `ref.py`, `_compat.py` | **not ported** | `ref.py` is a reference, not on the query path [static; imports only]. `_compat.py` handles old import names [doc] |

## 3. Query-time SymPy construction: the sites that conflict

"No SymPy expression construction at query time" conflicts with these sites, which all exist in today's Python [census]. Python stays as it is, so the rule binds the backend and each site needs a Rust replacement.

| Site | What it builds | Rust replacement | Difficulty |
|---|---|---|---|
| `relations.py:1366` `_eq_links`, `:2008` `glue_objects` | `d = p - q` | Term algebra: the termwise difference. See below | **High** |
| `relations.py:688` `_termwise` | `-t` per term | Same | **High** |
| `relations.py:496-502` `_affine_strip` | The rest of `as_coeff_Add` and `as_coeff_Mul`: a new `Add` or `Mul` when 3 or more args remain (1,552 on fuzz) | Same args minus the coefficient; order kept | Medium |
| `knowledge/domain.py:482` `kept_product` | `Mul(*factors)` | Term algebra on non-coefficient factors | Medium, unread in detail |
| `templates/wiring.py:303` | `Mul(c, a)` | Term algebra | Medium |
| `templates/wiring.py:307`, `functions.py:93` `shifted` | `a + c` | Term algebra | Medium |
| `wiring.py:148` | `S(c)` for the shift | Number | Low |
| `lra_adapter.py:213` | `Mul(*closed)`, then `from_sympy` | Multiply field elements directly. Check it's the same element | Medium |
| `sympy_api.py:924` `_Split.part` | `And(*conjuncts)` | A list of conjunct ids. SymPy's `And` can also drop duplicates and evaluate, so check `to_formula` of it agrees | Medium |
| `relations.py:555` `sympy_atom` | `Q.eq(a, b)`, `Q.lt(a, b)` for adapters | Gone once adapters take ids | Low |
| `core.py:173`, `:79`, `:84`, `:419`, `lra_adapter.py:200`, `wiring.py:464` | Rational arithmetic, `Integer(n)` | Rust rationals | Low |
| `_rows_runtime.py:40`, `:62-68` | Numbers from row text | Parser over Rust numbers. `-1/E` and `exp(-1)` need the constant field, not a rational | Low to medium |
| `sympy_api.py:386`, `:1134` | Error text, `str(expr)` | Python keeps the original objects and writes the message | Low |

**Added by the unread-modules reading [read, sa-port-3 confirmed each line]:**

| Site | What it builds | Rust replacement | Difficulty |
|---|---|---|---|
| `functions.py:90`, `:92`, `:93`, `:315` | `Add(*x.args)` as a test, `Add(x, c, evaluate=False)`, `x + c`, `Add(*others)`. The result becomes a template slot, so it can reach the node table and a sort key | Term algebra; the `Add(*x.args)` rebuild test is refused unless the sum's args are plain | Medium |
| `functions.py:404` `_value_units` | `expr.func(c)`, evaluating six functions (`factorial2`, `subfactorial`, `catalan`, `andre`, `partition`, `genocchi`, per the reading, not re-derived) at an integer of size 200 or less | **Call:** an offline table of each value's unit facts. Only the value's facts are used, so nothing built reaches a node | Low |
| `relations.py:1176` `_trichotomy` | A second route into `_affine_strip`, through `relation_atom("eq", a, b)` | Same as `_affine_strip` | Medium |
| `limits.py:83`, `:92`, `:172`, `:208` | Inner limit, the `xreplace`, `b - a + 1`, `a - b` | None: these stay on Python, section 7 item 4 | - |

Reached in the suite, by the partial census (section 8), so no longer static only: `a/2` at `wiring.py:147`, `functions.py:90`, `:92`, and construction at `special.py:63` and `:101`. `special.py:60,62` (`Add(*x.args)`, `Mul(S(2), x, evaluate=False)`) showed no build row under those line numbers, which on a partial run isn't evidence they're unreached. `constfield.py:1281` `to_sympy` builds terms, but only tests call it, by search; `:1293-1297` is `__repr__`. Neither is at query time.

**Why canonical form must be exact, not just stable.** A derived term can equal an input term (`Q.zero(x - y)` and `Q.eq(x, y)` in one query), and then Python has one node. Cones count nodes, and the discovery budget reads that count (`Engine._struct` :1609, `_cone_info` :1676), so a missed merge can change an answer as well as state.

**What the term algebra has to reproduce** [run, this SymPy]:

- `Add` evaluation reads declared facts: `oo + p` is `oo` for a real `p`, while `oo + x` stays. So `p - q` isn't purely syntactic when an infinity is present.
- Negation distributes: `-(2*(x + y))` is `-2*x - 2*y`.
- Args come in SymPy's canonical order, so a hash-consed `Add` needs that order. I didn't read how `_addsort` and `Basic.compare` behave on every class.

**`_termwise` narrows the need [read].** `d` is used only if SymPy built it term by term (`relations.py:672-688`). So Rust needs `d` only in that case, and it must detect the other cases without building them. Merge and cancel detection is by non-coefficient part; absorption needs facts.

**Call, needs a ruling if the planner disagrees:** the algebra is a Rust module with the rule "unhandled shape means this query stays on Python, counted", not a callback that constructs. A callback here would break the rule outright, since the derived object doesn't exist in SymPy.

**`default_sort_key` is the sharpest case.** It's called at `relations.py:466` (orientation of `eq` atoms, `:523`), `lra_adapter.py:324`, `:348`, `:412`. For input terms, conversion can supply the key. For a derived term, `Expr.sort_key` (`sympy/core/expr.py:168`) goes through `as_ordered_terms` (:1179) and `as_terms` (:1226), which does `complex(factor)` on number factors (:1242): floating evaluation inside a sort key.

Options, in the order I'd try them:

1. Find out how many derived terms actually reach a sort key (measured below). If it's only stripped sums of input terms, a small Rust key may do.
2. Port `sort_key` for the derived shapes, with number factors' `complex` values supplied by conversion.
3. Propose a PR 328-style change to Python's key for atom orientation, to a structural order Rust can compute. That changes the reference, so it would be for Tilo.

**Measured: which derived terms reach a sort key [run, sa-port-2].** Hooks on `Session.node`, `relations._key` and `lra_adapter.default_sort_key`, memos cleared and a fresh engine per query. Derived means not in the preorder set of the query's proposition and assumptions. Tool: `derived.py`.

| Workload (queries) | `relations._key` calls, derived of all | LRA sort calls, derived of all | Derived shapes at a sort key |
|---|---|---|---|
| dev (1,985) | 891 of 2,906 | 7 of 4,271 | `0`; `re(x)*im(x)` (LRA) |
| fuzz 424242 (3,000) | 18,627 of 55,252 | 0 of 117,684 | `0`; two-term sums such as `-2*x + y` |
| corpus (2,863) | 190 of 862 | 0 of 1,303 | `0` |
| stream-unique (8,393) | 8,918 of 25,446 | 14 of 36,257 | `0`; `re(x)*im(x)` (LRA) |
| battery (16,386) | 11,390 of 33,016 | 14 of 45,285 | `0`; `re(x)*im(x)` (LRA) |

All derived calls at `relations._key` come from `relation_atom:523`. At `Session.node` the shapes are `0`, `c*input`, sums of input or `c*input` terms (2 or 3 args), and products of input terms, some with a closed factor (`pi*k`, `I*pi*k`, `sqrt(2)*x`). No derived `Pow`, function application or deeper nesting appeared on any of the five. **So option 1 holds on these workloads: a small Rust key.** The suite wasn't measured (`derived_plugin.py` is written and has never run).

**Measured: the algebra and key without building the term [run, Python only].** `algebra_check.py` predicts `-t`, `c*t`, `t + c` and `p - q` from input terms' args, classes, supplied sort keys and rationals, and checks against SymPy's real result, arg order included. Over the first 9 commutative input terms per query, on dev, fuzz and corpus, 445,688 attempts:

- **0 form mismatches and 0 key mismatches** among those it didn't refuse. One bug was found and fixed on the way: `Expr.sort_key` nests a `Dummy`'s own key, which a flat rule misses (507 key mismatches on dev before the fix).
- **Refused:** 1,280 where the coefficient merges with a numeric-base power (`2*sqrt(2)`, `2*2**x`), 82 where a key needs a power base that isn't an input term (`decompose_power` builds it), all on corpus; and 162 input terms holding an infinity, `nan` or a `Float`. These are the shapes that would stay on Python.

**What Rust needs for this, from the same code:** the `Basic.compare` order over class rank (`_cmp_name`, `ordering_of_classes`) and hashable content, including the number singletons' classes (`Zero`, `One`, `Half`, `NegativeOne`); a rational type; per closed factor, its `complex()` value; for each `Pow` factor, the `decompose_power` split; `str` and `class_key` per input term, through the supplied key.

**What this doesn't show:** it ran in Python with SymPy's `Rational`, `complex` and `compare` on input terms, so it says nothing about a Rust implementation's rounding (`complex(Rational)` goes through `evalf`). The combinations are synthetic, not the glue's own terms. `Mul(*factors)` of separate terms (`kept_product`, `product:input` above) wasn't predicted. Infinities are refused, not handled.

## 4. SymPy reads at query time

Appendix B lists every direct call site [census], collapsed per function. By kind:

| # | Read | Sites | Up front or callback |
|---|---|---|---|
| R1 | `.args`, `.func`, class | `euf_adapter.py:206`, `relations.py:1632`, `:1733`, `engine.py:697`, `:1641`, templates throughout | Up front: term and class rows |
| R2 | Plain class flags: `is_Add`, `is_Mul`, `is_Atom`, `is_Rational`, `is_Symbol` | [static], many | Up front: class row. Derived terms get them from their kind |
| R3 | `is_number`, `free_symbols` | `relations.py:563`, `:408`, `scope.py:141`, `engine.py:1752`, `lra_adapter.py:185`, `:197`, `sympy_api.py:553`, `constfield.py:1386` | Up front per term. Derived terms compute from args. Note that `free_symbols` has class-specific meaning (bound variables); conversion supplies it so Rust needn't know, and only `Add`, `Mul` and `Pow` are derived |
| R4 | `has(...)`, `atoms(AppliedUndef)`, `preorder_traversal` | `lra_adapter.py:293`, `:376`, `:406`, `euf_adapter.py:135`, `relations.py:1801`, `:584`, `sympy_api.py:554`, `constfield.py:1386` | Up front: per-term bits (`has_nan`, `has_bad`, `has_float`, `has_applied_undef`), computed in Rust for derived terms. `_under_apps` becomes a walk of the DAG |
| R5 | `is_<pred>` of atomic numbers | `_common.py:87`, `:91`, `:99`, `core.py:339` | Up front: a row of truth values per atomic-number term. Rationals made by Rust compute their own |
| R6 | `assumptions0` | `atoms.py:36`, `stats.py:26`, `:29` | Up front: symbol row |
| R7 | `as_coeff_Add`, `as_coeff_Mul`, `make_args` | `relations.py:496-502`, `:685`, `lra_adapter.py:239`, `:369` | Rust from the term row. These build (section 3) |
| R8 | `default_sort_key` | `relations.py:466`, `lra_adapter.py:324`, `:348`, `:412` | Up front for input terms. Derived terms: section 3 |
| R9 | Interval evaluation of closed constants, during search | `constfield.py:1415-1436` `_generic`, `lra_bounds.py` `_interval` :150 on, `lra_adapter.py:279`, `:285` | **Needs a callback.** The 128-bit bound can come up front (`_IV_PREC`, `lra_bounds.py:26`), but a higher-precision enclosure is asked for during a sign test (`enclose`, `constfield.py:1431`). **Call:** a long-lived, read-only callback on the original term rather than a port of mpmath's interval functions. I read the head of `_interval` and saw no construction; that isn't the whole function |
| R10 | Predicate heads `atom.function`, `.arguments` | `sympy_api.py:260-266`, `:326`, `:370`, `:387`, `:549`, `:815`, `euf_adapter.py:120-126`, `lra_adapter.py:159-172` | Up front: atoms arrive as predicate id plus term ids |
| R11 | `exp` metaclass `isinstance` | `core.py:528`, `constfield.py:1408` | Up front: class kind |
| R12 | `is` on compound terms | `wiring.py:210` (`same` shape), `:310` (`b is e` in the Pow key) | **Up front, with a catch.** `(x + 1) is Add(x, 1)` is False while `==` is True [run], so ids merge what `is` separates. **Call:** conversion supplies the `is` bit for these reads on input terms. **Measured [run]:** on dev, fuzz and corpus, no scalar class holds args that are == but distinct objects (only `MatMul` 3 and `MatrixSlice` 5, corpus). No derived `Pow` or function application reaches `Session.node` on the five workloads above, so derived terms never meet these two reads. **Call:** replace the bit with a refusal: args that are == but not `is` keep the query on Python. Note `Pow(b, e)` can return an earlier cached object, so this `is` already depends on SymPy's cache history in Python (seen in one run, not traced) |
| R13 | `__hash__`, `__eq__` of SymPy objects | Most `[census]` sites | Gone: integer id comparison. Conversion's own table uses them once per term |
| R14 | `poly`, `index`, `poly.domain` of `ComplexRootOf` | `rootof.py:25-26`, `:47` | Up front: coefficients and index, in the term payload |
| R15 | `_redefines` and handler lookups on classes | `registry.py:67` | Up front: resolved per class, in the class row |
| R16 | `Dummy`, `Wild` and other atoms' names, via `sort_key` and `str` | Inside R8 | Up front: part of the key |
| R17 | `is_finite` of a closed term | `relations.py:683`, in `_termwise` | Up front per closed input term. For a derived closed term, Rust computes it from a nonzero rational times a closed input term, and refuses other shapes. **New, an assumptions read not in R1 to R16** [read] |
| R18 | The construction-time non-commutative level | `domain.py:58`, reading `_assumptions0`, the class MRO, the `is_commutative` slot and `type(a).doit` | Up front: level 0, 1 or 2 per term, with `noncommutative_false` as data [read] |
| R19 | `is_commutative` evaluated on every subterm | `limits.py:106` `_scalar` | Stays on Python, with the limits. The notes report it writes SymPy's `_assumptions` cache, against `domain.py:36-41`; that's in Python today and I didn't re-run it |

## 5. History independence and cross-query memos

**The claim checked:** "Per-query or per-session ids behind conversion look like the way out, so the inventory should settle this."

**Finding: the claim holds on reading, for per-query ids, with three conditions below. SLICE-PLAN section 3's objection doesn't survive tracing.** It rested on names and docstrings, saying process memos such as `_FORMULAS` hold terms across sessions. They do, but each is declared as a pure function of its key (`state/memos.py:6-10`, `:24-28`), so none is needed for an answer, and a backend that doesn't keep them loses speed only.

**Ids per query, not per session. Call.** Sessions nest inside one query: the relevance layer calls `Engine.verdict` (`sympy_api.py:1106`, in `_consistent` :1088), and the glue calls `Engine.is_` (`relations.py:1374`, `_closed_extended_real`). They share terms, so the table belongs to the top-level `ask` or `Engine.is_` and dies with it.

| `RESULT-ids.md` channel | Under per-query ids |
|---|---|
| Lookup equivalence | Conversion's table uses SymPy's real hash and == for one query, so same id exactly when ==, for `Basic` values |
| Raw `bool` and `float` | Only `Basic` gets an id. Anything else is refused and that query stays on Python. Within `Basic`, the hand cases need a raw value: `S.true == Integer(1)` and `Float(2.0) == Integer(2)` are both False here [run]. **The comments at `_common.py:51` and `:317` saying the second is True are stale for this SymPy; `pattern_key` includes `type(c)` anyway** |
| Set order depending on earlier queries | Gone. An id depends on first sight within the query, a function of the query alone. It's also independent of the hash seed, which real hashes aren't |
| Clearing, pinning, `Dummy` growth, weak refs, `clear_cache` | Don't arise: nothing outlives the query |

**Conditions:**

1. **Rust's constant registry must be per query too.** Today's Python has this channel: `constfield.py:142` says the registry "is global and grows... the variable order is the registration order", and `harness/state.py:262-269` classes `_CONSTANTS` and `_BY_KEY` as intern tables, checked only by the fresh-process reference. A per-query Rust registry with `pi` and `E` first matches a fresh Python process, not a Python with history. Variable order can change representation, and so possibly the size budget (`MAX_TERMS` and the like). I didn't test whether that moves an answer.
2. **`is` reads** (R12) must not be replaced by id equality.
3. **Term-keyed memos go.** See below.

**What happens to each memo [read for keys; the purity is as declared]:**

| Memo | Key | In the backend |
|---|---|---|
| `Engine.answers` (`sympy_api.py:418` on) | `(proposition, assumptions)` SymPy objects | **Stays in Python, before conversion.** Real hash and ==; holds no ids |
| `_FORMULAS` :493, `_KEYS` :683, `_CONST` :684, `_NONCOMM` (`domain.py:32`) | SymPy objects | Dropped, recomputed in conversion or Rust per query |
| `splits`, `_verdict`, `_failed` (`ENGINE_MEMOS`, `engine.py:101`) | Set or formula | **Call:** dropped first. Could return as Python-side memos keyed by the SymPy assumptions object, holding no ids |
| `_kids`, `_cones`, `_qcones`, `_glue_adapters`, `_xbasis` | Terms | Dropped; rebuilt per query. Speed is reported, not a gate |
| `cache.store`, `custom_cache.store` | `(node, pred)` | Same as `_verdict` |
| `_CLOSED` (`relations.py:391`), `_SYMPY_ATOMS` :546, `_ZERO_TWINS` :566, `_UNDER_APPS` :567, `_INTERPRETED` (`lra_adapter.py:434`), `_BOUNDS`, `_ENCLOSURES` (`lra_bounds.py:32`, `:85`), `_class_ok` (`euf_adapter.py:63`) | Terms or classes | Dropped. `_class_ok` becomes a class-row bit |
| `_CACHE` (`_common.py:320`), `registry._clauses_cache`, `_mro_cache`, `_RULE_TABLES` (`solver.py:116`), `_MASKS` (`rules.py:299`), `_DEF_IMPL` (`rules.py:240`), `_NEIGH`, `_WANT`, `_SPLIT` (`engine.py:2263-2307`) | Predicates, ints, pattern keys with constants by value, class | **Can stay process-wide in Rust,** provided the key holds no id: class by name, constants by value, `type(c)` kept. `_SPLIT` is keyed on `id(clauses)` and needs a pattern id instead. `_CACHE` is bounded and cleared at 4,096 (`MAX_CACHE`, `_common.py:322`); pure, so this is harmless |

**Consequence for "state matching Python":** with no term memos, Rust builds sessions that Python's memos skip. So position-based comparison breaks. The reference has to be Python with memos cleared per query (or a fresh process), compared per session by outermost `Engine` call and arguments, the keying PR 328's write-up used (0 sessions with more than one clause digest in 836 dev and 3,062 fuzz keyed sessions, from that PR's text).

**The purity doubt: settled for the budget's answer [read, run].** `_within_budget` does read `rel` from a cone that may be None (`engine.py:1795`, `:1798`), so `set-iter-audit.md`'s "unread fields only" is wrong as written. It doesn't change the boolean: if the unlinked cone is over budget, the linked one is too, because its objects are a superset and `_union`'s weight is the exact sum over the union. So the call returns False whichever way `link` went. `w` is read only after the None checks. On a long-lived engine against a fresh one, same call: at budget 5, 0 differences in 8,094 calls on dev and fuzz, 2,256 of them with a None unlinked cone; at budget 400, 0 in 3,967, none with a None cone. PYTHONHASHSEED 0 against 1 gave 0 differing verdicts at both budgets. **Call:** Rust may drop these memos, and store a constant for an over-budget cone. Still not traced: whether a re-entrant query (`engine.py:1998`) can make `_struct`'s kids depend on visit order, which this run covers only partly.

**Real-hash order reaches solver state today [run, sa-port-2].** `seed_state.py`: fresh engine and cleared memos per query, a digest of each session's `solver` at query end, on this branch without PR 328.

| Compared | Queries with different state | Answers different | Session counts different |
|---|---|---|---|
| dev, seed 0 and 1 | 39 of 1,985 | 0 | 0 |
| dev, seed 0 and 2 | 31 of 1,985 | 0 | 0 |
| fuzz, seed 0 and 1 | 131 of 3,000 | 0 | 0 |

This contradicts any reading of `set-iter-audit.md` (16 SAFE, 0 UNSAFE) as "set order doesn't reach state".

**Repeated in the source [run, sa-port-4]:** with PR 328 applied on this branch the same sample gives 39 and 131 without it and 0 with it, on the same seed pairs (`slice/results/pr328-check.md`).

**Cause: the sites PR 328 changes [run, sa-port-3].** The same tool on PR 328's tree (68c86b5, extracted with `git archive`, first on `PYTHONPATH`):

| Workload | Without PR 328: state differs (seeds 0, 1) | With PR 328: state differs | Seed pairs run with PR 328 | Answers or session counts different |
|---|---|---|---|---|
| dev (1,985) | 39 | **0** | 0-1, 0-2, 0-3 | 0 |
| fuzz 424242 (3,000) | 131 | **0** | 0-1, 0-2 | 0 |
| corpus (2,863) | 13 | **0** | 0-1 | 0 |

On 8 of the 39 dev queries, the fields that differ are `trail`, `reason`, `clauses`, `watches` and `acache`, plus `level` and `learnts` on one. In query 825 the trail reorders variables 184, 186 and 188 and nothing else near them, which fits interface equalities being created in another order (`relations.py:1581` with `sat/theory.py:206-215`, by reading). That's the path PR 328 changes.

**Call: the reference for state comparison is `rust-slice` plus PR 328.** Rust takes PR 328's order (section 6). Without it, Python's state on these queries depends on the seed, so a state gate can only compare answers there.

**The other set iterations don't need an order, for now.** `engine.py:1713` and `:1767` and the rest of the 31 sites PR 328's text names moved no solver state on these workloads. By reading, they change traversal order and not the budget's verdict (`_within_budget`, above).

**What this doesn't show:**

- `PYTHONHASHSEED` moves `str` hashes, and through them `Symbol` hashes. It's a sample of orders, not a proof, over 2 to 4 seeds.
- The digest covers the solver dump (`state.dump_py`). LRA and EUF internals appear only through what they give the solver.
- The suite wasn't run this way, so suite-only shapes aren't covered. Queries that stay on Python (section 7, items 2 and 4) don't need it.
- Nothing here shows that Rust's first-seen order equals PR 328's, only that PR 328's is stable. The state gate of each port tests that.

**What this doesn't show:** nothing here ran. The tests in SLICE-PLAN section 3's list still have to pass for each component.

## 6. Other settled items

### Heuristics: runtime sites to rule on

"No heuristics deciding which facts an answer rests on." These exist in Python today. The port must reproduce them exactly and add none, but each arguably reads on that rule, so they're named here:

| Site | What it does | Why it's named |
|---|---|---|
| `sympy_api.py:929` `_relevant`, `_Split` :864 | Answers under the conjuncts connected by shared keys | Directly decides which facts an answer rests on. Documented as sound by monotonicity. A pure function of syntax, but `:632` says one key class is "out of conservatism" |
| `scope.py:45` | `zero(t)` twin only under an application: "chosen for its cost" | Chosen for cost; "same answers outside it" is the stated claim |
| `scope.py:96`, `engine.py:1783` `_within_budget` | Discovery budget decides whether a query is answered | "A budget, not a scope" (`scope.py:96-97`) |
| `engine.py:1642-1652` | Over-wide sum or product: templates not built | Budget |
| `wiring.py:372`, `:378` `LEAVE_OUT_WIDE`, `SOME_PER_ARGUMENT` | Rules left out of wide nodes | Drops facts by size |
| `relations.py:629-655`, with its docstring `:172-181` | Zero twins only under an application | Fixed for cost: per the docstring, widening costs 56%, and it leaves a pinned difference (`Q.zero(k - x + 1)` None where `Q.eq` gives False) |
| `relations.py:691-695`, docstring `:323-329` | Interface atoms with non-rational constants left out | Search cost is the stated reason; the docstring calls it a relaxation |
| `relations.py:1423-1425`, `:408-415`; `constfield.py:1123-1132`, `PREC_CAP` :164 | A sign that stays `Undecided` at the precision cap drops clauses or sign facts | A cap decides whether facts exist. Deterministic |
| `relations.py:1989`, `:2011`, `:2018` | `except Exception` around adapter reads in `glue_objects` | Which terms get counted shapes the discovery budget. An error that Rust can't predict would change a weight. Port as "the adapter refuses", and the state gate catches a mismatch |
| `functions.py:395` `MAX_VALUE_ARG` | Value facts only for an integer of size 200 or less | A cap on facts |
| `limits.py:84`, `:92`, `engine.py:1245` | Nested queries always use a default engine, budget 400, and an unanswered one means the rule isn't built | **Hidden, and visible to users [run]:** `Q.finite(Sum(...))` with `n` a positive integer, caller budget 100,000: 50 terms gives True; 450 gives None with `last_budget_limited` False. Stays on Python with item 4 of section 7 |
| `engine.py:1998` | A re-entrant `is_` on a node under construction returns None | A guard, not a choice, but it does decide an answer. Port exactly |

**Checked and not a heuristic:** `Session.escalate` (`engine.py:813`) and `want_of` (:2340). The callers I read (`:1971`, `:2112`) pass no budget, the docstrings at `:1270` and `:1793` say escalation is uncapped, and `truncated` needs an explicit budget. Two independent readings say demand only parks clauses, so it's a performance order. I read the callers, not the whole of `want_of`. No differential run.

**My reading, for the planner to confirm:** the rule stops the port adding such things. It doesn't remove these, which are defined functions of the query and the settings. No port step needs a new one so far.

### PR 328

Write against this order, from its diff:

- `LRATheory.propagate` walks `sorted(self._dirty)` (`lra.py:614`): ascending ints. The port's CPython set copy goes.
- `shared_terms()` returns a list in first-seen order (`euf_adapter.py:243`, `lra_adapter.py:547`). LRA's `_shared` is a dict used as an ordered set, extended from `atom_terms`.
- `_share` passes those lists to `EqualitySharing.update` without building sets (`relations.py:1586-1587`).
- The pinned behaviour: `update([[1,2,3],[2,3,1]]) == [(2,1),(2,3),(1,3)]`, and `shared == [2,1,3]`.

The PR leaves `engine.py:1713` and `:1767` alone, and its text says 31 sites still iterate sets of two or more on dev, moving nothing there. Those are real-hash orders in Python that a Rust first-seen order won't copy. Measured in section 5: with the PR, no solver state moves on dev, fuzz or corpus, so they need no order yet.

PR 328 is held for Tilo and isn't on main. It's on `rust-slice` as 2d00bea, so the port has its order as the state reference, whether or not it merges (section 10). Checks: `slice/results/pr328-check.md`. `lra/port/src/lra.rs` still carries the set copy, until step 1a.

## 7. Closest things to blockers

1. **Derived-term canonical form and sort key** (section 3). The rule forbids the easy way out. Sized on five workloads and on the suite (section 8). On the suite, `relations._key` shows the same shapes, LRA's sort key shows wider products of input terms, and `Session.node` shows deeper shapes.
2. **User registrations.** `register` (extensions), custom templates and custom `relation_specs` hand SymPy objects to user code by design, and `Engine.__init__` takes `clause_templates` (`engine.py:1338`). **Call:** a query under a non-default registry stays wholly on Python, reported as "kept on Python with reason". It's not a temporary callback; the backend is optional, so this meets the terms. Counted, not fixed.
3. **Generic-constant enclosures** (R9). A permanent read-only callback unless someone ports mpmath's interval functions. It's a small exception to "everything runs in Rust", and rare on the workloads, but the planner should see it. The suite calls `constant_enclosure` 248 times and `_interval` 3,951 times, with memos on; that's calls, not queries. Read in full now: `_interval` (`lra_bounds.py:150`) builds no SymPy term past its head and handles a closed set of heads, so a port is possible, but it must round as mpmath does.
4. **`Sum`, `Product`, `Integral` (`limits.py:92`): settled as a call, and it needs a ruling.** See below.

### Limits: the one place the rules can't all hold

`_inner` asks a nested engine about `inner.xreplace({v: Dummy(v.name, **assumptions)})` for up to 6 domains. `xreplace` rebuilds with evaluation, so SymPy rewrites the summand from the `Dummy`'s assumptions: `Mod(k, 1)` becomes `0`, `log(exp(k))` becomes `_k`. Rust can't do that without SymPy's evaluators, and the facts this produces reach answers.

**Differential [run, Python only, patched from outside the source].** `lim_replay.py` replaces the `xreplace` with a structural substitution that evaluates nothing, as a Rust version would, and compares against today's code, fresh engine per query.

| Queries | Substitutions rewritten by SymPy | Nested results differ | Answers differ | Direction |
|---|---|---|---|---|
| Plain summands, 2,592 (`floor(k)`, `cos(pi*k)`, `Abs(k)`, `sin(k)`, `f(k)`, ...) | 4,800 of 12,312 | 0 of 4,800 | 0 | - |
| Chosen to break it, 1,800 (`Mod(k, 1)`, `tan(pi*k)`, `Heaviside(k)`, `arg(k)`, `log(exp(k))`, ...) | 3,912 of 7,404 | 1,512 of 3,912 | **158** | All True or False to None |
| The suite's, 46 distinct, from the 9 test files I chose | 0 of 192 | 0 | 0 | - |

- **Control:** with all domain facts removed, 266 of the first grid's 266 decided answers and 15 of the suite's 23 become None, so this path does carry answers.
- **No wrong answer appeared,** only lost ones, and no fact was held only by the structural form in the 63 distinct differences kept. That's two grids I wrote, not a proof. Python's extra facts rest on SymPy's automatic evaluation, which isn't ground truth (issue 247), and I checked none of them independently.
- **Reach:** 0 of 32,627 queries on dev, fuzz, corpus, battery and stream-unique hold any of the three classes. Only the suite and direct `ask` calls do.

**Call: a query holding `Sum`, `Product` or `Integral` stays wholly on Python,** reported as kept on Python with a reason, like user registrations. Conversion sees it from the class row. A search of `satassume/` finds these classes built only at `limits.py:83`, from one already in the input, so no derived term can introduce one. The suite's derived census saw one derived `Sum`, `Sum(k, (k, 1, 3))`, which fits: `tests/test_notmpl_limits.py:32` holds `Sum(k, (k, 1, 3), (n, 1, k))` (by reading, not traced to that query). `lra.py:247` `Integral` is LRA's own unrelated tuple class. It keeps answers the same and breaks neither rule, and costs nothing on the five workloads.

**The ruling needed, from the planner or Tilo,** because the call leaves these three classes unported, against "pretty much everything":

| Option | Answers | Rule it strains |
|---|---|---|
| A. Stay on Python (the call) | Same | "Everything from there on runs in Rust" |
| B. Conversion runs the `xreplace` once per limit and domain and sends the results as input rows, with the nested queries in Rust | Same, by reading; not run | "No SymPy expression construction at query time", and it also reads SymPy's assumptions |
| C. Rust structural substitution | Loses facts (158 of 1,800 above) | "Answers matching Python" |

This isn't a blocker: option A works today, and the port doesn't depend on the choice.

## 8. What wasn't completed, and what rests on it

Nothing is open that stops sections 9 and 10. Done by sa-port-2: the derived-term census on five workloads, `_within_budget`, and `is` on compound terms (R12). The `is` scan classed all 968 compares by AST: 906 are constants, `type()`, sentinels, classes or `S.x`. Of the other 62, `wiring.py:210` and `:310` are the only term reads that matter. About 12 were read in context and the rest by their line alone. `relations.py:1134`, `:1136` are by line only. Done by sa-port-3: the hash-order cause, the unread modules, the limits differential, and sections 9 and 10.

**Finished 7 Nov by sa-port-16, on source 2d00bea (`slice/results/suite-censuses.md`).** The older `suite2` ran without PR 328. Census keys are `file|function|line` at 2d00bea; this document's lines are at c230ee0, so compare by file and function. The status lines at the top and section 3's "the suite wasn't measured" were written before these; this section supersedes them.

1. **Suite census: complete by id, 6,125 of 6,125, in two parts.** 5,000 from orion's `suite3`, which hit its 7,000 s limit and kept only each worker's whole 200-test dumps, so 562 tests it finished are in no JSON; and those 562 plus the 563 it never ran, on pareto1 (`suite4`, all 1,125 finished; 5 wall-clock failures). Same source, same SymPy files. In the query phase, functions run: `special` 5, `stats` 2, `rootof` 5, `physics` 2, `limits` 18, `functions` 27, `realroots` 18, `extensions` 26. **These are `suite2`'s numbers exactly, so `suite2`'s reach for these modules stands,** and the port still can't skip them. **"Not reached" is now evidence for the suite, within limits:** 50 of 927 module-level functions and methods weren't seen, and none ran on dev or fuzz either (the results file names them). That's with memos on, nested functions aren't in the 927, and `suite3`'s 26 failures aren't named, so a test that failed early reached less. Appendix A wasn't regenerated, so its marks still come from dev and fuzz.
2. **Derived census over the suite: complete, 6,125 of 6,125, 282,466 top-level queries.** Memos on, so floors. Calls by tests driving `Session` or an adapter directly weren't classed (`node` 89,167, `sort.relations` 54,902, `sort.lra` 4,375). **"Only small shapes reach a sort key" holds in kind, not in size:** `relations._key` shows only `0` and two-term sums, as on the five; LRA's sort key shows products of input terms of 2, 3 and 4 or more args, with `Pow` factors (`n*w**2*x*y`), in 39 queries, where the five showed only `re(x)*im(x)`. None carries a float, an infinity or a non-rational number factor. So section 3's option 1, a small Rust key, stands, and the key must cover those products. `algebra_check.py` didn't test them, and component 0's shadow hasn't run on the suite. **At `Session.node` the suite shows what the five didn't:** `Pow`, function applications and deeper sums and products, 143 of 53,827 shape counts, plus 194 `Dummy` atoms. Their source isn't traced. **"If the suite shows more shapes, the plan doesn't change" stands:** it did show more, and an unhandled shape refuses and stays on Python. How many suite queries that keeps on Python isn't measured.

**Read, not run:** sections 2, 4, 9 and 10; the `relations.py` lines around `:1570-1830` and `constfield.py:1123`, `:1400-1450` were read only in part. The unread-modules findings come from two subagent readings, and only the sites named as confirmed in section 3 and section 6 were checked by me. Option B of section 7 wasn't run.

## 9. The converted format

**Final as a specification. Nothing has built it, and no Rust has read it.** The Python algebra check is the only part that ran against real terms (section 3).

One call per top-level query, Python to Rust: flat arrays of the tables below. Rust owns the layout. Python keeps no handles except a list of the original objects by term id, used for R9 and for error text. Nothing here crosses queries, so history independence follows from the query alone (section 5).

**When conversion runs.** `Engine.answers` (`sympy_api.py:418` on) stays first and holds its answer memo. On a miss, conversion runs and either sends the tables or keeps the query on Python.

**Ids.** `u32`, numbered by first sight in one defined walk: proposition, then assumptions, each preorder over `.args` in order. Same id exactly when SymPy's hash and `==` agree (R13). Derived terms take the next ids in Rust, in the order Rust first builds them.

### Tables

| Table | One row per | Fields | From |
|---|---|---|---|
| Strings | Distinct text | Bytes | Names, used by the rows below |
| Settings | Query | `discovery_budget`, `transfer`, `uninterpreted`, `relevance`, generic-constants setting | `Engine.__init__` (`engine.py:1313` on) |
| Predicates | Predicate in the formula | Name or vocabulary index, arity | R10 |
| Classes | Distinct class under `==`, not `is`, since undefined functions compare by SymPy's rule | Name; kind enum (`Add`, `Mul`, `Pow`, `Symbol`, `Dummy`, `Wild`, `Integer`, `Rational`, `Float`, each number singleton including `Zero`, `One`, `Half`, `NegativeOne`, each number symbol, `AppliedUndef`, named function, other); class flags; resolved template kinds; `structural`; `class_key`; rank for `Basic.compare` (`_cmp_name`, `ordering_of_classes`) | R1, R2, R11, R15; `euf_adapter.py:85-92`; section 3 |
| Terms | Distinct term | Class; arg ids; payload: rational `p`, `q` as bytes; `Float` mantissa and precision; symbol name; `Dummy` index; `ComplexRootOf` coefficients and index | R1, R14, R16 |
| Term facts | Term | `is_number`; free-symbol ids; `has_nan`, `has_bad`, `has_float`, `has_applied_undef`; non-commutative level 0, 1 or 2; `may_be_nan`; `sort_key` in a form that compares the same | R3, R4, R8, R18; `_may_be_nan` |
| Closed terms | Closed term | `is_finite`; `complex()` value as two exact `f64` bit patterns, for a factor in a sort key | R17; section 3 |
| Power factors | `Pow` factor of a term | `decompose_power` split: base id, exponent rational. If the base isn't an input term, the row holds no base and a key that needs it refuses ("Refused during a run") | Section 3 |
| Atomic numbers | Atomic number | Truth values for the whole vocabulary, from `const_value` | R5 |
| Symbols | Symbol | `assumptions0` | R6 |
| Generic constants | Closed generic constant | The 128-bit bound (`_IV_PREC`) | R9 |
| Formula | Node | `And`, `Or`, `Not`, `Implies`, `Equivalent`, `ITE`, or an atom as predicate id plus term ids, after `to_formula`'s scope check | R10 |

**Dropped from the draft:** the `is` bits. **Call:** args that are `==` but not `is` keep the query on Python (R12). On dev, fuzz and corpus only `MatMul` and `MatrixSlice` hold such args, and those are corpus-only.

### Kept on Python

Conversion decides each of these before sending anything, and the query runs on Python as if Rust didn't exist. Each is counted with its reason.

- A non-`Basic` value in a term, or a class conversion can't row.
- A non-default registry: `register`, custom templates, `clause_templates`, custom `relation_specs`, node facts or custom handlers (section 7, item 2).
- `Sum`, `Product` or `Integral` anywhere in the query (section 7, item 4).
- Args `==` but not `is` (R12).

**Refused during a run.** Rust can also return "refused, with reason" when it reaches a derived shape the term algebra doesn't handle (section 3). Python discards that run and answers on Python. Rust holds no state after a query, so nothing needs undoing, and the query counts as kept on Python.

- **A `Pow` factor whose `decompose_power` base isn't an input term** refuses when a key needs it, not at conversion (planner's ruling on component 0, 7 Nov). This is that mechanism: the whole run is discarded and answered on Python, with no partial result, and it isn't 1a's state transfer. It's an unported shape, so it's reported as a gap, not as a new exception. Reported: refusals at key time, and queries holding such a `Pow` that finished without refusing. The refusal count must not change across hash seeds.
- **A limit on "Rust holds no state":** that covers Rust only. Until component 5, Python's engine and its memos are still running. Component 0's shadow only counts, so it isn't affected. Whichever session first uses Rust's key for real must show that a discarded run leaves nothing in Python, or ask the planner.

### Offline data, read once at load

Generated offline, in one versioned file with a hash of its sources. Rust refuses a file whose hash doesn't match. Nothing here is computed at query time.

- `rules.py` output, including `BASIS_INDEX` (`rules.py:61`), and `_compiled_rows.py`'s `FAMILIES`, with number texts for Rust's parser.
- `wiring.py`'s tables by name, and `core.py`'s module-level tables.
- `noncommutative_false()` (`domain.py:388`).
- **New:** unit facts for `VALUE_AT_INTEGER` (`wiring.py:69`) at integers of size 200 or less, replacing `_value_units`' evaluation.

### Returned

Answer as true, false, none or a status (inconsistent, uninterpreted, budget-limited, gave up), so Python raises what it raises today, writing the text from its original objects, and sets `last_budget_limited`. Also: refused with a reason, the theory-gave-up count for `Engine.stats`, and the count of each callback.

### The one permanent callback

`enclose(term_id, precision) -> (lo, hi)`, read-only, on the original object, during a sign test (R9). It builds no term. By reading, only input terms should reach it: with `lra_adapter.py:213` multiplying field elements directly (section 3), a derived closed value is an element over input constants. No run confirms that, so a derived term reaching it refuses.

## 10. Port order

**Final as a plan. It comes from reading and the censuses, and no step has run.** Solver and the rational LRA core already exist in Rust (`slice/solver_rs`, `lra/port/src/lra.rs`).

**Call: the order needs a component 0.** EUF, relations, engine and knowledge all need the term table and its algebra; only LRA's rational core can go without. **Call: every step works end to end before the next,** with Python doing what isn't ported yet. That follows Tilo's "something that works first", and speed is reported, not a gate.

| # | Component | Modules | Needs from the others | Can run in parallel with | Temporary callbacks |
|---|---|---|---|---|---|
| D | Offline data generator | Writes section 9's file | Nothing | Everything | None |
| 0 | Conversion, term table, term algebra | `sympy_api.py`'s conversion part; `domain.py` reads; `registry.py` class walk; `Add`, `Mul`, negation, key from section 3 | Section 9 | D, 1a, 2, 3 | None. Unhandled shapes refuse and stay on Python |
| 1a | LRA rational: connect the port | `lra.py`, `lra_cert.py` | Solver | D, 0, 2, 3 | Adapter stays Python, calling Rust |
| 1b | LRA constants | `constfield.py`, with a Rust gcd for `_sympy_inner_gcd` | 1a. Term rows from 0 for `_from_sympy` | 2, 3, 6 | R9 `enclose`: **permanent** |
| 2 | EUF core | `euf.py` | Solver; terms as handles until 0 lands | D, 0, 1, 3 | `euf_adapter` stays Python. On `rust-slice`: `slice/results/port-2.md` |
| 3 | Transfer core | `transfer.py`, `EqualitySharing`, `P` | Solver; `BASIS_INDEX` from D; EUF classes, through the Python adapter until 2 | D, 0, 1, 2 | Same |
| 4 | Relations and adapters | `relations.py`, `lra_adapter.py` and `euf_adapter.py` term work, `scope.py` | 0, 1, 2, 3 | 6, by family. Not 1, 2 or 3 while their interfaces move, since it touches every adapter | Templates and `is_` into Python, until 5 and 6. Takes ids and returns clauses over ids |
| 5 | Engine, session, relevance | `engine.py`, `knowledge/compile.py`, `state/`, `_keys_rel`, `_Split`, `_relevant`, `_consistent` | 0, 4 | 6, by family | Templates into Python, until 6 |
| 6 | Runtime knowledge | `rules.py` runtime part, `_rows_runtime.py`, `wiring.py` per-node code, templates except `limits.py`, `realroots.py` | 0, D. `is_` from relations and engine, by callback until 4 and 5 | 1b, 4, 5, by family | `is_` into Python-side engine, until 5 |

**Order to start:** D, 0, 1a, 2 and 3 can begin together. 4 follows 0 to 3. 5 follows 4. 6 can run from 0 and D onward, and finishes after 5. 1b can start after 1a and needs 0's rows to finish.

**The suite censuses (section 8) change neither the order nor the modules.** One thing to carry into 0 and 4: LRA's sort sites (`lra_adapter.py:324`, `:348`, `:412`), which move in 4, reach products of input terms of 4 or more args with `Pow` factors, so 0's key has to cover those or refuse them. The suite doesn't install 0's shadow, so that isn't tested yet.

**The scaffolding has one cost to name.** Until 6 lands, a template callback on a *derived* term needs that term in SymPy, and it isn't there. In that window, Python builds it from Rust's class-and-args recipe. That's SymPy construction at query time, and it's allowed only as temporary scaffolding: Rust's own algebra has still decided the form, and the callback's rebuilt term is checked against it. It goes away with 6, and its count is reported per step. If the planner won't accept even that, 6 has to land before 4, and 4 and 5 then wait for it.

**At the end,** the only callback left is R9's `enclose`, and Python holds conversion, the answer memo, error text and the queries kept on Python. Those are section 9's list, and `lra_bounds.py` and `extensions.py`.

### What each step is held to

- **Reference:** `rust-slice`, which now holds PR 328 (2d00bea; section 5). The PR is held for Tilo; if it doesn't merge, the port's comparison still applies it. Answers and state match Python per session, on a fresh engine with memos cleared. For queries kept on Python there's nothing to compare.
- **Report:** the suite with the three-number report, planted bugs where they apply, callback counts per component, and queries kept on Python, by reason. Speed is reported, not a gate.
- **Standing rulings:**
  - A public-API version of `test_incremental_matches_fresh` and its family during step 5 at the latest, added alongside the existing tests.
  - Each component's port re-scores its own boundary, since these boundaries move. Mutants 2, 5, 6, 7 and 9 rest on the API fuzzer alone and get rerun once real theories run on Rust (from 1a, 2 and 3). 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run.
- **Exactness:** the discovery budget reads node counts, so `_struct` and `_cone_info` weights, including how derived terms merge, must match exactly (section 3). Step 4 tests this with the budget at the boundary values.

## Appendix A: every function

Generated from an AST walk plus the dev and fuzz census. The class column follows section 2's calls by rule, not by reading each function. Suffix on a name: `~i` ran only at import; `~u` didn't run on dev or fuzz, so it's unreached there, not necessarily offline. `port?` means a split module's function that was unreached, so the call is open. No suffix means it ran at query time, or it's a class.

**`__init__.py`**

- port: `__getattr__:15`~i

**`_compat.py`**

- none: `new_name:97`, `old_name:109`, `_deprecated:126`~u, `package_getattr:131`~i, `_optional:143`~u, `_add_renamed:155`, `_AliasLoader:177`, `_AliasLoader.__init__:180`~u, `_AliasLoader.create_module:184`~u, `_AliasLoader.exec_module:199`~u, `_MovedLoader:205`, `_MovedLoader.__init__:211`, `_MovedLoader.__getattr__:214`~u, `_MovedLoader.create_module:217`, `_MovedLoader.exec_module:220`, `AliasFinder:233`, `AliasFinder.find_spec:238`, `AliasFinder.invalidate_caches:260`~u, `install:264`~i

**`engine.py`**

- port: `engine_memos:107`, `InconsistentAssumptions:123`, `_noncommutative:140`, `_noncommutative_answer:151`~u, `_construction_level:165`~u, `_noncommutative_atoms:170`, `_kid:177`, `DictCache:188`, `DictCache.__init__:241`, `DictCache.sync:250`, `DictCache.facts:262`, `DictCache.get:265`~u, `DictCache.put:269`, `AnswerMemo:278`, `AnswerMemo.__init__:283`, `AnswerMemo.put:287`, `Session:304`, `Session.__init__:305`, `Session.var:385`, `Session.dvar:414`, `Session._dvar:449`, `Session._link:481`, `Session.query_lit:506`, `Session.prepare_query:521`, `Session.emit:539`, `Session.node:545`, `Session._visit:572`, `Session._compile_patterns:614`, `Session._emit_pattern:654`, `Session._compile:664`~u, `Session._flush:687`, `Session._custom:707`, `Session._compile_pending:734`, `Session.ensure:772`, `Session.discover:790`, `Session._discover:799`, `Session.incomplete:809`, `Session.escalate:813`, `Session.query_literal:852`, `Session._query_all:906`, `Session.assume_formula:936`, `Session.link_set:972`, `Session.assumption_lits:982`, `Session._set_glue:1072`, `Session._group_sel:1119`, `Session.literal_of:1155`, `Session._relations:1168`, `Session._glue_of:1182`, `Session._ensure_atoms:1198`, `Session._ensure_twins:1210`, `_check_writeback:1230`, `_check_uninterpreted:1239`, `_context_free:1245`~u, `Engine:1251`, `Engine.__init__:1313`, `Engine._fresh_session:1412`, `Engine.extensions:1418`, `Engine.extensions:1425`, `Engine.relation_specs:1431`, `Engine.relation_specs:1440`, `Engine.discovery_budget:1447`~u, `Engine.discovery_budget:1455`~u, `Engine.transfer:1461`, `Engine.transfer:1467`, `Engine.uninterpreted:1473`, `Engine.uninterpreted:1480`, `Engine.writeback:1487`~u, `Engine.writeback:1495`~u, `Engine.relevance:1502`, `Engine.relevance:1508`, `Engine.templates:1514`~u, `Engine.templates:1522`~u, `Engine._settings_changed:1528`~u, `Engine._check_version:1556`, `Engine._settings_fingerprint:1582`, `Engine._drop_set_memos:1589`~u, `Engine._drop_cones:1603`, `Engine._struct:1609`, `Engine._cone_info:1676`, `Engine._query_cone:1726`, `Engine._union:1759`, `Engine._within_budget:1783`, `Engine._over_budget:1829`~u, `Engine._context_session:1835`, `Engine._build_context_memoized:1854`, `Engine._build_context:1878`, `Engine.verdict:1922`, `Engine._complete_check:1952`, `Engine.is_:1986`, `Engine.is_many:2026`, `Engine._decide:2091`, `Engine._put_result:2119`, `Engine._is_custom:2152`, `Engine.ask:2172`, `Engine._ask:2220`, `Engine._note_budget:2246`, `_gave_up:2270`, `_exhausted:2278`, `neighbourhood:2287`~u, `_split:2311`, `want_of:2340`

**`knowledge/compile.py`**

- port: `basis_formula:17`, `_def:31`, `VarTable:64`, `VarTable.__init__:85`, `VarTable.node_base:98`, `VarTable.var:107`, `VarTable.aux:122`, `VarTable.atom:128`~u, `VarTable.atom_of:137`~u, `VarTable.__len__:142`, `VarTable.lit_name:145`~u, `compile_formula:151`, `_or_cnf:271`~u, `formula_literal:378`, `_literal:384`, `_plain:462`~u, `_shared:469`~u, `_Lit:478`, `_Lit.__init__:481`~u, `_true_lit:486`~u

**`knowledge/domain.py`**

- conversion: `_fixed_noncommutative:35`, `constructed_noncommutative:58`~u, `_swept_unary:271`~u, `_fixed_level:281`~u, `_plain_undefined:301`~u, `_label:320`~u, `_nonzero_number:329`~u, `_nc_symbol:335`~u, `_nc_product_level:340`~u, `_nc_sum_level:356`~u, `noncommutative_false:388`~u, `_is_matrix:402`, `_holds_matrix:406`, `_matrix_to_scalar:418`, `_noncommutative:431`
- port: `kept_product:474`

**`knowledge/extensions.py`**

- python: `Args:42`, `_name:48`~u, `Snapshot:57`, `Extensions:63`, `Extensions.__init__:64`~i, `Extensions.version:75`, `Extensions.version:83`, `Extensions.register:88`~u, `Extensions.unregister:109`~u, `Extensions._vocab_changed:117`~u, `Extensions.snapshot:123`~u, `Extensions.restore:133`~u, `Extensions.is_registered:150`~u, `Extensions.handlers:157`, `Extensions.is_scalar_like:162`, `Extensions.is_scalar_class:167`, `Extensions.facts_for:175`, `Extensions.node_facts:183`~u, `Extensions._node_handlers:193`~u, `_collect:205`~u, `register:224`~u, `unregister:235`~u

**`knowledge/realroots.py`**

- port: `_strip:22`~u, `_rem:29`~u, `_monic:41`~u, `_primitive:45`~u, `gcd:58`~u, `_derivative:66`~u, `_div:71`~u, `squarefree:84`~u, `_chain:89`~u, `_changes:100`~u, `_at_inf:105`~u, `_at_zero:109`~u, `real_root_counts:113`~u, `_distinct_nonzero_real_roots:128`~u, `imaginary_root_count:139`~u, `root_facts:154`~u

**`knowledge/rules.py`**

- offline: `_lit:123`~i, `_side:133`~i, `compile_rule:143`~i, `compile_rules:167`~i, `_cnf:195`~i, `minimize_for_propagation:392`~i
- port: `basis_lits:183`, `cnf_of:207`, `expand_clause:270`, `lit_bit:303`, `lits_mask:309`, `mask_lits:317`, `_masks:328`, `closure_mask:355`, `unit_propagate:383`
- port?: `_basis_models:219`~u, `def_implications:243`~u

**`knowledge/templates/__init__.py`**

- port: `_may_be_nan:142`, `_applied_to_nan:162`

**`knowledge/templates/_common.py`**

- port: `const_key:50`, `lits:55`, `Rules:59`, `Rules.__init__:63`, `Rules.rule:66`, `Rules.equiv:71`~u, `ge2_alternatives:77`~u, `const_value:83`, `_resolve_lit:104`, `resolve:121`, `instantiate:162`~u, `_unsubsumed:185`, `Pattern:224`, `Pattern.__init__:236`, `TemplateKeyError:280`, `Compiled:287`, `Compiled.__init__:292`, `Compiled.formulas:296`~u, `Compiled.wide_formulas:299`~u, `facts:325`, `units:340`, `_signed:394`, `consts_of:399`, `pattern_key:407`

**`knowledge/templates/_rows.py`**

- offline: `Constant:147`, `Arguments:169`, `Arguments.__iter__:175`~u, `_over:197`~u, `_function:205`~u, `every:210`~u, `some:216`~u, `count:222`~u, `_applied:227`~u, `Rows:233`, `Rows.__init__:238`~u, `Rows.__and__:241`~u, `Rows.__rand__:244`~u, `Rows.__rrshift__:247`~u, `Rows.__iter__:251`~u, `_Conditioned:255`, `_Conditioned.__and__:260`~u, `_row:267`~u, `_literal:277`~u, `_flat:281`~u, `closed:292`~u, `rows_of:297`~u, `ForAll:302`, `AtMost:308`, `for_all:315`~u, `by_function:340`~u, `bind:353`~u, `_node:368`~u, `rules:377`~u, `compile_rows:385`~u, `_term_order:435`~u, `_term_data:444`~u, `_number_data:456`~u, `_constant_text:467`~u, `constant_term:476`~u, `from_text:492`~u, `_specs:499`~u, `_conjuncts:529`~u, `_value_equality:539`~u, `_lit:570`~u, `_of_constant_only:601`~u, `_of_constant:606`~u, `_shift:629`~u, `_times:643`~u, `_number:657`~u, `_compared:663`~u, `_relation:669`~u, `_slots:692`~u, `_not_an_argument:733`~u, `_shape:741`~u, `_constant_shape:775`~u, `_not_distinct:787`~u, `_inner:792`~u, `_value_data:801`~u, `_term:817`~u, `_plain:838`~u, `_schema:851`~u, `_pick:906`~u, `_star_lit:922`~u, `_star_rule:948`~u, `_implies:966`~u, `_groups:976`~u

**`knowledge/templates/_rows_runtime.py`**

- port: `from_text:32`, `constant_value:47`, `_read:60`, `_shape_object:74`, `_term_object:80`, `generator:91`

**`knowledge/templates/atoms.py`**

- port: `symbol_units:35`, `constant_units:47`, `value_units:51`

**`knowledge/templates/core.py`**

- port: `_half_split:58`, `_coeff_term:88`, `_half_rules:100`, `_half_templates:120`, `_bound_split:150`, `_bound_rules:166`, `_bound_templates:183`, `_recip_rules:203`~u, `_recip_templates:225`, `_imag_term:235`, `_imag_split:252`, `_imag_rules:259`~u, `_imag_number_rules:280`~u, `_imag_templates:288`~u, `_not_unit_premises:309`~u, `_mul_factor_sets:325`, `_quotient_rules:353`, `_quotient_templates:360`, `_unit_angle:380`, `ipi_split:392`, `pi_split:400`, `_pi_split:406`, `_ipi_table_rows:448`~u, `ipi_rules:476`~u, `irrational_root:485`, `_unit_power_units:498`~u, `_exp_arg:524`, `_pow_bound_templates:533`, `_table:575`~u, `__getattr__:584`

**`knowledge/templates/functions.py`**

- port: `_unary:41`, `shifted:84`, `_exp_ipi:100`, `_parts_of_round_rules:143`~u, `parts_of_round_templates:150`, `_pi_trig_rules:177`~u, `_pi_trig:214`, `_in_unit_interval_units:247`~u, `_cosh_shift_rules:280`~u, `_cosh_shift_split:302`, `_cosh_shift:322`, `nary:354`, `_value_units:398`~u, `_genocchi_half:412`~u

**`knowledge/templates/limits.py`**

- port: `_inner:75`~u, `_scalar:102`~u, `_plain:110`~u, `_compiled:120`~u, `_sum_or_product:127`~u, `sum_templates:176`~u, `product_templates:181`~u, `integral_templates:186`~u

**`knowledge/templates/nodes.py`**

- port: `_accum:22`~u, `accumbounds_templates:30`~u, `idx_units:37`~u

**`knowledge/templates/physics.py`**

- port: `quantity_units:22`~u

**`knowledge/templates/registry.py`**

- port: `own_facts:54`, `_redefines:62`, `TemplateRegistry.__init__:75`, `TemplateRegistry.lazy:97`, `TemplateRegistry._covers:124`, `TemplateRegistry._load:141`, `TemplateRegistry.load_all:155`, `TemplateRegistry.register:161`, `TemplateRegistry.templates_for:194`, `TemplateRegistry.clauses_for:226`, `_split:265`
- port?: `TemplateRegistry:74`, `TemplateRegistry._imported:136`~u, `TemplateRegistry.facts_for:216`~u, `TemplateRegistry.classes:245`~u, `_collect:250`~u

**`knowledge/templates/rootof.py`**

- port: `_coefficients:22`~u, `_facts:31`~u, `crootof_units:45`~u

**`knowledge/templates/special.py`**

- port: `_register:38`~u, `_doubled:56`~u, `_multigamma_rules:66`~u, `multigamma_templates:88`~u

**`knowledge/templates/stats.py`**

- port: `randomsymbol_units:22`~u

**`knowledge/templates/table.py`**

- port: `Row:44`, `Row.__init__:49`~u, `Row._compile:64`~u, `Row.__repr__:72`~u, `Row.text:75`~u, `Section:90`, `Section.__init__:94`~u, `_holds:102`~u, `_norm:109`~u, `_lits:116`~u, `_premise_alternatives:128`~u, `_row_specs:148`~u, `_rows:164`~u, `_bindings:175`~u, `expand:193`~u, `rules_of:209`~u, `iter_rows:218`~u, `count_rows:227`~u

**`knowledge/templates/wiring.py`**

- port: `template:94`, `load:151`, `_declared:176`, `_attributed:186`, `matches:196`, `power:223`, `expand:381`, `_placements:417`, `_allowed:440`, `_instances:453`, `_wide_of:558`, `rows_block:565`, `rules_for:596`, `product:620`, `addition:650`
- port?: `functions:87`~u, `piecewise_values:349`~u, `_clauses:479`~u, `wide_formulas:489`~u, `_wide:511`~u, `_atom:535`~u, `any_arity:539`~u

**`ref.py`**

- none: `RefInfo:91`, `RefInfo.__init__:98`~u, `RefInfo.__repr__:108`~u, `theory_scope:119`~u, `_RefEngine:163`, `_RefEngine.__init__:170`~u, `_RefEngine.is_:183`~u, `_RefEngine.is_many:198`~u, `_RefSession:204`, `_RefSession.__init__:211`~u, `_RefSession.emit:231`~u, `_RefSession.var:235`~u, `_RefSession.ensure:257`~u, `_RefSession._flush:260`~u, `_RefSession.discover:272`~u, `_RefSession.node:282`~u, `_RefSession._visit:291`~u, `_RefSession._emit_pattern:328`~u, `_RefSession._compile:345`~u, `_RefSession._custom:349`~u, `_RefSession.assume_formula:368`~u, `_RefSession.literal_of:381`~u, `_RefSession.glue:397`~u, `_translate:426`~u, `_assumption_lits:437`~u, `_entails:450`~u, `_glue_atoms_of:463`~u, `_answer:477`~u, `ask_ref:522`~u, `_routed:565`~u, `ref_outcome:595`~u

**`relations.py`**

- port: `AdapterSpec:378`, `_missing:384`~u, `closed_units:394`, `with_closed_units:422`, `default_specs:434`, `Uninterpreted:455`, `_key:464`, `_ext_atoms:469`, `_affine_strip:478`, `relation_atom:510`, `relational_name:541`~u, `sympy_atom:549`, `_is_number:562`, `_under_apps:570`, `zero_args:594`, `under_of:606`, `zero_twin:617`~u, `zero_twins:629`, `glue_atoms:658`, `_termwise:672`, `_constant_term:691`, `_number_basis:697`, `_number_facts:751`, `_own_term:760`, `Relations:776`, `Relations.__init__:780`, `Relations.enqueue:868`, `Relations.note_formula:871`, `Relations.process:877`, `Relations._mention_number:957`, `Relations._link_later:974`, `Relations._fresh:979`, `Relations._adapter:991`, `Relations._interpret:997`, `Relations._guard:1081`, `Relations._link_integer:1105`, `Relations._eq_infinity:1126`, `Relations._trichotomy:1153`, `Relations._add_role:1196`, `Relations._apply_role:1218`, `Relations._tsource:1263`, `Relations._tvar:1281`, `Relations._atom_selector:1316`, `Relations._eq_links:1324`, `Relations._closed_extended_real:1374`, `Relations._order_sides:1386`, `Relations._order_infinite:1404`, `Relations._bound:1462`~u, `Relations._atom_var:1474`, `Relations._link:1479`, `Relations.wants_transfer:1515`, `Relations.selectors_of:1526`, `Relations._share:1583`, `Relations._share_guard:1600`, `Relations._congruent:1624`, `Relations._note_sides:1654`, `Relations._engage_transfer:1662`, `Relations._transfer_terms:1691`, `Relations.sync_transfer:1750`, `Relations._xswitch:1848`, `Relations._congruence_pairs:1855`, `_guarded_adapters:1922`, `_terms_of:1935`, `_structural_subterms:1948`, `link_objects:1970`, `glue_objects:1994`

**`sat/formula.py`**

- port: `P:14`, `P.__repr__:19`~u, `P.__invert__:22`~u, `P.__and__:25`~u, `P.__or__:28`~u, `P.__rshift__:31`~u, `Formula:35`, `Formula.__init__:38`, `Formula.__repr__:41`~u, `Formula.__eq__:44`, `Formula.__hash__:47`, `Formula.__invert__:50`~u, `Formula.__and__:53`~u, `Formula.__or__:56`~u, `Formula.__rshift__:59`~u, `And:63`, `Or:67`, `Not:71`, `Not.__init__:72`, `Implies:76`, `Implies.__init__:77`~u, `Equivalent:81`, `Equivalent.__init__:82`~u, `Exclusive:86`, `ITE:90`, `ITE.__init__:95`~u, `allargs:105`~u, `anyarg:111`~u, `exactlyonearg:117`~u, `atoms_of:126`

**`sat/solver.py`**

- port: `Clause:43`, `BlockOwner:68`, `BlockOwner.__init__:74`~u, `BlockOwner.__eq__:77`~u, `BlockOwner.__hash__:80`~u, `BlockOwner.__repr__:83`~u, `_common:87`, `_is_learnt:98`, `_luby:102`, `_block_models:122`, `_BlockClosure:200`, `_BlockClosure.__init__:213`, `_BlockClosure.flags:237`, `_BlockClosure.lits_of:250`, `_BlockClosure.values_of:265`, `_BlockClosure.closure:279`, `_BlockClosure.model_of:307`, `_BlockClosure.explain:314`, `_rule_tables:362`, `Solver:390`, `Solver.__init__:402`, `Solver.new_var:538`~u, `Solver.nvars:544`~u, `Solver._grow:547`, `Solver._to_int:572`~u, `Solver._to_ext:576`~u, `Solver._internal_lits:579`, `Solver._heap_insert:597`, `Solver._heap_up:606`, `Solver._heap_down:623`, `Solver._heap_pop:646`, `Solver._bump_var:658`, `Solver._bump_clause:669`, `Solver.add_clause:680`, `Solver._add_lits:694`, `Solver._attach_held:758`, `Solver.add_clauses:823`~u, `Solver.ensure_vars:912`, `Solver.add_internal:917`, `Solver.add_pattern:974`~u, `Solver.set_rule_block:1032`, `Solver.register_block:1080`, `Solver._rb_settle:1176`, `Solver._rb_reason:1225`, `Solver._mention:1243`, `Solver._rb_room:1270`, `Solver.mention_blocks:1280`, `Solver._rb_mentioned:1321`, `Solver._rb_late:1350`, `Solver.mention:1388`, `Solver.propagate:1395`, `Solver.value:1412`, `Solver.root_trail:1422`~u, `Solver.implied:1429`, `Solver.release:1445`, `Solver._assume:1457`, `Solver._assume_propagate:1548`, `Solver._propagate:1600`, `Solver._propagate_clauses:1734`~u, `Solver._backtrack:1805`, `Solver.attach_theory:1851`, `Solver.theories:1872`, `Solver.register_atom:1876`, `Solver.theory_models:1932`~u, `Solver._tpropagate:1938`, `Solver._theory_sync:1953`, `Solver._theory_clause:1982`, `Solver._theory_conflict:1994`, `Solver._theory_imply:2025`, `Solver._theory_decide:2063`, `Solver._theory_check:2091`, `Solver._learn:2105`, `Solver._analyze:2144`, `Solver._analyze_final:2227`, `Solver._pick_branch:2265`, `Solver.set_inert:2296`, `Solver._reduce_db:2321`~u, `Solver._search:2348`, `Solver.solve:2419`, `Solver._solve:2432`, `Solver._fill:2516`, `Solver._model:2540`~u, `Solver._ring_hit:2553`, `Solver._ring_blocks:2613`~u, `Solver.model:2634`~u, `Solver.conflict:2639`~u, `Solver._witness_satisfies:2649`, `Solver.consistent:2665`, `Solver.entails:2677`, `Solver.entails_all:2719`, `Solver.root_step:2754`~u, `Solver.provenance:2793`~u, `Solver.stats:2826`~u

**`sat/theory.py`**

- port: `TheorySolver:108`, `TheorySolver.register_atom:112`~u, `TheorySolver.assert_lit:125`~u, `TheorySolver.check:136`~u, `TheorySolver.push_level:152`~u, `TheorySolver.pop_level:156`~u, `PropagatingTheory:163`, `PropagatingTheory.propagate:181`~u, `EqualitySharing:185`, `EqualitySharing.__init__:202`, `EqualitySharing.update:206`

**`scope.py`**

- port: `Scope:122`, `affine_pair:133`, `linked_terms:150`, `scope_of_atoms:164`, `theory_scope:177`, `_custom_pred:192`, `extension_atoms:196`

**`state/epoch.py`**

- port: `bump:42`

**`state/memos.py`**

- port: `Table:49`, `Table.__init__:57`~i, `Table.put:63`~u, `Table.restamp:72`, `Table.reset:77`~u, `Table.__repr__:84`~u, `Memos:89`, `Memos.__init__:92`, `Memos.table:99`~i, `Memos.adopt:109`, `Memos.items:117`~u, `Memos.names:128`~u, `Memos.sizes:131`~u, `Memos.clear:134`~u, `Memos.__repr__:143`~u, `_path:151`~u, `_module_attr:168`, `load_owners:187`~u, `__getattr__:206`, `adopt:213`, `module_locations:222`~u, `owner_memos:234`

**`sympy_api.py`**

- conversion: `Unsupported:144`, `Unsupported.__init__:148`, `AssumptionSymbolError:154`, `AssumptionSymbolError.__init__:161`~u, `_declared:167`~u, `check_strict:178`~u, `default_engine:206`, `set_default_engine:213`~u, `matrix_predicates:225`, `_is_matrix_predicate:241`, `_is_scalar:253`, `_applied_category:257`, `_categories:279`~u, `out_of_scope:300`~u, `relation_parts:316`, `_relation_formula:339`, `to_formula:354`, `ask:418`, `_formula:496`, `_Failed:519`, `_Failed.__init__:522`, `is_constant_proposition:530`
- port: `_ask:560`, `_ask_general:576`, `_const_base:693`, `_const_free:705`, `_closed_keys:724`, `_expr_keys:745`, `_arg_keys:768`, `_keys:779`~u, `_keys_rel:784`, `_bool_keys:807`, `_sides_keys:844`, `_Split:864`, `_Split.__init__:869`, `_Split.part:912`, `_relevant:929`, `_vocab_blocks:1009`~u, `_part_consistent:1076`, `_consistent:1088`, `_engine_ask:1111`

**`theories/euf/euf.py`**

- port: `EqAtom:75`, `EqAtom.__new__:84`, `EqAtom.__getnewargs__:87`~u, `EqAtom.__repr__:90`~u, `EUFTheory:101`, `EUFTheory.__init__:118`, `EUFTheory._new:146`, `EUFTheory.term:160`, `EUFTheory.value:181`, `EUFTheory._apply:188`, `EUFTheory._index_app:197`, `EUFTheory.find:225`~u, `EUFTheory.equal:229`~u, `EUFTheory.explain:232`, `EUFTheory._reroot:243`, `EUFTheory._union:254`, `EUFTheory._undo_union:319`, `EUFTheory._process:335`, `EUFTheory._explain_edge:344`, `EUFTheory._explain:363`, `EUFTheory.register_atom:408`, `EUFTheory._index_atom:422`, `EUFTheory.assert_lit:434`, `EUFTheory.check:463`, `EUFTheory.propagate:468`, `EUFTheory.push_level:487`, `EUFTheory.pop_level:490`, `EUFTheory.__repr__:530`~u

**`theories/euf/euf_adapter.py`**

- conversion: `EUFAdapter.parse:116`
- port: `_inherits_from_basic:66`, `structural:73`, `EUFAdapter:98`, `EUFAdapter.__init__:105`, `EUFAdapter.interprets:139`~u, `EUFAdapter.register:142`, `EUFAdapter.attach:156`, `EUFAdapter.term:169`, `EUFAdapter.node_term:176`, `EUFAdapter._intern:191`, `EUFAdapter.interned:216`, `EUFAdapter.term_of:231`, `EUFAdapter.terms_since:235`, `EUFAdapter.shared_terms:243`

**`theories/lra/constfield.py`**

- port: `Undecided:180`, `TooLarge:188`, `_zero:198`, `_mk:202`, `_add:213`, `_neg:237`, `_sub:243`~u, `_scale:247`, `_mul:254`, `_too_many_bits:278`~u, `_add_bounded:282`~u, `_mul_bounded:310`~u, `_mul_fast:338`~u, `_mul_checked:348`, `_pow_checked:363`, `_deg:377`~u, `_lc:381`~u, `_lcrec:385`, `_shift:392`~u, `_divexact:399`, `_monomial:435`, `_order:446`, `_udiv:454`~u, `_monic:473`~u, `_ugcd:483`~u, `_inner_gcd:510`, `_denominators:537`~u, `_to_dmp:555`~u, `_from_dmp:568`~u, `_sympy_inner_gcd:577`~u, `_gcd:595`~u, `_psize:605`, `_short:637`~u, `_checked:642`, `_vars:652`, `_qenc:664`, `_ieval:671`, `Constant:694`, `Constant.__init__:709`~i, `Constant.enclose:718`, `Constant.__repr__:727`~u, `constant:735`~i, `_scaled_down:749`, `_atan_inv:754`, `_pi_enclose:768`, `_e_enclose:776`~u, `_iroot:789`~u, `radical:801`~u, `num:827`, `formally_zero:840`, `sign:847`, `_make:854`, `_coerce:872`, `_coerce_foreign:885`~u, `Element:906`, `Element._new:914`, `Element.__init__:925`~u, `Element.numerator:931`~u, `Element.denominator:935`~u, `Element.constants:938`~u, `Element._varset:942`, `Element._size:948`, `Element._budget_scale:957`, `Element._budget_product:964`, `Element._single_transcendental:978`, `Element.__hash__:987`, `Element.__neg__:995`, `Element.__pos__:998`~u, `Element.__abs__:1001`~u, `Element.__add__:1004`, `Element.__sub__:1033`, `Element.__rsub__:1039`, `Element.__mul__:1045`, `Element._inverse:1073`, `Element.__truediv__:1085`, `Element.__rtruediv__:1098`, `Element.__pow__:1104`, `Element._env:1120`, `Element._precisions:1123`, `Element._nonzero:1134`, `Element.sign:1150`, `Element.enclosure:1170`, `Element._cmp:1191`, `Element.__eq__:1209`, `Element.__ne__:1226`, `Element.__lt__:1230`, `Element.__le__:1234`, `Element.__gt__:1238`, `Element.__ge__:1242`, `Element.__bool__:1246`, `Element.__floor__:1249`, `Element.__ceil__:1258`, `Element.is_integer:1261`, `Element.to_sympy:1281`~u, `Element.__repr__:1293`~u, `pi_laurent:1325`, `from_sympy:1353`, `_Unread:1367`, `_from_sympy:1375`, `_generic:1415`, `_sympy_constant:1439`~u

**`theories/lra/lra.py`**

- port: `Negated:230`, `Negated.__new__:235`~u, `Negated.__getnewargs__:238`~u, `Negated.__repr__:241`~u, `Integral:247`, `Integral.__new__:252`, `Integral.__getnewargs__:255`~u, `Integral.__repr__:258`~u, `constraint:265`~u, `_is_int:287`~u, `_floor:298`, `_ceil:312`, `_within_cert:323`, `_dedupe:329`, `LRATheory:339`, `LRATheory.__init__:348`, `LRATheory.undecidable:411`~u, `LRATheory.certified:417`~u, `LRATheory.certified_with:427`~u, `LRATheory.rational_values:434`~u, `LRATheory._certificate:448`, `LRATheory._certify:466`, `LRATheory._new_var:479`, `LRATheory._term_var:494`, `LRATheory._slack:498`, `LRATheory._give_up:541`~u, `LRATheory.register_atom:545`, `LRATheory.assert_lit:553`, `LRATheory.check:590`, `LRATheory.propagate:599`, `LRATheory._register_atom:646`, `LRATheory._lin:681`, `LRATheory._var_of_form:701`, `LRATheory._register_integral:719`, `LRATheory.push_level:749`, `LRATheory.pop_level:753`, `LRATheory._undo_to:759`, `LRATheory._assert_kind:781`, `LRATheory._set_upper:801`, `LRATheory._set_lower:816`, `LRATheory._update:831`, `LRATheory._assert_integral:857`, `LRATheory._int_verdict:870`, `LRATheory._int_verdict_bounds:891`, `LRATheory._int_bounds:907`, `LRATheory._branch:917`, `LRATheory._simplex:1010`, `LRATheory._pivot_and_update:1055`, `LRATheory._pivot_rational:1080`, `LRATheory._pivot:1110`, `LRATheory._concrete:1158`, `LRATheory._model:1173`, `LRATheory._check:1176`, `LRATheory._implied:1234`, `LRATheory.__repr__:1268`~u

**`theories/lra/lra_adapter.py`**

- conversion: `relation:155`
- port: `_Unhandled:139`, `_lin:179`, `_closed:225`, `closed_sign:254`, `constant_bounds:275`, `constant_enclosure:283`~u, `_linear:289`, `to_constraint:302`~u, `_constraint:318`, `interpret:337`, `terms:351`~u, `_side:359`, `order_sides:382`, `integer_form:400`, `_memoized:439`, `LRAAdapter:454`, `LRAAdapter.__init__:466`, `LRAAdapter.register:471`, `LRAAdapter._attach:490`, `LRAAdapter.interpret:498`, `LRAAdapter.order_sides:504`, `LRAAdapter.integer_form:508`, `LRAAdapter.register_integer:512`, `LRAAdapter.terms:520`, `LRAAdapter.to_constraint:525`~u, `LRAAdapter.register_bounds:530`~u, `LRAAdapter.shared_terms:547`

**`theories/lra/lra_bounds.py`**

- python: `constant_bounds:36`, `_bounds:59`, `_iv_context:75`, `constant_enclosure:89`~u, `_enclosure:109`~u, `_rational:119`~u, `_mag:126`~u, `_sign:135`~u, `_heads:145`, `_interval:150`, `_iv_atan:268`~u, `_iv_zeta:281`~u, `_iv_asin:330`~u, `_loose:346`~u, `_iv_exp:361`~u

**`theories/lra/lra_cert.py`**

- port: `_ceil_abs:31`, `_magnitude:35`, `within:41`, `_window:53`, `_decided:60`, `limits:83`, `_limits_suffice:90`, `CertAtoms:102`, `CertAtoms.__init__:109`, `CertAtoms.update:125`, `certify:188`

**`theories/transfer.py`**

- port: `transfer_wanted:94`, `TransferTheory:109`, `TransferTheory.__init__:113`, `TransferTheory.guard:146`, `TransferTheory.switch:158`, `TransferTheory._kind:174`, `TransferTheory._why:187`, `TransferTheory._merged:196`, `TransferTheory.register_atom:200`, `TransferTheory.assert_lit:223`, `TransferTheory.set_fixed:253`, `TransferTheory._explain:264`, `TransferTheory._members_on:272`, `TransferTheory._scan:296`, `TransferTheory._spread:357`, `TransferTheory._classes:403`, `TransferTheory.propagate:423`, `TransferTheory.check:456`, `TransferTheory.decide:471`, `TransferTheory.push_level:526`, `TransferTheory.pop_level:530`, `TransferTheory.__repr__:545`~u

## Appendix B: direct SymPy calls at query time

From the census, dev and fuzz together, per satassume function: SymPy function and call count. `__hash__`, `__eq__` and `__ne__` are collapsed into `hash/eq`. Line numbers per read are in section 4.

| Function | Calls |
|---|---|
| `engine.py` `AnswerMemo.put` | hash/eq 14,023 |
| `engine.py` `DictCache.facts` | hash/eq 1,282 |
| `engine.py` `DictCache.put` | hash/eq 213 |
| `engine.py` `Engine._cone_info` | hash/eq 92,160 |
| `engine.py` `Engine._query_cone` | hash/eq 10,884 |
| `engine.py` `Engine._query_cone.<genexpr>` | Basic.free_symbols 957 |
| `engine.py` `Engine._struct` | hash/eq 31,449, Basic.args 412 |
| `engine.py` `Engine._union` | hash/eq 298 |
| `engine.py` `Engine._within_budget` | hash/eq 1,314 |
| `engine.py` `Engine.is_` | hash/eq 2,355 |
| `engine.py` `Engine.is_many` | hash/eq 16 |
| `engine.py` `Session._compile_patterns` | hash/eq 83,295 |
| `engine.py` `Session._compile_pending` | hash/eq 56,032 |
| `engine.py` `Session._discover` | hash/eq 113,111 |
| `engine.py` `Session._dvar` | hash/eq 87,300 |
| `engine.py` `Session._link` | hash/eq 7,828 |
| `engine.py` `Session._set_glue` | hash/eq 5,199 |
| `engine.py` `Session._set_glue.<genexpr>` | hash/eq 11,427 |
| `engine.py` `Session.ensure` | hash/eq 337,720 |
| `engine.py` `Session.escalate` | hash/eq 99 |
| `engine.py` `Session.node` | hash/eq 273,281 |
| `knowledge/compile.py` `VarTable.node_base` | hash/eq 54,292 |
| `knowledge/compile.py` `_def` | hash/eq 1,218 |
| `knowledge/domain.py` `_noncommutative` | hash/eq 12,182, Basic.args 1,647 |
| `knowledge/domain.py` `kept_product` | Basic.args 78, cached call 39 |
| `knowledge/templates/__init__.py` `_applied_to_nan` | Basic.args 36 |
| `knowledge/templates/__init__.py` `_may_be_nan` | Basic.args 28 |
| `knowledge/templates/_common.py` `const_value` | is_* property 2,611, Expr.is_hermitian 74, Expr.is_antihermitian 31 |
| `knowledge/templates/_common.py` `facts` | hash/eq 689 |
| `knowledge/templates/_common.py` `units` | hash/eq 36 |
| `knowledge/templates/_rows_runtime.py` `_read` | cached call 33, Integer.__mul__ 21, sympified op 9, Integer.__sub__ 3, Expr.__neg__ 1 |
| `knowledge/templates/_rows_runtime.py` `from_text` | SingletonRegistry.__call__ 83 |
| `knowledge/templates/atoms.py` `symbol_units` | Symbol.assumptions0 17 |
| `knowledge/templates/core.py` `<module>` | sympified op 2, One.__neg__ 2, Rational.__neg__ 2 |
| `knowledge/templates/core.py` `_bound_rules` | Integer.__mul__ 333, BooleanTrue.__bool__ 299, Integer.__add__ 207, Integer.__gt__ 117, sympified op 111, Integer.__lt__ 96, Integer.__radd__ 87, Rational.__gt__ 87, BooleanFalse.__bool__ 70, hash/eq 70, Rational.__lt__ 69 |
| `knowledge/templates/core.py` `_bound_split` | hash/eq 76, Expr.is_number 17 |
| `knowledge/templates/core.py` `_coeff_term` | Basic.args 482 |
| `knowledge/templates/core.py` `_exp_arg` | ExpMeta.__instancecheck__ 8 |
| `knowledge/templates/core.py` `_half_split` | Basic.args 530, Integer.__rmul__ 149, sympified op 111 |
| `knowledge/templates/core.py` `_imag_term` | Basic.args 271, hash/eq 1 |
| `knowledge/templates/core.py` `_mul_factor_sets` | Basic.args 93, is_* property 5 |
| `knowledge/templates/core.py` `_pi_split` | Basic.args 94, Integer.__mul__ 51 |
| `knowledge/templates/core.py` `_pow_bound_templates` | Basic.args 8 |
| `knowledge/templates/core.py` `_quotient_templates` | Basic.args 193 |
| `knowledge/templates/core.py` `_unit_angle` | Basic.args 1, hash/eq 1 |
| `knowledge/templates/functions.py` `_cosh_shift.template` | Basic.args 2 |
| `knowledge/templates/functions.py` `_exp_ipi.template` | Basic.args 1 |
| `knowledge/templates/functions.py` `_pi_trig.template` | Basic.args 8 |
| `knowledge/templates/functions.py` `_unary.template` | Basic.args 70 |
| `knowledge/templates/functions.py` `parts_of_round_templates` | Basic.args 6 |
| `knowledge/templates/functions.py` `shifted` | sympified op 2 |
| `knowledge/templates/registry.py` `TemplateRegistry.clauses_for` | hash/eq 21,628 |
| `knowledge/templates/wiring.py` `_instances` | cached call 392 |
| `knowledge/templates/wiring.py` `addition.template` | Basic.args 240 |
| `knowledge/templates/wiring.py` `matches` | hash/eq 16 |
| `knowledge/templates/wiring.py` `power.template` | Basic.args 8, sympified op 6, cached call 3 |
| `knowledge/templates/wiring.py` `product.template` | Basic.args 93 |
| `knowledge/templates/wiring.py` `template.<lambda>.<genexpr>` | SingletonRegistry.__call__ 2 |
| `relations.py` `Relations._congruence_pairs` | hash/eq 24,481, Basic.args 6,604 |
| `relations.py` `Relations._congruent` | hash/eq 51,177, Basic.args 26,674, Basic.func 8,501 |
| `relations.py` `Relations._eq_links` | sympified op 1,620 |
| `relations.py` `Relations._guard` | hash/eq 75,386 |
| `relations.py` `Relations._link` | hash/eq 9,798 |
| `relations.py` `Relations._link_later` | hash/eq 28,496 |
| `relations.py` `Relations._mention_number` | hash/eq 863 |
| `relations.py` `Relations._note_sides` | hash/eq 36,513 |
| `relations.py` `Relations._order_infinite` | hash/eq 51,955 |
| `relations.py` `Relations._transfer_terms` | hash/eq 20,184, Basic.func 3,886, Basic.args 3,886 |
| `relations.py` `Relations._tsource` | hash/eq 236,896 |
| `relations.py` `Relations._tvar` | hash/eq 43,245 |
| `relations.py` `Relations.note_formula` | hash/eq 11,953 |
| `relations.py` `Relations.selectors_of` | hash/eq 14,122 |
| `relations.py` `Relations.selectors_of.<genexpr>` | hash/eq 25,648 |
| `relations.py` `Relations.sync_transfer` | hash/eq 30,187, cached call 5,854 |
| `relations.py` `_affine_strip` | hash/eq 7,756, Expr.as_coeff_Mul 6,645, Expr.as_coeff_Add 5,470, Add.as_coeff_Add 1,564, Mul.as_coeff_Mul 213 |
| `relations.py` `_is_number` | Expr.is_number 78,449, Basic.free_symbols 60,220 |
| `relations.py` `_key` | default_sort_key 45,424 |
| `relations.py` `_number_basis` | hash/eq 1,055 |
| `relations.py` `_own_term` | hash/eq 12,288 |
| `relations.py` `_structural_subterms` | hash/eq 37,984, Basic.args 14,064 |
| `relations.py` `_terms_of` | hash/eq 44,881 |
| `relations.py` `_termwise` | Mul.__neg__ 3,091, Expr.__neg__ 1,479 |
| `relations.py` `_termwise.terms` | AssocOp.make_args 8,838 |
| `relations.py` `_under_apps` | hash/eq 6,218, Basic.atoms 359 |
| `relations.py` `closed_units` | hash/eq 21,628, Expr.is_number 377 |
| `relations.py` `glue_objects` | hash/eq 5,391, sympified op 1,520 |
| `relations.py` `link_objects` | hash/eq 30,021 |
| `relations.py` `relation_atom` | hash/eq 935, Integer.__lt__ 166, BooleanFalse.__bool__ 131, BooleanTrue.__bool__ 115, Integer.__gt__ 74, Rational.__lt__ 6 |
| `relations.py` `sympy_atom` | Q.* accessor 6,244, BinaryRelation.__call__ 3,122 |
| `relations.py` `zero_args` | hash/eq 14 |
| `sat/theory.py` `EqualitySharing.update` | hash/eq 367,043 |
| `scope.py` `affine_pair` | hash/eq 126, Basic.free_symbols 65 |
| `scope.py` `linked_terms` | hash/eq 23,908 |
| `sympy_api.py` `_Split.__init__` | Basic.args 1,782 |
| `sympy_api.py` `_Split.part` | LatticeOp.__new__ 80 |
| `sympy_api.py` `_applied_category` | AppliedPredicate.function 4,572, AppliedPredicate.arguments 2,286 |
| `sympy_api.py` `_ask_general` | hash/eq 3,524 |
| `sympy_api.py` `_bool_keys` | AppliedPredicate.function 4,962, AppliedPredicate.arguments 3,884, hash/eq 15, Basic.args 1 |
| `sympy_api.py` `_closed_keys` | hash/eq 31, Basic.args 31 |
| `sympy_api.py` `_const_base` | hash/eq 17, Basic.args 1 |
| `sympy_api.py` `_const_free` | hash/eq 156, Basic.args 13 |
| `sympy_api.py` `_engine_ask` | Printable.__str__ 207 |
| `sympy_api.py` `_expr_keys` | Basic.args 11,945, hash/eq 9,641 |
| `sympy_api.py` `_formula` | hash/eq 14,364 |
| `sympy_api.py` `_keys_rel` | hash/eq 16,762 |
| `sympy_api.py` `_part_consistent` | hash/eq 137 |
| `sympy_api.py` `_relevant` | hash/eq 5,074 |
| `sympy_api.py` `_relevant.<genexpr>` | hash/eq 7 |
| `sympy_api.py` `ask` | hash/eq 10,852 |
| `sympy_api.py` `is_constant_proposition` | AppliedPredicate.function 4,203, AppliedPredicate.arguments 4,190 |
| `sympy_api.py` `is_constant_proposition.<genexpr>` | Basic.free_symbols 3,657, Symbol.free_symbols 663, cached call 432, MatrixSymbol.free_symbols 10 |
| `sympy_api.py` `relation_parts` | AppliedPredicate.function 5,469, AppliedPredicate.arguments 5,469 |
| `sympy_api.py` `to_formula` | AppliedPredicate.function 7,746, AppliedPredicate.arguments 2,258, Basic.args 1,832, Printable.__str__ 11 |
| `theories/euf/euf.py` `EUFTheory._new` | hash/eq 17,162 |
| `theories/euf/euf.py` `EUFTheory.term` | hash/eq 5,785 |
| `theories/euf/euf.py` `EUFTheory.value` | hash/eq 11,377 |
| `theories/euf/euf_adapter.py` `EUFAdapter._intern` | hash/eq 110,084, Basic.args 21,284, Basic.func 10,584, Application.func 58 |
| `theories/euf/euf_adapter.py` `EUFAdapter._intern.<genexpr>` | hash/eq 26,403 |
| `theories/euf/euf_adapter.py` `EUFAdapter.interned` | hash/eq 114,839, Basic.args 14,491 |
| `theories/euf/euf_adapter.py` `EUFAdapter.node_term` | hash/eq 3,666 |
| `theories/euf/euf_adapter.py` `EUFAdapter.parse` | AppliedPredicate.function 62,537, Q.* accessor 62,537, hash/eq 62,537, AppliedPredicate.arguments 13,259 |
| `theories/euf/euf_adapter.py` `EUFAdapter.parse.<genexpr>` | cached call 26,518 |
| `theories/euf/euf_adapter.py` `EUFAdapter.shared_terms` | hash/eq 1,168 |
| `theories/euf/euf_adapter.py` `EUFAdapter.term` | hash/eq 26,658 |
| `theories/euf/euf_adapter.py` `EUFAdapter.term_of` | hash/eq 7,792 |
| `theories/euf/euf_adapter.py` `structural` | Basic.args 114,433 |
| `theories/lra/constfield.py` `_from_sympy` | Integer.__int__ 194, Basic.free_symbols 105, cached call 105, Basic.args 104, ExpMeta.__instancecheck__ 1 |
| `theories/lra/lra.py` `LRATheory._lin` | hash/eq 194,259 |
| `theories/lra/lra.py` `LRATheory._model` | hash/eq 13,650 |
| `theories/lra/lra.py` `LRATheory._new_var` | hash/eq 5,776 |
| `theories/lra/lra.py` `LRATheory._term_var` | hash/eq 95,751 |
| `theories/lra/lra.py` `LRATheory._var_of_form` | hash/eq 64,753 |
| `theories/lra/lra_adapter.py` `<module>` | Q.* accessor 12, hash/eq 12 |
| `theories/lra/lra_adapter.py` `LRAAdapter.register` | hash/eq 52,437 |
| `theories/lra/lra_adapter.py` `_closed` | Expr.as_coeff_Mul 36, Mul.as_coeff_Mul 34, hash/eq 34 |
| `theories/lra/lra_adapter.py` `_constraint` | hash/eq 2, Integer.__gt__ 1, BooleanFalse.__bool__ 1 |
| `theories/lra/lra_adapter.py` `_constraint.<lambda>` | default_sort_key 4,797 |
| `theories/lra/lra_adapter.py` `_lin` | hash/eq 37,414, Basic.free_symbols 31,339, Symbol.free_symbols 23,156, Basic.args 14,032, Integer.__mul__ 9,239, is_* property 9,215, cached call 102 |
| `theories/lra/lra_adapter.py` `_linear` | cached call 6,243 |
| `theories/lra/lra_adapter.py` `_memoized` | hash/eq 188,446 |
| `theories/lra/lra_adapter.py` `_side` | cached call 8,558, AssocOp.make_args 4,124 |
| `theories/lra/lra_adapter.py` `integer_form` | default_sort_key 299, cached call 198 |
| `theories/lra/lra_adapter.py` `integer_form.<genexpr>` | hash/eq 598 |
| `theories/lra/lra_adapter.py` `interpret` | default_sort_key 5,514, hash/eq 2, Integer.__gt__ 1, BooleanFalse.__bool__ 1 |
| `theories/lra/lra_adapter.py` `relation` | AppliedPredicate.arguments 10,368, AppliedPredicate.function 5,184, hash/eq 5,184 |
| `theories/lra/lra_bounds.py` `<module>` | hash/eq 3 |
| `theories/lra/lra_bounds.py` `_interval` | hash/eq 3, Basic.args 1 |
| `theories/lra/lra_bounds.py` `constant_bounds` | hash/eq 4 |
| `theories/transfer.py` `transfer_wanted` | hash/eq 66,417 |
