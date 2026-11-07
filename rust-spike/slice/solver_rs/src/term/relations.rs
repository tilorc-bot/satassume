//! The term work of `satassume/relations.py` on ids (component 4, slice B): `_is_number`, `_affine_strip`, the eq branch
//! of `relation_atom` with `_key`, `_termwise`, and `_eq_links`'s difference. Nothing here decides a clause: it answers
//! which terms the clauses are about. A shape it can't answer exactly refuses, and the query goes back to Python.
use super::rat::Rat;
use super::table::{fact, flag, Kind, Refuse, TermTable, CLASS_ADD, CLASS_MUL};
use super::TermId;
use std::cmp::Ordering;
use std::collections::HashMap;

impl TermTable {
    /// `_is_number`: `is_number` and no free symbols.
    pub fn is_number_term(&self, t: TermId) -> bool {
        let r = self.row(t);
        r.bits & fact::NUMBER != 0 && r.free.is_empty()
    }

    /// The Rational coefficient `as_coeff_Add` or `as_coeff_Mul` reads off `t`, when that split can strip anything: only
    /// an `Add` or `Mul` whose head is Rational has one. A Float or infinite head is no Rational, so it's left alone.
    /// A class that overrides the splits, or that isn't an `Expr` (whose sides `_affine_strip` returns as they are, and
    /// which can't be told apart here), refuses.
    fn rational_head(&self, t: TermId, class: super::ClassId) -> Result<Option<Rat>, Refuse> {
        let c = self.class_of(t);
        match c.kind {
            Kind::Add | Kind::Mul => {
                if self.row(t).class != class {
                    return Ok(None);
                }
                Ok(self.rat(self.row(t).args[0]))
            }
            _ if c.flags & flag::PLAIN_OPS != 0 => Ok(None),
            _ => Err(Refuse("strip: a class that overrides the coefficient splits, or not an Expr")),
        }
    }

    /// `_affine_strip`: the sides without a shared Rational offset and factor, to a fixed point.
    pub fn affine_strip(&mut self, mut l: TermId, mut r: TermId) -> Result<(TermId, TermId), Refuse> {
        loop {
            let (c1, c2) = (self.rational_head(l, CLASS_ADD)?, self.rational_head(r, CLASS_ADD)?);
            if let (Some(a), Some(b)) = (c1, c2) {
                if a == b && !a.is_zero() {
                    l = self.coeff_add(l)?.1;
                    r = self.coeff_add(r)?.1;
                    continue;
                }
            }
            let (k1, k2) = (self.rational_head(l, CLASS_MUL)?, self.rational_head(r, CLASS_MUL)?);
            if let (Some(a), Some(b)) = (k1, k2) {
                if a == b && !a.is_one() && !a.is_zero() {
                    l = self.coeff_mul(l)?.1;
                    r = self.coeff_mul(r)?.1;
                    continue;
                }
            }
            return Ok((l, r));
        }
    }

    /// The two sides of `relation_atom`'s eq atom, in order. nan goes last and is never sorted, since
    /// `default_sort_key` would compare it. Otherwise `sorted((l, r), key=_key)`, which is stable: they swap only when
    /// the key of `r` is below the key of `l`.
    pub fn eq_sides(&mut self, lhs: TermId, rhs: TermId) -> Result<(TermId, TermId), Refuse> {
        let (l, r) = if self.is_number_term(lhs) || self.is_number_term(rhs) {
            (lhs, rhs)
        } else {
            self.affine_strip(lhs, rhs)?
        };
        if self.class_of(l).kind == Kind::NaN {
            return Ok((r, l));
        }
        if self.class_of(r).kind == Kind::NaN {
            return Ok((l, r));
        }
        Ok(if self.key_cmp(r, l)? == Ordering::Less { (r, l) } else { (l, r) })
    }

    /// `t.is_finite` of a closed term. A derived one is a nonzero Rational times a closed input term, and any other shape
    /// refuses (R17).
    fn closed_finite(&self, t: TermId) -> Result<Option<bool>, Refuse> {
        if t.index() < self.n_input {
            return self.finite_of(t);
        }
        let row = self.row(t);
        if row.class == CLASS_MUL && row.args.len() == 2 {
            if let Some(k) = self.rat(row.args[0]) {
                if !k.is_zero() && row.args[1].index() < self.n_input {
                    return self.finite_of(row.args[1]);
                }
            }
        }
        Err(Refuse("termwise: is_finite of a derived closed term that isn't a Rational times an input term"))
    }

    /// `terms` in `_termwise`: `Add.make_args`, without the Numbers and the finite closed terms.
    fn wise_terms(&self, e: TermId) -> Result<Vec<TermId>, Refuse> {
        let args = if self.row(e).class == CLASS_ADD { self.row(e).args.to_vec() } else { vec![e] };
        let mut out = Vec::with_capacity(args.len());
        for t in args {
            if self.class_of(t).flags & flag::IS_NUMBER != 0 {
                continue;
            }
            if self.is_number_term(t) && self.closed_finite(t)? == Some(true) {
                continue;
            }
            out.push(t);
        }
        Ok(out)
    }

    /// `_termwise`: `d` is the terms of `a` and the negated terms of `b`, as multisets of ids.
    pub fn termwise(&mut self, a: TermId, b: TermId, d: TermId) -> Result<bool, Refuse> {
        let mut want: HashMap<TermId, i64> = HashMap::new();
        for t in self.wise_terms(a)? {
            *want.entry(t).or_insert(0) += 1;
        }
        for t in self.wise_terms(b)? {
            let n = self.neg(t)?;
            *want.entry(n).or_insert(0) += 1;
        }
        for t in self.wise_terms(d)? {
            *want.entry(t).or_insert(0) -= 1;
        }
        Ok(want.values().all(|n| *n == 0))
    }

    /// One difference of `_eq_links`: `p - q` when it's no number and SymPy would build it term by term.
    pub fn eq_diff(&mut self, p: TermId, q: TermId) -> Result<Option<TermId>, Refuse> {
        let d = self.sub(p, q)?;
        if self.is_number_term(d) || !self.termwise(p, q, d)? {
            return Ok(None);
        }
        Ok(Some(d))
    }
}
