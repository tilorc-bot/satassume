//! The hooks the solver calls, in the shape of `satassume.sat.theory`. The solver is generic over this trait and
//! knows nothing of Python: `lib.rs` implements it over a Python object, and a later step can add a Rust theory.
//!
//! A hook that fails doesn't return an error: it unwinds, with `resume_unwind`, up to the public entry that called
//! the solver. That leaves the solver's state exactly where a Python exception raised at that call would leave it.

/// What `check` said. `Nothing` is a theory that returned None; its entry in `theory_models` is None.
pub enum Check<M> {
    Nothing,
    Model(M),
    Conflict(Vec<u32>),
}

/// Literals cross as external ints cast to u32, as everywhere in `solver.rs`.
pub trait Theory {
    /// Opaque to the solver; handed to `register_atom` and not kept.
    type Payload;
    /// Opaque to the solver; kept for `theory_models` and in the model ring.
    type Model: Clone;
    /// One `(literal, reason clause)` per implication, read lazily: if a theory hands over a generator, a conflict
    /// on one pair means the later pairs are never asked for, as in Python's `for x, why in prop()`.
    type Props: Iterator<Item = (i32, Vec<u32>)>;

    fn register_atom(&mut self, var: i32, payload: Self::Payload);
    /// None, or the conflict clause.
    fn assert_lit(&mut self, x: i32) -> Option<Vec<u32>>;
    fn check(&mut self) -> Check<Self::Model>;
    fn push_level(&mut self);
    fn pop_level(&mut self);
    /// Whether the theory has the optional `propagate`; read once, at attach, like Python's bound method.
    fn has_propagate(&self) -> bool;
    fn propagate(&mut self) -> Self::Props;
    /// Whether the theory has the optional `decide`; read once, at attach.
    fn has_decide(&self) -> bool;
    /// None, or the variable the theory wants decided, not yet checked.
    fn decide(&mut self) -> Option<i64>;
}
