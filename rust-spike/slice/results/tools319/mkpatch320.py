"""mkpatch320.py SRC_DIR (sa-port-320): edits a scratch copy of solver_rs/src into the count build.
Every edit is an exact-string replacement with its expected number of matches; a miss stops the script.
The package is never edited: the result is kept as a diff (count320.patch)."""
import sys, pathlib
D = pathlib.Path(sys.argv[1])


def edit(name, pairs):
    f = D / name
    s = f.read_text()
    for old, new, n in pairs:
        k = s.count(old)
        if k != n:
            sys.exit(f"{name}: {k} matches, wanted {n}: {old[:70]!r}")
        s = s.replace(old, new)
    f.write_text(s)


TAIL = r'''
// ---- sa-port-320 count build: a scratch patch, never part of the package (issue 323) ----
// Marks: bit = kind * 3 + phase, and bit 9 + kind for the kind in any phase. kind 0 visited by propagation, 1 a reason or the conflict, 2 read by conflict
// analysis or in a reason cone (the proof). phase 0 outside build_context (the query), 1 build_context, 2 its
// complete check.
use std::sync::atomic::{AtomicU32, AtomicU64, Ordering as CxO};
pub static CX_PHASE: AtomicU32 = AtomicU32::new(0);
pub static CX_ROW: AtomicU32 = AtomicU32::new(0);
pub static CX_ROWSEQ: AtomicU32 = AtomicU32::new(0);
pub static CX_ROWK: [AtomicU32; 4] = [AtomicU32::new(0), AtomicU32::new(0), AtomicU32::new(0), AtomicU32::new(0)];
static CX_SERIAL: AtomicU64 = AtomicU64::new(0);
static CX_OUT: std::sync::OnceLock<Option<std::sync::Mutex<std::fs::File>>> = std::sync::OnceLock::new();

pub struct CxPhase(u32);
impl CxPhase {
    pub fn enter(p: u32) -> CxPhase {
        CxPhase(CX_PHASE.swap(p, CxO::Relaxed))
    }
}
impl Drop for CxPhase {
    fn drop(&mut self) {
        CX_PHASE.store(self.0, CxO::Relaxed);
    }
}
pub struct CxRow(u32);
impl CxRow {
    /// kind 0 a user eq atom, 1 a queued atom interpreted, 2 a top entry, 3 a pending link
    pub fn enter(kind: u32) -> CxRow {
        let id = (CX_ROWSEQ.fetch_add(1, CxO::Relaxed) + 1) * 4 + kind;
        CX_ROWK[kind as usize].fetch_add(1, CxO::Relaxed);
        CxRow(CX_ROW.swap(id, CxO::Relaxed))
    }
}
impl Drop for CxRow {
    fn drop(&mut self) {
        CX_ROW.store(self.0, CxO::Relaxed);
    }
}
fn cx_ph() -> usize {
    CX_PHASE.load(CxO::Relaxed) as usize
}

#[derive(Default)]
pub struct Cx {
    serial: u64,
    born: usize,
    c_org: Vec<u8>, // 0..2 the phase a problem clause was added in, 3 learnt, 4 other (theory, explanation)
    c_mk: Vec<u16>,
    c_row: Vec<u32>,
    v_mk: Vec<u16>,
    v_org: Vec<u8>,
    v_row: Vec<u32>,
    u_org: Vec<u8>, // 0 no unit, else 1 + the phase the unit clause was added in
    u_mk: Vec<u16>,
    u_row: Vec<u32>,
    b_mk: std::collections::HashMap<u32, u16>,
    rows: std::collections::HashMap<u32, u16>,
    nb: [u64; 5],
    cm: [[u64; 12]; 5],
    vb: [u64; 3],
    vm: [[u64; 12]; 3],
    ub: [u64; 3],
    um: [[u64; 12]; 3],
    bb: [u64; 3],
    rb_seen: u64,
    bm: [u64; 12],
    re: [u64; 4],
    rm: [[u64; 12]; 4],
    ec: [u64; 8], // 0 solve_int, 1 assume, 2 propagate, 3 entails by a live trail, 4 by a trail that is not live, 5 root conflicts
    walk: Vec<u32>,
    walk_id: u32,
    rootdone: Vec<u8>,
    dirty: bool,
}

impl Cx {
    fn row_emit(&mut self, row: u32) {
        if row != 0 && !self.rows.contains_key(&row) {
            self.rows.insert(row, 0);
            self.re[(row & 3) as usize] += 1;
        }
    }
    fn row(&mut self, row: u32, bi: usize) {
        if row == 0 {
            return;
        }
        let e = self.rows.entry(row).or_insert(0);
        if *e & (1 << bi) == 0 {
            *e |= 1 << bi;
            self.rm[(row & 3) as usize][bi] += 1;
        }
    }
    fn new_clause(&mut self, learnt: bool) {
        let o = if learnt { 3 } else { 4 };
        self.c_org.push(o);
        self.c_mk.push(0);
        self.c_row.push(0);
        self.nb[o as usize] += 1;
        self.dirty = true;
    }
    /// a problem clause: the caller has just pushed it on `clauses`
    fn orig(&mut self, c: u32) {
        let i = c as usize;
        let ph = cx_ph();
        self.nb[self.c_org[i] as usize] -= 1;
        self.c_org[i] = ph as u8;
        self.nb[ph] += 1;
        let row = CX_ROW.load(CxO::Relaxed);
        self.c_row[i] = row;
        self.row_emit(row);
    }
    fn grow(&mut self, v: usize, k: usize) {
        let ph = cx_ph();
        let row = CX_ROW.load(CxO::Relaxed);
        self.v_mk.resize(v + 1, 0);
        self.v_org.resize(v + 1, ph as u8);
        self.v_row.resize(v + 1, row);
        self.u_org.resize(v + 1, 0);
        self.u_mk.resize(v + 1, 0);
        self.u_row.resize(v + 1, 0);
        self.walk.resize(v + 1, 0);
        self.rootdone.resize(v + 1, 0);
        self.vb[ph] += k as u64;
        self.row_emit(row);
        self.dirty = true;
    }
    fn atom(&mut self, v: usize) {
        let row = CX_ROW.load(CxO::Relaxed);
        if row != 0 && v < self.v_row.len() && self.v_row[v] == 0 {
            self.v_row[v] = row;
            self.row_emit(row);
        }
    }
    fn unit(&mut self, v: usize) {
        if v < self.u_org.len() && self.u_org[v] == 0 {
            let ph = cx_ph();
            let row = CX_ROW.load(CxO::Relaxed);
            self.u_org[v] = 1 + ph as u8;
            self.u_row[v] = row;
            self.ub[ph] += 1;
            self.row_emit(row);
            self.dirty = true;
        }
    }
    #[inline]
    fn c(&mut self, c: u32, k: usize) {
        let i = c as usize;
        for bi in [k * 3 + cx_ph(), 9 + k] {
            if self.c_mk[i] & (1 << bi) == 0 {
                self.c_mk[i] |= 1 << bi;
                self.cm[self.c_org[i] as usize][bi] += 1;
                self.dirty = true;
                let row = self.c_row[i];
                self.row(row, bi);
            }
        }
    }
    #[inline]
    fn v(&mut self, v: usize, k: usize) {
        if v >= self.v_mk.len() {
            return;
        }
        for bi in [k * 3 + cx_ph(), 9 + k] {
            if self.v_mk[v] & (1 << bi) == 0 {
                self.v_mk[v] |= 1 << bi;
                self.vm[self.v_org[v] as usize][bi] += 1;
                self.dirty = true;
                let row = self.v_row[v];
                self.row(row, bi);
            }
            if self.u_org[v] != 0 && self.u_mk[v] & (1 << bi) == 0 {
                self.u_mk[v] |= 1 << bi;
                self.um[(self.u_org[v] - 1) as usize][bi] += 1;
                self.dirty = true;
                let row = self.u_row[v];
                self.row(row, bi);
            }
        }
    }
    fn b(&mut self, base: u32, k: usize) {
        for bi in [k * 3 + cx_ph(), 9 + k] {
            let e = self.b_mk.entry(base).or_insert(0);
            if *e & (1 << bi) == 0 {
                *e |= 1 << bi;
                self.bm[bi] += 1;
                self.dirty = true;
            }
        }
    }
}

fn cx_join(xs: &[u64]) -> String {
    xs.iter().map(|x| x.to_string()).collect::<Vec<_>>().join(",")
}

impl<Th: Theory> Solver<Th> {
    fn cx_blocks(&mut self) {
        let n = self.rb_blocks as u64;
        if n > self.cx.rb_seen {
            self.cx.bb[cx_ph()] += n - self.cx.rb_seen;
            self.cx.rb_seen = n;
            self.cx.dirty = true;
        }
    }

    /// The reason cone of an assigned variable: every clause, block and variable its value rests on.
    /// Root-level variables are walked once per phase (the root trail never changes); others once per walk.
    fn cx_cone(&mut self, v0: usize) {
        let ph = cx_ph();
        self.cx.walk_id += 1;
        let id = self.cx.walk_id;
        let mut st = vec![v0];
        let mut buf: Vec<u32> = Vec::new();
        while let Some(v) = st.pop() {
            if v == 0 || v > self.nvars || v >= self.cx.walk.len() || self.val[v << 1] == U {
                continue;
            }
            if self.level[v] == 0 {
                if self.cx.rootdone[v] & (1 << ph) != 0 {
                    continue;
                }
                self.cx.rootdone[v] |= 1 << ph;
            } else {
                if self.cx.walk[v] == id {
                    continue;
                }
                self.cx.walk[v] = id;
            }
            self.cx.v(v, 2);
            match self.reason[v] {
                Reason::None => {}
                Reason::Clause(c) => {
                    self.cx.c(c, 2);
                    for &l in &self.db[c as usize].lits {
                        let u = (l >> 1) as usize;
                        if u != v {
                            st.push(u);
                        }
                    }
                }
                Reason::Block(m, b) => {
                    self.cx.b(b, 2);
                    self.rb_reason(v, m, b, &mut buf);
                    for &l in &buf {
                        let u = (l >> 1) as usize;
                        if u != v {
                            st.push(u);
                        }
                    }
                }
            }
        }
    }

    /// A variable met by conflict analysis: at the root its cone is the proof's, above it the analysis walks on.
    fn cx_use(&mut self, v: usize) {
        if self.level[v] == 0 {
            self.cx_cone(v);
        } else {
            self.cx.v(v, 2);
        }
    }

    /// Minimisation dropped this literal: its reason is part of the learnt clause's derivation.
    fn cx_min(&mut self, v: usize) {
        match self.reason[v] {
            Reason::None => {}
            Reason::Clause(c) => {
                self.cx.c(c, 2);
                let ls = self.db[c as usize].lits.clone();
                for &l in &ls[1..] {
                    self.cx_use((l >> 1) as usize);
                }
            }
            Reason::Block(_, b) => self.cx.b(b, 2),
        }
    }

    fn cx_snap(&mut self, tag: &str) {
        self.cx_blocks();
        if !self.cx.dirty {
            return;
        }
        self.cx.dirty = false;
        let out = CX_OUT.get_or_init(|| {
            std::env::var("SA320_COUNT").ok().and_then(|p| std::fs::OpenOptions::new().create(true).append(true).open(p).ok()).map(std::sync::Mutex::new)
        });
        let Some(out) = out else { return };
        let cx = &self.cx;
        let flat = |m: &[[u64; 12]]| m.iter().map(|r| cx_join(r)).collect::<Vec<_>>().join(";");
        let rk: Vec<u64> = CX_ROWK.iter().map(|a| a.load(CxO::Relaxed) as u64).collect();
        let line = format!(
            "S pid={} ser={} born={} tag={} nvars={} ncl={} nlearnt={} db={} blocks={} nb={} vb={} ub={} bb={} re={} rk={} ec={} cm={} vm={} um={} bm={} rm={}\n",
            std::process::id(), cx.serial, cx.born, tag, self.nvars, self.clauses.len(), self.learnts.len(), self.db.len(), self.rb_blocks,
            cx_join(&cx.nb), cx_join(&cx.vb), cx_join(&cx.ub), cx_join(&cx.bb), cx_join(&cx.re), cx_join(&rk), cx_join(&cx.ec),
            flat(&cx.cm), flat(&cx.vm), flat(&cx.um), cx_join(&cx.bm), flat(&cx.rm)
        );
        if let Ok(mut f) = out.lock() {
            let _ = std::io::Write::write_all(&mut *f, line.as_bytes());
        }
    }

    /// A conflict at the root runs no analysis: the refutation is the conflict clause and its literals' cones.
    fn cx_root_confl(&mut self, r: Option<u32>) -> Option<u32> {
        if let Some(c) = r {
            if self.trail_lim.is_empty() {
                self.cx.ec[5] += 1;
                self.cx.c(c, 2);
                let ls = self.db[c as usize].lits.clone();
                for &l in &ls {
                    self.cx_cone((l >> 1) as usize);
                }
            }
        }
        r
    }

    fn prop(&mut self) -> Option<u32> {
        let r = self.prop_i();
        self.cx_root_confl(r)
    }

    fn tprop(&mut self) -> Option<u32> {
        let r = self.tprop_i();
        self.cx_root_confl(r)
    }

    fn solve_int(&mut self, lits: &[u32], keep: usize) -> bool {
        self.cx.ec[0] += 1;
        let r = self.solve_int_i(lits, keep);
        self.cx.dirty = true;
        self.cx_snap("E");
        r
    }

    fn assume(&mut self, assumptions: &[u32], hold: i32) -> R<Tr> {
        self.cx.ec[1] += 1;
        let r = self.assume_i(assumptions, hold);
        self.cx_snap("A");
        r
    }

    pub fn register_block(&mut self, base: i32, mentions: u128) -> R<bool> {
        let r = self.register_block_i(base, mentions);
        self.cx_blocks();
        r
    }
}

impl<Th: Theory> Drop for Solver<Th> {
    fn drop(&mut self) {
        self.cx.dirty = true;
        self.cx_snap("D");
    }
}
'''

