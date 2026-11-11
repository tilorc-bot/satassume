# Group D regression cause (issue 323, C; sa-port-285 measured, sa-port-286 read round 2)

Read-only. No source or package changes. Range tested: 1401d1f (146's tree, 5c6) to f252daf (state part 2 + 3), rust-slice 50f1421.
Method: 280's harness. Samples: pysampler, 10 dev + 3 fuzz runs per tree, `--cpus 1`, under a shared lease on pareto1. Timing:
pinned, interleaved, 7 rounds, on bench-container BENCH_CPU=2 under a quiet pareto1 lease. Group D = `capi<-rust` share x the
tree's pinned Rust median. Round 1 (sa-port-285, 8 trees, 112 rows) is taken as given. Round 2 (12 trees, 168 rows, quiet lease
4d7cb91c, ended 11:03Z) is read here from its medians only. Both rounds: 0 digest mismatches. Sampling SE is about 0.003 s
(dev) and 0.02 s (fuzz) per tree. Dev has 1,985 queries and fuzz 3,000.

## Headline

**Method gap: 0.015 s dev.** Measured the same way, 146's own tree (1401d1f, .so identical) gives 0.173 s dev and 1.953 s fuzz,
not 146's 0.158 / 1.990. 146 multiplied ana143 shares by 034e6bc's medians. This report uses ana195 shares times today's pinned
medians. So 0.015 s of the +0.043 s dev gap is method.

**Same-method regression, 1401d1f to f252daf (round 1): dev +0.022 s (+13%), fuzz +0.315 s (+16%).**

**Total Rust time did not regress:** dev 0.787 -> 0.776 s, fuzz 6.757 -> 6.616 s. Group D grows while the Python and callback
categories shrink. Ported Python becomes C API calls from Rust on Python-held objects. Most of the growth is time moving between
categories. The adapters step below is the exception: it adds about 0.14 s of new overhead.

No package changes.

## By step (Group D change, s)

Round 2 chains 1401d1f to 9529850. Round 1 carries 9529850 to f252daf. Round 2 sums to fuzz +0.301 / dev +0.027, against
round 1's +0.315 / +0.022 between the same endpoints. The difference is round-to-round offset: at the shared trees, 1401d1f is
1.959/1.953 and 9529850 is 2.212/2.220. That is within SE.

| step (tree) | fuzz D | dev D | what moved (fuzz) | cause ids |
|---|---|---|---|---|
| 6d (6526445) | +0.067 | +0.003 | rust -0.050, callback -0.035; SessionCore::emit +0.014, PyTheory push_level/assert_lit +0.016, PyIterator +0.009 | C9 |
| before-5c7 (44f4762) | -0.019 | +0.007 | noise | - |
| **adapters part B (3cf4315, holds 96be463)** | **+0.152** | +0.001 | callback -0.083; adapters module 0 -> 0.127 s; answers and digest identical (173502b6ef285ad6) | C1-C5 |
| adapters C1 (f92a360) | -0.052 | -0.003 | noise / partial give-back | - |
| 6g(b) (b838d3f) | +0.021 | -0.002 | noise | - |
| adapters C2 (9c8d981) | -0.003 | +0.003 | noise | - |
| 5c7, 5c8, 5c9a-c, 5c10a (67d108d) | +0.052 | +0.003 | python -0.164; new budget::query_cone 0.018, drop of PySolver 0.016, procmemo PyKeyMap::find 0.013; compile_loop::split -0.041, sympy_atom -0.031 | C10 |
| 5c10b (4215655) | -0.012 | +0.008 | dev: new context module (patched/konst/helper, about 0.007 s), ctx:cb_helpers 2,563 | C8 |
| 6g c3-c5 (eac4537) | -0.012 | +0.005 | noise | - |
| 5c10c (b384ec1) | -0.017 | -0.004 | noise | - |
| 5c10d (9529850) | +0.076 | +0.009 | python -0.086; entry::ent_ask 0.017; per-ask callbacks ent:cb_noncomm 3,556, ent:cb_gave_up 2,565 | C7 |
| 6g c6-c9 (2742b66, round 1) | +0.001 | 0.000 | noise | - |
| state part 1 (a8a4bae, round 1) | +0.061 | -0.003 | adapters +0.118 (Reader::pairs 0.025, order_sides 0.021, id 0.018, interpret 0.013, memoized 0.015); callback -0.523, so fuzz total -0.43 s | C6 |
| state parts 2 + 3 (f252daf, round 1) | -0.014 | 0.000 | relations_core/discovery fall, offset by session | - |

