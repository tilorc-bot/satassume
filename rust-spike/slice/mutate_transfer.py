"""Planted bugs in component 3 (`transfer.rs`, `transfer_py.rs`, `pyset.rs`), each scored per check. Builds in WORK; the tree isn't touched.
  mutate_transfer.py WORK [--jobs J] [--only a,b] [--wl dev,transfer:1:300] [--timeout T]
Checks, for each workload W: rust:W    a fresh engine per query, against pure Python, by answer and session digest
                             shadow:W  both side by side, per hook; and the digest compare as in rust:W
and api, `transfer_fuzz.py --seed 1 --rounds 400`.
Each cell says what the check saw:
  answer@I   query I's answer differs from Python's (a comparison)
  state@I    query I's answer is the same and a session's digest differs (a comparison)
  hook:H     shadow only: the per-hook compare logged a difference, first at hook H (a comparison)
  fuzz:PART  api only: the fuzzer's compare failed in PART (a comparison)
  CRASH      the process died (a panic or a signal); no comparison saw anything before it
  HANG       out of time
  no         ran to the end with no difference
`q=N` follows when the quiet handlers caught N; a quiet catch is never by itself a catch. The row "base" has to be all `no`.
Output: WORK/results.jsonl as checks end, then WORK/table.md."""
import argparse
import concurrent.futures as cf
import json
import os
import shutil
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
T, TP, PS, FP = "transfer.rs", "transfer_py.rs", "pyset.rs", "formula_py.rs"
M = [
    ("t01", T, "switch: polar's new variable before full's", "for (v, k) in [(full, 2u8), (polar, 1u8)] {", "for (v, k) in [(polar, 1u8), (full, 2u8)] {"),
    ("t02", T, "switch: kinds swapped", "[(full, 2u8), (polar, 1u8)]", "[(full, 1u8), (polar, 2u8)]"),
    ("t03", T, "switch: term not dirty", "self.sw.insert(term, (f, p));\n        self.dirty.push(term);", "self.sw.insert(term, (f, p));"),
    ("t04", T, "kind: full on reads as polar", "if f != 0 && self.on.get(&f).copied().unwrap_or(false) {\n            return 2;", "if f != 0 && self.on.get(&f).copied().unwrap_or(false) {\n            return 1;"),
    ("t05", T, "why: full and polar swapped", "Some(if k == 2 { -f } else { -p })", "Some(if k == 2 { -p } else { -f })"),
    ("t06", T, "merged: rb not dirty", "self.dirty.push(rb);\n        self.multi.push(rb);", "self.multi.push(rb);"),
    ("t07", T, "merged: rb not in multi", "self.dirty.push(rb);\n        self.multi.push(rb);", "self.dirty.push(rb);"),
    ("t08", T, "register_atom: every atom partial", "if partial {", "if true {"),
    ("t09", T, "register_atom: term not dirty", "None => d.0.push((pred, vec![literal])),\n        }\n        self.dirty.push(term);", "None => d.0.push((pred, vec![literal])),\n        }"),
    ("t10", T, "selector on: no rescan", "if on {\n                    self.rescan = true;\n                }", ""),
    ("t11", T, "selector: history saves the wrong value", "self.ehist.push((self.lims.len(), self.enabled));", "self.ehist.push((self.lims.len(), !self.enabled));"),
    ("t12", T, "enable var: on the trail at root too", "if !self.olims.is_empty() {", "if true {"),
    ("t13", T, "enable var on: term not dirty", "if literal > 0 {\n                self.dirty.push(term);\n            }", ""),
    ("t14", T, "assert: a singleton class is dirty_p", "if euf.members(euf.rep(term)?)?.len() > 1 {", "if euf.members(euf.rep(term)?)?.len() >= 1 {"),
    ("t15", T, "assert: dirty_p dropped", "self.dirty_p.push(v);", ""),
    ("t16", T, "set_fixed: term not dirty", "self.fixed.insert(term, facts);\n        self.dirty.push(term);", "self.fixed.insert(term, facts);"),
    ("t17", T, "explain: not negated", ".map(|l| -l).collect();\n        memo.insert", ".map(|l| l).collect();\n        memo.insert"),
    ("t18", T, "members_on: polar-only term shows all", "let Some(vs) = d.get(self.polar) else { continue };\n                    out.push((m, View::Polar(self.polar, vs), 1));", "out.push((m, View::Full(d), 1));"),
    ("t19", T, "members_on: switched-off term not skipped", "if k == 0 {\n                    continue;\n                }\n                if k == 1 {", "if k == 1 {"),
    ("t20", T, "scan: empty fixed dict counts", ".filter_map(|m| self.fixed.get(m).filter(|f| !f.is_empty()).map(|f| (*m, f)))", ".filter_map(|m| self.fixed.get(m).map(|f| (*m, f)))"),
    ("t22", T, "scan: last assigned witness", "wit = Some((*m, v, b, *k));\n                            break 'assigned;", "wit = Some((*m, v, b, *k));"),
    ("t23", T, "scan: last fixed witness", "wit = Some((*m, 0, *b, 2));\n                        break 'fixed;", "wit = Some((*m, 0, *b, 2));"),
    ("t24", T, "scan: witness's switch not in the lemma", "if has_sw {\n                head.extend(self.why(wm, wk));\n            }", ""),
    ("t25", T, "scan: already-true atoms get lemmas", "if v == wv || self.val.get(&v) == Some(&wb) {\n                        continue;\n                    }\n                    if tail.is_none()", "if v == wv {\n                        continue;\n                    }\n                    if tail.is_none()"),
    ("t26", T, "scan: lemma's polarity flipped", "let lit = if wb { v } else { -v };\n                    let mut why = vec![lit];\n                    why.extend_from_slice(&head);", "let lit = if wb { -v } else { v };\n                    let mut why = vec![lit];\n                    why.extend_from_slice(&head);"),
    ("t27", T, "scan: clause literals reordered", "why.extend_from_slice(&head);\n                    why.extend_from_slice(tail.as_ref().unwrap());", "why.extend_from_slice(tail.as_ref().unwrap());\n                    why.extend_from_slice(&head);"),
    ("t28", T, "scan: witness's own switch in its tail", "if has_sw && *m != wm {", "if has_sw {"),
    ("t29", T, "spread: polar-only witness spreads any predicate", "if k == 0 || (k == 1 && p != polar) {\n                return Ok(());", "if k == 0 {\n                return Ok(());"),
    ("t30", T, "spread: goes on after a fixed fact's lemma", "out.push((lit, why));\n                        return Ok(());", "out.push((lit, why));"),
    ("t31", T, "spread: fixed test inverted", "if b != wb {", "if b == wb {"),
    ("t32", T, "spread: the witness in a fixed lemma", "why.extend_from_slice(&wneg[1..]);", "why.extend_from_slice(&wneg);"),
    ("t33", T, "spread: member's switch not in the lemma", "why.extend(whym);", ""),
    ("t34", T, "spread: the witness's own member re-read", "if self.sw.contains_key(&m) && m != wm {", "if self.sw.contains_key(&m) {"),
    ("t35", T, "classes: a repeated rep", "if seen.insert(r) {\n                    reps.push(r);\n                }", "let _ = seen.insert(r);\n                reps.push(r);"),
    ("t36", T, "classes: multi not pruned", "self.multi = keep;", "let _ = keep;"),
    ("t37", T, "propagate off: dirty kept", "if !self.enabled {\n            self.dirty.clear();\n            self.dirty_p.clear();", "if !self.enabled {"),
    ("t38", T, "propagate: rescan stays set", "self.rescan = false;\n            let reps", "let reps"),
    ("t39", T, "propagate: spread also on scanned classes", "if !seen.contains(&euf.rep(self.atoms[&v].0)?) {", "if true {"),
    ("t40", T, "propagate: selector's sign", "for (_, why) in &mut out {\n                why.push(-sel);", "for (_, why) in &mut out {\n                why.push(sel);"),
    ("t41", T, "propagate: dirty not cleared at the end", "self.dirty.clear();\n        self.dirty_p.clear();\n        if let Some(sel) = self.sel {", "if let Some(sel) = self.sel {"),
    ("t42", T, "check: conflict test inverted", "if b != (lit > 0) {", "if b == (lit > 0) {"),
    ("t43", T, "check: no selector in the conflict", "if let Some(sel) = self.sel {\n                        why.push(-sel);\n                    }\n                    return Ok(Some(why));", "return Ok(Some(why));"),
    ("t44", T, "check: runs when disabled", "if !self.enabled {\n            return Ok(None);\n        }\n        let mut out", "let mut out"),
    ("t45", T, "decide: runs when disabled or nothing partial", "if self.multi.is_empty() || (self.pterms.is_empty() && self.sw.is_empty()) || !self.enabled {", "if self.multi.is_empty() {"),
    ("t46", T, "decide: polar-only term reads pterms", "let ps = if *k == 1 { Some(&self.polar_only) } else { self.pterms.get(m) };", "let ps = self.pterms.get(m);"),
    ("t47", T, "decide: union's operands swapped", "Some(q) => q.union(ps),", "Some(q) => ps.union(&q),"),
    ("t48", T, "decide: last member's variable", "first = first.or(Some(vs[0]));", "first = Some(vs[0]);"),
    ("t49", T, "decide: a lone atom is decided", "if n > 1 {", "if n >= 1 {"),
    ("t50", T, "decide: assigned predicates not skipped", "if vs.iter().any(|v| self.val.contains_key(v)) {\n                        continue 'pred;\n                    }", ""),
    ("t51", T, "pop: selector history off by one", "if lvl <= n {", "if lvl < n {"),
    ("t52", T, "pop: enable values kept", "self.on.remove(&v);", ""),
    ("t53", T, "pop: atom values kept", "self.val.remove(&v);", ""),
    ("t54", T, "pop: selector value kept", "self.enabled = prev;", ""),
    ("t55", T, "push: no olims level (a panic in pop)", "self.olims.push(self.otrail.len());", ""),
    ("t57", T, "new: initial multi empty", "multi: euf.initial_multi()?,", "multi: Vec::new(),"),
    ("t58", T, "kind: an unset polar var reads on", "if p != 0 && self.on.get(&p).copied().unwrap_or(false) {", "if p != 0 && self.on.get(&p).copied().unwrap_or(true) {"),
    ("t59", T, "register_atom: a predicate's atoms reversed", "Some(e) => e.1.push(literal),", "Some(e) => e.1.insert(0, literal),"),
    ("p01", TP, "set_fixed: facts reversed", "self.core.set_fixed(term, out);", "out.reverse();\n        self.core.set_fixed(term, out);"),
    ("p02", TP, "set_fixed: a second call overwrites", "if self.core.has_fixed(term) {\n            return Ok(());\n        }", ""),
    ("p03", TP, "register_atom: control variables not skipped", "if self.core.is_control(literal) {\n            return Ok(());\n        }", ""),
    ("p04", TP, "register_atom: partial by length only", "payload.len()? > 2 && payload.get_item(2)?.is_truthy()?", "payload.len()? > 2"),
    ("p05", TP, "merged: ra in place of rb", "fn _merged(&mut self, _ra: u32, rb: u32) {\n        self.core.merged(TermId(rb));", "fn _merged(&mut self, _ra: u32, rb: u32) {\n        let _ = rb;\n        self.core.merged(TermId(_ra));"),
    ("p06", TP, "PLANTED RAISE: check raises ValueError (forces the quiet handler)", "Ok(self.core.check(&view)?.map(|why| (false, why)))", "let _ = self.core.check(&view)?;\n        Err(PyValueError::new_err(\"planted\"))"),
    ("p07", TP, "PLANTED RAISE: propagate raises RuntimeError on any lemma", "self.core.propagate(&view)\n", "let r = self.core.propagate(&view)?;\n        if !r.is_empty() { return Err(PyRuntimeError::new_err(\"planted\")); }\n        Ok(r)\n"),
    ("y01", PS, "set order: perturb shift 4", "const PERTURB_SHIFT: u32 = 5;", "const PERTURB_SHIFT: u32 = 4;"),
    ("y02", PS, "set order: 8 linear probes", "const LINEAR_PROBES: usize = 9;", "const LINEAR_PROBES: usize = 8;"),
    ("f01", FP, "P: hash of (expr, pred)", "PyTuple::new(p, [self.pred.bind(p), self.expr.bind(p)])?.hash()", "PyTuple::new(p, [self.expr.bind(p), self.pred.bind(p)])?.hash()"),
    ("f02", FP, "P: == ignores pred", "let x = PyTuple::new(p, [a.pred.bind(p), a.expr.bind(p)])?;\n        let y = PyTuple::new(p, [b.pred.bind(p), b.expr.bind(p)])?;", "let x = PyTuple::new(p, [a.expr.bind(p)])?;\n        let y = PyTuple::new(p, [b.expr.bind(p)])?;"),
    ("f03", FP, "P: repr without the expr's parentheses", "format!(\"{}({})\", a.extract", "format!(\"{} {}\", a.extract"),
    ("f04", FP, "P: & builds Or", "intern!(slf.py(), \"And\")", "intern!(slf.py(), \"Or\")"),
    ("f05", FP, "P: >> operands swapped", "intern!(slf.py(), \"Implies\"))?.call1((slf, other))", "intern!(slf.py(), \"Implies\"))?.call1((other, slf))"),
    ("f06", FP, "P: ~ gives the atom back", "form(slf.py(), intern!(slf.py(), \"Not\"))?.call1((slf,))", "Ok(slf.clone().into_any())"),
    ("s01", T, "sharing: a term of one set is shared", "count[t] >= 2 && !self.seen.contains(t)", "count[t] >= 1 && !self.seen.contains(t)"),
    ("s02", T, "sharing: seen ignored", "count[t] >= 2 && !self.seen.contains(t)", "count[t] >= 2"),
    ("s03", T, "sharing: pairs flipped", "pairs.push((u, t));", "pairs.push((t, u));"),
    ("s04", T, "sharing: pairs newest first", "for &u in &self.shared {", "for &u in self.shared.iter().rev() {"),
    ("s05", T, "sharing: seen not recorded", "self.seen.insert(t);", ""),
    ("s06", TP, "sharing: last object, not first", "first.entry(id).or_insert_with(|| t.clone().unbind());", "first.insert(id, t.clone().unbind());"),
    ("s07", T, "sharing: order repeated per occurrence", "if *c == 0 {\n                    order.push(t);\n                }", "order.push(t);"),
    ("w01", TP, "wanted: an eq atom says False", "if a.getattr(pred)?.eq(intern!(p, \"eq\"))? {\n            return Ok(true);", "if a.getattr(pred)?.eq(intern!(p, \"eq\"))? {\n            return Ok(false);"),
    ("w02", TP, "wanted: eq atoms ignored", "if a.getattr(pred)?.eq(intern!(p, \"eq\"))? {", "if a.getattr(pred)?.eq(intern!(p, \"ne\"))? {"),
    ("w03", TP, "wanted: any lt atom says True", "lts.contains(&(y, x))", "lts.contains(&(x, y))"),
    ("w04", TP, "wanted: gt in place of lt", "if a.getattr(pred)?.eq(intern!(p, \"lt\"))? {", "if a.getattr(pred)?.eq(intern!(p, \"gt\"))? {"),
    ("w05", TP, "wanted: all, not any", "Ok(order.iter().any(", "Ok(order.iter().all("),
]
LOCK = threading.Lock()


