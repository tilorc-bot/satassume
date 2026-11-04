# Slice plan: what to build first, and what it can show (issue 323)

**Build S first: the SAT solver alone in Rust, with every theory, including rational LRA, as a live callback into the unchanged Python.**
S reaches the same queries as Q and is the smallest thing I found that runs real queries. If S passes its gate, add rational LRA to get Q.
Neither reaches 2x as estimated, except possibly Q on fuzz if the SAT share is at the top of its range. Getting past that needs code outside the solver in Rust, and there's no measurement behind its gain.

| | queries in Rust, dev / fuzz | time of those queries, dev / fuzz | most it can show, crossings free, dev / fuzz | with the crossing estimate, dev / fuzz |
|---|---:|---:|---:|---:|
| P, plan as written | 669 of 1985 / 84 of 3000 | 38.9% / 0.2% | 1.18 / 1.00 | not worked out |
| **S, solver only (new here)** | 867 / 2937 | 99.1% / 100% | **1.53 / 1.53** | **1.45 to 1.51 / 1.40 to 1.51** |
| **Q, S plus rational LRA** | 867 / 2937 | 99.1% / 100% | **1.62 / 1.90** | **1.54 to 1.60 / 1.74 to 1.86** |

The remaining 1118 dev and 63 fuzz queries open no session, so they never reach the solver.

**History:** S and Q need no id table. Rust holds only per-session ints, and in Q rationals, and every term stays in Python's existing per-session table under SymPy's real hash and ==. That meets issues 96 and 97 for S and Q by the argument in section 3.
It doesn't carry over to a port of Session, Relations or knowledge. No design here meets the requirement there, so that stays open.

**One thing in sa-rust-11's candidate is false as worded.** First sight doesn't come from the query alone. It also depends on the hash seed (section 3).

**Build:** 5 steps for S and 2 more for Q, each one session (section 4). The check compares solver state at every solver entry, and adds a direct API fuzzer for the paths the workloads don't reach.

## 1. Audit of `set-iter-audit.md`

I read the three sites and ran one instrument, `slice/audit.py`, on both workloads: 5 runs each, hash seeds 0, 1, 2 in recorded order and two shuffled query orders at seed 0. Results are in `slice/results/audit-order.txt`. All 10 runs gave the pinned digests, `31cd0945c07f02a6` and `173502b6ef285ad6`.

| Item | Result | How I know |
|---|---|---|
| engine.py:1713 (`_cone_info`) | **The audit is right.** A cone that fits is order-free. Only `w` and `rel` of an over-budget entry depend on order | Read. **The workloads never reach it: 0 of 221 dev and 0 of 2690 fuzz cones are over budget**, so this rests on argument alone |
| engine.py:1767 (`_union`) | **The audit is right, including that a partial `rel` can flip `link`** | Read, including :1795-1810. Same limit: never over budget on the workloads |
| lra.py:614 (`_dirty`) | **The audit is right.** A set of per-theory ints sets the order of `out`, and ids don't touch it. The port has to reproduce that order | Read, plus mutant 7 in `RESULT-k-lra.md` |
| Re-entrant template queries (:1998) | **Not reached on the workloads; open beyond them.** 0 `is_` or `is_many` calls arrived with `_constructing` non-empty. Kids of all 270 dev and 2732 fuzz objects were the same in all 5 runs | Measured. The engine's own docstring (:2138) says "accepted, not proved". The test suite wasn't run |
| LRA atom order across a session | **Doesn't move with query order; does move with the hash seed.** Atom sequence differs on 0 queries across shuffles, and on 8 dev queries at seed 1. Other seeds and fuzz: 0 | Measured on queries with the same number of sessions in both runs (dev about 1700 of 1985 under shuffle) |
| `_glue_adapters` purity | **Pure as far as I read.** It holds `spec.factory()` by spec name. The adapter's only attribute writes are at :467, :468 and :496, and :496 is attach. Its reading paths write none | Read and rg, not a proof. Kids don't vary in any run |
| Registered custom predicates | **Settled: none on either workload.** At the end of each pass the registry has 0 handlers and 0 vocabulary entries, and `facts_for` never returned anything. `_is_custom` saw only `eq` and `lt`, which are relation atoms | Measured, with `facts_for` wrapped this time |

**Two new findings:**

