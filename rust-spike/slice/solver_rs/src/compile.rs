//! `satassume/knowledge/compile.py` over ids (component 5, step 5a): formulas to integer clauses. No Python here. `Cx` is what
//! the Python file got from its `table`, `emit` and `dv` arguments; `dv` can visit a node, which runs templates by callback,
//! so an implementation holds no borrow across a `Cx` call. Clause and variable order follow the Python line for line, since
//! the session digests compare them.
use std::rc::Rc;

/// `(op, literals)` of `DEF_LITS`: `true` is `'&'`, literals are signed 1-based basis indices.
pub type Def = Rc<(bool, Vec<i32>)>;
pub type R = Rc<F>;

pub enum F {
    True,
    False,
    /// `P(pred, expr)`: a predicate id (below `NPRED`, the basis index) and a node id.
    Atom(u32, u32),
    Not(R),
    And(Vec<R>),
    Or(Vec<R>),
    Implies(R, R),
    Equivalent(Vec<R>),
    Exclusive(Vec<R>),
    Ite(R, R, R),
    /// `_Lit`: an allocated literal.
    Lit(i32),
    /// Not a formula. Python raises `TypeError` when compilation reaches it, after what it emitted before, so it stays in the
    /// tree and raises here at the same point. The number is the shell's index of the object, for the message.
    Bad(u32),
}

#[derive(Clone)]
pub enum Kind {
    Basis(u32),
    Derived(Def),
    Custom,
}

#[derive(Clone, Copy, PartialEq)]
pub enum Need {
    Pos,
    Neg,
    Both,
    PosUnit,
    NegUnit,
}

pub trait Cx {
    type E;
    fn kind(&self, pred: u32) -> Kind;
    fn node_base(&mut self, nid: u32) -> i32;
    /// `table.var`: the variable of a basis or custom atom.
    fn var(&mut self, pred: u32, nid: u32) -> Result<i32, Self::E>;
    fn aux(&mut self) -> i32;
    fn true_var(&mut self) -> &mut Option<i32>;
    fn emit(&mut self, clause: Vec<i32>) -> Result<(), Self::E>;
    /// Whether the Python call passed `dv`.
    fn has_dv(&self) -> bool;
    /// `dv((d, node), need)`; `None` from the `*Unit` needs means expand the atom.
    fn dv(&mut self, d: &Def, nid: u32, need: Need) -> Result<Option<i32>, Self::E>;
    /// `dv(atom, 'basis')`.
    fn dv_basis(&mut self, pred: u32, nid: u32) -> Result<i32, Self::E>;
    /// `lits`, in the order given, put in a set and read back: `_def` sorts that by `abs`, so a tie (`l` and `-l`) keeps the
    /// set's order. Only called on a tie.
    fn set_order(&mut self, lits: &[i32]) -> Result<Vec<i32>, Self::E>;
    /// The `TypeError` of `cannot compile` (`literal` false) or `cannot make a literal from`.
    fn bad(&mut self, i: u32, literal: bool) -> Self::E;
}

fn at(b: i32, l: i32) -> i32 {
    if l > 0 {
        b + l - 1
    } else {
        -(b - l - 1)
    }
}

/// The literals of definition `ls` at the node block `b`.
pub fn block_lits(b: i32, ls: &[i32]) -> Vec<i32> {
    ls.iter().map(|&l| at(b, l)).collect()
}

fn not(f: &R) -> R {
    Rc::new(F::Not(f.clone()))
}

fn lit(l: i32) -> R {
    Rc::new(F::Lit(l))
}

fn basis_formula<C: Cx>(cx: &C, pred: u32, nid: u32) -> R {
    match cx.kind(pred) {
        Kind::Derived(d) => {
            if d.1.is_empty() {
                return Rc::new(if d.0 { F::True } else { F::False });
            }
            let args = d
                .1
                .iter()
                .map(|&l| {
                    let a = Rc::new(F::Atom(l.unsigned_abs() - 1, nid));
                    if l > 0 {
                        a
                    } else {
                        not(&a)
                    }
                })
                .collect();
            Rc::new(if d.0 { F::And(args) } else { F::Or(args) })
        }
        _ => Rc::new(F::Atom(pred, nid)),
    }
}

