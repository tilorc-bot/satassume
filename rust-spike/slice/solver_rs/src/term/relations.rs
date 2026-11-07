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
    pub fn is_number_term(&self, t: TermId) -> Result<bool, Refuse> {
        let r = self.facts(t)?;
        Ok(r.bits & fact::NUMBER != 0 && r.free.is_empty())
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
        let (l, r) = if self.is_number_term(lhs)? || self.is_number_term(rhs)? {
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
            if self.is_number_term(t)? && self.closed_finite(t)? == Some(true) {
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
        if self.is_number_term(d)? || !self.termwise(p, q, d)? {
            return Ok(None);
        }
        Ok(Some(d))
    }
}

/// One step of a clause plan (slice C): Python runs these left to right on its `Session`, so var numbering holds.
#[derive(Clone, Debug)]
pub enum PlanOp {
    /// `s.ensure(term, {preds})`.
    Ensure(TermId, Vec<&'static str>),
    /// `s.emit([lits] + [g])`. A literal is (negated, pred and term), or (negated, None) for the atom's own var.
    Clause(Vec<(bool, Option<(&'static str, TermId)>)>),
}

/// What `relation_atom` does for an order relation, by position in `(lhs, rhs)`, so Python keeps the objects it was given.
#[derive(Clone, Debug, PartialEq)]
pub struct OrderAtom {
    pub first: usize,
    pub second: usize,
    pub negated: bool,
    pub ext: Vec<usize>,
}

impl TermTable {
    /// `_ext_atoms`' test: not a Rational, `oo` or `-oo`.
    pub fn needs_ext(&self, t: TermId) -> bool {
        let c = self.class_of(t);
        !(c.flags & flag::IS_RATIONAL != 0 || c.kind == Kind::Infinity || c.kind == Kind::NegativeInfinity)
    }

    /// `relation_atom`'s lt, gt, le and ge. None is le or ge with a nan side, which Python answers False.
    pub fn order_relation(&self, name: &str, l: TermId, r: TermId) -> Result<Option<OrderAtom>, Refuse> {
        let sides = [l, r];
        Ok(Some(match name {
            "lt" => OrderAtom { first: 0, second: 1, negated: false, ext: vec![] },
            "gt" => OrderAtom { first: 1, second: 0, negated: false, ext: vec![] },
            "le" | "ge" => {
                let (a, b) = if name == "le" { (0, 1) } else { (1, 0) };
                if self.class_of(sides[a]).kind == Kind::NaN || self.class_of(sides[b]).kind == Kind::NaN {
                    return Ok(None);
                }
                let ext = [a, b].into_iter().filter(|&p| self.needs_ext(sides[p])).collect();
                OrderAtom { first: b, second: a, negated: true, ext }
            }
            _ => return Err(Refuse("relation_atom: an unknown relation")),
        }))
    }

    /// `Relations._eq_links`' clauses, in its order. Empty for a side that is a number.
    pub fn eq_links_plan(&mut self, a: TermId, b: TermId) -> Result<Vec<PlanOp>, Refuse> {
        if self.is_number_term(a)? || self.is_number_term(b)? {
            return Ok(vec![]);
        }
        const INF: [&str; 2] = ["positive_infinite", "negative_infinite"];
        let mut plan = vec![PlanOp::Ensure(a, INF.to_vec()), PlanOp::Ensure(b, INF.to_vec())];
        for pred in INF {
            plan.push(PlanOp::Clause(vec![(true, Some((pred, a))), (true, Some((pred, b))), (false, None)]));
        }
        for (p, q) in [(a, b), (b, a)] {
            if let Some(d) = self.eq_diff(p, q)? {
                plan.push(PlanOp::Ensure(d, vec!["zero", "nonzero"]));
                plan.push(PlanOp::Clause(vec![(true, Some(("zero", d))), (false, None)]));
                plan.push(PlanOp::Clause(vec![(true, Some(("nonzero", d))), (true, None)]));
            }
        }
        Ok(plan)
    }

    /// `Relations._eq_infinity`: the other side, the pred, whether that side is a number (Python then asks `engine.is_`,
    /// and only an unknown goes on to the plan), and the plan. None when neither side is infinite.
    pub fn eq_infinity_plan(&self, a: TermId, b: TermId) -> Result<Option<(TermId, &'static str, bool, Vec<PlanOp>)>, Refuse> {
        for (kind, pred) in [(Kind::Infinity, "positive_infinite"), (Kind::NegativeInfinity, "negative_infinite")] {
            let e = if self.class_of(b).kind == kind {
                a
            } else if self.class_of(a).kind == kind {
                b
            } else {
                continue;
            };
            let plan = vec![
                PlanOp::Ensure(e, vec![pred]),
                PlanOp::Clause(vec![(true, None), (false, Some((pred, e)))]),
                PlanOp::Clause(vec![(false, None), (true, Some((pred, e)))]),
            ];
            return Ok(Some((e, pred, self.is_number_term(e)?, plan)));
        }
        Ok(None)
    }

    /// `scope.affine_pair`, given the argument of each sign atom in order.
    pub fn affine_pair(&self, signs: &[TermId]) -> Result<bool, Refuse> {
        let mut sums: Vec<TermId> = vec![];
        for &e in signs {
            if self.class_of(e).flags & flag::IS_ADD == 0 || sums.contains(&e) {
                continue;
            }
            let free = &self.facts(e)?.free;
            if free.is_empty() {
                continue;
            }
            for &o in &sums {
                if self.facts(o)?.free.iter().any(|x| free.contains(x)) {
                    return Ok(true);
                }
            }
            sums.push(e);
        }
        Ok(false)
    }

    /// `_under_apps` of the sides: every term at or under an argument of an `AppliedUndef`. None when a side's class has its
    /// own `atoms`, which Python keeps. A set on Python's side, whose consumers only test membership.
    pub fn under_apps(&self, sides: &[TermId]) -> Option<Vec<TermId>> {
        let mut out = vec![];
        let mut seen = std::collections::HashSet::new();
        for &side in sides {
            if self.class_of(side).flags & flag::PLAIN_ATOMS == 0 {
                return None;
            }
            let mut stack = vec![side];
            let mut visited = std::collections::HashSet::new();
            while let Some(t) = stack.pop() {
                if !visited.insert(t) {
                    continue;
                }
                let args = &self.row(t).args;
                if self.class_of(t).kind == Kind::AppliedUndef {
                    for &arg in args.iter() {
                        let mut under = vec![arg];
                        while let Some(u) = under.pop() {
                            if seen.insert(u) {
                                out.push(u);
                                under.extend(self.row(u).args.iter().copied());
                            }
                        }
                    }
                }
                stack.extend(args.iter().copied());
            }
        }
        Some(out)
    }

    /// `euf_adapter.structural`: the class's bit, and it has args.
    pub fn structural(&self, t: TermId) -> bool {
        !self.row(t).args.is_empty() && self.class_of(t).structural
    }

    /// `EUFAdapter.interned`, with its stack order.
    pub fn interned(&self, exprs: &[TermId]) -> Vec<TermId> {
        let mut out = vec![];
        let mut seen = std::collections::HashSet::new();
        let mut stack = exprs.to_vec();
        while let Some(e) = stack.pop() {
            if !seen.insert(e) {
                continue;
            }
            out.push(e);
            if self.class_of(e).flags & flag::IS_RATIONAL == 0 && self.structural(e) {
                stack.extend(self.row(e).args.iter().copied());
            }
        }
        out
    }

    /// `relations._structural_subterms`, with its stack order.
    pub fn structural_subterms(&self, e: TermId) -> Vec<TermId> {
        let mut out = vec![];
        let mut seen = std::collections::HashSet::new();
        let mut stack: Vec<TermId> = if self.structural(e) { self.row(e).args.to_vec() } else { vec![] };
        while let Some(x) = stack.pop() {
            if seen.contains(&x) || self.class_of(x).flags & flag::IS_RATIONAL != 0 || !self.structural(x) {
                continue;
            }
            seen.insert(x);
            out.push(x);
            stack.extend(self.row(x).args.iter().copied());
        }
        out
    }
}
