# Term handles and the conversion interface (component 0, issue 323)

For ports that hold terms before component 0 lands everywhere. Section 9 of `PORT-INVENTORY.md` is the format; this is
the part another component codes against. Stable from this commit: additions only, and any change gets a note here.

**Built so far:** the handle types, `convert.py`, `TermTable`'s reads (`row`, `class_of`, `find`, `compare`, `key_cmp`), the algebra (`neg`, `sub`, `add`, `mul`, `coeff_add`, `coeff_mul`, `raw_add`, `raw_mul`, `number`) and `sort_key` of derived terms (`solver_rs/src/term/algebra.rs`). All of it runs beside the real engine under a shadow that checks it against Python on dev, fuzz and corpus, with memos cleared per query. **Nothing consumes it yet: the shadow decides nothing,** so no answer comes from this code. The first consumer has to meet section 9's limit on discarded runs in `PORT-INVENTORY.md`, and recount `engine.py:1906` with conversion raising there.

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
c.objects                              # [SymPy term by id], for R9, error text and reads
```

Conversion runs on an answer-memo miss (`sympy_api._ask`), once per top-level query, and holds no state across queries.

**Changed 7 Nov (lazy reads):** conversion no longer computes a sort key, `is_finite`, `complex()`, `decompose_power` or
`is_commutative`. `c.tables` has a new required entry `reads`, the walk's `read(kind, id)`, and the rows no longer carry
those values. If you read them from a row's stream, use the methods below. Additive classes and `Kept` reasons in
`convert.py` are unaffected.

`read` returns `(tokens, strings)`, or `None` if the read raised an `Exception`; a `BaseException` goes up through Rust as
itself. `c.counts` holds `read:key`, `read:finite`, `read:complex`, `read:power`, `read:commutative`, `read:symbol`, `read:constant`, `read_raised` and
`read_term_missing`. `symbol` and `constant` are what `atoms.py`'s two templates read, asked for when the template visits the term.

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
table.sort_key(t);      // default_sort_key, in a form that compares the same. Reads an input term's key when it's first needed
table.finite_of(t);     // Result<Option<bool>, Refuse>: is_finite of a closed input term, read when first needed
table.complex_of(t);    // Result<Option<(f64, f64)>, Refuse>: complex() of one, read when first needed
table.power_of(t);      // Result<Option<(Option<TermId>, BigInt)>, Refuse>: decompose_power's split, read when first needed
table.commutative_of(t);// Result<bool, Refuse>: is_commutative is True, read when first needed
table.peek(kind, t);    // what's been read so far, forcing nothing. peek_closed and peek_power the same
table.reads_held();     // how many reads this table's memo holds
```

These can run Python, and can take as long as Python takes: `complex()` of a `CRootOf` can take minutes. Ask only when the
run needs the value, at the point Python's run would. Don't read ahead, cache across tables, or hold a lock across one.

- **Memo.** Each read happens at most once per table and dies with the table. A miss isn't memoized, since it's an `Err`
  that discards the run.
- **A lazy key can't add a term.** Ids are fixed when the table is built, so a key holding a term with no row refuses with
  `read_term_missing`. `term_row` adds one such row: `-oo` when it reaches `nan`, whose key holds it. Don't add a second
  line like it without telling the planner.
- **Python's side:** `TermTable.row(i)` shows `key`, `closed` and `power` as read so far, `None` if not, and forces
  nothing. `sort_key`, `finite`, `complex`, `power` and `commutative` read. `reads_held` counts the memo.

`Refuse` carries a reason. It means this query goes back to Python and nothing in Rust is kept, so it propagates to the
top of the run; never catch it to carry on. Reads refuse too: a read that raised, or a key with no row. The handlers at
`engine.py:1906` and `sympy_api.py:1107` catch `Exception`, and so catch the Python `TermRefuse`: the first consumer has to
get it past them.