- **Clause order depends on the hash seed today.** The clause sequence differs on 27 and 19 of 1985 dev queries and 131 and 225 of 3000 fuzz queries at seeds 1 and 2. No answer changed. This is within Python, with no Rust involved.
- **One clause-order change came from query order alone.** Dev query 873 has a different clause sequence in one shuffled run at the same seed. Its answer is the same (False), and it is a no-theory session. **I didn't find the cause.** It is the one case of session contents depending on history here.

## 2. S and Q as slices

**Why not Q first.** Q and S reach the same queries, so Q's rational LRA doesn't add coverage. It adds 0.37 of speedup on fuzz and 0.09 on dev, and it adds the hardest parts of the build: row conversion, the switch when a session gains a constant atom, and the `_dirty` order.

**Nothing smaller answers the question.** P runs 84 fuzz queries. Replays and the crossing tables already exist, and they can't show live behaviour.

S rests on three facts:

- No Session, Relations or adapter frame ran during a solver call, on either workload.
- Theory cores make no solver calls; only adapters do, at setup (`register_atom`, `attach_theory`, `theories`). This is from rg, not a trace.
- No code outside the solver reads a private solver attribute (rg: 0 hits).

| | A timed pass of S can settle | A timed pass of S can't settle |
|---|---|---|
| Speed | The real speedup with live crossings, the live k for the solver, and the real SAT share (31-46% by other timers) | Any gain in Session, Relations, knowledge or adapters. k_lra live (Q does that) |
| Answers | Same state and answers as Python on what the check reaches | Inputs the workloads, suite and fuzzer don't reach |
| 2x | Whether it's in reach of this boundary | Whether 2x is reachable past it |

**Crossing cost: an estimate that the slice replaces with a measurement.** Built from `results/tables-cross.md`, with counts from `coverage.md`. The low end is full API. The high end is abi3 plus conversion.

| Item | ns per call or item, low to high | Basis |
|---|---:|---|
| Rust into Python, per theory call | 17 to 156 | Low: `f(o)`. High: abi3 `o.m(i)` at 80, plus 76 to read a returned list, using the `o.args` row as a stand-in |
| Python into Rust, per solver call, not batched | 27 to 92 | One int in; abi3 538-byte row |
| Each clause literal | 13 to 39 | One-int row minus the no-arg row. **Assumes 3 literals per clause, not measured** |
| Each LRA atom's row (Q only) | 290 to 650 | **Assumes 3 terms**, 2 ints each at 40 to 100, plus 50 for a handle |

| Totals | dev: seconds, % of 0.527 s pass | fuzz: seconds, % of 8.033 s pass |
|---|---:|---:|
| S (80k callbacks and 47k solver calls on dev; 2.67M and 691k on fuzz) | 0.003 to 0.018, 0.6 to 3.4 | 0.076 to 0.52, 0.9 to 6.5 |
| Q (about 55k and 1.47M callbacks; constant-session LRA calls prorated by share, **a guess**) | 0.004 to 0.017, 0.7 to 3.1 | 0.083 to 0.39, 1.0 to 4.9 |

Batching would remove most of the Python-into-Rust charge, but it adds Python list work I didn't price. A lock per callback would add about 50 ns each; PyO3 shouldn't need one during a search, which I didn't test.

If the SAT share is anywhere in its 31-46% range, the crossings-free figures become:

| | dev | fuzz |
|---|---:|---:|
| S | 1.40 to 1.74 | 1.41 to 1.75 |
| Q | 1.48 to 1.86 | 1.71 to 2.25 |

**What 2x would need beyond Q, crossings free.** Q leaves 61.7% of dev and 52.6% of fuzz, so 2x needs 11.7 more points on dev and 2.6 on fuzz.

| Port next | Python lines | Share of pass it could speed, dev / fuzz | k needed, dev / fuzz |
|---|---:|---:|---:|
| EUF and transfer cores | 1,079 | 1.4 / 4.4 | **can't reach 2x** / 2.4 |
| engine.py and relations.py | 4,371 | 21.7 / 21.5 | 2.2 / 1.1 |
| Both | 5,450 | 23.2 / 25.9 | 2.0 / 1.1 |
| Everything but `outside`: the k_rest case | about 20,000, of which knowledge is 11,462 | | 1.29 to 1.37 / 1.06 to 1.08 |

"Could speed" takes out the SymPy-on-stack share, because SymPy calls from Rust aren't faster: table (c) gives -29 to +0.5 ns.

