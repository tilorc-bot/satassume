# HANDOFF sa-port-160: Element._new step, parts 2/2b pushed (port/elemnew 5b705df); bar E2 running; not landed (issue 323)

## State (8 Nov, ~09:35 UTC)
- port/elemnew = **5b705df** on rust-slice **9c8d981** (C2 report; only results/ changed since 29ee93e). Pushed (own branch,
  force-pushed after rebase). Commits: a360067 (part 1, was dbcda83), 4b44d30 (159 handoff), e2dcace (part 2), 5b705df (2b).
- **Bar E2 running** on pareto1, tested 5b705df, rows `~/sp19/sa-rust-ids-work/sa-port-160/bar-E2/`, env
  `~/sp19/bar-sa-port-160-env.sh` (script `~/sp19/bar-sa-port-160.sh` = p1/bar.sh sha 1f9c6d92), launcher pid on orion in
  `~/sa-rust-ids-work/sa-port-160/bar-E2.pid` (machine run, shared lease, reason 'sa-port-160 Element._new bar E2 on
  5b705df'). At 09:35: build, tests (09:04 exit 0), suite (09:09 exit 0) done; live/plants/seed1/extra/suiteplants running.
  Done when phases.txt has a `sum` line; read `sum.txt` by head/rg.
  Config: BASE = C2b suite rows `sa-port-153/bar-C2b/suite`, KEPT_BASE = `sa-port-153/bar-C2b`; PLANTS = elem-memo-plus1
  elem-eq-flip elem-hash-skew elem-repr-bracket elem-from-neg + C2b's five; WLS = C2b's ten (incl. cert); SEED1=1;
  SUITE_PLANTS=zero; TESTS = C2b's list + test_elem_pyclass.py; DIRECT as C2b.
- Bar E1 (e2dcace) was stopped by me during its suite (superseded by 2b); its rows `bar-E1/` are partial, not a bar.
- Report draft started: `rust-spike/slice/results/port-elemnew.md` ("What moved" only), uncommitted -> committed with this file.

## What parts 2/2b did
- Part 2 (e2dcace): `PyElem.sign()` = `Elem::sign` (counter 177 `cf:elem_sign`); constfield.py `sign` tests Element,
  then Fraction/int, then calls `x.sign()` if present (pyclass). test_elem_pyclass.py: 27 passed (new
  `test_constfield_sign_on_rust`; `test_counters_and_fallback` now expects +7 py_reads and +1 elem_sign).
- Part 2b (5b705df): the 100 came from Rust: relations_core.rs `_order_infinite` port (~:540) called Python's
  `relations.sign` on an order_sides memo coefficient (profile hook `~/sa-rust-ids-work/sa-port-160/who/who.py`:
  `session_live.py:292 _rel_interpret <- :412 _rel_process`, 100 on dev). A PyElem coefficient now uses `Elem::sign` on
  Rust, counter 178 `rel:elem_sign`. No plant covers this branch (plant numbers 123+ not taken, to avoid sibling clashes):
  say so in the report.
- Unit tests local: test_elem_pyclass + test_relations_core + test_cf_laurent 118 passed; test_cf_diff.py 7: 0 mismatches.

## Numbers so far (orion local, `~/sa-rust-ids-work/sa-port-160/q3/` = 5b705df source; q2 = e2dcace)
- dev, cert, fuzz Python vs Rust **MATCH**: 31cd0945c07f02a6, 6a09c059eb266747, 173502b6ef285ad6; 0 Python solvers.
- **Element._new** (cf_trace, Rust), base C2 -> 159 -> now: dev 703 -> 100 -> **0**; fuzz 1,552 -> ? -> **0**; cert 163 ->
  0 -> **0**. f6 30, core 24, wiring 3, opaque 2 **unchanged** (`t4/`): all inside the named Python callbacks
  `constant`/`radical` (constant's Element) and, on wiring, 1 via Python `from_sympy` <- lra_adapter.closed_sign (Python's
  own path) (`who/wiring.json`). So none crosses from Rust; those go with `constant`'s owner (adapters' rest).
