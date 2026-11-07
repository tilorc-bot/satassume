//! `satassume.theories.transfer.TransferTheory`, method for method; see its docstring for what the theory means.
//! No pyo3 here: EUF's classes come through `Classes`, implemented over Python's EUF in `transfer_py.rs` until component
//! 2 lands, and the wrapper for Python is there too.
//!
//! Order: where Python's order reaches a lemma or a decision, this keeps it. Python's insertion-ordered dicts that are
//! iterated are `Vec`s here (`TermPreds`, `per`), and the one iterated set is a `BTreeSet`, walked sorted as Python's `decide` does. The `HashMap`s are only ever
//! looked up, never iterated, except sorted in `dump`, so their random hasher can't reach anything.
use crate::handle::TermId;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};

pub type Pred = u32;

/// What the theory reads of EUF's classes: `euf.rep`, `euf.members`, `euf.explain`.
pub trait Classes {
    type Err;
    fn rep(&self, t: TermId) -> Result<TermId, Self::Err>;
    fn members(&self, r: TermId) -> Result<Vec<TermId>, Self::Err>;
    fn explain(&self, a: TermId, b: TermId) -> Result<Vec<i32>, Self::Err>;
    /// `[r for r, ms in enumerate(euf.members) if len(ms) > 1 and euf.rep[r] == r]`, read once at construction.
    fn initial_multi(&self) -> Result<Vec<TermId>, Self::Err>;
}

/// A term's `{pred: [var, ...]}`, in first-registered order.
#[derive(Default)]
struct TermPreds(Vec<(Pred, Vec<i32>)>);

impl TermPreds {
    fn get(&self, p: Pred) -> Option<&Vec<i32>> {
        self.0.iter().find(|e| e.0 == p).map(|e| &e.1)
    }
}

/// `_members_on`'s `d`: all of a term's predicates, or its `polar` atoms alone.
enum View<'a> {
    Full(&'a TermPreds),
    Polar(Pred, &'a Vec<i32>),
}

impl<'a> View<'a> {
    fn get(&self, p: Pred) -> Option<&'a Vec<i32>> {
        match self {
            View::Full(d) => d.get(p),
            View::Polar(q, vs) => (*q == p).then_some(*vs),
        }
    }
    /// `d.items()`, in dict order.
    fn items(&self) -> Vec<(Pred, &'a Vec<i32>)> {
        match self {
            View::Full(d) => d.0.iter().map(|e| (e.0, &e.1)).collect(),
            View::Polar(q, vs) => vec![(*q, *vs)],
        }
    }
}

/// `explain`'s memo in one `_scan` or `_spread`, for the same crossings as Python.
type Memo = HashMap<(TermId, TermId), Vec<i32>>;
pub type Lemma = (i32, Vec<i32>);

pub struct TransferCore {
    pub sel: Option<i32>,
    pub enabled: bool,
    polar: Pred,
    polar_only: BTreeSet<Pred>,
    ehist: Vec<(usize, bool)>,
    rescan: bool,
    atoms: HashMap<i32, (TermId, Pred)>,
    by_term: HashMap<TermId, TermPreds>,
    val: HashMap<i32, bool>,
    trail: Vec<i32>,
    lims: Vec<usize>,
    dirty: Vec<TermId>,
    dirty_p: Vec<i32>,
    fixed: HashMap<TermId, Vec<(Pred, bool)>>,
    pterms: HashMap<TermId, BTreeSet<Pred>>,
    multi: Vec<TermId>,
    sw: HashMap<TermId, (i32, i32)>,
    onv: HashMap<i32, (TermId, u8)>,
    on: HashMap<i32, bool>,
    otrail: Vec<i32>,
    olims: Vec<usize>,
}