The dev steps are each within 2-3 SE of a difference (about 0.004 s). The dev window 67d108d -> 9529850 (+0.018 in round 2,
+0.015 in round 1) is spread over 5c10b (context, C8) and 5c10d (entry, C7). No single dev step dominates.

## The adapters step, taken down to functions (fuzz, 44f4762 -> 3cf4315, D +0.152 s)

The counters changed nowhere except the 9 new `ad:` rows (cdiff: removed 0, changed 0), and the answers and digest are equal.
So the step only adds time. Each 3,000-query fuzz run makes, per query: 55 `ad:cb_memoized`, 12.1 `ad:cb_parse`, 12.1 each of
`ad:lra_register`/`ad:euf_register`, 8.7 `ad:cb_structural`, 4.2 `ad:cb_interned`, 2.0 `ad:cb_theory_new` (1 LRA + 1 EUF
adapter built per query).

| cause | D s | calls (per query) | per call | why |
|---|---|---|---|---|
| C1 EufAdapter::py_class | 0.034 | 49,130 parse+interned (16.4) | 0.69 us | `module.getattr_opt("_PyEUFAdapter")` misses on every call. `_PyEUFAdapter` is set only by ad_swap.py, and make_adapter builds the Rust adapter without it. On Python 3.12 a module attribute miss builds and swallows an AttributeError: the samples are PyUnicode_FromFormatV, PyUnicode_Concat, PyMember_SetOne and PyErr_GivenExceptionMatches. This is unchanged on 172d690 (adapters.rs:660). |
| C2 relations_core::rel_interpret | +0.039 | 72,794 register calls (24.3) | 0.54 us | Rust calls the Rust adapter through Python's method protocol: `ad.call_method1("register")`, `"interned"`, and `getattr_opt("node_term"/"order_sides")`, all of which pass a pyo3 trampoline (PyObject_VectorcallMethod, _Py_CheckFunctionResult). Before the step these were Python-to-Python calls, counted as callbacks. Unchanged on 172d690 (relations_core.rs:1291, :1302, :1766). |
| C3 EufAdapter::intern_into | 0.027 | 26,151 structural nodes (8.7) | 1.0 us/node | Per node it makes two PyDict_Contains (out, known) on SymPy objects (SymPy hash/eq), `is_instance(Rational)`, a Python `structural()` call and a getattr on `args`. This was Python's `_intern` before, counted as callback. |
| C4 LraAdapter::memoized | 0.017 | 164,954 (55) | 0.10 us | Two module getattrs (`_memoized`, the read) plus a key tuple per call, then a call into Python. State part 1 replaced it (ad:cb_memoized 164,954 -> 0, ad:lra_native 164,954), so what remains of it is in C6. |
| C5 adapter build + attach | 0.025 | 6,037 adapters (2.0) | 4.1 us | adapters::module (0.005: `relations_package` getattr, a format! string, an import per build), EufAdapter::build (0.006: also imports sympy.Rational), attach_to (0.014: scans `solver.theories()` and calls attach_theory). |
| rest | 0.010 | | | compile_loop::emit_pattern +0.015, visit +0.013, a generic pyo3 any call -0.019 and others: diffuse |

C1 and C2 are new work: the Python side never paid for an AttributeError or a trampoline. C3-C5 are mostly moved work (callback
-0.083 at the same step). The fuzz Rust median for the step moves 6.771 -> 6.869 s, within the 7-round spread.

## By cause: fix candidate and owner

Each fix keeps every answer identical and adds no heuristic. Each decides only order or speed, never which facts are built.
Owners: A owns session.rs, session_live.py, query.rs and session_glue.rs. B (paused) owns compile_loop.rs and formula's files;
relations_core.rs relation-wrapper calls are formula's. Anything else goes to a new step. Formula has edited adapters.rs before
(a5fa1f6, 425ca5e, ded8c3f), so the planner may prefer to route the adapters.rs items to B.

