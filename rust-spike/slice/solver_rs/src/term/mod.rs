//! The term table of one top-level query: `TERMS-INTERFACE.md`, and section 9 of `PORT-INVENTORY.md`.
//! No statics and nothing kept across queries: a table lives for one query and its ids mean nothing outside it.

/// A term of one query's table. Equal ids exactly when SymPy's hash and `==` agree.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
#[repr(transparent)]
pub struct TermId(pub u32);

/// A row of the class table: a distinct class under `==`, not `is`.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
#[repr(transparent)]
pub struct ClassId(pub u32);

/// A row of the predicate table.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
#[repr(transparent)]
pub struct PredId(pub u32);

impl TermId {
    #[inline]
    pub fn index(self) -> usize {
        self.0 as usize
    }
}

impl ClassId {
    #[inline]
    pub fn index(self) -> usize {
        self.0 as usize
    }
}

pub mod algebra;
pub mod knowledge;
pub mod offline;
pub mod py;
pub mod rat;
pub mod relations;
pub mod table;
