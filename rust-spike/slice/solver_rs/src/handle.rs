//! The term handle of component 3 is `crate::term::TermId`: `repr(transparent)` over a public u32, a plain int to Python.
//!
//! The ids held here today are not yet that table's. `TransferCore` holds EUF's own term numbers, as Python's theory
//! does, and `SharingCore` holds its instance's own numbers for the objects it is given. Both are per-instance, so
//! they die with the session that owns them; nothing in the crate holds one in process state.

pub use crate::term::TermId;