| cause | step | D s (fuzz/dev) | fix candidate | owner |
|---|---|---|---|---|
| C1 py_class AttributeError per call | adapters B | 0.034 / 0.002 | Look up `_PyEUFAdapter` in the module's `__dict__` (PyDict get, no exception), still per call, so a later swap is still seen. Fall back to `EUFAdapter` exactly as now. It returns the same class object, with no exception built. | new step (adapters.rs) |
| C2 Rust-to-Rust calls through Python's method protocol | adapters B | 0.039 / <0.001 | In rel_interpret and the :1766 site, when `ad` is exactly the Rust LraAdapter/EufAdapter type (not a subclass), borrow it and call `register`/`interned`/`order_sides` directly. `node_term`/`order_sides` presence comes from the type. User adapters and subclasses keep the Python call. The same code runs in the same order. | B (relations_core.rs) |
| C3 intern_into per-node dict and `structural` calls | adapters B | 0.027 / 0.001 | Keep the `_terms`/`_node_terms` dicts (shared_terms reads them), but test membership and cache `structural` per node through a Rust map keyed by the query table's term id. By R1, == classes have one id in the query's table, so membership equals the dict's hash/== answer. | new step (adapters.rs) |
| C4 memoized per-call getattrs | adapters B | 0.017 / 0.001 | Superseded at state part 1, see C6. | (C6) |
| C5 per-adapter module import, Rational import, theories scan | adapters B | 0.025 / 0.001 | Resolve the package's adapter modules and `sympy.Rational` once per `rel_install` (stored next to HOOKS) instead of per build. These are the same objects from sys.modules. attach_to is unchanged. | new step (adapters.rs) |
| C6 Reader per-call reads of Python relation objects; 64,424 Python term-id reads | state part 1 | 0.077 + 0.015 / -0.003 | Read each relation object's pairs, sides and id once per query into the query's table, keyed by term id, so the native lra path doesn't re-read Python attributes per call. ad:lra_term_id_py goes native. | new step (adapters.rs; B if the planner routes adapters.rs to formula) |
| C7 per-ask entry frame and per-ask callbacks | 5c10d | 0.076 / 0.009 (largely moved: python -0.086) | ent_ask as one Rust call per entry (A's "sympy_api entry frames as single Rust calls"). ent:cb_noncomm (3,556 fuzz, 1,209 dev) goes away with B's `_noncommutative_atoms` native item. | A (entry frame); B (cb_noncomm) |
| C8 context rows' per-call helpers | 5c10b | -0.012 / 0.008 | Call context::patched/konst/helper's Python helpers (ctx:cb_helpers 2,563 dev) natively where P1's direct-call rule already allows it (not when the user patched the method). | new step (context.rs; formula's P1 instruments it, so B is an option) |
| C9 PyTheory per-level calls | 6d | 0.067 / 0.003 (rust -0.050) | When a PyTheory wraps the Rust LRA/EUF theory (exact type), call push_level/assert_lit/propagate directly instead of through Python methods. User theories keep the same calls in the same order. | new step (solver/theory) |
| C10 PySolver drop, procmemo PyKeyMap::find, budget::query_cone | 5c7-5c10a | 0.052 / 0.003 (python -0.164) | Key PyKeyMap by term id instead of Python objects (no SymPy hash per find). PySolver drop and query_cone were not drilled further and need a short read first. | new step (procmemo/budget) |

C1, C2, C3 and C5 are present on the head 172d690, and together they are worth about 0.12 s fuzz. C1 and C2 are the cheapest:
local changes with a direct identity argument.

## Files

Scratch: ~/sa-rust-ids-work/sa-port-286/ (med-r2.md, fdiff-*.txt, cdiff-*.txt). Round 2 SUMMARY.md per tree:
~/sa-rust-ids-work/sa-port-285/gd/run-SHA/. Tools: ~/sa-rust-ids-work/sa-port-285/tools/{med285,fdiff,cdiff}.py.
