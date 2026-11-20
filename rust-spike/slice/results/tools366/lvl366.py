"""lvl366.py DIFF359 WL OUT.jsonl (sa-port-366, issue 323; step 2 of the per-term level's removal): tools359/diff359.py's
pass, unchanged, with the walkers' reference to `constructed_noncommutative` (convert.py's module global, which Python's
walker calls by name and Rust's WalkCtx copies when term_live.from_env() builds it) replaced by a counting wrapper as
`convert` finishes executing, so it is in before either walker can read it. The engine's own on-demand read
(engine._construction_level imports the function from satassume.knowledge.domain) is not wrapped and not counted.

Per call of convert.convert (in order; diff359.py's `cv` lists them per query, so the two files join by position):
calls = the walkers' level calls in that conversion, raised = how many of them raised and the exception types,
init = 1 if one of them first filled domain._UNDEFINED_KEYS (the function's only write: a constant, filled once a process).
Written to OUT.lvl.jsonl with a last line of totals. On a tree without the global (the removal), present is false and
every count is 0. LVL366_PLANT=N makes the Nth counted call raise RuntimeError('lvl366 plant'): the proof that `raised`
can fire, and what a raise in the level would have done to the query (read it in OUT.jsonl)."""
import importlib.abc, importlib.util, json, os, runpy, sys
diff, wl, out = sys.argv[1:4]
PLANT = int(os.environ.get("LVL366_PLANT", "0"))
recs, cur, tot = [], [None], dict(calls=0, raised=0, init=0, outside=0, present=None)


def patch(module):
    real = module.__dict__.get("constructed_noncommutative")
    tot["present"] = real is not None
    if real is None:
        real_convert = module.convert
    else:
        import satassume.knowledge.domain as D

        def level(t):
            tot["calls"] += 1
            r = cur[0]
            if r is None:
                tot["outside"] += 1
            else:
                r["calls"] += 1
            unset = D._UNDEFINED_KEYS is None
            try:
                if PLANT and tot["calls"] == PLANT:
                    raise RuntimeError("lvl366 plant")
                return real(t)
            except BaseException as e:
                tot["raised"] += 1
                if r is not None:
                    r["raised"] += 1
                    r["types"].append(type(e).__name__)
                raise
            finally:
                if unset and D._UNDEFINED_KEYS is not None:
                    tot["init"] += 1
                    if r is not None:
                        r["init"] += 1

        module.constructed_noncommutative = level
        real_convert = module.convert

    def convert(*a, **k):
        outer = cur[0]
        r = cur[0] = dict(calls=0, raised=0, init=0, types=[], nested=outer is not None)
        recs.append(r)
        try:
            return real_convert(*a, **k)
        finally:
            cur[0] = outer

    module.convert = convert


class Loader(importlib.abc.Loader):
    def __init__(self, inner):
        self.inner = inner

    def create_module(self, spec):
        return self.inner.create_module(spec)

    def exec_module(self, module):
        self.inner.exec_module(module)
        patch(module)


class Finder(importlib.abc.MetaPathFinder):
    busy = False

    def find_spec(self, name, path=None, target=None):
        if name != "convert" or Finder.busy:
            return None
        Finder.busy = True
        try:
            spec = importlib.util.find_spec(name)
        finally:
            Finder.busy = False
        spec.loader = Loader(spec.loader)
        return spec


sys.meta_path.insert(0, Finder())
sys.argv = [diff, wl, out]
try:
    runpy.run_path(diff, run_name="__main__")
finally:
    with open(out[:-6] + ".lvl.jsonl", "w") as f:
        for r in recs:
            f.write(json.dumps([r["calls"], r["raised"], r["init"], r["types"], r["nested"]]) + "\n")
        f.write(json.dumps(dict(total=1, wl=wl, conversions=len(recs), plant=PLANT, **tot)) + "\n")
