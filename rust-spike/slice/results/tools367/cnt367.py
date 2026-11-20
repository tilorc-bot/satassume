"""cnt367.py WL MODE OUT.json FILE... (sa-port-367, issue 323): computed against read, per result, for the Python files
named (sa/engine.py, slice/term_live.py, ...: sa/ = TREE/satassume, slice/ = TREE/rust-spike/slice). One cold pass of WL
(dev, fuzz 424242, budget, wiring) as tools342/qt342.py runs it: MODE py = the package alone (the default path, no
install), rust = the slice as `live.py --check plain` installs it (the environment picks the switches). Counting only:
nothing here is a time. No source change: everything is installed from outside after the imports.

What is counted, per query index and over the pass:

  functions  sys.monitoring PY_START on every code object whose file is a FILE: calls ("computed") and the call site
             (the nearest Python frame's code and instruction; a call that arrives through C or Rust is charged to the
             Python line that entered the native code). PY_RETURN: `discarded` when the caller's next instruction is
             POP_TOP, i.e. the returned value is dropped at the call site (`returns` says whether the function
             has a `return` of anything but None at all: one that has none computes no returned value) (exact for a direct Python call; a call
             through native code shows the native call's own fate, so a nonzero `discarded` is checked by reading the
             site). Generators are counted as calls only.
  fields     every attribute a class defined in a FILE stores (its __slots__, `self.X = ...` in its methods, annotated
             class fields; found by ast) gets a counting data descriptor on the class, in front of the slot or the
             instance dict. A write is `trivial` when the value stored is None, a bool, a number or an empty
             str/tuple/list/dict/set/frozenset (an initial value, not a computation). A read is one of three kinds,
             decided from the reader's source by the position of its instruction (ast): `mut` = the field's
             container is filled or changed in place and nothing is taken from it (`self.f[k] = v`, `del self.f[k]`,
             `self.f[k] += v`, `self.f.append(v)` and add/extend/update/insert/clear/discard/remove/appendleft/
             setdefault as a statement, through any chain of subscripts); `aug` = `self.f += v`, the field read
             only to be rewritten; `use` = every other read, and every read that does not come from a LOAD_ATTR
             of that name (getattr(), a native reader). Computes = non-trivial writes + mut + aug. Per object the
             field is `dirty` from a compute until its next `use`: `epochs` counts clean-to-dirty changes (results
             computed), `epochs_read` the uses that found it dirty (results read: the read count of the ruling,
             per compute). Also: writes, trivial writes, reads by kind, `read_writes` (writes of any kind followed
             by a use before the next write), the
             queries with a write and with a read, the writers (the line that stores it) and the readers (code and instruction; `via` marks a read that did
             not come from a LOAD_ATTR of that name at the reader's instruction: getattr(), a native reader, a C slot).
             Reads made inside the class's own __repr__/__eq__/__hash__ are readers like any other and show as such.
             A name the class inherits as a descriptor from a base (a property, a slot, a native getset: the class
             found under the module's name may be a replacement defined elsewhere) is not wrapped and is listed in
             `skipped` as "inherited TYPE"; an inherited plain class constant is kept as the default (sa-port-368).

Excluded readers are not decided here: every reader is listed with file:line, and tab367.py puts tests/, shadow checks
and instruments in their own column by file.

False zeros. A counter that never fired proves nothing, so after the pass (outside the counted window, reported under
`plant`): (1) a function compiled under each FILE's name is called twice, once as a statement (its value dropped) and
once assigned: the file's function counter must read 2 calls and 1 discarded; (2) for every field with a live last
written object, one planted LOAD_ATTR read and one planted native read (operator.attrgetter: PyObject_GetAttr, the
call Rust's getattr makes) must each move `reads` by exactly 1. `plant.failed` lists every counter that did not.

Prints one JSON line (the summary); the rows go to OUT.json.
"""
import ast, collections, dis, gc, hashlib, json, operator, os, sys, types
wl, mode, out = sys.argv[1:4]
FILES = sys.argv[4:]
S = os.environ["SLICE_DIR"]
TREE = os.path.dirname(os.path.dirname(S))
so = None
if mode != "py":
    sys.path.insert(0, S)
    import p_install
    p_install.install()