**k_rest has no measurement behind it.** k and k_lra come from replays of solver and LRA traces, with no SymPy in them. Nothing has timed Session, Relations or knowledge code in Rust. The only nearby data is that P ids bought nothing in Python and that SymPy operations cost about the same from Rust. So 1.06 to 1.37 looks modest, but it's an assumption. Those rows also assume no added crossing, while this code reads SymPy terms all the time. S and Q don't measure it either. The cheapest later measurement is porting EUF, which has few SymPy calls, and it wouldn't speak for the SymPy-heavy code.

## 3. History independence

**Requirement.** Issue 96: previous queries must not change later answers. It also asks for random test order, irrelevant assumptions, irrelevant rules and invalidated caches. Issue 97: one session per query, pure memos, nothing cached injected into another computation.

**Design for S and Q: no id table at all.**

- **S:** Rust holds solver ints and an opaque handle for each atom payload and each theory. It never hashes or compares a term.
- **Q:** Rust LRA also sees variable numbers and rationals. Numbers come from the existing Python mapping per `LRATheory`, whose `_new_var` takes `len(self._key)`, keyed on real SymPy hash and ==. This is simpler than sa-rust-11's candidate of a table in Rust, and it adds no new table.
- **Lifetime:** Rust state is owned by one solver object, created by the session and dropped with it. The crate has no `static` or `thread_local` holding state. Nested sessions get their own.

Against `RESULT-ids.md`:

| Rule or channel | S and Q |
|---|---|
| Lookup is an equivalence | No lookup in Rust. Python's dict is as it is today |
| Named exception: int and Integer in one key | Same key as today, because the key is SymPy's. In a Q row, `int` 3 and `Integer(3)` both convert to the rational 3, as == says |
| Named exception: Python bool and float | No ids, so the hand cases can't arise. In a Q row, conversion accepts exactly `type(x) is int`, `Integer` and `Rational`. Anything else, including `bool`, `float` and `Float`, keeps that session's LRA in Python, counted. **That path hasn't been built, and how often it's reached isn't known** |
| Rule 1, one hash discipline | Yes: real hash only |
| Rule 2, no id-hashed container reaches SymPy | Yes: there are none |
| Rule 3, table outlives its holders | Yes: the table is `LRATheory`'s own |
| Rule 4, atomic assignment | Unchanged Python, under the GIL |
| Set iteration | **No new channel.** Rust takes its order from Python's calls, so it's the same as Python's order |
| Clearing, pinning, weak refs, `clear_cache` | Don't arise: nothing outlives the session |

**What this doesn't cover:**

- **It adds no new channel, but it doesn't remove existing ones.** Dev query 873 changes clause order with query order in Python today. S and Q would inherit that.
- **First sight depends on the seed.** The numbering is a function of the query and the hash seed, not of the query alone. No answer moved across 3 seeds.
- **Past Q, no design here meets the requirement.** Session and Relations could use per-session ids, but knowledge's templates and process memos such as `_FORMULAS` hold terms across sessions (from their names and docstrings, not traced). They'd need SymPy's real hash, which limits the gain, or a process table, and `RESULT-ids.md` has hand cases where a process table makes a P equality depend on history.

**What the slice runs to show it**, each with the backend off and on:

1. Per-session state digests, recorded order against two shuffles, at one seed. Rust must match Python's own result per query, including query 873.
2. Fork per query against recorded order: same answers.
3. The same query twice in one process: same answers.
4. Hash seeds 0, 1, 2: answers equal, and Rust's state equals Python's at the same seed.
5. `tests/test_history.py`, the harness presets, and the random-order runs that issue 96 asks for.
6. A counter on sessions created and dropped, and a grep for `static` in the crate.

## 4. Build steps

Each step is one session under a 120k budget. Each stops at its check and reports. In the slice, the backend is switched by a monkeypatch under `rust-spike/`, as `cover.py` does, so no Python source changes.

| # | Step | Copied | New | Check |
|---|---|---|---|---|
| 1 | Crate with the solver as a PyO3 class: the 14 methods `coverage.md` lists, plus any it missed | `replay/src/solver.rs`, `block.rs`, `map.rs` (2,363 lines) | Wrapper, about 300 lines; theory hooks as a trait; session-end drop | Hand CNFs and propositional API calls give the same results as Python |
| 2 | **The compare tool:** a state dump on both solvers, and a direct API fuzzer with a scripted stub theory | Ideas from `replay/src/main.rs` | Fuzzer and dump, about 500 lines Python, 150 Rust | Runs clean; `mutate.py`'s 10 mutants ported and scored per check |
| 3 | Live theory callbacks into the Python theories | | Callback layer, about 300 lines; monkeypatched backend | Dev and fuzz digests match; per-session state matches on every session |
| 4 | Whole-suite and history gate | | Scripts | `satassume` tests with the backend on; the 6 history runs; new boundary mutants |
| 5 | **Timed S on pareto1, quiet lease.** Alternating Python and Rust rounds, digests checked | `run-slice.sh` | Crossing counts times measured cost; report | Speedup by whole, None and definite, against the table above. **The gate:** decide on Q or stop |
| 6 | Only if the gate says so: rational LRA | `lra/port/src/lra.rs`, `rat.rs` (1,509 lines), and its `PySet` | Row conversion, constant-atom switch, about 400 lines | Same check, with the LRA mutants, and the `_dirty` order compared call by call |
| 7 | Timed Q | | | As step 5, with k_lra live |