def env(so=None):
    e = dict(os.environ)
    e.pop("SLICE_TRANSFER", None)
    return e


def build(k, crate, target, out, py):
    r = subprocess.run(["cargo", "build", "--release"], cwd=crate, capture_output=True, text=True, env=dict(
        env(), PYO3_PYTHON=py, CARGO_TARGET_DIR=target, CARGO_PROFILE_RELEASE_LTO="off", CARGO_PROFILE_RELEASE_OPT_LEVEL="1",
        CARGO_PROFILE_RELEASE_CODEGEN_UNITS="16", CARGO_PROFILE_RELEASE_INCREMENTAL="true"))
    if r.returncode:
        return r.stderr[-1500:]
    os.makedirs(out, exist_ok=True)
    shutil.copy(os.path.join(target, "release", "libsa_solver.so"), os.path.join(out, "sa_solver.so"))
    return None


def rows(path):
    out = []
    if os.path.exists(path):
        for line in open(path):
            p = line.rstrip("\n").split("\t")
            if len(p) == 3:
                out.append(p)
    return out


def compare(ref, got):
    """The first answer difference and the first digest difference. Rows are by query, in order."""
    a = s = None
    for x, y in zip(ref, got):
        if a is None and x[1] != y[1]:
            a = int(x[0])
        if s is None and x[2] != y[2]:
            s = int(x[0])
    return a, s


