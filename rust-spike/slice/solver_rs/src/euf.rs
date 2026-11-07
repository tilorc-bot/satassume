//! `satassume/theories/euf/euf.py`: incremental congruence closure with explanations and trail undo. A line-for-line
//! port, in the same order, because term ids, class order and explanations reach the solver's state. Python stays the
//! reference; `euf.py` has the algorithm's explanation.
//!
//! No Python in this file. Two things differ in shape from `euf.py`, and neither changes what runs:
//! - Heads and value keys are `Handle`s. `euf_py.rs` hands them out; component 0's term table replaces it.
//! - `union` returns the merge in place of calling `on_merge`, and whatever drains `pending` calls the listener after
//!   each step. `union` has nothing left to do at that point in Python either, so a listener sees the same state, and
//!   nothing here is borrowed while it runs.
//!
//! The maps are only ever looked up, never iterated, so their hash order can't reach anything. All state is per object.
use crate::map::Map;

pub type Term = u32;
/// Nothing in the proof forest, `-1` in Python.
const NIL: Term = u32::MAX;

/// An opaque head or value key: equal objects, equal handle. Minimal on purpose, until component 0's handle lands
/// (sa-port-5, port/D0): this type and `euf_py::Handles` are all that swap.
#[derive(Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Debug)]
pub struct Handle(pub u32);

/// `_keys`: Python's `("c", head)`, `("h", head, n)`, `("v", key)`, `("a", f, a)`.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Key {
    Const(Handle),
    Head(Handle, u32),
    Value(Handle),
    App(Term, Term),
}

/// The label of a proof-forest edge: the asserted literal, or the pair of congruent applications.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Label {
    None,
    Lit(i32),
    Pair(Term, Term),
}

#[derive(Clone, Copy, Debug)]
pub struct Diseq {
    pub lit: i32,
    pub s: Term,
    pub t: Term,
}

#[derive(Clone, Copy, Debug)]
pub struct Atom {
    pub s: Term,
    pub t: Term,
    pub pos: bool,
}

/// The trail; `_UNION`, `_LOOKUP`, ... in Python.
#[derive(Clone, Copy, Debug)]
pub enum Op {
    Union { ra: Term, rb: Term, a: Term, old_root: Term, nuse: usize, ndiseq: usize, natoms: usize, set_val: bool },
    Lookup(Term, Term),
    Assign(i32),
    Diseq { rs: Term, ns: usize, rt: Term, nt: usize },
    RegApp(Term),
    RegAtom { v: i32, rs: Term, rt: Term },
    Use(Term),
}

/// What Python's `pop_level` raises: IndexError, or KeyError on the `del` of a trail entry with nothing behind it.
#[derive(Debug)]
pub enum PopError {
    NoLevel,
    NoAssign(i32),
    NoLookup(Term, Term),
}

/// How `assert_lit` goes on after its first part.
pub enum Asserted {
    /// Not an atom of this theory: Python returns None, whatever the conflict state.
    NotAtom,
    /// Nothing queued: the answer is `conflict`.
    Done,
    /// A merge is queued: drain `pending`, then the answer is `conflict`.
    Merge,
}

#[derive(Default)]
pub struct Euf {
    pub keys: Map<Key, Term>,
    pub app: Vec<Option<(Term, Term)>>,
    pub rep: Vec<Term>,
    pub members: Vec<Vec<Term>>,
    pub uses: Vec<Vec<Term>>,
    pub lookup: Map<(Term, Term), Term>,
    pub pfp: Vec<Term>,
    pub pfl: Vec<Label>,
    /// rep -> value term of the class, or -1
    pub val: Vec<i64>,
    pub diseq: Vec<Vec<Diseq>>,
    pub atoms_of: Vec<Vec<i32>>,
    pub atoms: Map<i32, Atom>,
    pub assigned: Map<i32, i32>,
    pub pending: Vec<(Term, Term, Label)>,
    pub propq: Vec<i32>,
    /// The clause, sorted; Python's `(False, clause)` until popped.
    pub conflict: Option<Vec<i32>>,
    pub trail: Vec<Op>,
    pub lims: Vec<usize>,
}