from evalbench.common import workload
from satassume import sympy_api
if mode != "py":
    import sa_solver
    import backend
    backend.install_euf()
    import term_live
    term_live.from_env()
    import lra_live
    lra_live.from_env()
    import session_live
    session_live.from_env()
    import knowledge_live
    knowledge_live.from_env()
    backend.install()
    so = hashlib.sha256(open(sa_solver.__file__, "rb").read()).hexdigest()[:16]
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
elif wl in ("budget", "wiring"):
    import importlib
    if S not in sys.path:
        sys.path.append(S)
    pairs = importlib.import_module({"budget": "budget_wl", "wiring": "knowledge_wiring_wl"}[wl]).queries()
else:
    pairs = workload(wl)


def path_of(f):
    return os.path.join(TREE, "satassume", f[3:]) if f.startswith("sa/") else os.path.join(S, f[6:])


def short(fn):
    for pre, tag in ((os.path.join(TREE, "satassume") + "/", "sa/"), (S + "/", "slice/"), (TREE + "/", "tree/")):
        if fn.startswith(pre):
            return tag + fn[len(pre):]
    i = fn.rfind("/sympy/")
    return "sympy/" + fn[i + 7:] if i >= 0 else fn


PATHS = {os.path.realpath(path_of(f)): f for f in FILES}
Q = [-1]            # the query index; -1 outside the loop, -2 while planting
ON = [False]

# ---- functions -------------------------------------------------------------------------------------------------------
calls = collections.Counter()           # code -> calls
callq = collections.defaultdict(set)    # code -> queries with a call
sites = collections.defaultdict(collections.Counter)    # code -> (caller code, lasti) -> calls
disc = collections.defaultdict(collections.Counter)     # code -> (caller code, lasti) -> returns dropped
_pop = {}
_target = {}
M = sys.monitoring
TOOL = 4
POP_TOP = dis.opmap["POP_TOP"]
CACHE = dis.opmap["CACHE"]


def is_target(code):
    r = _target.get(code)
    if r is None:
        r = _target[code] = os.path.realpath(code.co_filename) in PATHS
    return r


def next_is_pop(code, lasti):
    k = (code, lasti)
    r = _pop.get(k)
    if r is None:
        b = code.co_code
        i = lasti + 2
        while i < len(b) and b[i] == CACHE:
            i += 2
        r = _pop[k] = i < len(b) and b[i] == POP_TOP
    return r


def on_start(code, off):
    if not is_target(code):
        return M.DISABLE
    if not ON[0]:
        return
    calls[code] += 1
    callq[code].add(Q[0])
    fr = sys._getframe(1).f_back
    if fr is not None:
        sites[code][fr.f_code, fr.f_lasti] += 1


def on_return(code, off, val):
    if not is_target(code):
        return M.DISABLE
    if not ON[0] or code.co_flags & 0x2a0:      # generators, coroutines: calls only
        return
    fr = sys._getframe(1).f_back
    if fr is not None and next_is_pop(fr.f_code, fr.f_lasti):
        disc[code][fr.f_code, fr.f_lasti] += 1


# ---- fields ----------------------------------------------------------------------------------------------------------
_MISSING = object()


class Field:
    """A counting data descriptor in front of a slot (`orig` is the member descriptor) or of the instance dict."""
    __slots__ = ("cls", "name", "orig", "default", "writes", "reads", "read_writes", "wq", "rq", "readers", "writers", "unread", "last", "key",
                 "trivial", "mut", "aug", "use", "dirty", "epochs", "epochs_read")

    def __init__(self, cls, name, orig, default):
        self.cls, self.name, self.orig, self.default = cls, name, orig, default
        self.writes = self.reads = self.read_writes = self.trivial = self.mut = self.aug = self.use = self.epochs = self.epochs_read = 0
        self.dirty = set()
        self.wq, self.rq, self.readers, self.unread, self.last = set(), set(), collections.Counter(), set(), None
        self.writers = collections.Counter()

    def __get__(self, obj, tp=None):
        if obj is None:
            if self.default is _MISSING:
                return self
            return self.default
        if self.orig is not None:
            v = self.orig.__get__(obj, tp)      # AttributeError for an unset slot, as before
        else:
            try:
                v = obj.__dict__[self.name]
            except KeyError:
                if self.default is _MISSING:
                    raise AttributeError(f"{type(obj).__name__!r} object has no attribute {self.name!r}") from None
                v = self.default
        if ON[0]:
            self.reads += 1
            fr = sys._getframe(1)
            k = (fr.f_code, fr.f_lasti)
            self.readers[k] += 1
            kind = _kind.get((k, self.name)) or read_kind(k, self.name)
            i = id(obj)
            if kind == "use":
                self.use += 1
                self.rq.add(Q[0])
                if i in self.unread:
                    self.unread.discard(i)
                    self.read_writes += 1
                if i in self.dirty:
                    self.dirty.discard(i)
                    self.epochs_read += 1
            else:
                if kind == "mut":
                    self.mut += 1
                else:
                    self.aug += 1
                if i not in self.dirty:
                    self.dirty.add(i)
                    self.epochs += 1
        return v

    def __set__(self, obj, v):
        if self.orig is not None:
            self.orig.__set__(obj, v)
        else:
            obj.__dict__[self.name] = v
        if ON[0]:
            self.writes += 1
            self.wq.add(Q[0])
            i = id(obj)
            self.unread.add(i)
            self.last = obj
            if v is None or v is True or v is False or type(v) in _NUM or (type(v) in _EMPTY and not v):
                self.trivial += 1
            elif i not in self.dirty:
                self.dirty.add(i)
                self.epochs += 1
            fr = sys._getframe(1)
            self.writers[fr.f_code, fr.f_lasti] += 1

    def __delete__(self, obj):
        if self.orig is not None:
            self.orig.__delete__(obj)
        else:
            try:
                del obj.__dict__[self.name]
            except KeyError:
                raise AttributeError(self.name) from None


