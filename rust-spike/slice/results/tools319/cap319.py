"""cap319.py (sa-port-319) TOOLS RUNDIR WL OUT.json: attribute every capi<-rust sample (ana195's category: the leaf is C,
with a sa_solver.so frame before the first eval loop) to its nearest project Rust function.

TOOLS is the directory holding dec143.py, ana195.py and prof292.py (read only); run with GD_NM=RUNDIR/nm.
Per capi<-rust sample, leaf first:
  cfr     the C frames below the first sa_solver.so frame; entry = cfr[-1], the C function Rust called; leaf = cfr[0].
  proj    the nearest sa_solver.so frame whose demangled path is the crate's own (sa_solver::... or <sa_solver::...).
          pyo3 wrappers and std/alloc/hashbrown instantiations between it and the C entry are skipped and recorded as
          `via` (the innermost of them), since they say which pyo3 operation was asked for. A #[pymethods] or
          #[pyfunction] wrapper counts as its function (the name keeps __pymethod_NAME__).
  kind    what the sample asks Python for, from via, then entry, then leaf (kind() below). The entry is the outermost C
          frame the walker recovered: libpython tail-calls (PyObject_GetAttr -> tp_getattro) and its unexported static
          functions ("past end": the PC is after the named symbol's end) blur it, so via decides first.
  r292    prof292.py's key (first non-glue Rust frame), for comparing against 317's dcat table.
Counters: fk[proj, kind], fkl[proj, kind, leaf], fve[proj, via, entry], kind[kind], fn[proj], fe[proj, entry], fel[proj, entry, leaf], fv[proj, via], ent[entry], leaf[leaf], lib[entry's library],
par[proj <- next two project frames], q[query index] over capi<-rust samples, qall[query index] over all samples.
"""
import collections, glob, json, os, re, subprocess, sys
sys.path.insert(0, sys.argv[1])
import dec143 as D
import ana195 as A
import prof292 as P

_raw = {}


def full(s):
    """Demangled symbol with the crate path kept (prof292.dem strips it)."""
    if s not in _raw:
        o = s
        if s.startswith(("_R", "_ZN")):
            o = subprocess.run(["c++filt"], input=s, capture_output=True, text=True).stdout.strip()
            o = re.sub(r"\[[0-9a-f]{16}\]", "", o)
        _raw[s] = o
    return _raw[s]


def is_proj(v):
    f = full(v[2])
    return v[0] in ("rust", "glue") and f.startswith(("sa_solver::", "<sa_solver::"))


KINDS = [   # (kind, substrings of via, prefixes of entry); first match wins
    ("import by name", ("::import",), ("PyImport_",)),
    ("attribute by name", ("::getattr", "::hasattr", "::setattr", "::getattr_opt"), ("PyObject_GetAttr", "_PyObject_LookupAttr", "PyObject_SetAttr", "PyObject_GenericGetAttr", "_PyObject_GenericGetAttr", "PyObject_HasAttr", "_PyType_Lookup", "_PyObject_GetMethod", "PyObject_GetOptionalAttr")),
    ("method call by name", ("::call_method",), ("PyObject_VectorcallMethod", "PyObject_CallMethod")),
    ("call of a C callable", ("::call::", "::call_positional", "::call0", "::call1"), ("PyObject_Vectorcall", "PyObject_Call", "_PyObject_MakeTpCall", "_Py_CheckFunctionResult", "PyVectorcall_")),
    ("iteration", ("PyIterator", "::try_iter"), ("PyIter_", "PyObject_GetIter", "PyObject_LengthHint")),
    ("type test", ("::is_instance", "::is_subclass", "::is_exact_instance"), ("PyObject_IsInstance", "PyObject_IsSubclass", "PyType_IsSubtype")),
    ("container write", ("::append", "::set_item", "::insert", "::add::"), ("PyDict_SetItem", "PyList_Append", "PySet_Add", "PyObject_SetItem", "PyList_SetSlice", "PyList_Insert")),
    ("container lookup", ("::get_item", "::contains"), ("PyDict_GetItem", "PyDict_Contains", "PySequence_Contains", "PySet_Contains", "PyObject_GetItem", "PyTuple_GetItem", "PyList_GetItem", "PyObject_Size", "PyObject_Length", "PyTuple_GetSlice", "PySequence_")),
    ("hash or compare", ("::hash", "::is_truthy", "::rich_compare", "::eq::", "::ne::"), ("PyObject_Hash", "PyObject_RichCompare", "PyObject_IsTrue")),
    ("release of a Python object", ("drop_glue", "::drop"), ("_Py_Dealloc", "PyObject_Free", "PyObject_GC_Del", "PyObject_GC_UnTrack")),
    ("new Python object", ("PyString>::new", "into_pyobject", "pyclass_init", "::empty", "PyTuple>::new", "PyList>::new", "::intern"), ("PyTuple_New", "PyList_New", "PyLong_From", "PyUnicode_From", "PyFloat_From", "PyMethod_New", "_PyObject_New", "PyType_GenericAlloc", "PyObject_Malloc", "_PyObject_GC_New", "PyDict_New", "PySet_New", "PyFrozenSet_New", "PyUnicode_Intern", "_PyUnicode_Intern", "PyTuple_Pack")),
    ("read of a Python value", ("::extract", "FromPyObject"), ("PyLong_As", "PyUnicode_AsUTF8", "PyFloat_As", "PyNumber_", "_PyLong_", "PyUnicode_")),
]