impl TransferCore {
    /// `polar` is `BASIS_INDEX["polar"]`, which the caller reads as Python does until D lands.
    pub fn new<C: Classes>(euf: &C, polar: Pred) -> Result<TransferCore, C::Err> {
        Ok(TransferCore {
            sel: None,
            enabled: true,
            polar,
            polar_only: BTreeSet::from([polar]),
            ehist: Vec::new(),
            rescan: false,
            atoms: HashMap::new(),
            by_term: HashMap::new(),
            val: HashMap::new(),
            trail: Vec::new(),
            lims: Vec::new(),
            dirty: Vec::new(),
            dirty_p: Vec::new(),
            fixed: HashMap::new(),
            pterms: HashMap::new(),
            multi: euf.initial_multi()?,
            sw: HashMap::new(),
            onv: HashMap::new(),
            on: HashMap::new(),
            otrail: Vec::new(),
            olims: Vec::new(),
        })
    }

    pub fn guard(&mut self, sel: i32) {
        self.sel = Some(sel);
        self.enabled = false;
    }

    pub fn switch(&mut self, term: TermId, full: i32, polar: i32) -> Vec<i32> {
        let old = self.sw.get(&term).copied().unwrap_or((0, 0));
        let mut new = Vec::new();
        for (v, k) in [(full, 2u8), (polar, 1u8)] {
            if v != 0 && !self.onv.contains_key(&v) {
                self.onv.insert(v, (term, k));
                new.push(v);
            }
        }
        let f = if full != 0 { full } else { old.0 };
        let p = if polar != 0 { polar } else { old.1 };
        self.sw.insert(term, (f, p));
        self.dirty.push(term);
        new
    }

    fn kind(&self, m: TermId) -> u8 {
        let Some(&(f, p)) = self.sw.get(&m) else { return 2 };
        if f != 0 && self.on.get(&f).copied().unwrap_or(false) {
            return 2;
        }
        if p != 0 && self.on.get(&p).copied().unwrap_or(false) {
            return 1;
        }
        0
    }

    /// Python's `[-sw[0]]`, 0 included: a switched term with no such variable gives a 0 there too.
    fn why(&self, m: TermId, k: u8) -> Option<i32> {
        let &(f, p) = self.sw.get(&m)?;
        Some(if k == 2 { -f } else { -p })
    }

    pub fn merged(&mut self, rb: TermId) {
        self.dirty.push(rb);
        self.multi.push(rb);
    }

    /// True if `literal` is the selector or an enable variable, which carry no payload to read.
    pub fn is_control(&self, literal: i32) -> bool {
        self.sel == Some(literal) || self.onv.contains_key(&literal)
    }

    pub fn is_bad_atom(&self, literal: i32) -> bool {
        literal <= 0 || self.atoms.contains_key(&literal)
    }

    pub fn register_atom(&mut self, literal: i32, term: TermId, pred: Pred, partial: bool) {
        self.atoms.insert(literal, (term, pred));
        if partial {
            self.pterms.entry(term).or_default().insert(pred);
        }
        let d = self.by_term.entry(term).or_default();
        match d.0.iter_mut().find(|e| e.0 == pred) {
            Some(e) => e.1.push(literal),
            None => d.0.push((pred, vec![literal])),
        }
        self.dirty.push(term);
    }

    pub fn assert_lit<C: Classes>(&mut self, euf: &C, literal: i32) -> Result<(), C::Err> {
        let v = literal.abs();
        if Some(v) == self.sel {
            let on = literal > 0;
            if on != self.enabled {
                self.ehist.push((self.lims.len(), self.enabled));
                self.enabled = on;
                if on {
                    self.rescan = true;
                }
            }
            return Ok(());
        }
        if let Some(&(term, _)) = self.onv.get(&v) {
            self.on.insert(v, literal > 0);
            if !self.olims.is_empty() {
                self.otrail.push(v);
            }
            if literal > 0 {
                self.dirty.push(term);
            }
            return Ok(());
        }
        let Some(&(term, _)) = self.atoms.get(&v) else { return Ok(()) };
        self.val.insert(v, literal > 0);
        if !self.lims.is_empty() {
            self.trail.push(v);
        }
        if euf.members(euf.rep(term)?)?.len() > 1 {
            self.dirty_p.push(v);
        }
        Ok(())
    }