_NUM = (int, float)
_EMPTY = (str, tuple, list, dict, set, frozenset)
_MUT = {"append", "add", "extend", "update", "insert", "clear", "discard", "remove", "appendleft", "setdefault"}
_kind = {}
_attrs = {}


def attr_kinds(fn):
    """{(lineno, col, end_lineno, end_col): kind} for every Attribute node of the file (see the module docstring)."""
    r = _attrs.get(fn)
    if r is not None:
        return r
    r = _attrs[fn] = {}
    try:
        tree = ast.parse(open(fn).read())
    except (OSError, SyntaxError, ValueError):
        return r
    par = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            par[c] = n
    for n in ast.walk(tree):
        if not isinstance(n, ast.Attribute):
            continue
        kind = "use"
        p = par.get(n)
        if isinstance(n.ctx, ast.Store) and isinstance(p, ast.AugAssign) and p.target is n:
            kind = "aug"
        else:
            cur = n
            while True:
                p = par.get(cur)
                if isinstance(p, ast.Subscript) and p.value is cur:
                    if not isinstance(p.ctx, ast.Load):
                        kind = "mut"
                        break
                    cur = p
                    continue
                if isinstance(p, ast.Attribute) and p.value is cur and p.attr in _MUT:
                    c = par.get(p)
                    if isinstance(c, ast.Call) and c.func is p:
                        if isinstance(par.get(c), ast.Expr):
                            kind = "mut"
                            break
                        if p.attr == "setdefault":
                            cur = c
                            continue
                break
        r[n.lineno, n.col_offset, n.end_lineno, n.end_col_offset] = kind
    return r


def read_kind(k, name):
    code, lasti = k
    kind = "use"
    try:
        op = code.co_code[lasti]
        if dis.opname[op] == "LOAD_ATTR" and code.co_names[code.co_code[lasti + 1] >> 1] == name:
            pos = next(x for j, x in enumerate(code.co_positions()) if j == lasti // 2)
            kind = attr_kinds(code.co_filename).get((pos[0], pos[2], pos[1], pos[3]), "use")
    except Exception:
        kind = "use"
    _kind[k, name] = kind
    return kind


def class_fields(path):
    """{class qualname: field names} by ast: __slots__, self.X targets in methods, annotated class-level names."""
    tree = ast.parse(open(path).read())
    res = {}

    def visit(node, prefix):
        for n in node.body:
            if isinstance(n, ast.ClassDef):
                q = prefix + n.name
                names = set()
                for b in n.body:
                    if isinstance(b, ast.AnnAssign) and isinstance(b.target, ast.Name):
                        names.add(b.target.id)
                    if isinstance(b, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__slots__" for t in b.targets):
                        try:
                            v = ast.literal_eval(b.value)
                            names.update([v] if isinstance(v, str) else v)
                        except Exception:
                            pass
                    if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)) and b.args.args:
                        me = b.args.args[0].arg
                        for w in ast.walk(b):
                            if isinstance(w, ast.Attribute) and isinstance(w.ctx, ast.Store) and isinstance(w.value, ast.Name) and w.value.id == me:
                                names.add(w.attr)
                res[q] = names
                visit(n, q + ".")
    visit(tree, "")
    return res


FIELDS = []
SKIPPED = []


