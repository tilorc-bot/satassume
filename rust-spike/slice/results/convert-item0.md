# convert.py's `_Walk`: where its time goes, before the port (sa-port-300, item 0, issue 323)

Measure only. Start SHA 899d354 (rust-slice). Samples: sa-port-295's S1 pysampler runs of tested tree 1d22f9a
(pareto1, bench-container, 3 dev + 6 fuzz runs; `~/sa-rust-ids-work/sa-port-295/gd/run-1d22f9a`). convert.py and
term_live.py are byte-identical between 1d22f9a and 899d354 (`git diff --stat 1d22f9a 899d354`: session_live.py,
session_glue.rs and three tests only), so no new run was taken. Tool: `tools300/split300.py` (dec143 merge, as
prof292.py), table by `tools300/tab300.py`.

Method: for each in-loop sample with a convert.py frame on the Python stack, take the innermost convert.py frame F and
class the sample by what runs below it: F's own **bytecode** (leaf is the eval loop); **C** called straight from F's
bytecode with no Python frame between (isinstance, getattr on a class, dict/list/tuple/int work; libpython's symbol
names resolve to the nearest exported symbol, so they aren't listed by name); a **Python callee** (keyed by the first
frame inside F: SymPy's and satassume's functions); **rust** (TEMPLATES_FOR -> Dispatch.templates_for). "Root" is who
asked: `convert.convert` (the per-query conversion) or `_Walk.read` (a lazy read Rust asks for during the run).

## The split

N = in-loop samples (dev 2,498; fuzz 46,540). Shares of N.

| root / part | dev samples | dev % of N | fuzz samples | fuzz % of N |
|---|---|---|---|---|
| **conversion (`convert.convert`)** | 985 | 39.4 | 7,604 | 16.3 |
| walk's own logic: bytecode of the ported methods (enc, klass, term_row, walk, enc_int, s, term) | 208 | 8.3 | 1,411 | 3.0 |
| walk's own logic: `isinstance(v, numbers.Integral)` in enc (ABCMeta.__instancecheck__, a Python frame per value) | 56 | 2.2 | 373 | 0.8 |
| C straight from the ported methods (class attribute reads, isinstance, dict/list/tuple/int) | 377 | 15.1 | 2,831 | 6.1 |
| SymPy/satassume Python the ported methods call (stays: the input is SymPy) | 168 | 6.7 | 1,945 | 4.2 |
| Rust under klass (templates_for) | 19 | 0.8 | 103 | 0.2 |
| not ported (convert, formula, default_engine_settings, _structural_class, _template_name, power_rows) | 157 | 6.3 | 941 | 2.0 |
| **lazy reads (`_Walk.read`)** | 39 | 1.6 | 1,929 | 4.1 |
| bytecode of enc/enc_int/s under read | 13 | 0.5 | 495 | 1.1 |
| `isinstance(v, numbers.Integral)` under read | 2 | 0.1 | 400 | 0.9 |
| C straight from enc/enc_int/s under read | 7 | 0.3 | 571 | 1.2 |
| not ported under read (default_sort_key, const_value, read's own frame) | 17 | 0.7 | 463 | 1.0 |

The conversion alone, as shares of its own 985 / 7,604 samples: bytecode 25.8% / 21.6%, C straight from convert.py
43.7% / 42.6%, Python callees 27.2% / 33.4%, Rust 3.4% / 2.5%.

The Python callees of the ported methods, the SymPy calls the gate's count rule keeps (samples dev / fuzz):
Basic.atoms 35 / 447, constructed_noncommutative 38 / 444, cacheit wrapper (`has`) 31 / 347, Basic.free_symbols
13 / 224, _may_be_nan 15 / 177, Expr.is_number 8 / 85, Basic.__hash__ 7 / 79, Basic.args - / 46. All under term_row
except __hash__ and args (walk). Per method, conversion root (samples; bytecode / C / Python callee / rust):

| method | dev | fuzz |
|---|---|---|
| klass (+ its genexpr) | 330: 94 / 213 / 4 / 19 | 2,080: 519 / 1,439 / 20 / 102 |
| term_row | 215: 23 / 43 / 149 / 0 | 2,487: 198 / 492 / 1,796 / 1 |
| enc | 175: 54 / 65 / 56 / 0 | 1,219: 425 / 421 / 373 / 0 |
| walk | 56: 14 / 29 / 13 / 0 | 528: 127 / 290 / 111 / 0 |
| enc_int | 22: 10 / 12 / 0 / 0 | 125: 46 / 79 / 0 / 0 |
| s | 20: 10 / 10 / 0 / 0 | 140: 61 / 79 / 0 / 0 |

## The gain the port can expect

- Goes for certain: the ported methods' bytecode and the ABC check's Python frame, both roots: dev 279 samples
  = 11.2% of N, fuzz 2,679 = 5.8% of N.
- Stays: the SymPy/satassume Python the methods call (dev 6.7%, fuzz 4.2% of N), the parts of convert.py not in
  items 1-5 (dev 7.0%, fuzz 3.0%), and whatever of the "C straight from convert.py" part is the work itself (40
  class attribute reads per class row, the `ids` dict, isinstance against Basic): Rust makes the same C API calls.
- Uncertain: the rest of that C part (dev 15.4%, fuzz 7.3% of N, both roots) is interpreter overhead around those
  calls (argument tuples, `out += (...)`, int boxing), which a native walker sheds in part. Taken as nothing to
  half of it.

Expected, on 295's medians for 1d22f9a (dev 0.760 s, fuzz 6.420 s; pareto1, so only the shares carry to pareto0):
**dev 11% to 19% of loop time (about 0.085 to 0.145 s), fuzz 6% to 9% (about 0.37 to 0.60 s)**, less what the pyo3
calls add. klass is the largest single piece on dev (13% of N) and is mostly class attribute reads, which stay, so
dev is likelier near the low end. Wall time includes what isn't in the loop, so the wall share is a little smaller.