/// `basis_lits(pred, pos)`, or `None` for a custom predicate, which the Python's caller has already ruled out.
fn basis_lits<C: Cx>(cx: &C, pred: u32, pos: bool) -> Option<(bool, Vec<i32>)> {
    match cx.kind(pred) {
        Kind::Basis(i) => {
            let v = i as i32 + 1;
            Some((true, vec![if pos { v } else { -v }]))
        }
        Kind::Derived(d) => {
            if pos {
                Some((d.0, d.1.clone()))
            } else {
                Some((!d.0, d.1.iter().map(|l| -l).collect()))
            }
        }
        Kind::Custom => None,
    }
}

/// `_def`.
pub fn def_of<C: Cx>(cx: &mut C, f: &F) -> Result<Option<(Def, u32)>, C::E> {
    if let F::Atom(p, n) = f {
        return Ok(match cx.kind(*p) {
            Kind::Derived(d) => Some((d, *n)),
            _ => None,
        });
    }
    let F::And(args) = f else { return Ok(None) };
    let (mut lits, mut node, mut derived): (Vec<i32>, Option<u32>, bool) = (vec![], None, false);
    let mut many = false;
    for a in args {
        let (g, pos): (&F, bool) = match &**a {
            F::Not(x) => (x, false),
            x => (x, true),
        };
        let F::Atom(p, n) = g else { return Ok(None) };
        let Some((op, ls)) = basis_lits(cx, *p, pos) else { return Ok(None) };
        if !op && ls.len() != 1 {
            return Ok(None);
        }
        derived |= matches!(cx.kind(*p), Kind::Derived(_));
        for l in ls {
            if !lits.contains(&l) {
                lits.push(l);
            }
        }
        match node {
            None => node = Some(*n),
            Some(m) if m != *n => many = true,
            _ => {}
        }
    }
    if !derived || many {
        return Ok(None);
    }
    let Some(node) = node else { return Ok(None) };
    if lits.iter().any(|l| lits.contains(&-l)) {
        lits = cx.set_order(&lits)?; // issue 325, held PR 334: this tie is what that PR changes
    }
    lits.sort_by_key(|l| l.abs());
    Ok(Some((Rc::new((true, lits)), node)))
}

/// `compile_formula`.
pub fn compile<C: Cx>(f: &R, cx: &mut C) -> Result<(), C::E> {
    match &**f {
        F::True => Ok(()),
        F::False => cx.emit(vec![]),
        F::Atom(p, n) => {
            if let Kind::Derived(d) = cx.kind(*p) {
                if cx.has_dv() && !d.0 {
                    if let Some(v) = cx.dv(&d, *n, Need::PosUnit)? {
                        return cx.emit(vec![v]);
                    }
                }
                compile(&basis_formula(cx, *p, *n), cx)
            } else {
                let v = if cx.has_dv() { cx.dv_basis(*p, *n)? } else { cx.var(*p, *n)? };
                cx.emit(vec![v])
            }
        }
        F::Not(inner) => compile_not(inner, cx),
        F::And(args) => {
            for a in args {
                compile(a, cx)?;
            }
            Ok(())
        }
        F::Or(args) => {
            for c in or_cnf(args, cx)? {
                cx.emit(c)?;
            }
            Ok(())
        }
        F::Implies(a, b) => {
            if let F::And(xs) = &**a {
                let mut v: Vec<R> = xs.iter().map(not).collect();
                v.push(b.clone());
                compile(&Rc::new(F::Or(v)), cx)
            } else {
                compile(&Rc::new(F::Or(vec![not(a), b.clone()])), cx)
            }
        }
        F::Equivalent(xs) => {
            let args = shared_args(xs, cx)?;
            for i in 0..args.len().saturating_sub(1) {
                compile(&Rc::new(F::Implies(args[i].clone(), args[i + 1].clone())), cx)?;
                compile(&Rc::new(F::Implies(args[i + 1].clone(), args[i].clone())), cx)?;
            }
            Ok(())
        }
        F::Ite(c, a, b) => {
            let c = if plain(c) { c.clone() } else { lit(literal(c, cx)?) };
            compile(&Rc::new(F::Implies(c.clone(), a.clone())), cx)?;
            compile(&Rc::new(F::Or(vec![c, b.clone()])), cx)
        }
        F::Exclusive(xs) => {
            let args = shared_args(xs, cx)?;
            for i in 0..args.len() {
                for j in i + 1..args.len() {
                    compile(&Rc::new(F::Or(vec![not(&args[i]), not(&args[j])])), cx)?;
                }
            }
            Ok(())
        }
        F::Lit(_) => {
            // Python's `compile_formula` has no case for a bare `_Lit`: it raises. The `Equivalent` and `Exclusive` cases only
            // reach one under `Implies` and `Or`, which go through `_literal`.
            Err(cx.bad(u32::MAX, false))
        }
        F::Bad(i) => Err(cx.bad(*i, false)),
    }
}