- `Constant.enclose` dev 100 -> 0: those were the fallback Python Element's own `_env`; Rust's `Elem::sign` uses the
  ENCLOSURES cache (constfield.rs:185, :1232-1243). R9 itself is unchanged.
- Session counts (dev / cert / fuzz): elem_py_read 0/0/0; elem_sign 0/0/0; rel:elem_sign 100/0/0; elem_new 1380/446/2506;
  elem_hash 179/0/0; elem_repr 2870/533/37501; memo hit 2642/1532/94596, miss 2833/738/70358.
- **`_memoized` crossing (`ad:cb_memoized`)**, base C2b -> now: dev 5508 -> 5508, fuzz 164954 -> 164954, cert 2270 -> 2270
  (C2b extra also: zero 18671, scope 2472, value 2626, others 0 — compare bar E2's extra session.json).
- **Plant 118 elem-memo-plus1 caught as a WRONG VALUE** (`p118/`, e2dcace build; memo code unchanged in 2b): dev answer_diff
  78, msg 41, lra_diff 182, DIFFER (b16286339cca9ca0); cert answer_diff 9, lra_diff 61, DIFFER (591e7bdf3a98b861);
  rel:plant_fired = lra:memo_hit (dev 2461, cert 1532), so entries are still hit, values are wrong.
- Memo tuple identity: rg over satassume/tests/slice found no reader of result identity except `is True/False/None`
  (singletons; tests/test_lra_adapter.py:213, test_lra_constants.py). Name it as the state-rule search in the report.

## `_memoized` decision (write into the report)
Own named step, not moved here: after this step no Element crosses on it; what's left is Rust adapter -> Python
`_memoized` -> lra_live `memoized` -> `interpret`/`relation(atom)`/`_ids` (term_live's Python id lookup of a SymPy atom)
-> Rust table -> `_pairs`/`_objs` (q.objects) -> back. Moving it needs the atom's term ids and the query's table on the
Rust adapter, i.e. term_live/session_live per-query state: slice wiring the state ruling gives to the state step(s).
Proposed owner: the named state step right after 5c10 (or earlier if the planner prefers). Counts unchanged (above).

## Next, in order
1. Wait for bar E2 `sum`; read sum.txt: five bar items, three suite numbers with passed split by firing, handler multiset
   vs base, plants table (all 10 on dev/fuzz/WLS), kept-reasons shares vs base, extra workloads MATCH, quiet catches.
   Get `ad:cb_memoized` and the new counters from `live/*-rust.session.json` and `extra/*-rust.session.json`.
2. Finish results/port-elemnew.md (sections as port-adapters.md part C2: SHAs and incoming diff, bar, plants, reached,
   Element._new/_memoized before-after incl. cert, module count, kept reasons, not run). Module count: **13 of 32
   unchanged**, cite STATUS.md's "Counted modules" list (constfield.py still not whole: `constant`, `radical`, `_generic`,
   `Constant.__init__`, gcd trio, `_short`, `enclose`; lra_adapter.py: `_memoized`, `constant_bounds` called back).
3. Ownership: port-ownership.md :101 (constfield `Element._new` row -> landed, Rust pyclass), :110 (`_memoized` owner ->
   named state step), :132 (partials), plus an "Updated by sa-port-160" note at the top; TSV rows 653 (`Element._new`) and
   768 (`_memoized`).
4. `git fetch`; if rust-slice moved (siblings 5c7 sa-port-154/158 and 6g(c1) sa-port-155/157 had bars on pareto1),
   `sh rust-spike/slice/p1/bar.sh land 5b705df` (no PUSH), read the incoming diff; guarded source changed -> full bar
   again (5c7 owns counters 156-169 / plants 114-117: drop the `rsv:5c7:*` placeholders and keep 5c7's names). Else
   `PUSH=1 sh rust-spike/slice/p1/bar.sh land 5b705df`. Commit report+ownership, push, `agent report`.