def install_fields():
    mods = {}
    for m in list(sys.modules.values()):
        fn = getattr(m, "__file__", None)
        if fn and os.path.realpath(fn) in PATHS:
            mods[os.path.realpath(fn)] = m
    for p, f in PATHS.items():
        m = mods.get(p)
        if m is None:
            SKIPPED.append((f, "module not loaded"))
            continue
        for q, names in class_fields(p).items():
            cls = m
            for part in q.split("."):
                cls = getattr(cls, part, None) if cls is not None else None
            if not isinstance(cls, type):
                SKIPPED.append((f + ":" + q, "class not found"))
                continue
            for name in sorted(names):
                if name.startswith("__") and name.endswith("__"):
                    continue
                cur = cls.__dict__.get(name, _MISSING)
                if isinstance(cur, types.MemberDescriptorType):
                    d = Field(cls, name, cur, _MISSING)
                elif cur is _MISSING:
                    if not cls.__dictoffset__ or any(name in getattr(b, "__slots__", ()) for b in cls.__mro__[1:]):
                        SKIPPED.append((f"{f}:{q}.{name}", "slot of a base or no instance dict"))
                        continue
                    # sa-port-368: the name may be defined on a base (the class found under the module's name can be a
                    # replacement, e.g. backend.EUFTheory over the crate's sa_solver.EUFTheory, whose `rep`, `members`,
                    # `on_merge` and `_lims` are getset descriptors). A Field here would read the instance dict in front
                    # of the inherited descriptor and raise AttributeError where the class answers: not wrapped. An
                    # inherited plain constant stays the default of a read before the first write.
                    inh = next((b.__dict__[name] for b in cls.__mro__[1:] if name in b.__dict__), _MISSING)
                    if inh is not _MISSING and (hasattr(type(inh), "__get__") or hasattr(type(inh), "__set__")):
                        SKIPPED.append((f"{f}:{q}.{name}", "inherited " + type(inh).__name__))
                        continue
                    d = Field(cls, name, None, inh)
                elif isinstance(cur, (types.FunctionType, property, classmethod, staticmethod, Field)) or hasattr(cur, "__set__") or hasattr(type(cur), "__get__"):
                    SKIPPED.append((f"{f}:{q}.{name}", "class-level " + type(cur).__name__))
                    continue
                else:
                    if not cls.__dictoffset__:
                        SKIPPED.append((f"{f}:{q}.{name}", "class constant, no instance dict"))
                        continue
                    d = Field(cls, name, None, cur)     # a class-level default (dataclass default, constant)
                try:
                    setattr(cls, name, d)
                except (TypeError, AttributeError) as e:
                    SKIPPED.append((f"{f}:{q}.{name}", "cannot set: " + type(e).__name__))
                    continue
                d.key = f"{f}:{q}.{name}"
                FIELDS.append(d)


install_fields()

M.use_tool_id(TOOL, "cnt367")
M.register_callback(TOOL, M.events.PY_START, on_start)
M.register_callback(TOOL, M.events.PY_RETURN, on_return)
M.set_events(TOOL, M.events.PY_START | M.events.PY_RETURN)

ans = [None] * len(pairs)
ask = sympy_api.ask
gc.collect()
ON[0] = True
for i, (p, a) in enumerate(pairs):
    Q[0] = i
    try:
        r = ask(p, a)
        if r is not None and r is not True and r is not False:
            r = "non-bool " + repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as e:
        r = "raise " + type(e).__name__
    ans[i] = r
ON[0] = False
digest = hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16]


def site(k):
    code, lasti = k
    line = next((ln for s, e, ln in code.co_lines() if s <= lasti < e and ln is not None), code.co_firstlineno)
    return f"{short(code.co_filename)}:{line} {code.co_qualname}"


def via(k, name):
    code, lasti = k
    try:
        ins = next(x for x in dis.get_instructions(code) if x.offset == lasti)
    except StopIteration:
        return True
    return not (ins.opname in ("LOAD_ATTR", "LOAD_METHOD", "LOAD_SUPER_ATTR") and ins.argval == name)


def top(counter, n=40, f=site):
    agg = collections.Counter()
    for k, v in counter.items():
        agg[f(k)] += v
    return agg.most_common(n)


funcs = {}
for code, n in calls.items():
    k = f"{PATHS[os.path.realpath(code.co_filename)]}:{code.co_qualname}:{code.co_firstlineno}"
    funcs[k] = dict(calls=n, queries=len(callq[code]), discarded=sum(disc[code].values()), sites=top(sites[code]),
                    discarded_sites=top(disc[code]), generator=bool(code.co_flags & 0x2a0),
                    returns=any(x.opname == 'RETURN_VALUE' or (x.opname == 'RETURN_CONST' and x.argval is not None) for x in dis.get_instructions(code)))
