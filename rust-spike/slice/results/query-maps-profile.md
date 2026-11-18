# term_live's per-query maps: the profile before the port (issue 323; sa-port-316)

Read-only: no source changed. Times UTC, 18 Nov. Tree 5b1d96f staged by sa-port-314 on pareto1 (source-equal to
rust-slice 5f53735, which differs in results/term-live-step.md only), .so b18cc160, `SLICE_CONVERT=rust`, pysampler under
quiet lease 27294543, pinned to CPU 2: dev 30 runs, fuzz 6 runs, frames on and off. Scripts: `tools316/prof316.sh` (the
runs), `tools316/live316.py` (the split below). Raw samples: orion and pareto1 `~/sa-rust-ids-work/sa-port-316/prof/`.

The planner's question: of the C API time term_live's frames moved into Rust, what share is dict get/set with SymPy
`__hash__`/`__eq__`, against everything else, and can it beat the run-to-run spread?

## Answer

No. SymPy hash and `==` under live.rs are 0.10% of dev's samples and 0.30% of fuzz's. Everything the seven maps'
functions cost is 1.24% (dev) and 2.64% (fuzz). The dev slowdown the frames brought is in `_Mark`, which the maps
don't touch.

Samples are those inside the query loop. "live.rs's own" is every sample whose innermost `term::live` frame has no
Python callable it was asked to run beneath it (the guarded function, a relation's atoms): its Rust, the C API it calls
directly, and `__hash__`/`__eq__` reached through a lookup.

| frames on, Rust walker | dev | fuzz |
|---|---|---|
| samples | 20,465 | 36,046 |
| live.rs's own | 1,767 (8.63%) | 2,191 (6.08%) |
| `_Mark`: `note`, `add_in`, `mark` | 1,385 (6.77%) | 710 (1.97%) |
| the seven maps' functions: `term_id_in`, `int_id`, `same_class`, `ids_in` | 253 (1.24%) | 951 (2.64%) |
| `current` and the stack | 56 (0.27%) | 261 (0.72%) |
| `Guarded`/`RelationRun`, their own part | 60 (0.29%) | 245 (0.68%) |
| other | 13 | 24 |

The seven maps' functions, split by what the sample is in:

| | dev | fuzz |
|---|---|---|
| SymPy `__hash__`/`__eq__` through a lookup | 21 (0.10%) | 108 (0.30%) |
| dict get/set, C only | 44 (0.22%) | 164 (0.45%) |
| other C API (attribute reads on the query, method calls, isinstance, `.args`) | 77 (0.38%) | 306 (0.85%) |
| `count`/`planted` (the counters, string keys) | 55 (0.27%) | 166 (0.46%) |
| other Rust (the table's `number`, `raw_add`, `py_int`) | 34 (0.17%) | 118 (0.33%) |
| live.rs itself | 22 (0.11%) | 89 (0.25%) |

Of all live.rs's own time, SymPy hash and `==` are 1.2% (dev) and 4.9% (fuzz). A port that took the first three rows to
zero would gain at most 0.69% on dev and 1.60% on fuzz, and it can't take them to zero: `term_id` is handed a SymPy
object, so finding its id still needs a hash and, on a hit by an equal but distinct object, an `==`.

S1's spread on 5b1d96f (results/term-live-step.md): frames off to on, paired, dev -1.88 to +5.72% (Rust walker -0.91
to +4.76%), fuzz -0.62 to +1.62% (Rust walker -0.74 to +0.46%). The dev ceiling is inside it; the fuzz ceiling is at
its edge and isn't reachable.

## Where the dev slowdown is

The same functions on Python's frames (frames off, Rust walker; samples whose innermost Python frame is the function,
so with the C it calls directly; 19,843 dev and 35,962 fuzz samples):

| | dev, Python | dev, Rust | fuzz, Python | fuzz, Rust |
|---|---|---|---|---|
| `_Mark` (`__init__`, `_note`, `add`) | 722 (3.64%) | 6.77% | 407 (1.13%) | 1.97% |
| `term_id`, `_ids`, `same_class`, plus their SymPy hash/`==` | 269 (1.36%) | 1.24% | 1,104 (3.07%) | 2.64% |
| `current`, `stack` | 119 (0.60%) | 0.27% | 424 (1.18%) | 0.72% |
| `_guarded`'s `g` | 37 (0.19%) | 0.29% | 102 (0.28%) | 0.68% |

`_Mark` costs 3.1 points more in Rust on dev, which is the whole +3% (sampled wall here: dev 0.666 to 0.687 s, +3.2%;
fuzz 6.014 to 6.038 s, +0.4%; digests equal). On dev, of `_Mark`'s 1,385 samples: 398 are `attr_or`'s attribute
reads (`native` and `stamp` asked of plain dicts, each miss making and dropping an AttributeError, where Python's
`getattr(t, name, default)` makes none) and 179 are `import builtins` / `import collections`, done per noted table
(live.rs:294 and :302). Neither involves the seven maps.

## Two facts for the port's design

- The Rust walker has no native id table. `term/walk.rs` fills Python's own `ids` dict, `objects` list and `classes`
  dict (walk.rs:3-13, :182-184, `setdefault` at :444), so there are no walker ids to key a native map on without first
  giving convert a native interner; that interner would call `__hash__` and `__eq__` itself to keep R1.
- Non-test Python readers of the maps outside the moved frames: `ids`/`objects` in knowledge_core_live.py:88-89 and
  :139-140, knowledge_f6_live.py:184-185, knowledge_live.py:305 and :312, term_ids_direct.py:57, session_live.py:415;
  `objects` handed to Rust in lra_live.py:135, :157, :176, :192; `derived` in session_live.py:417; and term_live.py's
  own unmoved functions (:327-329, :486-487, :513-519, :648-649, reading `ids`, `objects`, `derived`, `rev`, `ints`).
  Under the State ruling each needs a Rust accessor or the map stays.

## Not done

The port, its plants (746 up), the bar, the 2x2, the history check and the probe count: stopped at the planner's
second addition, before any source change. rust-slice is still 5f53735, 21 of 32.