**Identical-answers check.** The replays compared results at entries, and some paths never mattered on those traces. They missed 5 of 10 solver mutants and 2 of 9 LRA ones. This check is stronger in three ways:

1. **It compares more.** At every solver entry, in every session, on two processes with the same seed:
   - trail, with level and reason of each literal
   - learnt clauses and watch lists, in order
   - activity and var_inc as exact bits
   - saved phases, decision and conflict counts, and the model and ring state
   - each theory call, with its arguments and its result, in order

   Streams are hashed per entry. A mismatch re-runs that session to dump the first difference.
2. **It reaches more.** The API fuzzer drives `mention`, `set_inert`, `register_block`, `release` and a stub theory directly, to reach paths the workloads miss, such as `_fill` growth past the model's end or a None in the ring. The test suite is also run, since it reaches things the workloads don't.
3. **Mutants judge it.** The 5 missed were `_mention` order, ring None, `_fill` growth, `_learn` bump order and the theory unit reason. Each is scored per check: digest, state compare, fuzzer. New boundary mutants are batch flush order, swapped callback order, a dropped theory result and a stale handle after a nested session.

**Pass rule:** every mutant caught, or argued equivalent in writing, one at a time, with that argument reviewed. If the 5 missed mutants still aren't caught, S hasn't shown identical behaviour, and the plan's check has to change before any timing counts.

**Keeping SymPy able to use it (Tilo's constraint):** Rust is an optional backend behind one factory, with pure Python unchanged as the reference. It adds no change to SymPy, no new hash or identity behaviour, and no Rust dependency for a user who doesn't want it. Step 5 should report full API and abi3 both, since abi3 is what makes wheels easier and it costs up to twice as much per crossing.

**One thing that goes against the constraint, for step 6 only:** the LRA port copies CPython 3.12's set table to match `_dirty` order. A CPython change would then split the backends' answers or search. The alternative is a defined order such as `sorted(self._dirty)` in Python too. That changes search and possibly answers (mutant 7 changed 1 dev and 8 fuzz calls; ascending order wasn't told apart). It's a change to Python source, so it's a decision for the architect and Tilo. S doesn't meet this.

## 5. Method and limits

**Method.** Share and coverage figures are from `slice/results/coverage.md`, not re-measured. S's maximum is computed here with the formula behind that table, and the same formula reproduces its Q row (1.62, 1.90). Audit runs were on orion, untimed. No Rust was written or run for this plan. No new timing was needed.

**Limits:**

- **Sampler bias.** Shares come from a sampler biased to thin callees; SAT is 31-46% by other timers. That's why the range in section 2 is wide.
- **Reused k.** k and k_lra are whole-workload values applied to every class, from replays, not live runs.
- **The maximums assume no crossing cost and no added Python.** The crossing estimate rests on the assumed 3 literals, 3 terms, and prorated constant-LRA calls, and on the `o.args` row standing in for reading a return value.
- **Constant-atom switch not traced.** `_fields` is set at lra.py:663, :691 and :723, so a session can start rational and turn constant. Whether this happens after an assert hasn't been measured, and step 6 must handle it. S is unaffected.
- **Audit coverage is the workloads only.** The test suite wasn't run with `audit.py`. Over-budget cones and re-entrant queries are 0 on the workloads, so those paths have no evidence there. Sessions with a different session count across runs weren't compared query by query.
- **Dev query 873 is unexplained.**
- **`custom.facts_for` in `analyze.py` is still never wrapped.** The 0 in `coverage.md` means nothing; the audit's own wrap replaces it.
- **Step sizes are my estimates.** The new-line counts haven't been checked against any build.
- **Nothing here measures memory or other CPython versions**, or how a SymPy install would pick up the backend.