def fresh(k, so, wl, mode, ref, w, timeout):
    out = os.path.join(w, "out", f"{k}.{mode}.{wl.replace(':', '_')}")
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "transfer_fresh.py"), wl, mode, out, "--so", so], cwd=HERE,
                           capture_output=True, text=True, timeout=timeout, env=env())
        rc = r.returncode
        err = r.stderr[-400:]
    except subprocess.TimeoutExpired:
        rc, err = "hang", ""
    got = rows(out)
    a, s = compare(ref, got)
    q = n = None
    if os.path.exists(out + ".json") and rc == 0:
        d = json.load(open(out + ".json"))
        q, n = sum(d["quiet_catches"].values()), d.get("raised", 0)
    hook = None
    if mode == "shadow" and os.path.exists(out + ".diffs"):
        first = open(out + ".diffs").readline()
        if first:
            hook = json.loads(first)
    bits = []
    if hook:
        bits.append(f"hook:{hook['hook']}/{hook['field']}@{hook['query']}")
    if a is not None:
        bits.append(f"answer@{a}")
    if s is not None:
        bits.append(f"state@{s}")
    if rc == "hang":
        bits.append("HANG")
    elif rc != 0 or len(got) < len(ref):
        bits.append("CRASH" + (" " + err.strip().splitlines()[-1][:80] if err.strip() else ""))
    if not bits:
        bits = ["no"]
    if q:
        bits.append(f"q={q}")
    for suffix in ("", ".diffs"):
        if os.path.exists(out + suffix):
            os.remove(out + suffix)
    return " ".join(bits)


