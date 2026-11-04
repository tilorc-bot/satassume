# Can interned ids stand in for SymPy's hash and ==? (issue 323)

**On everything tested, ids give the same answers as SymPy's hash and ==, apart from one test, once the rules below are kept.
They also give no speedup while the code stays in Python. Moving only P to a cached id was 8.8% slower on dev and within noise on fuzz.**
The answers depended on no history in any replay. That isn't proved: I built hand cases where an id table makes a P equality depend on
history, and the set-order channel isn't ruled out.

| P hash and eq on a cached id, against main 9bafaa5 | dev | fuzz 424242 |
|---|---:|---:|
| Speedup, base / P id, median of 10 rounds | **0.919** (0.914 to 0.928) | **1.006** (0.978 to 1.019) |
| Noise floor, base / base, same runs | 1.000 (0.994 to 1.012) | 1.000 (0.984 to 1.012) |
| Median seconds, base and P id | 0.527, 0.571 | 8.046, 8.005 |
| Share of asks P covers before the edit | 31.0% | 30.7% |
| Total asks, before and after | 282,918, 201,486 | 5,946,570, 4,305,518 |
| Digest, all 66 pinned runs | `31cd0945c07f02a6` | `173502b6ef285ad6` |

Below 1 means slower. **There's no gain to report.** The edit removed 28% of asks and bought no time, so a removed ask here isn't a saved
cost. The likely reason, which I didn't measure, is that a SymPy hash ask is one Python method reading a cached value, and P's new path is
also a Python method. Only P was converted. I give no upper bound for a full conversion, because this run has no per-ask saving to scale.

## Method

- **Stand-in** (`ids/ids_core.py`): monkeypatches give ids by caller frame, with scopes `sa`, `repo` and all frames. Modes are shadow, eqonly, live,
  and live with random hashes. The package itself is not edited. This stand-in can't be timed, because its wrappers are the cost.
- **P edit** (`ids/p-id.patch`): only P's hash and eq in `sat/formula.py`, on a throwaway copy. A process-wide table maps `(pred, expr)` to an id,
  looked up by the real hash and ==, and each P caches its id. All P share one hash discipline, and P isn't a SymPy object. I checked by
  reading that no id-hashed dict goes into SymPy, not by tracing it. Not merged anywhere.
- **Timing**: quiet lease on pareto1, `bench-container`, `BENCH_CPU=2`, `sa-eval-bench:1`, `PYTHONHASHSEED=0`. Cold process per run, 11 rounds with
  round 0 a warmup, modes rotating. The base package hashes the same as a `git archive` of 9bafaa5. Raw: `ids/results/pid-pinned.raw`.
- **Asks**: `rc.py mon`, outermost SymPy entries inside the boundary. Same count as `ids/results/asks.md`.

## What was tested and what happened

| Test | Result |
|---|---|
| Shadow, dev and fuzz, whole suite | 0 disagreements between ids and real hash and == |
| Live ids, recorded and shuffled, dev and fuzz | digests match |
| Live ids, each query in a fork, all queries; 120 sampled as separate processes | match |
| History: 32 replays, random hashes and shuffles, `PYTHONHASHSEED` 1 to 4 on base | digests match |
| P id, recorded and 3 shuffles, dev and fuzz | digests match |
| == by ids only, whole suite | 0 failures beyond base |

### Suite: every failure has a class

Live ids at frame scope failed 116 tests beyond base, counting serial and xdist together (`ids/results/suite-classes.tsv`).

| Class | Tests | How it was shown |
|---|---:|---|
| Artifact: a container crosses test code and satassume | 66 | pass with ids in test frames too |
| Artifact: a container crosses satassume and SymPy | 48 | pass with 3 functions exempt, and at all frames |
| Artifact: wall-clock limit, wrappers | 1 | 2.35 s against a limit of 2 |
| **Real: int and Integer mixed in one key** | **1** | `test_add_rows::test_the_pattern_keys_are_legacys` fails at every scope |

With ids at all frames, and with random hashes, only that test fails beyond base, plus one wall-clock test serially.

**The P copy:** xdist and serial each gave 12 failed, 6,071 passed (`ids/results/pid-suite.txt`): the 11 on base plus one. The new failure is `test_history::test_module_state_inventory_is_classified`: the
guard rejects `_P_IDS` as unclassified global state. That's a fair catch, see below. `test_performance_smoke_300_vars` also fails on base
under load, so it isn't counted either way.

## Exceptions and rules

**Named exceptions**

1. **int and Integer in one key.** `hash(Integer(3)) == hash(3)` and == holds, so `('add_bound', 3, 2)` and its Integer form are one set key. An int
   needs the Integer's id. This is the one real failure.
2. **Raw Python bool and float.** `True` can't have one id: `S.true == True` and `Integer(1) == True`, but `S.true != Integer(1)`. The same holds for
   `1 == 1.0`, `1.0 == Float(1.0)`, `Float(1.0) != Integer(1)` (`ids/results/pid-hand.txt`). The float case is new here. A backend can't intern these
   and must fall back to SymPy's == for them. That path ran 0 times in testing.