fields = {}
for d in FIELDS:
    rd = collections.Counter()
    for k, v in d.readers.items():
        rd[site(k) + (" (via)" if via(k, d.name) else "") + {"use": "", "mut": " [mut]", "aug": " [aug]"}[_kind.get((k, d.name), "use")]] += v
    fields[d.key] = dict(writes=d.writes, reads=d.reads, read_writes=d.read_writes, wq=len(d.wq), rq=len(d.rq),
                         trivial=d.trivial, mut=d.mut, aug=d.aug, use=d.use, epochs=d.epochs, epochs_read=d.epochs_read,
                         slot=d.orig is not None, readers=rd.most_common(40), writers=top(d.writers, 12))

# ---- the plants: every counter shown to fire, outside the counted window -----------------------------------------------
plant = dict(functions={}, fields_ok=0, fields_no_object=[], failed=[])
Q[0] = -2
for p, f in PATHS.items():
    ns = {}
    exec(compile("def _planted367():\n    return 1\ndef _go367():\n    _planted367()\n    x = _planted367()\n    return x\n", p, "exec"), ns)
    pc = ns["_planted367"].__code__
    b = (calls[pc], sum(disc[pc].values()))
    ON[0] = True
    ns["_go367"]()
    ON[0] = False
    got = (calls[pc] - b[0], sum(disc[pc].values()) - b[1])
    plant["functions"][f] = got
    if got != (2, 1):
        plant["failed"].append(("function counter", f, got))
for d in FIELDS:
    o = d.last
    if o is None:
        plant["fields_no_object"].append(d.key)
        continue
    g = operator.attrgetter(d.name)
    try:
        ON[0] = True
        r0, u0 = d.reads, d.use
        exec(compile(f"o.{d.name}", "<plant367>", "exec"), {"o": o})
        r1 = d.reads
        g(o)
        r2 = d.reads
    except AttributeError:
        r1 = r2 = -1
    finally:
        ON[0] = False
    if (r1 - r0, r2 - r1) == (1, 1) and d.use - u0 == 2:
        plant["fields_ok"] += 1
    else:
        plant["failed"].append(("field counter", d.key, (r1 - r0, r2 - r1)))
M.set_events(TOOL, 0)
# the read kinds on a planted class: one use, one mut by subscript, one mut by method, one aug, a chain, a trivial write
_src = ("class _P367:\n    def __init__(self):\n        self.f = {}\n        self.n = 0\n        self.g = (1,)\n"
        "def _kinds367(o):\n    o.f[1] = 2\n    o.f.setdefault(3, []).append(4)\n    o.n += 1\n    x = o.f\n    y = o.f[1]\n    return o.g\n")
_pp = next(iter(PATHS)) + ".plant367.py"
open(_pp, "w").write(_src)
try:
    ns = {}
    exec(compile(_src, _pp, "exec"), ns)
    P = ns["_P367"]
    pf = {n: Field(P, n, None, _MISSING) for n in ("f", "n", "g")}
    for n, d in pf.items():
        setattr(P, n, d)
    ON[0] = True
    o = P()
    ns["_kinds367"](o)
    ON[0] = False
finally:
    os.unlink(_pp)
got = dict(f=(pf["f"].writes, pf["f"].trivial, pf["f"].mut, pf["f"].use, pf["f"].epochs, pf["f"].epochs_read),
           n=(pf["n"].writes, pf["n"].trivial, pf["n"].aug, pf["n"].use, pf["n"].epochs, pf["n"].epochs_read),
           g=(pf["g"].writes, pf["g"].trivial, pf["g"].use, pf["g"].epochs, pf["g"].epochs_read))
plant["kinds"] = got
if got != dict(f=(1, 1, 2, 2, 1, 1), n=(2, 2, 1, 0, 1, 0), g=(1, 0, 1, 1, 1)):
    plant["failed"].append(("read kinds", got))
row = dict(wl=wl, mode=mode, n=len(pairs), digest=digest, so=so, files=FILES,
           env={k: v for k, v in os.environ.items() if k.startswith("SLICE_") and k != "SLICE_DIR"},
           nfuncs=len(funcs), nfields=len(fields), skipped=SKIPPED, plant=plant)
json.dump(dict(row, funcs=funcs, fields=fields), open(out, "w"))
row["skipped"] = len(SKIPPED)
row["plant"] = dict(plant, fields_no_object=len(plant["fields_no_object"]))
print(json.dumps(row))
