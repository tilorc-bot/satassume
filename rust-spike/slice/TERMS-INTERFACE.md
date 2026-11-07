# Term handles and the conversion interface (component 0, issue 323)

For ports that hold terms before component 0 lands everywhere. Section 9 of `PORT-INVENTORY.md` is the format; this is
the part another component codes against. Stable from this commit: additions only, and any change gets a note here.

## The handle

- **Rust:** `crate::term::TermId`, a `#[repr(transparent)]` newtype over `u32`, `Copy + Eq + Ord + Hash`. `ClassId` is
  the same over `u32`, and `PredId` for predicates.
- **Python:** a plain `int`, the same number. Nothing wraps it.
- **Meaning:** an index into one query's `TermTable`. Two ids are equal exactly when SymPy's hash and `==` agree (R13).
  So an id means nothing outside its table, and **no id may be kept across top-level queries**.
- **Order:** by first sight in one walk: proposition, then assumptions, each preorder over `.args`. Derived terms take
  the next ids, in the order Rust first builds them. Comparing ids is a deterministic order but it is *not*
  `Basic.compare` or `default_sort_key`; use `TermTable::compare` or `TermTable::sort_key` where Python uses those.

## Until a consumer has a table

A component can take terms as opaque `u32`s with the same meaning (equal handle means the same term in this query) and
need nothing else from here. EUF's core needs no more than that: it compares handles and never looks inside them.

## Conversion

```python
import convert                         # rust-spike/slice/convert.py
c = convert.convert(proposition, assumptions, engine)
if isinstance(c, convert.Kept):        # c.reason, one of convert.REASONS: the query runs on Python, counted
    ...
c.tables                               # flat arrays, section 9; give to sa_solver.TermTable(c.tables)
c.ids                                  # {SymPy term: id}, by SymPy's hash and ==. Python's side of the table
c.objects                              # [SymPy term by id], for R9 and error text
```

Conversion runs on an answer-memo miss (`sympy_api._ask`), once per top-level query, and holds no state across queries.

## Rust

```rust
use crate::term::{TermId, ClassId, TermTable, Refuse};
table.kind(t);          // Kind enum: Add, Mul, Pow, Symbol, Integer, ..., Other
table.class(t);         // ClassId; table.class_name(c) is its name
table.args(t);          // &[TermId]
table.facts(t);         // is_number, free symbols, has_* bits, nc level, may_be_nan
table.neg(t);           // Result<TermId, Refuse>: -t, as SymPy builds it
table.sub(a, b);        // a - b
table.add(&[a, b]);     // Add(a, b)
table.mul(&[a, b]);     // Mul(a, b)
table.coeff_add(t);     // (c, rest): as_coeff_Add
table.coeff_mul(t);     // (c, rest): as_coeff_Mul
table.compare(a, b);    // Basic.compare
table.sort_key(t);      // default_sort_key, in a form that compares the same
```

`Refuse` carries a reason. It means this query goes back to Python and nothing in Rust is kept, so it propagates to the
top of the run; never catch it to carry on.