fn negated_sorted(mut lits: Vec<i32>) -> Vec<i32> {
    for l in &mut lits {
        *l = -*l;
    }
    lits.sort_unstable();
    lits.dedup();
    lits
}

impl Euf {
    pub fn new() -> Euf {
        Euf::default()
    }

    pub fn len(&self) -> usize {
        self.rep.len()
    }

    // Terms

    fn new_term(&mut self, key: Key, app: Option<(Term, Term)>, value: bool) -> Term {
        let t = self.rep.len() as Term;
        self.keys.insert(key, t);
        self.app.push(app);
        self.rep.push(t);
        self.members.push(vec![t]);
        self.uses.push(Vec::new());
        self.pfp.push(NIL);
        self.pfl.push(Label::None);
        self.val.push(if value { t as i64 } else { -1 });
        self.diseq.push(Vec::new());
        self.atoms_of.push(Vec::new());
        t
    }

    fn intern(&mut self, key: Key, value: bool) -> Term {
        match self.keys.get(&key) {
            Some(&t) => t,
            None => self.new_term(key, None, value),
        }
    }

    /// `term(head)` with no arguments.
    pub fn constant(&mut self, head: Handle) -> Term {
        self.intern(Key::Const(head), false)
    }

    /// The head constant of `term(head, args)`, keyed by arity. `apply` then curries the arguments onto it.
    pub fn head(&mut self, head: Handle, arity: u32) -> Term {
        self.intern(Key::Head(head, arity), false)
    }

    pub fn value(&mut self, key: Handle) -> Term {
        self.intern(Key::Value(key), true)
    }

    /// `_apply` up to its `_process`: the application, and whether it's new, when the caller drains `pending`.
    pub fn apply(&mut self, f: Term, a: Term) -> (Term, bool) {
        let key = Key::App(f, a);
        if let Some(&t) = self.keys.get(&key) {
            return (t, false);
        }
        let t = self.new_term(key, Some((f, a)), false);
        self.index_app(t);
        (t, true)
    }

    fn index_app(&mut self, t: Term) {
        let on = !self.lims.is_empty();
        if on {
            self.trail.push(Op::RegApp(t));
        }
        let (f, a) = self.app[t as usize].expect("an application");
        let (rf, ra) = (self.rep[f as usize], self.rep[a as usize]);
        match self.lookup.get(&(rf, ra)) {
            None => {
                self.lookup.insert((rf, ra), t);
                self.uses[rf as usize].push(t);
                if on {
                    self.trail.push(Op::Lookup(rf, ra));
                    self.trail.push(Op::Use(rf));
                }
                if ra != rf {
                    self.uses[ra as usize].push(t);
                    if on {
                        self.trail.push(Op::Use(ra));
                    }
                }
            }
            Some(&o) => {
                if self.rep[o as usize] != self.rep[t as usize] {
                    self.pending.push((t, o, Label::Pair(t, o)));
                }
            }
        }
    }

    // Queries

    /// The asserted literals behind `a == b`, sorted. The caller has checked that they're equal.
    pub fn explain(&self, a: Term, b: Term) -> Vec<i32> {
        let mut out = Vec::new();
        self.explain_into(a, b, &mut out);
        out.sort_unstable();
        out.dedup();
        out
    }

    // Union and the proof forest

    fn reroot(&mut self, x: Term) -> Term {
        let (mut prev, mut plab, mut cur) = (NIL, Label::None, x);
        while cur != NIL {
            let c = cur as usize;
            let (nxt, lab) = (self.pfp[c], self.pfl[c]);
            self.pfp[c] = prev;
            self.pfl[c] = plab;
            prev = cur;
            plab = lab;
            cur = nxt;
        }
        prev
    }