fn compile_not<C: Cx>(inner: &R, cx: &mut C) -> Result<(), C::E> {
    if let (F::And(_), true) = (&**inner, cx.has_dv()) {
        if let Some((d, n)) = def_of(cx, inner)? {
            if let Some(v) = cx.dv(&d, n, Need::NegUnit)? {
                return cx.emit(vec![-v]);
            }
        }
    }
    match &**inner {
        F::Atom(p, n) => {
            if let Kind::Derived(d) = cx.kind(*p) {
                if cx.has_dv() && d.0 {
                    if let Some(v) = cx.dv(&d, *n, Need::NegUnit)? {
                        return cx.emit(vec![-v]);
                    }
                }
                compile(&not(&basis_formula(cx, *p, *n)), cx)
            } else {
                let v = if cx.has_dv() { cx.dv_basis(*p, *n)? } else { cx.var(*p, *n)? };
                cx.emit(vec![-v])
            }
        }
        F::Not(x) => compile(x, cx),
        F::And(xs) => compile(&Rc::new(F::Or(xs.iter().map(not).collect())), cx),
        F::Or(xs) => {
            for a in xs {
                compile(&not(a), cx)?;
            }
            Ok(())
        }
        F::Implies(a, b) => compile(&Rc::new(F::And(vec![a.clone(), not(b)])), cx),
        F::Ite(c, a, b) => compile(&Rc::new(F::Ite(c.clone(), not(a), not(b))), cx),
        _ => {
            let l = literal(inner, cx)?;
            cx.emit(vec![-l])
        }
    }
}

fn plain(f: &F) -> bool {
    let g = if let F::Not(x) = f { &**x } else { f };
    matches!(g, F::True | F::False | F::Atom(..) | F::Lit(_))
}

fn shared(f: &F) -> bool {
    let g = if let F::Not(x) = f { &**x } else { f };
    matches!(g, F::Equivalent(_) | F::Exclusive(_) | F::Ite(..))
}

fn shared_args<C: Cx>(xs: &[R], cx: &mut C) -> Result<Vec<R>, C::E> {
    let mut out = Vec::with_capacity(xs.len());
    for a in xs {
        out.push(if shared(a) { lit(literal(a, cx)?) } else { a.clone() });
    }
    Ok(out)
}

const MAX_DISTRIBUTE: i128 = 16;
const MAX_EXACT: usize = 8;

struct Part {
    clauses: Vec<Vec<i32>>,
    src: Option<(Def, u32, bool)>,
}

/// `(m, l, part)` of the Python, and its `cost`.
fn cost(info: &[(i128, i128, usize)], skip: Option<usize>, width: i128) -> (i128, i128) {
    let mut n: i128 = 1;
    for (j, (m, _, _)) in info.iter().enumerate() {
        if Some(j) != skip {
            n = n.saturating_mul(*m);
        }
    }
    let mut c = n.saturating_mul(width);
    for (j, (m, l, _)) in info.iter().enumerate() {
        if Some(j) != skip {
            c = c.saturating_add((n / m).saturating_mul(*l));
        }
    }
    (n, c)
}

