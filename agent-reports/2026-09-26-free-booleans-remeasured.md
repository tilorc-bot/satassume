# Agent report: the free-Boolean option re-measured after irrational constants

- **Date:** 2026-09-26
- **Status:** measured on `main` at `c8361d7` (items 1 and 2 landed). No
  engine change. For the owner's decision on the default of
  `Engine(uninterpreted=...)`.
- **Scripts:** `agent-reports/scripts/free_stream.py` (replay under one
  mode), `free_compare.py` (classification, SymPy check, census of
  unreadable relations), `free_gate2_stream.py` (gate2 as a stream file),
  `free_ab.py` (interleaved local timing).
- **Read with:** `2026-09-25-facts-0-measurements.md` sections 6 and 7 (the
  first census), `2026-09-26-irrational-landing.md`, next-steps plan
  section 2, last bullet.

## Numbers

| | before item 1 and 2 (facts-0, section 6 and 7) | now (`c8361d7`) |
|---|---:|---:|
| stream: answers changed, default -> free | 534 (498 more definite, 36 new errors) | **3** (3 more definite, 0 new errors) |
| stream: flipped or less definite | 0 | **0** |
| stream: queries with a relation no theory reads | (663 whose assumption sets failed) | **193** (all in the assumptions) |
| gate2 (2,863 queries): answers changed | 0 | **0** (no unreadable relation at all) |
| refine scoreboard, `satassume` backend | 422 vs 416 passed (+6) | **423 vs 423 (+0)**, same 474 outcomes, same 6,679 answers |
| refine scoreboard, `combined` backend | | 467 vs 467, same 474 outcomes |
| combined backend: SymPy fallbacks `no-theory` | 124 | **1** (`Q.eq(nan, 1)`) |
| cost, local, indicative only | | +3.8% (best of 5, noise level) |

### Stream (13,877 queries), default vs free

The 3 changed answers, all None -> False, each once in the stream, SymPy's
`ask` (pin `ddbb536`) None on all three, checked by hand:

| # | query | assumptions | free | unreadable atom | by hand |
|---|---|---|---|---|---|
| 4147 | `Q.zero(x)` | `Q.le(x, 4.712) & Q.ge(x, pi/2)` | False | `4.712 < x` (Float) | correct: `zero(x)` is `eq(x, 0)`, which makes `x` real, and LRA then has `0 >= pi/2` |
| 5814 | `Q.negative(x)` | `Q.ge(x, 0) & Q.le(x, AccumBounds(0, 1))` | False | `AccumBounds(0, 1) < x` | correct: `x >= 0` is `~(x < 0)`, and `negative(x)` implies `x < 0` |
| 5838 | `Q.negative(x)` | `Q.ge(x, 0) & Q.lt(x, zoo)` | False | `x < zoo` | correct, as above |

No new InconsistentAssumptions (the 36 of the first census were 24
answered by item 2, where SymPy raises too, and 12 constant queries that
item 1 now answers without the assumptions, in both modes). Nothing
flipped, nothing less definite.

**What is still unreadable in the stream** (193 distinct queries, each
once; the relation is always in the assumptions, never in the
proposition; 10 distinct atoms):

| kind | queries | atoms |
|---|---:|---|
| Float | 93 | `1.5707963267948966 < x`, `1.5707963267948967 < x`, `1.571 < x`, `4.712 < x` |
| `oo`, `-oo`, `zoo` | 72 | `oo < x`, `x < zoo`, `x < -oo` |
| constant without bounds | 24 | `AccumBounds(0, 1) < x` |
| non-real constant | 4 | `x < I`, `I < x` |
| nonlinear `pi*x`, `sqrt(2)*x`, `I*x` | **0** | |

`x*y` and `x**2` are not unreadable: LRA reads them as opaque terms. The
only nonlinear shape it refuses is an irrational or imaginary coefficient
(`pi*x`, `sqrt(2)*x`, `I*x`), and the stream has none. Of the 193, free
changes 3; default and free both answer 124 None, 18 True, 48 False (the
definite ones never reach the unreadable atom: fast paths and constant
queries).

### gate2 (2,863 frozen SymPy assumption-test queries)

0 answers differ between default and free; no query has an unreadable
relation. (Separately: current `main`'s default answers differ from the
frozen file on 5 queries, all None -> True, from items 1 and transfer:
`Q.algebraic(1**x)` 4 times and `Q.prime(x)` given `Q.prime(y) & Q.eq(...)`.
The frozen file predates them; free changes none of the 5.)

### Refine scoreboard (recipe of `2026-09-25-refine-capability-baseline.md`)

`main` (`c8361d7`) merged with `refine-identities` `eb106a6` (clean,
local merge only), SymPy `6379c4da69` extracted with `git archive`,
`REFINE_BASELINE_ENGINE_KW='{"uninterpreted": "free"}'` for the free runs.