    pub fn has_fixed(&self, term: TermId) -> bool {
        self.fixed.contains_key(&term)
    }

    /// `facts` as `dict(facts)` holds them. The caller checked `has_fixed`.
    pub fn set_fixed(&mut self, term: TermId, facts: Vec<(Pred, bool)>) {
        self.fixed.insert(term, facts);
        self.dirty.push(term);
    }

    /// `[-l for l in euf.explain(a, b)]`, through the memo.
    fn explain<C: Classes>(&self, euf: &C, a: TermId, b: TermId, memo: &mut Memo) -> Result<Vec<i32>, C::Err> {
        if a == b {
            return Ok(Vec::new());
        }
        if let Some(e) = memo.get(&(a, b)) {
            return Ok(e.clone());
        }
        let e: Vec<i32> = euf.explain(a, b)?.into_iter().map(|l| -l).collect();
        memo.insert((a, b), e.clone());
        Ok(e)
    }

    fn members_on(&self, members: &[TermId]) -> Vec<(TermId, View<'_>, u8)> {
        let mut out = Vec::new();
        for &m in members {
            let Some(d) = self.by_term.get(&m) else { continue };
            if self.sw.contains_key(&m) {
                let k = self.kind(m);
                if k == 0 {
                    continue;
                }
                if k == 1 {
                    let Some(vs) = d.get(self.polar) else { continue };
                    out.push((m, View::Polar(self.polar, vs), 1));
                } else {
                    out.push((m, View::Full(d), k));
                }
            } else {
                out.push((m, View::Full(d), 2));
            }
        }
        out
    }