def api(k, so, timeout):
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "transfer_fuzz.py"), "--seed", "1", "--rounds", "400", "--so", so],
                           cwd=HERE, capture_output=True, text=True, timeout=timeout, env=env())
    except subprocess.TimeoutExpired:
        return "HANG"
    if r.returncode == 0:
        return "no"
    tail = (r.stdout + r.stderr).strip().splitlines()
    t = tail[-1][:100] if tail else ""
    if "Panic" in r.stderr or r.returncode < 0:
        return "CRASH " + t
    return "fuzz: " + t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--only")
    ap.add_argument("--wl", default="dev,transfer:1:300")
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()
    w = os.path.abspath(a.work)
    os.makedirs(os.path.join(w, "out"), exist_ok=True)
    src = os.path.join(HERE, "solver_rs")
    crate = os.path.join(w, "crate")
    shutil.copytree(src, crate, dirs_exist_ok=True, ignore=shutil.ignore_patterns("target"))
    for name in os.listdir(os.path.join(crate, "src")):    # copytree keeps mtimes: a reused target would look fresh
        os.utime(os.path.join(crate, "src", name))
    for k, f, d, old, new in M:
        n = open(os.path.join(src, "src", f)).read().count(old)
        if n != 1:
            sys.exit(f"{k}: old text occurs {n} times in {f}")
    only = set(a.only.split(",")) if a.only else None
    chosen = [m for m in M if only is None or m[0] in only]
    wls = a.wl.split(",")
    target = os.path.join(w, "target")
    res = open(os.path.join(w, "results.jsonl"), "a", buffering=1)

    def record(**row):
        with LOCK:
            res.write(json.dumps(row) + "\n")

    err = build("base", crate, target, os.path.join(w, "so", "base"), sys.executable)
    if err:
        sys.exit(err)
    refs = {}
    for wl in wls:
        ref = os.path.join(w, "ref." + wl.replace(":", "_"))
        subprocess.run([sys.executable, os.path.join(HERE, "transfer_fresh.py"), wl, "py", ref], cwd=HERE, check=True,
                       capture_output=True, env=env())
        refs[wl] = rows(ref)

    def run_checks(k, desc):
        so = os.path.join(w, "so", k)
        cell = {"api": api(k, so, a.timeout)}
        for wl in wls:
            for mode in ("rust", "shadow"):
                cell[f"{mode}:{wl}"] = fresh(k, so, wl, mode, refs[wl], w, a.timeout)
        record(k=k, desc=desc, **cell)
        return cell

    bad = {c: v for c, v in run_checks("base", "unmutated").items() if v != "no"}
    if bad:    # every other row would be void
        sys.exit(f"the unmutated build isn't clean: {bad}")

    with cf.ThreadPoolExecutor(a.jobs) as ex:
        futs = []
        for k, f, d, old, new in chosen:
            path = os.path.join(crate, "src", f)
            text = open(os.path.join(src, "src", f)).read()
            open(path, "w").write(text.replace(old, new))
            err = build(k, crate, target, os.path.join(w, "so", k), sys.executable)
            open(path, "w").write(text)
            if err:
                record(k=k, desc=d, build_error=err)
                continue
            futs.append(ex.submit(run_checks, k, d))
        for fu in futs:
            fu.result()
    with open(os.path.join(w, "table.md"), "w") as fh:
        got = [json.loads(line) for line in open(os.path.join(w, "results.jsonl"))]
        got.sort(key=lambda r: (r["k"] != "base", r["k"]))
        cols = ["api"] + [f"{m}:{wl}" for wl in wls for m in ("rust", "shadow")]
        fh.write("| id | bug | " + " | ".join(cols) + " |\n|" + "---|" * (len(cols) + 2) + "\n")
        for r in got:
            fh.write(f"| {r['k']} | {r['desc']} | " + " | ".join(r.get(c, r.get("build_error", "?")[:60]) for c in cols) + " |\n")
    open(os.path.join(w, "DONE"), "w").write("done\n")


main()