    /// One merge. Returns `(retired, new)` where Python calls `on_merge`, or None if they were one class already.
    pub fn union(&mut self, a: Term, b: Term, label: Label) -> Option<(Term, Term)> {
        let (mut a, mut b) = (a, b);
        let (mut ra, mut rb) = (self.rep[a as usize], self.rep[b as usize]);
        if ra == rb {
            return None;
        }
        if self.members[ra as usize].len() > self.members[rb as usize].len() {
            std::mem::swap(&mut a, &mut b);
            std::mem::swap(&mut ra, &mut rb);
        }
        let (ia, ib) = (ra as usize, rb as usize);
        let old_root = self.reroot(a);
        self.pfp[a as usize] = b;
        self.pfl[a as usize] = label;
        let ma = std::mem::take(&mut self.members[ia]);
        for &c in &ma {
            self.rep[c as usize] = rb;
        }
        self.members[ib].extend_from_slice(&ma);
        self.members[ia] = ma; // the undo reads it back
        let set_val = self.val[ib] < 0 && 0 <= self.val[ia];
        let on = !self.lims.is_empty();
        if on {
            self.trail.push(Op::Union {
                ra,
                rb,
                a,
                old_root,
                nuse: self.uses[ib].len(),
                ndiseq: self.diseq[ib].len(),
                natoms: self.atoms_of[ib].len(),
                set_val,
            });
        }
        let mut conflict: Option<Vec<i32>> = None;
        if set_val {
            self.val[ib] = self.val[ia];
        } else if self.val[ia] >= 0 {
            // two distinct values in one class
            let mut out = Vec::new();
            self.explain_into(self.val[ia] as Term, self.val[ib] as Term, &mut out);
            conflict = Some(out);
        }
        // congruence: rekey the applications that used the smaller class
        let used = std::mem::take(&mut self.uses[ia]);
        for &t in &used {
            let (f, x) = self.app[t as usize].expect("an application");
            let key = (self.rep[f as usize], self.rep[x as usize]);
            match self.lookup.get(&key) {
                None => {
                    self.lookup.insert(key, t);
                    self.uses[ib].push(t);
                    if on {
                        self.trail.push(Op::Lookup(key.0, key.1));
                    }
                }
                Some(&o) => {
                    if self.rep[o as usize] != self.rep[t as usize] {
                        self.pending.push((t, o, Label::Pair(t, o)));
                    }
                }
            }
        }
        self.uses[ia] = used;
        // disequalities between the two classes are now violated
        if !self.diseq[ia].is_empty() {
            let dl = std::mem::take(&mut self.diseq[ia]);
            if conflict.is_none() {
                for d in &dl {
                    if self.rep[d.s as usize] == self.rep[d.t as usize] {
                        let mut out = vec![d.lit];
                        self.explain_into(d.s, d.t, &mut out);
                        conflict = Some(out);
                        break;
                    }
                }
            }
            self.diseq[ib].extend_from_slice(&dl);
            self.diseq[ia] = dl;
        }
        // atoms whose sides just became equal
        if !self.atoms_of[ia].is_empty() {
            let al = std::mem::take(&mut self.atoms_of[ia]);
            for &v in &al {
                if !self.assigned.contains_key(&v) {
                    let at = self.atoms[&v];
                    if self.rep[at.s as usize] == self.rep[at.t as usize] {
                        self.propq.push(v);
                    }
                }
            }
            self.atoms_of[ib].extend_from_slice(&al);
            self.atoms_of[ia] = al;
        }
        if let Some(c) = conflict {
            self.conflict = Some(negated_sorted(c));
        }
        Some((ra, rb))
    }

    fn undo_union(&mut self, op: Op) {
        let Op::Union { ra, rb, a, old_root, nuse, ndiseq, natoms, set_val } = op else {
            unreachable!()
        };
        let (ia, ib) = (ra as usize, rb as usize);
        self.pfp[a as usize] = NIL;
        self.pfl[a as usize] = Label::None;
        self.reroot(old_root);
        let keep = self.members[ib].len() - self.members[ia].len();
        self.members[ib].truncate(keep);
        for k in 0..self.members[ia].len() {
            let c = self.members[ia][k];
            self.rep[c as usize] = ra;
        }
        self.uses[ib].truncate(nuse);
        self.diseq[ib].truncate(ndiseq);
        self.atoms_of[ib].truncate(natoms);
        if set_val {
            self.val[ib] = -1;
        }
    }

