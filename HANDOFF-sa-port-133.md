# HANDOFF sa-port-133: adapters step (issue 323), part B rebased twice, not landed; part C not started

## State
- port/adapters (pushed): **aba6a66** = part B code rebased on rust-slice **1401d1f** (scope 803d073 + 5c6), then
  ae6e767 (part A addendum, docs), b88a782 (sa-port-129's handoff, docs), and this file. Part A is landed (d91ee15).
- **HOLD (architect, ~04:50 UTC 8 Nov):** don't push to rust-slice until 6d lands (sa-port-131's bar on c69cd6a, until about
  05:40 UTC). 6d changes `_common`/knowledge_live, which dev and fuzz run, so after it lands: `bar.sh land aba6a66` no-PUSH,
  rebase, and a full bar on the merged tree is owed. Then land with PUSH=1.
- No bar on part B has finished. bar-B1 (sa-port-129, 15dff82 on d91ee15) and bar-B2 (mine, e80acdf on 803d073) were
  stopped at the architect's request after their `live` and `plants` phases, because each was superseded by a rebase that
  brought in executed code. Their partial rows: pareto1 `~/sp19/sa-rust-ids-work/sa-port-129/bar-B1/` and
  `~/sp19/sa-rust-ids-work/sa-port-133/bar-B2/` (no sum.txt; `live/`, `plants` rows only). bar-B1's suite: 5,958 / 126 / 23 /
  18 (same totals as bar-A2; not compared by id). Use neither as the landing bar.
- Local check on aba6a66 (orion): test_adapters_core.py + test_scope_core.py + test_relations_core.py, 97 passed; satassume
  and sa_solver.so imported from the clone (`~/sa-rust-ids-work/sa-port-133/smoke-aba6a66.txt`).

## Renumbering (name in the report)
Both rebases conflicted only on numbering in relations_core.rs (plant consts + `rel_plant` names) and session.rs (counter
consts, NAMES, COUNTS). Part B's numbers are now: plants **104-107** (ad-lra-shared, ad-euf-node, ad-kind-swap,
ad-euf-shared; were 91-94), counters **140-150** (ad:lra_new .. ad:euf_register; were 123-133); arrays 151. Scope owns plants
91-96 / counters 123-132, 5c6 plants 97-103 / counters 133-139. sa-port-129's handoff and part B's commit message still say
the old numbers. Plants and counters are addressed by name in Python, so nothing else changed.

## Bar config for part B on the merged tree
As bar-B2 (launcher log `~/sa-rust-ids-work/sa-port-133/bar-B2.log` on orion, first lines), with BASE and KEPT_BASE set to
the latest landed bar on rust-slice (6d's bar rows once 6d lands; before that sa-port-134/bar-5c6). bar-B2 used:
PLANTS "ad-lra-shared ad-euf-node ad-kind-swap ad-euf-shared spec-row-flip adapter-fresh theory-no-assume" (one scope plant to
check the renumbering; add one 5c6 plant, e.g. al-drop-delta, caught on dev in bar-5c6), WLS "loop scope", SEED1=1,
SUITE_PLANTS=zero, TESTS = bar-5c6's list + test_adapters_core.py (+ 6d's test, if any), DIRECT "relations_direct.py 300
0;dispatch_direct.py", N=8. Launch: scp bar.sh to pareto1:sp19/bar-NAME.sh, then `setsid nohup machine run pareto1 --shared
--wait 4h -r "..." -- env OUT=... ... setsid bash /home/tilo/sp19/bar-NAME.sh NAME port/adapters > LOG 2>&1 < /dev/null &`.
The bar clones origin/port/adapters, so push the branch first. Local Python: `. ~/sa-rust-ids-work/env.sh` gives `$PY`.

## Part C map (not started; scope confirmed by the planner, 03:51 UTC: both Negated and Integral in scope)
- **EqAtom** (euf.py:75): built in adapters.rs `EufAdapter::register` (~:319) by calling the module's `EqAtom`; decoded in
  euf_py.rs `register_atom` (:235-260, `is_instance(eq_atom)` then iterates parts; `eq_atom` imported at :132). A Rust
  `#[pyclass(frozen)]` payload built in register and downcast first in euf_py.rs would remove the Python tuple.
- **Negated** (lra.py:230): built in adapters.rs `LraAdapter::register` (~:114) via module `Negated`; decoded in
  rust-spike/slice/lra_backend.py `_register` (:139-173, `while isinstance(payload, Negated)`), which calls
  `core.register_plain` (lra_py.rs:120).
- **Integral** (lra.py:247): built in lra_live.py:168 (`integer_form`'s Rust route wraps `lra.Integral(_pairs(...), c)`),
  memoized through `_memoized` (ad:cb_memoized), registered by `LRAAdapter.register_integer`; decoded in lra_backend.py
  :141 → `core.register_integral` (lra_py.rs:135). The ids → objects mapping (`_pairs`) is in the term-id glue, so a Rust
  Integral either carries objects (as now) or moves with `_pairs`. `_check` in lra_live compares against Python's tuple.
- Payloads pass through the Rust Solver as `Py<PyAny>` (lib.rs:166 `PyTheory::register_atom`), so a Rust pyclass payload
  works without solver changes. Tests that build Python payloads directly: test_lra_raises.py, identity_rule.py,
  euf_fuzz.py, transfer_fuzz.py, portmut_reach.py (keep the Python classes accepted).
- **constfield** (port-ownership.md :99 and :124; TSV rows 625-697): `_to_dmp`/`_from_dmp`/`_sympy_inner_gcd` (gcd
  callback, constfield.rs:777), `_short` (:108), `Element._new` (:2022), `pi_laurent` (lra_cert.rs:87), `radical`
  (lra_read.rs:425, constfield.rs:1196), `_generic`/`constant`/`Constant.__init__` (lra_read.rs:446), `enclose` permanent.
- One plant per moved item, counters named and counted, as in part B.