    fn scan<C: Classes>(&self, euf: &C, r: TermId, out: &mut Vec<Lemma>) -> Result<(), C::Err> {
        let members = euf.members(r)?;
        if members.len() < 2 {
            return Ok(());
        }
        let ds = self.members_on(&members);
        // Python's `(f := fixed.get(m))` is falsy on an empty dict.
        let fs: Vec<(TermId, &Vec<(Pred, bool)>)> = members
            .iter()
            .filter_map(|m| self.fixed.get(m).filter(|f| !f.is_empty()).map(|f| (*m, f)))
            .collect();
        if ds.is_empty() || (ds.len() < 2 && fs.is_empty() && ds[0].1.items().iter().all(|e| e.1.len() < 2)) {
            return Ok(());
        }
        let mut per: Vec<(Pred, Vec<(TermId, &Vec<i32>, u8)>)> = Vec::new();
        for (m, d, k) in &ds {
            for (p, vs) in d.items() {
                match per.iter_mut().find(|e| e.0 == p) {
                    Some(e) => e.1.push((*m, vs, *k)),
                    None => per.push((p, vec![(*m, vs, *k)])),
                }
            }
        }
        let has_sw = !self.sw.is_empty();
        let mut memo = Memo::new();
        for (p, lst) in &per {
            let mut wit: Option<(TermId, i32, bool, u8)> = None;
            'fixed: for (m, f) in &fs {
                for (q, b) in f.iter() {
                    if q == p {
                        wit = Some((*m, 0, *b, 2));
                        break 'fixed;
                    }
                }
            }
            if wit.is_none() {
                if lst.len() < 2 && lst[0].1.len() < 2 {
                    continue;
                }
                'assigned: for (m, vs, k) in lst {
                    for &v in vs.iter() {
                        if let Some(&b) = self.val.get(&v) {
                            wit = Some((*m, v, b, *k));
                            break 'assigned;
                        }
                    }
                }
            }
            let Some((wm, wv, wb, wk)) = wit else { continue };
            let mut head = Vec::new();
            if wv != 0 {
                head.push(if wb { -wv } else { wv });
            }
            if has_sw {
                head.extend(self.why(wm, wk));
            }
            for (m, vs, k) in lst {
                let mut tail: Option<Vec<i32>> = None;
                for &v in vs.iter() {
                    if v == wv || self.val.get(&v) == Some(&wb) {
                        continue;
                    }
                    if tail.is_none() {
                        let mut t = self.explain(euf, wm, *m, &mut memo)?;
                        if has_sw && *m != wm {
                            t.extend(self.why(*m, *k));
                        }
                        tail = Some(t);
                    }
                    let lit = if wb { v } else { -v };
                    let mut why = vec![lit];
                    why.extend_from_slice(&head);
                    why.extend_from_slice(tail.as_ref().unwrap());
                    out.push((lit, why));
                }
            }
        }
        Ok(())
    }

    fn spread<C: Classes>(&self, euf: &C, v: i32, out: &mut Vec<Lemma>) -> Result<(), C::Err> {
        let Some(&wb) = self.val.get(&v) else { return Ok(()) };
        let (wm, p) = self.atoms[&v];
        let polar = self.polar;
        let mut wneg = vec![if wb { -v } else { v }];
        if self.sw.contains_key(&wm) {
            let k = self.kind(wm);
            if k == 0 || (k == 1 && p != polar) {
                return Ok(());
            }
            wneg.extend(self.why(wm, k));
        }
        let mut memo = Memo::new();
        for m in euf.members(euf.rep(wm)?)? {
            if let Some(f) = self.fixed.get(&m) {
                if let Some(&(_, b)) = f.iter().find(|e| e.0 == p) {
                    if b != wb {
                        let lit = if b { v } else { -v };
                        let mut why = vec![lit];
                        why.extend_from_slice(&wneg[1..]);
                        why.extend(self.explain(euf, m, wm, &mut memo)?);
                        out.push((lit, why));
                        return Ok(());
                    }
                }
            }
            let Some(vs) = self.by_term.get(&m).and_then(|d| d.get(p)) else { continue };
            let mut whym = None;
            if self.sw.contains_key(&m) && m != wm {
                let k = self.kind(m);
                if k == 0 || (k == 1 && p != polar) {
                    continue;
                }
                whym = self.why(m, k);
            }
            for &u in vs {
                if u == v || self.val.get(&u) == Some(&wb) {
                    continue;
                }
                let lit = if wb { u } else { -u };
                let mut why = vec![lit];
                why.extend_from_slice(&wneg);
                why.extend(self.explain(euf, wm, m, &mut memo)?);
                why.extend(whym);
                out.push((lit, why));
            }
        }
        Ok(())
    }

    fn classes<C: Classes>(&mut self, euf: &C) -> Result<Vec<TermId>, C::Err> {
        let (mut keep, mut reps) = (Vec::new(), Vec::new());
        let (mut kept, mut seen) = (HashSet::new(), HashSet::new());
        for &r0 in &self.multi {
            let r = euf.rep(r0)?;
            if euf.members(r)?.len() > 1 {
                if kept.insert(r0) {
                    keep.push(r0);
                }
                if seen.insert(r) {
                    reps.push(r);
                }
            }
        }
        self.multi = keep;
        Ok(reps)
    }

    pub fn propagate<C: Classes>(&mut self, euf: &C) -> Result<Vec<Lemma>, C::Err> {
        if !self.enabled {
            self.dirty.clear();
            self.dirty_p.clear();
            return Ok(Vec::new());
        }
        if self.rescan {
            self.rescan = false;
            let reps = self.classes(euf)?;
            self.dirty.extend(reps);
        }
        if self.dirty.is_empty() && self.dirty_p.is_empty() {
            return Ok(Vec::new());
        }
        let mut seen = HashSet::new();
        let mut out = Vec::new();
        for &t in &self.dirty {
            let r = euf.rep(t)?;
            if seen.insert(r) {
                self.scan(euf, r, &mut out)?;
            }
        }
        for &v in &self.dirty_p {
            if !seen.contains(&euf.rep(self.atoms[&v].0)?) {
                self.spread(euf, v, &mut out)?;
            }
        }
        self.dirty.clear();
        self.dirty_p.clear();
        if let Some(sel) = self.sel {
            for (_, why) in &mut out {
                why.push(-sel);
            }
        }
        Ok(out)
    }

    /// None, or the conflict clause.
    pub fn check<C: Classes>(&mut self, euf: &C) -> Result<Option<Vec<i32>>, C::Err> {
        if !self.enabled {
            return Ok(None);
        }
        let mut out = Vec::new();
        for r in self.classes(euf)? {
            self.scan(euf, r, &mut out)?;
        }
        for (lit, mut why) in out {
            if let Some(&b) = self.val.get(&lit.abs()) {
                if b != (lit > 0) {
                    if let Some(sel) = self.sel {
                        why.push(-sel);
                    }
                    return Ok(Some(why));
                }
            }
        }
        Ok(None)
    }

    pub fn decide<C: Classes>(&mut self, euf: &C) -> Result<Option<i32>, C::Err> {
        if self.multi.is_empty() || (self.pterms.is_empty() && self.sw.is_empty()) || !self.enabled {
            return Ok(None);
        }
        for r in self.classes(euf)? {
            let members = euf.members(r)?;
            let ds = self.members_on(&members);
            let mut preds: Option<BTreeSet<Pred>> = None;
            for (m, _, k) in &ds {
                let ps = if *k == 1 { Some(&self.polar_only) } else { self.pterms.get(m) };
                if let Some(ps) = ps {
                    preds = Some(match preds {
                        None => ps.clone(),
                        Some(q) => &q | ps,
                    });
                }
            }
            let Some(preds) = preds else { continue };
            'pred: for &p in &preds {
                let mut first = None;
                let mut n = 0;
                for (_, d, _) in &ds {
                    let Some(vs) = d.get(p) else { continue };
                    if vs.iter().any(|v| self.val.contains_key(v)) {
                        continue 'pred;
                    }
                    first = first.or(Some(vs[0]));
                    n += vs.len();
                }
                if n > 1 {
                    return Ok(first);
                }
            }
        }
        Ok(None)
    }

    pub fn push_level(&mut self) {
        self.lims.push(self.trail.len());
        self.olims.push(self.otrail.len());
    }

    pub fn pop_level(&mut self) {
        let lim = self.lims.pop().expect("pop_level at root");
        while self.trail.len() > lim {
            let v = self.trail.pop().unwrap();
            self.val.remove(&v);
        }
        let lim = self.olims.pop().expect("pop_level at root");
        while self.otrail.len() > lim {
            let v = self.otrail.pop().unwrap();
            self.on.remove(&v);
        }
        let n = self.lims.len();
        while let Some(&(lvl, prev)) = self.ehist.last() {
            if lvl <= n {
                break;
            }
            self.enabled = prev;
            self.ehist.pop();
        }
    }

    pub fn repr(&self) -> String {
        format!(
            "<TransferTheory {} atoms over {} terms, level {}>",
            self.atoms.len(),
            self.by_term.len(),
            self.lims.len()
        )
    }

    /// Field -> string, the same as `transfer_shadow.dump_py` builds from Python's theory, so `state.diff` can name the
    /// first field that differs. Maps that order nothing are sorted; orders that reach a lemma are kept as they stand.
    pub fn dump(&self) -> BTreeMap<&'static str, String> {
        fn join<T: ToString>(xs: impl IntoIterator<Item = T>) -> String {
            xs.into_iter().map(|x| x.to_string()).collect::<Vec<_>>().join(" ")
        }
        fn terms(xs: &[TermId]) -> String {
            join(xs.iter().map(|t| t.0))
        }
        fn sorted<K: Copy + Ord, V>(m: &HashMap<K, V>) -> Vec<(K, &V)> {
            let mut v: Vec<_> = m.iter().map(|(k, x)| (*k, x)).collect();
            v.sort_by_key(|e| e.0);
            v
        }
        let mut d = BTreeMap::new();
        d.insert("sel", self.sel.map_or("None".to_string(), |s| s.to_string()));
        d.insert("enabled", (self.enabled as u8).to_string());
        d.insert("ehist", join(self.ehist.iter().map(|(l, b)| format!("{}:{}", l, *b as u8))));
        d.insert("rescan", (self.rescan as u8).to_string());
        d.insert("atoms", join(sorted(&self.atoms).iter().map(|(v, a)| format!("{}:{}:{}", v, a.0 .0, a.1))));
        d.insert(
            "by_term",
            join(sorted(&self.by_term).iter().map(|(t, ps)| {
                let inner: Vec<_> = ps.0.iter().map(|(p, vs)| format!("{}={}", p, join(vs.iter()).replace(' ', ","))).collect();
                format!("{}{{{}}}", t.0, inner.join(";"))
            })),
        );
        d.insert("val", join(sorted(&self.val).iter().map(|(v, b)| format!("{}:{}", v, **b as u8))));
        d.insert("trail", join(self.trail.iter()));
        d.insert("lims", join(self.lims.iter()));
        d.insert("dirty", terms(&self.dirty));
        d.insert("dirty_p", join(self.dirty_p.iter()));
        d.insert(
            "fixed",
            join(sorted(&self.fixed).iter().map(|(t, f)| {
                let inner: Vec<_> = f.iter().map(|(p, b)| format!("{}={}", p, *b as u8)).collect();
                format!("{}{{{}}}", t.0, inner.join(";"))
            })),
        );
        d.insert(
            "pterms",
            join(sorted(&self.pterms).iter().map(|(t, s)| format!("{}{{{}}}", t.0, join(s.iter()).replace(' ', ",")))),
        );
        d.insert("multi", terms(&self.multi));
        d.insert("sw", join(sorted(&self.sw).iter().map(|(t, s)| format!("{}:{}:{}", t.0, s.0, s.1))));
        d.insert("onv", join(sorted(&self.onv).iter().map(|(v, o)| format!("{}:{}:{}", v, o.0 .0, o.1))));
        d.insert("on", join(sorted(&self.on).iter().map(|(v, b)| format!("{}:{}", v, **b as u8))));
        d.insert("otrail", join(self.otrail.iter()));
        d.insert("olims", join(self.olims.iter()));
        d
    }
}

/// `EqualitySharing`, over handles. `update` takes the sets as Python reads them, and returns what became shared, in
/// the order it did, so a caller holding objects can keep Python's "first seen in this update" object for each.
#[derive(Default)]
pub struct SharingCore {
    pub shared: Vec<TermId>,
    seen: HashSet<TermId>,
}

impl SharingCore {
    pub fn update(&mut self, term_sets: &[Vec<TermId>]) -> (Vec<TermId>, Vec<(TermId, TermId)>) {
        let mut count: HashMap<TermId, u32> = HashMap::new();
        let mut order = Vec::new();
        for ts in term_sets {
            for &t in ts {
                let c = count.entry(t).or_insert(0);
                if *c == 0 {
                    order.push(t);
                }
                *c += 1;
            }
        }
        let new: Vec<TermId> = order.into_iter().filter(|t| count[t] >= 2 && !self.seen.contains(t)).collect();
        let mut pairs = Vec::new();
        for &t in &new {
            for &u in &self.shared {
                pairs.push((u, t));
            }
            self.shared.push(t);
            self.seen.insert(t);
        }
        (new, pairs)
    }
}