    fn explain_edge(&self, cur: Term, out: &mut Vec<i32>, todo: &mut Vec<(Term, Term)>, aux: &mut Map<Term, Term>) -> Term {
        let p = self.pfp[cur as usize];
        match self.pfl[cur as usize] {
            Label::Lit(l) => out.push(l),
            Label::Pair(t1, t2) => {
                let (f1, a1) = self.app[t1 as usize].expect("an application");
                let (f2, a2) = self.app[t2 as usize].expect("an application");
                if f1 != f2 {
                    todo.push((f1, f2));
                }
                if a1 != a2 {
                    todo.push((a1, a2));
                }
            }
            Label::None => unreachable!("an edge with no label"),
        }
        aux.insert(cur, p);
        high(aux, p)
    }

    /// `_explain`: adds to `out` the asserted literals behind `a == b`. `out` may repeat one; the readers dedup, as
    /// Python's set does.
    fn explain_into(&self, a: Term, b: Term, out: &mut Vec<i32>) {
        let mut aux: Map<Term, Term> = Map::default();
        let mut todo = vec![(a, b)];
        while let Some((x, y)) = todo.pop() {
            if x == y {
                continue;
            }
            // x's path to the root (node -> distance from x), then y's path up to the first node on x's path
            let mut px: Map<Term, usize> = Map::default();
            let (mut c, mut i) = (x, 0);
            while c != NIL {
                px.insert(c, i);
                c = self.pfp[c as usize];
                i += 1;
            }
            let mut py: Map<Term, ()> = Map::default();
            c = y;
            while !px.contains_key(&c) {
                py.insert(c, ());
                c = self.pfp[c as usize];
            }
            let top = px[&c];
            // explain the edges below the ancestor on both paths; high skips chains of edges explained already
            let mut cur = high(&mut aux, x);
            while px[&cur] < top {
                cur = self.explain_edge(cur, out, &mut todo, &mut aux);
            }
            cur = high(&mut aux, y);
            while py.contains_key(&cur) {
                cur = self.explain_edge(cur, out, &mut todo, &mut aux);
            }
        }
    }

    // Theory protocol

    /// `register_atom` past its checks of the arguments, which need Python's types: `euf_py.rs` makes them.
    pub fn register_atom(&mut self, v: i32, s: Term, t: Term, pos: bool) {
        self.atoms.insert(v, Atom { s, t, pos });
        self.index_atom(v);
    }

    fn index_atom(&mut self, v: i32) {
        let at = self.atoms[&v];
        let (rs, rt) = (self.rep[at.s as usize], self.rep[at.t as usize]);
        if !self.lims.is_empty() {
            self.trail.push(Op::RegAtom { v, rs, rt });
        }
        self.atoms_of[rs as usize].push(v);
        if rt != rs {
            self.atoms_of[rt as usize].push(v);
        } else if !self.assigned.contains_key(&v) {
            self.propq.push(v);
        }
    }

    /// `assert_lit` up to its `_process`.
    pub fn assert_begin(&mut self, literal: i32) -> Asserted {
        let Some(v) = literal.checked_abs() else {
            return Asserted::NotAtom;
        };
        let Some(&at) = self.atoms.get(&v) else {
            return Asserted::NotAtom;
        };
        if self.conflict.is_some() {
            return Asserted::Done;
        }
        self.assigned.insert(v, literal);
        let on = !self.lims.is_empty();
        if on {
            self.trail.push(Op::Assign(v));
        }
        if (literal > 0) == at.pos {
            self.pending.push((at.s, at.t, Label::Lit(literal)));
            return Asserted::Merge;
        }
        let (rs, rt) = (self.rep[at.s as usize], self.rep[at.t as usize]);
        if rs == rt {
            let mut out = vec![literal];
            self.explain_into(at.s, at.t, &mut out);
            self.conflict = Some(negated_sorted(out));
        } else {
            if on {
                self.trail.push(Op::Diseq {
                    rs,
                    ns: self.diseq[rs as usize].len(),
                    rt,
                    nt: self.diseq[rt as usize].len(),
                });
            }
            let d = Diseq { lit: literal, s: at.s, t: at.t };
            self.diseq[rs as usize].push(d);
            self.diseq[rt as usize].push(d);
        }
        Asserted::Done
    }