/// `_or_cnf`. An empty result: `f` holds.
fn or_cnf<C: Cx>(args: &[R], cx: &mut C) -> Result<Vec<Vec<i32>>, C::E> {
    let mut clause: Vec<i32> = vec![];
    let mut parts: Vec<Part> = vec![];
    for a0 in args {
        let mut a: &R = a0;
        loop {
            match &**a {
                F::Not(x) => match &**x {
                    F::Not(y) => a = y,
                    _ => break,
                },
                _ => break,
            }
        }
        match &**a {
            F::True => return Ok(vec![]),
            F::False => continue,
            F::Or(xs) => {
                let sub = or_cnf(xs, cx)?;
                if sub.is_empty() {
                    return Ok(vec![]);
                }
                if sub.len() == 1 {
                    clause.extend_from_slice(&sub[0]);
                    continue;
                }
                parts.push(Part { clauses: sub, src: None });
                continue;
            }
            _ => {}
        }
        let (g, neg): (&R, bool) = if let F::Not(x) = &**a { (x, true) } else { (a, false) };
        if let Some((d, node)) = def_of(cx, g)? {
            let b = cx.node_base(node);
            let mut lits = block_lits(b, &d.1);
            let mut op = d.0;
            if neg {
                for l in &mut lits {
                    *l = -*l;
                }
                op = !op;
            }
            if lits.is_empty() {
                if op {
                    return Ok(vec![]);
                }
                continue;
            }
            if !op {
                clause.extend_from_slice(&lits);
            } else {
                parts.push(Part { clauses: lits.iter().map(|&l| vec![l]).collect(), src: Some((d, node, neg)) });
            }
            continue;
        }
        let l = literal(a, cx)?;
        clause.push(l);
    }
    let mut rest: Vec<usize> = (0..parts.len()).collect();
    if !parts.is_empty() {
        let mut info: Vec<(i128, i128, usize)> = parts
            .iter()
            .enumerate()
            .map(|(i, p)| (p.clauses.len() as i128, p.clauses.iter().map(|c| c.len() as i128).sum(), i))
            .collect();
        let mut chosen: Vec<usize> = vec![];
        if info.len() > MAX_EXACT {
            // `heapq.nsmallest` is `sorted(...)[:n]`, stable.
            let mut order: Vec<usize> = (0..info.len()).collect();
            order.sort_by_key(|&i| (info[i].0, info[i].1));
            let keep: Vec<usize> = order[..MAX_EXACT].to_vec();
            chosen = (0..info.len()).filter(|i| !keep.contains(i)).map(|i| info[i].2).collect();
            info = (0..info.len()).filter(|i| keep.contains(i)).map(|i| info[i]).collect();
        }
        while !info.is_empty() {
            let w = clause.len() as i128;
            let (n, best) = cost(&info, None, w + chosen.len() as i128);
            let mut pick: Option<(usize, i128)> = None;
            for (j, (m, l, _)) in info.iter().enumerate() {
                let c = cost(&info, Some(j), w + chosen.len() as i128 + 1).1.saturating_add(*l).saturating_add(*m);
                if (c < best || (n > MAX_DISTRIBUTE && pick.is_none_or(|p| c < p.1))) && pick.is_none_or(|p| c < p.1) {
                    pick = Some((j, c));
                }
            }
            let Some((j, _)) = pick else { break };
            chosen.push(info.remove(j).2);
        }
        for i in chosen {
            let src = if cx.has_dv() { parts[i].src.clone() } else { None };
            if let Some((d, node, neg)) = src {
                let t = cx.dv(&d, node, if neg { Need::Neg } else { Need::Pos })?.expect("only the unit needs answer None");
                clause.push(if neg { -t } else { t });
                continue;
            }
            let t = cx.aux();
            for c in &parts[i].clauses {
                let mut e = Vec::with_capacity(c.len() + 1);
                e.push(-t);
                e.extend_from_slice(c);
                cx.emit(e)?;
            }
            clause.push(t);
        }
        rest = info.iter().map(|x| x.2).collect();
    }
    let mut out = vec![clause];
    for i in rest {
        let mut next = Vec::with_capacity(out.len() * parts[i].clauses.len());
        for c in &out {
            for d in &parts[i].clauses {
                let mut e = c.clone();
                e.extend_from_slice(d);
                next.push(e);
            }
        }
        out = next;
    }
    Ok(out)
}

fn true_lit<C: Cx>(cx: &mut C) -> Result<i32, C::E> {
    if let Some(v) = *cx.true_var() {
        return Ok(v);
    }
    let v = cx.aux();
    *cx.true_var() = Some(v);
    cx.emit(vec![v])?;
    Ok(v)
}

