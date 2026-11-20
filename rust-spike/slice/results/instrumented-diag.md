# Why full instrumentation moved the Rust path's answers (sa-port-368, issue 323)

Diagnosis only. No source change to satassume or the slice. Committed: this file, `results/tools368/`, and the fix to
the instrument `results/tools367/cnt367.py`.

**Result: class (a), the instrument is not transparent.** tools367's counting descriptor (`Field`) was installed on
`backend.EUFTheory` in front of four attributes that this class inherits as native getset descriptors from the
crate's `sa_solver.EUFTheory`: `rep`, `members`, `on_merge`, `_lims` (and likewise on three of
`backend.TransferTheory`, which move nothing). The `Field` reads and writes the instance
`__dict__`, where these values never are. Reads of `rep` and `members` raise `AttributeError`; a write of `on_merge`
goes to the instance dict and never reaches the crate. No mixed native/Python path disagrees with the reference
(not (b)), and the moved digests are the same run to run (not (c)). After the fix all digests are the reference ones.

## Tree and cells

- Head: rust-slice 966268c64c84 (worktree `~/sa-rust-ids-work/sa-port-368/wt`, branch diag/instrumented), tools367
  from audit/reads b832e5f. `.so` 4d8921d9c510e99f (built here by build_solver.sh; equal to sa-port-367's).
  Python 3.12.14, PYTHONHASHSEED=0, orion.
- Cells (`tools368/cell368.sh`, gocnt367.sh's environment):
  - `rust-nat`: SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust SLICE_WITNESS=1 SLICE_WITNESS_CAP=32 SLICE_WITNESS_RUST=1
  - `py-ref`: the slice installed, SLICE_CONVERT=py and no other SLICE_ switch (the ruling's Python reference)
  - `default`: the package alone, no SLICE_ switch
- "Full" = every satassume module and every slice module that is not a test (sa-port-367's filelist.txt, 208 files):
  354 descriptors on rust-nat, plus the PY_START/PY_RETURN hooks.
- `tools368/bis368.py` runs tools367's cnt367.py unchanged but for named knobs (which descriptors, hooks on/off, a
  probe before the pass, the answers written per query). Each patch of the source must match exactly once.
- Reference digests: dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6, budget 35bc2c4a937bebc0, wiring a0df9fd43e5180c1.
  With no instrument, rust-nat, py-ref and default all give them (rows below).

## Bisection trail (instrument as at b832e5f)

| stage | cell (rust-nat) | dev | fuzz |
|---|---|---|---|
| 0 reproducibility | full, run twice, same hash seed | 87c8bba93cdafb96 twice, answers byte-equal | dbcf7b7b9e3f33d8 twice |
| 0 | no instrument | 31cd0945c07f02a6 (ref) | 173502b6ef285ad6 (ref) |
| A | hooks only (PY_START/PY_RETURN, no descriptor) | ref | ref |
| A | descriptors only (hooks off) | **moved**, 87c8bba93cdafb96 | - |
| B by module | descriptors of one module (26 modules have any), each alone | moved only for `satassume/theories/euf/euf.py` (87c8bba93cdafb96); the other 25: ref | - |
| B | all but one module | ref only without euf.py; the other 25: moved | without euf.py: ref |
| C by field | each of euf.py's 19 `EUFTheory.*` descriptors alone | moved for `rep` and for `members` (each 87c8bba93cdafb96, answers byte-equal to the full cell); the other 17: ref | `rep`: dbcf7b7b9e3f33d8; `members`: dbcf7b7b9e3f33d8; `on_merge`: **f8dcab9c4f2137e8**; `_lims`: ref |
| C | all but one field | moved for every one (the other of rep/members remains) | - |
| C | all but `rep` and `members` | ref | **f8dcab9c4f2137e8** (not ref) |
| C | all but `rep`, `members`, `on_merge`, `_lims` | - | ref |

So three wraps each move a digest alone, and no set is needed: `EUFTheory.rep` (dev, fuzz), `EUFTheory.members` (dev,
fuzz), `EUFTheory.on_merge` (fuzz only). The hooks move nothing ([157]'s EXCEPTION_HANDLED event is not used by
cnt367; PY_START/PY_RETURN alone leave both digests at the reference).

With full instrumentation the py-ref cell moves too (dev 379373e76956513b, 40 queries, all `raise AttributeError`):
the Rust EUF is installed there as well (`backend.install_euf`), so this is the same wrap, not the Rust switches.

## What moves

- `rep` or `members` (dev: 32 of 1985 queries; fuzz: 561 of 3000): every moved answer becomes `raise AttributeError`
  (dev: 24 from False, 7 from None, 1 from True; fuzz: 389 None, 71 ValueError, 55 False, 46 True).
- `on_merge` (fuzz: 3 of 3000; dev: 0): True becomes None on queries 352, 360, 2333. No exception leaves `ask`.

First moved query per wrap, same order of answers each time:

| wrap | workload, index | query | instrumented Rust (rust-nat) | uninstrumented Rust (rust-nat) | Python reference (py-ref) |
|---|---|---|---|---|---|
| `EUFTheory.rep` (or `.members`) | dev 1709 | `ask(Q.eq(n, 0), Q.integer(n) & Q.positive(n))` | raise AttributeError | False | False |
| `EUFTheory.rep` (or `.members`) | fuzz 10 | `ask(Q.ne(0, 3*x + y + 2), Q.ge(x, 1))` | raise AttributeError | None | None |
| `EUFTheory.on_merge` | fuzz 352 | `ask(Q.ne(-x - 1, 2*x - 1), Q.lt(x, -1))` | None | True | True |

The default path (package alone) gives the uninstrumented answer on all of them.

## The exact non-transparency (class (a))

1. `backend.install_euf` (backend.py:88-94) sets `euf.EUFTheory = adapter.EUFTheory = backend.EUFTheory`, an empty
   Python subclass (backend.py:84) of the crate's `sa_solver.EUFTheory`.
2. cnt367's `install_fields` takes the field names from the ast of `satassume/theories/euf/euf.py` (the 19 names
   Python's `EUFTheory.__init__` stores) and finds the class by the module's attribute, `getattr(module,
   "EUFTheory")`, which is now `backend.EUFTheory`. It looked the name up in `cls.__dict__` only (b832e5f
   cnt367.py:359). The subclass's own dict is empty and it has an instance dict, so every name took the branch "not
   defined: a plain instance-dict field" and got `Field(cls, name, None, _MISSING)` (b832e5f cnt367.py:366). The
   check for a base's definition covered `__slots__` only.
3. On the base, `rep`, `members`, `on_merge` and `_lims` are getset descriptors (`#[getter]` at euf_py.rs:172, :178,
   :154 with the setter at :159). The `Field`, a data descriptor on the subclass, comes first in the lookup.
4. Read: `Field.__get__` reads `obj.__dict__[name]` (b832e5f cnt367.py:178), finds nothing, and raises
   `AttributeError` (:181). The first reader is the crate: `sa_solver.rel_init` (called at session_live.py:598, under
   `sa_solver.ses_init` at session_live.py:887) builds the transfer theory, whose `initial_multi` does
   `euf.getattr("rep")` and `euf.getattr("members")` (transfer_py.rs:60, :62; also :41, :47). The error leaves `ask`.
5. Write: the transfer theory's `_attach` does `euf.setattr("on_merge", merged)` (transfer_py.rs:133).
   `Field.__set__` stores it in the instance dict (b832e5f cnt367.py:213); `set_on_merge` (euf_py.rs:159) never
   runs, the crate's listener stays None (euf_py.rs:108), and the transfer theory is never told a merge. It loses
   the facts it derives from merges: 3 fuzz answers go from True to None. This one is silent.
6. `_lims` is shadowed the same way and moves nothing on dev or fuzz. The other 15 names are not defined on the Rust
   class at all; a descriptor on them is never reached.

P1 and the `_replaced`/fallback counters are not involved: no method was replaced and no fallback path ran. The
instrument put a dict-backed descriptor in front of a native attribute, so the crate was handed an AttributeError (or
its setter was bypassed). The default path is unaffected because there `euf.EUFTheory` is Python's own class, whose
fields are in the instance dict.

## Quiet catches (engine.py:1953 around `_complete_check`; sympy_api `_consistent` around `Engine.verdict`)

Counted with the slice's catch_count.py through `tools368/probe_catch368.py`; the counter is shown to fire on a
planted raise in every cell (PLANT sink 1).

| cell (rust-nat) | instrument | quiet catches |
|---|---|---|
| dev | none | 0 |
| fuzz | none | 0 |
| dev (py-ref) | none | 0 |
| dev | full, b832e5f | 1: an `AttributeError` into `_consistent`'s handler (besides the 32 that leave `ask`) |
| fuzz | `on_merge` alone, b832e5f | 0: the three lost answers come with no exception at all |
| dev | full, fixed | 0 |
| fuzz | full, fixed | 0 |

## The fix (tools367/cnt367.py, results only)

`install_fields` now looks a name that is not in the class's own dict up on the bases (cnt367.py:369-378): if a base
defines it as a descriptor (anything with `__get__` or `__set__`: a native getset, a property, a function) it is not
wrapped and is listed in `skipped` as "inherited TYPE"; an inherited plain constant becomes the Field's default, so a
read before the first write returns what the class returned. The own-dict test also skips any class-level object
with `__get__` (cnt367.py:379), which changes no installed descriptor in these cells.

It removes seven descriptors on the Rust path, all "inherited getset_descriptor", and adds none (354 -> 347): the
four on `EUFTheory` above and `TransferTheory.enabled`, `.euf`, `.sel` (backend.TransferTheory over
`sa_solver.TransferTheory`; shadowed the same way before the fix, though they moved no dev or fuzz answer: the
transfer.py-only cell and the all-but-four fuzz cell were at the reference). The default path keeps its 274.

Digests after the fix, full instrumentation (every module, hooks on), `plant.failed` empty in all twelve cells:

| cell | dev | fuzz | budget | wiring |
|---|---|---|---|---|
| rust-nat (347 descriptors) | 31cd0945c07f02a6 | 173502b6ef285ad6 | 35bc2c4a937bebc0 | a0df9fd43e5180c1 |
| py-ref (347) | 31cd0945c07f02a6 | 173502b6ef285ad6 | 35bc2c4a937bebc0 | a0df9fd43e5180c1 |
| default (274) | 31cd0945c07f02a6 | 173502b6ef285ad6 | 35bc2c4a937bebc0 | a0df9fd43e5180c1 |
| no instrument, each of the three cells | 31cd0945c07f02a6 | 173502b6ef285ad6 | 35bc2c4a937bebc0 | a0df9fd43e5180c1 |

All equal to the reference.

## Reproduce

```
T=rust-spike/slice/results/tools368; FL=$(cat ~/sa-rust-ids-work/sa-port-368/filelist.txt)
$T/cell368.sh OUT full rust-nat dev $FL                       # after the fix: 31cd0945c07f02a6
git show b832e5f:rust-spike/slice/results/tools367/cnt367.py > old.py
B368_CNT=$PWD/old.py $T/cell368.sh OUT old rust-nat dev $FL   # 87c8bba93cdafb96
echo 'sa/theories/euf/euf.py:EUFTheory.on_merge' > om.txt
B368_CNT=$PWD/old.py B368_ONLY=$PWD/om.txt $T/cell368.sh OUT om rust-nat fuzz $FL    # f8dcab9c4f2137e8
python3 $T/diff368.py OUT/ref.ans OUT/old.ans                 # the moved queries
```

Run output: orion `~/sa-rust-ids-work/sa-port-368/` s0 (reproducibility, references), s1 (stages A, B), s2 (stage C),
s3 (tracebacks, all-but-two), s4 and s6 (fuzz), s5 and s7 (catches, after the fix).

## Limits

- Bisected on dev and fuzz. Budget and wiring were only run full, before (sa-port-367: reference) and after the fix.
- sa-port-367's rust-nat tables used the seven marked files, none of them euf.py, so they are not affected. Its
  default-path cells never had the Rust class under `euf.EUFTheory`.
- The instrument still finds a class by the module attribute, so a replaced class gets descriptors for the names the
  replaced definition stores. After the fix these are either inert (the name is not defined on the replacement) or
  skipped (it is inherited as a descriptor). A replacement that defines such a name in its own dict as a descriptor was
  already skipped ("class-level TYPE").