def kind(via, entry, elib):
    if elib == "libc":
        if "tls_get_addr" in entry:
            return "thread-local read (libc, not Python)"
        return "Rust heap or libc (not Python)"
    for k, vs, es in KINDS:
        if any(x in via for x in vs):
            return k
    e = entry.replace(" (past end)", "")
    if entry.endswith("(past end)") and via == "-":
        return "unresolved (unexported C function)"
    for k, vs, es in KINDS:
        if e.startswith(es):
            return k
    return "other"


def main(d, wl, out):
    syms = D.Syms()
    C = {k: collections.Counter() for k in ("fn", "fe", "fel", "fv", "fk", "fkl", "kind", "fve", "ent", "leaf", "lib", "par", "q", "qall", "r292", "cats")}
    N = 0
    for b in sorted(glob.glob(f"{d}/{wl}-rust-pysample3-*.bin")):
        row, codes, maps, recs = D.load(b[:-4])
        for r in recs:
            if r[0] == 0xffffffff:
                continue
            m = D.merge(r, codes, maps, syms)
            c = A.classify(m)["cat"]
            N += 1; C["cats"][c] += 1; C["qall"][m["q"]] += 1
            if c != "capi<-rust":
                continue
            lc = m["leafc"]
            i = next(j for j, v in enumerate(lc) if v[0] in ("rust", "glue"))
            cfr = lc[:i]
            rs = [v for v in m["nat"][i:] if v[0] in ("rust", "glue")]   # all Rust frames outward, across eval loops
            pj = [v for v in rs if is_proj(v)]
            proj = P.dem(pj[0][2]) if pj else "?"
            via = P.dem(lc[i][2]) if not is_proj(lc[i]) else "-"
            entry, leaf = cfr[-1], cfr[0]
            e, l = entry[2] + ("" if entry[3] else " (past end)"), leaf[2] + ("" if leaf[3] else " (past end)")
            kd = kind(via, e, D.libkind(entry[1]))
            C["fk"][proj + "\t" + kd] += 1; C["kind"][kd] += 1; C["fkl"][proj + "\t" + kd + "\t" + l] += 1
            C["fve"][proj + "\t" + via[:160] + "\t" + e] += 1
            C["fn"][proj] += 1; C["fe"][proj + "\t" + e] += 1; C["fel"][proj + "\t" + e + "\t" + l] += 1
            C["fv"][proj + "\t" + via] += 1; C["ent"][e] += 1; C["leaf"][l] += 1; C["lib"][D.libkind(entry[1])] += 1
            C["par"][" <- ".join(P.dem(v[2]) for v in pj[:3])] += 1; C["q"][m["q"]] += 1
            r2 = next((v for v in lc if v[0] == "rust"), None) or lc[i]
            C["r292"][P.dem(r2[2])] += 1
    json.dump(dict(N=N, **C), open(out, "w"))
    print(f"{d} {wl}: {N} samples; capi<-rust {C['cats']['capi<-rust']}; libs {dict(C['lib'])}")


if __name__ == "__main__":
    main(*sys.argv[2:5])