/// `_literal`.
pub fn literal<C: Cx>(f: &R, cx: &mut C) -> Result<i32, C::E> {
    match &**f {
        F::Atom(p, n) => {
            if let Kind::Derived(d) = cx.kind(*p) {
                if cx.has_dv() {
                    return Ok(cx.dv(&d, *n, Need::Both)?.expect("only the unit needs answer None"));
                }
                return literal(&basis_formula(cx, *p, *n), cx);
            }
            if cx.has_dv() {
                cx.dv_basis(*p, *n)
            } else {
                cx.var(*p, *n)
            }
        }
        F::Not(inner) => {
            if let F::Atom(p, n) = &**inner {
                if let Kind::Derived(d) = cx.kind(*p) {
                    if cx.has_dv() {
                        return Ok(-cx.dv(&d, *n, Need::Both)?.expect("only the unit needs answer None"));
                    }
                    return Ok(-literal(&basis_formula(cx, *p, *n), cx)?);
                }
                return Ok(-(if cx.has_dv() { cx.dv_basis(*p, *n)? } else { cx.var(*p, *n)? }));
            }
            Ok(-literal(inner, cx)?)
        }
        F::Implies(a, b) => literal(&Rc::new(F::Or(vec![not(a), b.clone()])), cx),
        F::Equivalent(xs) => {
            let mut lits = Vec::with_capacity(xs.len());
            for a in xs {
                lits.push(lit(literal(a, cx)?));
            }
            if lits.len() < 2 {
                return true_lit(cx);
            }
            // `lits[i - 1]` with `i = 0` is the last one: the cycle closes first.
            let n = lits.len();
            let imp = (0..n).map(|i| Rc::new(F::Implies(lits[(i + n - 1) % n].clone(), lits[i].clone()))).collect();
            literal(&Rc::new(F::And(imp)), cx)
        }
        F::Exclusive(xs) => {
            let mut lits = Vec::with_capacity(xs.len());
            for a in xs {
                lits.push(literal(a, cx)?);
            }
            let mut pairs: Vec<R> = vec![];
            for i in 0..lits.len() {
                for j in i + 1..lits.len() {
                    pairs.push(Rc::new(F::Or(vec![not(&lit(lits[i])), not(&lit(lits[j]))])));
                }
            }
            if pairs.is_empty() {
                true_lit(cx)
            } else {
                literal(&Rc::new(F::And(pairs)), cx)
            }
        }
        F::Ite(c, a, b) => {
            let (c, a, b) = (literal(c, cx)?, literal(a, cx)?, literal(b, cx)?);
            let t = cx.aux();
            cx.emit(vec![-t, -c, a])?;
            cx.emit(vec![-t, c, b])?;
            cx.emit(vec![t, -c, -a])?;
            cx.emit(vec![t, c, -b])?;
            cx.emit(vec![-t, a, b])?;
            cx.emit(vec![t, -a, -b])?;
            Ok(t)
        }
        F::Lit(l) => Ok(*l),
        F::True => true_lit(cx),
        F::False => Ok(-true_lit(cx)?),
        F::And(xs) => {
            if cx.has_dv() {
                if let Some((d, n)) = def_of(cx, f)? {
                    return Ok(cx.dv(&d, n, Need::Both)?.expect("only the unit needs answer None"));
                }
            }
            let mut lits = Vec::with_capacity(xs.len());
            for a in xs {
                lits.push(literal(a, cx)?);
            }
            match lits.len() {
                0 => return true_lit(cx),
                1 => return Ok(lits[0]),
                _ => {}
            }
            let t = cx.aux();
            for &l in &lits {
                cx.emit(vec![-t, l])?;
            }
            let mut c = vec![t];
            c.extend(lits.iter().map(|l| -l));
            cx.emit(c)?;
            Ok(t)
        }
        F::Or(xs) => {
            let mut lits = Vec::with_capacity(xs.len());
            for a in xs {
                lits.push(literal(a, cx)?);
            }
            match lits.len() {
                0 => return Ok(-true_lit(cx)?),
                1 => return Ok(lits[0]),
                _ => {}
            }
            let t = cx.aux();
            for &l in &lits {
                cx.emit(vec![-l, t])?;
            }
            let mut c = vec![-t];
            c.extend_from_slice(&lits);
            cx.emit(c)?;
            Ok(t)
        }
        F::Bad(i) => Err(cx.bad(*i, true)),
    }
}