    /// One `(literal, reason)` per registered, unassigned atom whose sides became equal.
    pub fn propagate(&mut self) -> Vec<(i32, Vec<i32>)> {
        if self.propq.is_empty() || self.conflict.is_some() {
            return Vec::new();
        }
        let mut out = Vec::new();
        let mut seen: Map<i32, ()> = Map::default();
        let q = std::mem::take(&mut self.propq);
        for &v in &q {
            if self.assigned.contains_key(&v) || seen.contains_key(&v) {
                continue;
            }
            let at = self.atoms[&v];
            if self.rep[at.s as usize] != self.rep[at.t as usize] {
                continue;
            }
            seen.insert(v, ());
            let lit = if at.pos { v } else { -v };
            let mut why = Vec::new();
            self.explain_into(at.s, at.t, &mut why);
            let why = negated_sorted(why);
            let mut reason = Vec::with_capacity(why.len() + 1);
            reason.push(lit);
            reason.extend(why);
            out.push((lit, reason));
        }
        // `q.clear()` in Python: the same list, emptied, so its capacity stays and nothing else sees a difference
        let mut q = q;
        q.clear();
        self.propq = q;
        out
    }

    pub fn push_level(&mut self) {
        self.lims.push(self.trail.len());
    }

    /// `pop_level` up to its `_process`: undoes the trail and indexes again the applications made above this level.
    /// The caller drains `pending`, then gives the returned atoms to `pop_end`. An error leaves the state where
    /// Python's exception leaves it.
    pub fn pop_begin(&mut self) -> Result<Vec<i32>, PopError> {
        let lim = self.lims.pop().ok_or(PopError::NoLevel)?;
        let mut redo_apps = Vec::new();
        let mut redo_atoms = Vec::new();
        while self.trail.len() > lim {
            let e = self.trail.pop().expect("above the limit");
            match e {
                Op::Union { .. } => self.undo_union(e),
                Op::Lookup(x, y) => {
                    self.lookup.remove(&(x, y)).ok_or(PopError::NoLookup(x, y))?;
                }
                Op::Use(r) => {
                    self.uses[r as usize].pop();
                }
                Op::Assign(v) => {
                    self.assigned.remove(&v).ok_or(PopError::NoAssign(v))?;
                }
                Op::Diseq { rs, ns, rt, nt } => {
                    self.diseq[rt as usize].truncate(nt);
                    self.diseq[rs as usize].truncate(ns);
                }
                Op::RegApp(t) => redo_apps.push(t),
                Op::RegAtom { v, rs, rt } => {
                    if rt != rs {
                        self.atoms_of[rt as usize].pop();
                    }
                    self.atoms_of[rs as usize].pop();
                    redo_atoms.push(v);
                }
            }
        }
        self.pending.clear();
        self.propq.clear();
        self.conflict = None;
        // terms and atoms made above this level stay; index them again
        for &t in redo_apps.iter().rev() {
            self.index_app(t);
        }
        Ok(redo_atoms)
    }

    pub fn pop_end(&mut self, redo_atoms: Vec<i32>) {
        for &v in redo_atoms.iter().rev() {
            self.index_atom(v);
        }
    }
}

/// The auxiliary union-find of `_explain`: the highest node reached from `x`, with path compression.
fn high(aux: &mut Map<Term, Term>, x: Term) -> Term {
    let mut r = x;
    while let Some(&n) = aux.get(&r) {
        r = n;
    }
    let mut x = x;
    while let Some(&n) = aux.get(&x) {
        aux.insert(x, r);
        x = n;
    }
    r
}
