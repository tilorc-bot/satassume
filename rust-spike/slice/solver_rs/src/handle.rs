//! The minimal term handle of component 3, until component 0 lands: same shape as `crate::term::TermId` in
//! `TERMS-INTERFACE.md` on port/D0 (`repr(transparent)` over u32, a plain int to Python), so swapping is one `pub use`.
//!
//! The ids held here today are not yet that table's. `TransferCore` holds EUF's own term numbers, as Python's theory
//! does, and `SharingCore` holds its instance's own numbers for the objects it is given. Both are per-instance, so
//! they die with the session that owns them; nothing in the crate holds one in process state.

/// Equal handles mean the same term to whoever issued them, and nothing else: the order means nothing.
#[repr(transparent)]
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub struct TermId(pub u32);