| backend | default | free |
|---|---|---|
| satassume | 423 passed, 49 failed, 2 xfailed | 423 passed, 49 failed, 2 xfailed |
| combined | 467 passed, 3 failed, 4 xfailed | 467 passed, 3 failed, 4 xfailed |

Per test (JUnit): 0 of 474 outcomes differ in either backend. The
`satassume` query logs are identical line by line (6,679 queries, 0
answers differ). The 6 tests free Booleans fixed before are the 6 pi
relation losses item 2 now fixes. The `sympy` backend was not re-run (its
answers do not depend on the option; the build agent's 463 stands), so
the losses against SymPy are those of the irrational build report: 46 = 45
matrix + 1 stale expectation.

### Combined backend fallbacks

| | default | free |
|---|---:|---:|
| queries | 6,820 | 6,820 |
| SymPy fallbacks | 543 (541 matrix, 1 `no-theory`, 1 inconsistent) | 542 (541 matrix, 1 inconsistent) |
| satassume None that stands | 2,912 | 2,913 |

The one `no-theory` fallback is `Q.eq(nan, 1)` with no assumptions
(neither EUF nor LRA reads `nan`). SymPy `6379c4da69` answers False,
the pin `ddbb536` None. Under free, `route` no longer sees an
uninterpreted relation, satassume's None stands and the combined backend
**loses that False** (combined answers False 1,397 -> 1,396). No test
outcome depends on it. It is the only answer free makes less definite
anywhere in this measurement, and only through the routing.

### Cost (indicative, local, not the Pi)

`free_ab.py`, 5 interleaved rounds of the stream replay, fresh process
each, on this 4-core machine with another agent's load (load average
about 1.5):

| | runs (s) | best |
|---|---|---:|
| default | 3.78, 3.64, 3.55, 3.84, 3.56 | 3.554 s |
| free | 3.93, 3.70, 3.95, 3.69, 3.72 | 3.689 s |

+3.8% on the best-of, within the run-to-run spread (the default alone
spans 8%). The extra work is plausible: 193 sessions are built and
searched instead of abandoned at the first unreadable atom. **Not a
measurement to decide on**; the Pi timing is separate.

## Method

- Worktree `/home/tilo/satassume-wt-free` (detached at `c8361d7`,
  `.venv` symlinked), `PYTHONHASHSEED=0`,
  `PYTHONPATH=.:/home/tilo/sympy` (pin `ddbb536`), every Python command
  under `systemd-run --user --scope -p MemoryMax=1500M -p MemorySwapMax=0`
  and `timeout 250`.
- Stream: `free_stream.py STREAM OUT MODE` replays `stream.pkl` in order
  through `sympy_api.ask` on one engine, `Engine()` or
  `Engine(uninterpreted="free")`, and writes every answer. The comparison
  is default against free on the same `main`, not against the recording
  (which predates items 1 and 2). `free_compare.py` classifies each pair
  (same, more definite, new error, lost error, less definite, flipped),
  asks SymPy's `ask` on every distinct changed query (10 s alarm), and
  runs a static census: every `eq`/`lt` atom of the translated
  proposition and assumptions that `lra_adapter.interpret` does not read
  (and, for `eq`, `EUFAdapter.parse` does not either), classified by the
  first matching reason (matrix, `oo`/`zoo`/`nan`, Float, irrational or
  imaginary coefficient, non-real constant, constant without bounds).
- gate2: `free_gate2_stream.py` rebuilds the frozen records into a stream
  file, then the same two scripts.
- Scoreboard: section 5 recipe (satassume and combined backends, each
  mode, `refine_baseline_plugin` query logs), compared by JUnit outcome
  per test and by query log line by line; fallbacks with
  `refine_baseline_counts.py`. The free runs are confirmed to have used
  the free engine: the combined log has no `no-theory` route under free.
- Timing: `free_ab.py --rounds 5`.

## What making free the default would change

- **Answers:** 3 stream queries become False (correct, SymPy None). Nothing
  on gate2, nothing on the refine scoreboard. No new errors, nothing
  flipped.
- **Combined backend:** 1 fewer SymPy fallback, and with it 1 lost answer
  (`Q.eq(nan, 1)`, False from SymPy becomes None), because `route` can no
  longer tell that a relation was unread. If free became the default,
  keeping `route`'s `no-theory` signal (for instance, `_FlagUninterpreted`
  still flagging an unread atom under free) would avoid that loss.
- **Cost:** probably a few percent on the stream (the 193 sessions), to be
  timed on the Pi.
- **What free would still cover:** Floats (93 stream queries),
  infinities (72), `AccumBounds` (24), `I` (4), and nonlinear coefficients
  like `pi*x` (none in the stream). Items 1 and 2 took essentially all of
  the gain the first census found (498 -> 3 answers, 6 -> 0 tests, 124 -> 1
  fallbacks).