**Rules**

1. A container has one hash discipline for its whole life. Exempting whole functions while the rest used ids gave 862 failures beyond base.
2. No id-hashed container crosses into SymPy (`xreplace` rule dicts, `free_symbols` tests).
3. A table outlives everything holding one of its ids (next section).
4. Assigning an id must be atomic. Two threads could get one id for two values. By argument only, nothing here is threaded.

`is` needs no rule from ids: of 968 `is` checks, 74 are object identity, and ids don't change them. A port must keep the address for those.

## Lifetime and history

**Can the table make answers depend on history?**

| Channel | Seen in the replays | Ruled out by argument |
|---|---|---|
| Lookup, where == is an equivalence | no | **yes**: same id exactly when ==, so the same entry is found |
| Python bool and float | no, 0 reached | **no, and shown by hand.** `P('a',True) == P('a',Integer(1))` is False if `S.true` was interned first, True if `Integer(1)` was. `P('a',1) == P('a',1.0)` becomes False once `Integer(1)` and `Float(1.0)` are in. The real == is True in all of these |
| Set iteration order | no: random hashes and shuffles never moved an answer | **no.** An id depends on first sight, so a set's order can depend on earlier queries. `ids/set_iter.py` finds at least 19 sites iterating a visible set; I didn't audit them |
| Clearing the table | not tried in a replay | **no, and shown by hand.** After a clear, `P('a',x) == P('a',y)` is True for different x and y, and two P of one value compare False |

So the answer is **yes, it can, by construction, at the level of P equality. No changed answer was ever seen.** The hand cases change an equality, not a
query answer; I didn't build a query where the answer moves. On the set channel: real hashes already vary with the seed, so an order-sensitive site
would be a seed bug today. With ids it would become a history bug within one process, which issue 96 and the closed issue 97 exist to prevent.

The rest of the lifetime:

- **Purity.** `state/memos.py` allows only a pure function of the key on `PROCESS`. An id isn't one, since it depends on first sight. It's safe only if nothing
  reads more than equality from it.
- **Clearing.** `Memos.clear` and `harness.state.reset_module_state` don't reach the table. Registering it to satisfy the inventory guard would make it clearable,
  which is the false equality above. A counter that never reuses ids avoids false equality but still gives two ids for one value.
- **Ownership.** An id cached on a P lives as long as the P. Process memos such as `_FORMULAS` appear to hold formulas across engines (from the name and docstring,
  not traced), which would make a per-engine table wrong. So the table is process-wide.
- **Pinning.** The table is unbounded. Other process memos are bounded and empty when full; this one can't. Rows: P table dev 615 (385 exprs), fuzz 5,053 (4,400).
  All frames: dev 1,019 ids and 1,729 addresses, fuzz 7,681 and 13,405. By argument, each new `Dummy` adds a row forever.
- **No weak table without changing SymPy.** Symbol, Integer, Add and Dummy can't be weakly referenced here. I didn't measure how many rows would be alive without the pin.
- **`clear_cache`** doesn't touch the table, so objects it would free stay held.

## Limits

- **Why 22 tests flip between serial and xdist under live is not shown.** All 22 are in the artifact classes and clear at all frames in both orders. A memo filled by an
  earlier test is a candidate, nothing more.
- **`Integer(1) == True` was reached 0 times. That doesn't prove it's unreachable.** The hand pair shows the disagreement exists.
- **The workloads and the suite reach different things.** On the workloads, satassume reached only `has` and `atoms` of the crossing calls, with no `xreplace` or `subs`. `bind` and
  `constant_term` run at row compile and `limits._inner` only on Sum and Integral, so the suite reaches behaviour the digests can't see. The suite has no digest check, only its own tests.
- **Timing covers one edit in CPython on two workloads.** It says nothing about ids in a Rust backend.
- **The P table was not run under random hashes.** The random-hash replays used the stand-in. P's first-time lookups stay high: fuzz 92,073 for 5,053 rows, since P objects are
  rebuilt. An address path could cut those asks; I didn't try it.
- **Set-site count is a floor.** It misses sets passed in as arguments.

## Conclusion

**Ids hold with these named exceptions and these rules.**

- **Exceptions:** int and Integer mixed in one key, and raw Python bool and float.
- **Rules:** one hash discipline per container, no id-hashed container into SymPy, a table that outlives every holder of its ids, atomic id assignment.

History independence isn't established. It held in every replay and is not ruled out by argument.

**Which column of `RESULT-k-lra.md`:** the "integer ids" column, as far as its premise goes, since ids gave the same answers on everything tested. This doesn't say whether constants stay in Python,
so it doesn't choose between that column and its "constants stay in Python" variant. Nothing here measures the factors in that column, and the Python timing above doesn't bear on them.
