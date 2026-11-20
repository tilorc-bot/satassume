# HANDOFF sa-port-350: item 1 (the profile) done, GO by its stop rule; item 2 (the port) NOT STARTED; nothing landed

Stopped between items at the context budget (the ruling: hand off between items, never mid-item). Branch
port/witness-native (pushed), worktree ~/sa-rust-ids-work/sa-port-350/wt in clone ~/dev/sa-port-19, on rust-slice
6ee354f9. No source change yet: the commits are tools350, results/witness-native.md and this file. Nothing of mine
runs; no lease is held.

## Done

- Item 1, the profile: results/witness-native.md (1). On 6ee354f9, quiet lease on pareto1, bench-container CPU 2,
  .so 0982a28074215658. The check's inclusive time is 10.6% of Rust dev (8.2% on the queries it does not certify),
  and the guards that stay Python are 4% of it; wiring and fuzz are in the table there. The stop rule does not
  trigger: the share that would move is several times the S1 spread on wiring and on Rust dev. So item 2 is GO.

## Not done, in the ruling's order

2. The port behind SLICE_WITNESS_RUST=1 (design below; nothing written).
3. Same behaviour per query (certified set, witness_certified, Engine.stats, the points and their order, the work
   count tripping on the same call).
4. Plants 760-767 (free, checked by rg on 6ee354f9), counters 706-713 (free). At minimum: a wrong table entry on the
   native path, a native work count off by one, a skipped P1 guard; each in its own bar row with its switch on.
5. S1, 12 rounds, quiet lease: tools347/time347.sh and onlease347.sh are the model (arms SHA:MODE-WITNESS; add an arm
   with SLICE_WITNESS_RUST=1); med342.py's rule for the star.
6. The count rule. 7. Bar, bar.sh land, guard, PUSH=1; rule [91].

## What the profile and the reading say about the design (350's reading, not checked by running)

- **No extra walk is needed.** Under the slice `term_live._install._ask` (term_live.py:1094) converts the query
  (`_convert`, :306) and pushes its `_Query` (:74: `table` = sa_solver.TermTable, `ids` {SymPy term: id}, `objects`,
  `derived`/`rev` for scaffolded sides, `kept`) BEFORE it calls `sympy_api._ask`, so when
  `sympy_api._engine_ask` (:1136) reaches the check, `term_live.current()` already holds the query's native table.
  The table is there under the Python walker too (both walkers feed `TermTable.from_tokens`), so the port does not
  itself need SLICE_CONVERT=rust; the ruling ties the switch to it, so keep that and say so in the report.