edit("solver.rs", [
    # the struct and its constructor
    ("pub struct Solver<Th: Theory> {\n", "pub struct Solver<Th: Theory> {\n    pub cx: Cx,\n", 1),
    ("        Solver {\n            val: vec![U, U],\n",
     "        Solver {\n            cx: Cx { serial: CX_SERIAL.fetch_add(1, CxO::Relaxed) + 1, born: cx_ph(), ..Default::default() },\n            val: vec![U, U],\n", 1),
    # built: clauses, variables, units
    ("        self.db.push(Clause { lits, act: 0.0, learnt });\n",
     "        self.db.push(Clause { lits, act: 0.0, learnt });\n        self.cx.new_clause(learnt);\n", 1),
    ("self.clauses.push(c);\n", "self.clauses.push(c);\n self.cx.orig(c);\n", 3),
    ("self.clauses.push(cr);\n", "self.clauses.push(cr);\n self.cx.orig(cr);\n", 1),
    ("        self.nvars = v;\n    }\n", "        self.nvars = v;\n        self.cx.grow(v, k);\n    }\n", 1),
    ("            self.set_true(out[0], 0, Reason::None);\n",
     "            self.cx.unit((out[0] >> 1) as usize);\n            self.set_true(out[0], 0, Reason::None);\n", 1),
    ("                self.set_true(l, 0, Reason::None);\n                continue;\n",
     "                self.cx.unit((l >> 1) as usize);\n                self.set_true(l, 0, Reason::None);\n                continue;\n", 1),
    ("                self.set_true(lits[0], 0, Reason::None);\n",
     "                self.cx.unit((lits[0] >> 1) as usize);\n                self.set_true(lits[0], 0, Reason::None);\n", 1),
    ("    pub fn register_atom(&mut self, ti: usize, var: i32, payload: Th::Payload, mention: bool) -> R<bool> {\n",
     "    pub fn register_atom(&mut self, ti: usize, var: i32, payload: Th::Payload, mention: bool) -> R<bool> {\n        self.cx.atom(var.unsigned_abs() as usize);\n", 1),
    # reasons
    ("        self.reason[v] = r;\n        self.trail.push(l);\n",
     "        self.reason[v] = r;\n        match r {\n            Reason::None => {}\n            Reason::Clause(c) => {\n                self.cx.c(c, 1);\n                self.cx.v(v, 1);\n            }\n            Reason::Block(_, b) => {\n                self.cx.b(b, 1);\n                self.cx.v(v, 1);\n            }\n        }\n        self.trail.push(l);\n", 1),
    # propagation
    ("            let pv = (p >> 1) as usize;\n            if has_rb {\n",
     "            let pv = (p >> 1) as usize;\n            self.cx.v(pv, 0);\n            if has_rb {\n", 1),
    ("                let cr = ws[i];\n                i += 1;\n",
     "                let cr = ws[i];\n                i += 1;\n                self.cx.c(cr, 0);\n", 1),
    ("                        confl = Some(cr);\n                        while i < n {\n",
     "                        confl = Some(cr);\n                        self.cx.c(cr, 1);\n                        while i < n {\n", 1),
    ("                let base = self.rb_base[pv] as usize;\n                if base != 0 && !matches!(self.reason[pv], Reason::Block(..)) {\n",
     "                let base = self.rb_base[pv] as usize;\n                if base != 0 {\n                    self.cx.b(base as u32, 0);\n                }\n                if base != 0 && !matches!(self.reason[pv], Reason::Block(..)) {\n", 1),
    ("    pub fn propagate(&mut self) -> bool {\n", "    pub fn propagate(&mut self) -> bool {\n        self.cx.ec[2] += 1;\n", 1),
    # conflict analysis
    ("            if let Some(c) = cur {\n                if self.db[c as usize].learnt {\n",
     "            if let Some(c) = cur {\n                self.cx.c(c, 2);\n                if self.db[c as usize].learnt {\n", 1),
    ("            for &q in &buf[if first { 0 } else { 1 }..] {\n                let v = (q >> 1) as usize;\n",
     "            for &q in &buf[if first { 0 } else { 1 }..] {\n                let v = (q >> 1) as usize;\n                self.cx_use(v);\n", 1),
    ("                Reason::Block(m, b) => {\n                    self.rb_reason(pv, m, b, &mut buf);\n                    cur = None;\n",
     "                Reason::Block(m, b) => {\n                    self.cx.b(b, 2);\n                    self.rb_reason(pv, m, b, &mut buf);\n                    cur = None;\n", 1),
    ("                if keep {\n                    learnt[j] = q;\n                    j += 1;\n                }\n",
     "                if keep {\n                    learnt[j] = q;\n                    j += 1;\n                } else {\n                    self.cx_min((q >> 1) as usize);\n                }\n", 1),
    # analyze_final
    ("        let mut out = vec![p];\n        if self.trail_lim.is_empty() {\n",
     "        let mut out = vec![p];\n        let mut cx_roots: Vec<usize> = vec![(p >> 1) as usize];\n        if self.trail_lim.is_empty() {\n            self.cx_cone((p >> 1) as usize);\n", 1),
    ("            if self.seen[v] != 0 {\n                match self.reason[v] {\n",
     "            if self.seen[v] != 0 {\n                self.cx.v(v, 2);\n                match self.reason[v] {\n", 1),
    ("                    Reason::Clause(c) => {\n                        for &q in &self.db[c as usize].lits[1..] {\n                            let u = (q >> 1) as usize;\n                            if self.level[u] > 0 {\n                                self.seen[u] = 1;\n                            }\n",
     "                    Reason::Clause(c) => {\n                        self.cx.c(c, 2);\n                        for &q in &self.db[c as usize].lits[1..] {\n                            let u = (q >> 1) as usize;\n                            if self.level[u] > 0 {\n                                self.seen[u] = 1;\n                            } else {\n                                cx_roots.push(u);\n                            }\n", 1),
    ("                    Reason::Block(m, b) => {\n                        self.rb_reason(v, m, b, &mut buf);\n                        for &q in &buf[1..] {\n                            let u = (q >> 1) as usize;\n                            if self.level[u] > 0 {\n                                self.seen[u] = 1;\n                            }\n",
     "                    Reason::Block(m, b) => {\n                        self.cx.b(b, 2);\n                        self.rb_reason(v, m, b, &mut buf);\n                        for &q in &buf[1..] {\n                            let u = (q >> 1) as usize;\n                            if self.level[u] > 0 {\n                                self.seen[u] = 1;\n                            } else {\n                                cx_roots.push(u);\n                            }\n", 1),
    ("        self.seen[(p >> 1) as usize] = 0;\n        self.buf = buf;\n        self.conflict = out;\n",
     "        self.seen[(p >> 1) as usize] = 0;\n        self.buf = buf;\n        self.conflict = out;\n        for u in cx_roots {\n            if self.level[u] == 0 {\n                self.cx_cone(u);\n            }\n        }\n", 1),
    # entailment read off the trail: no analysis runs, so the cone is walked here
    ("        let vl = if self.in_trail(&tr, l) {\n            Some(true)\n",
     "        if self.val[l as usize] != U && (self.in_trail(&tr, l) || self.in_trail(&tr, l ^ 1)) {\n            self.cx.ec[3] += 1;\n            self.cx_cone(v);\n        } else if self.in_trail(&tr, l) || self.in_trail(&tr, l ^ 1) {\n            self.cx.ec[4] += 1;\n        }\n        let vl = if self.in_trail(&tr, l) {\n            Some(true)\n", 1),
    ("        for &l in &ins {\n            vals.push(if self.in_trail(&tr, l) {\n",
     "        for &l in &ins {\n            if self.in_trail(&tr, l) || self.in_trail(&tr, l ^ 1) {\n                if self.val[l as usize] != U {\n                    self.cx.ec[3] += 1;\n                    self.cx_cone((l >> 1) as usize);\n                } else {\n                    self.cx.ec[4] += 1;\n                }\n            }\n            vals.push(if self.in_trail(&tr, l) {\n", 1),
    # entry wrappers
    ("    fn prop(&mut self) -> Option<u32> {\n", "    fn prop_i(&mut self) -> Option<u32> {\n", 1),
    ("    fn tprop(&mut self) -> Option<u32> {\n", "    fn tprop_i(&mut self) -> Option<u32> {\n", 1),
    ("    fn solve_int(&mut self, lits: &[u32], keep: usize) -> bool {\n", "    fn solve_int_i(&mut self, lits: &[u32], keep: usize) -> bool {\n", 1),
    ("    fn assume(&mut self, assumptions: &[u32], hold: i32) -> R<Tr> {\n", "    fn assume_i(&mut self, assumptions: &[u32], hold: i32) -> R<Tr> {\n", 1),
    ("    pub fn register_block(&mut self, base: i32, mentions: u128) -> R<bool> {\n", "    pub fn register_block_i(&mut self, base: i32, mentions: u128) -> R<bool> {\n", 1),
])
with open(D / "solver.rs", "a") as f:
    f.write(TAIL)