- **The formula.** The check reads the `P` formula `to_formula` made (witness.py assumption 3). That formula is
  Python's (`sympy_api._FORMULAS` memo, so its terms can be an earlier query's ==-equal objects; a stripped `eq` side
  is a scaffolded term, term_live.py:571-581, in `q.derived`, not `q.ids`). Two ways in:
  (B, 350's recommendation) Rust walks the `P` formula once at the boundary, as solver_rs/src/formula.rs does (its
  header: isinstance against the nine classes, `.args`, `PyP.pred/.expr`), and maps each atom side to a term id with
  one lookup in `q.ids` (SymPy's hash; `==` only for a non-identical equal object), then everything below is on ids.
  A side that is not in the table (derived, `kept` query, a refused run's `_Refused` on the stack, no slice) sends
  the whole query to Python's witness.py, counted. This keeps "the formula is the query" by construction.
  (A) compile from `TermTable.formula` (convert.formula's mirror, relation atoms as ('rel', name, lhs, rhs)) plus
  `eq_sides`/`order_relation` (term/py.rs:399, :415): no Python read at all, but it must mirror to_formula,
  relation_atom's fallbacks, and sat/formula.py's constructors exactly, and a mismatch cannot be detected.
  Report B's per-query lookups under the count rule (item 6); they are not calls of witness.py.
- **Terms on ids.** `Kind` is the exact class (table.rs:34), which is what `_term` tests (`t is Add/Mul/Pow/Pi`,
  `t is Symbol or t is Dummy`). `isinstance(e, Rational)` is wider than Kind Integer/Rational/Zero/One/Half/
  NegativeOne: a subclass has Kind Other; send such a query to Python rather than call it undecided. p and q are in
  the row's `content` (`_hashable_content`). The symbol's own assumptions: `TermTable.symbol_facts` (table.rs:403),
  `assumptions0` in dict order, one memoized lazy read per symbol that the engine's symbol template shares later in
  a fall-through query. `q.syms`' order is the walk order: assumptions, then proposition.
- **Exact values.** One rational type is enough (Python's int against Fraction is never told apart: `_integer`,
  `.denominator`, `==` and hash agree); term/rat.rs has `Rat` over BigInt (new/add/mul/neg/Ord; needs sub, div,
  pow, bit lengths). Q[pi]: `_PiPoly` (witness.py:346-432), `_sign` and the enclosure `_LO/_HI` as exact rational
  bounds (:339-343, :442), PI_TABLE (:474). num-bigint/num-integer/num-traits are already dependencies: no new crate.
- **Guards stay Python and keep their order**: extensions (witness.py:828), compile, `not q.syms`, `_patched` (:852),
  `Engine._known_inconsistent` (:854), pools and search, the second `_holds` on the two points (:882),
  `_users_knowledge` (:886). So the native side is two calls: compile (undecided / not-mappable / a handle with the
  symbol count) and search (pools, `_by_index_sum`, `spend` at the same three sites of `_roots` and once per point,
  CAP/LIMIT/WORK read from witness.py's lists at call time, the two points decided again). A hook list in witness.py
  (`NATIVE = [None]`, read in `witnesses` after the extensions test) that the slice fills from its env keeps
  witness.py the default and the reference. `witnesses` returns `(symbols, yes, no, tried)`: give ints and Fractions
  back so tests compare with `==`.
- The plants of witness.py (:114-121, `PLANT`, `FIRED`) are read inside `spend`, `_own`, `witnesses`: the native path
  either honours them or falls to Python while one is set; say which.

## FILE:LINE MAP (6ee354f9)

- satassume/witness.py: CAP :103, LIMIT :104, WORK :113, PLANT :146, GUARDED :149, `accept` :155, `_patched` :165,
  `_users_knowledge` :186, limits :217-220, `_is_prime` :227, `_integer` :241, TABLE :249, RELATIONS :282, TWO_WAY
  :290, ONE_WAY :312, enclosure :339-343, `_PiPoly` :346, `_poly` :434, `_sign` :442, `_pi_rational` :468, PI_TABLE
  :474, `_pred` :513, `_pi_pred` :543, `_Query` :553 (`spend` :565), `_term` :573, `_pi_power` :634, `_formula` :655,
  `_own` :700, `_HEAD/_TAIL` :708, `_roots` :713, `_pools` :750, `_by_index_sum` :784, `_holds` :801, `witnesses` :825.
- satassume/sympy_api.py: `bind`/`accept` :137-138, the check's call :1136, `to_formula` :361, `_formula` memo :503;
  satassume/relations.py `relation_atom` :518.
- rust-spike/slice: term_live.py `_Query` :74, `current` :160, `_convert` :306, `_relation_atom` :568, `_ask` :1094,
  `from_env` :1259; convert.py `formula` :503, `convert` :534, KINDS :55; session_live.py :1525 (`witness.accept`),
  :1569 (witness_plant_fired); p1/bar.sh `penv` :100, witness rows :98-109.
- solver_rs/src/term: table.rs `V` :18, `Kind` :34, `TermRow` :136, `TermTable` :148, `symbol_facts` :403; py.rs
  `PyTermTable::new` :282; rat.rs; walk.rs plants :60. solver_rs/src/formula.rs header (the boundary read),
  formula_py.rs `PyP` :16. Cargo.toml: pyo3 0.30, num-bigint, num-integer, num-traits.
- results/tools350: prof350.py (plain / phase / cprof), prof350.sh (in the container), onlease350p.sh, goprof350.sh
  (never edit a launcher while it runs: 350's first pass lost its end marker that way), tab350.py.
  Output: orion ~/sa-rust-ids-work/sa-port-350/s1/prof (dev, fuzz), s1/profw (wiring); pareto1 the same path, with
  s1/common and s1/bench-6ee354f9 staged (S1's environment, reusable for item 5).

## Must stay in every report

Tested SHA 6ee354f9 (profile only; no source change, no new .so: bench 0982a28074215658). SLICE_WITNESS off by
default, Python witness.py the default and the reference, the unchanged path the default. No SymPy construction or
evaluation at query time; no floats in any decision; "exact" rests on 325's 14-predicate table plus 2030cdc6's Q[pi]
arguments (issue 247). Not yet measured, owed with items 3-6: per query certified set, witness_certified and
Engine.stats against Python's; bar row wall times; known base rows by id with the planted-history test footnoted
([137e], id()-reuse); S1 from quiet-lease runs only; on against off with the native check; witness.py's per-query
Python calls with the native check on; the probe count against 21/32.