edit("context.rs", [
    ("    tick(CTX_BUILD_CONTEXT);\n    let p = eng.py();\n",
     "    tick(CTX_BUILD_CONTEXT);\n    let _cx1 = crate::solver::CxPhase::enter(1);\n    let p = eng.py();\n", 1),
    ("    let checked = (|| -> PyResult<Bound<'py, PyAny>> {\n",
     "    let checked = (|| -> PyResult<Bound<'py, PyAny>> {\n        let _cx2 = crate::solver::CxPhase::enter(2);\n", 1),
])

edit("relations_core.rs", [
    ("    for a in &user {\n        if a.getattr(pred)?.eq(intern!(p, \"eq\"))? {\n",
     "    for a in &user {\n        if a.getattr(pred)?.eq(intern!(p, \"eq\"))? {\n            let _row = crate::solver::CxRow::enter(0);\n", 1),
    ("        if let Some(atom) = RList::of(rel, session::RL_QUEUE)?.pop()? {\n",
     "        if let Some(atom) = RList::of(rel, session::RL_QUEUE)?.pop()? {\n            let _row = crate::solver::CxRow::enter(1);\n", 1),
    ("            for e in keys {\n                if number(rel, &h, &e)? {\n",
     "            for e in keys {\n                let _row = crate::solver::CxRow::enter(2);\n                if number(rel, &h, &e)? {\n", 1),
    ("        if let Some(e) = RList::of(rel, session::RL_PENDING_LINKS)?.pop()? {\n",
     "        if let Some(e) = RList::of(rel, session::RL_PENDING_LINKS)?.pop()? {\n            let _row = crate::solver::CxRow::enter(3);\n", 1),
])
print("ok")
