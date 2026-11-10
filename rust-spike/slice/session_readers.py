"""session_readers.py OUT.json WL MODE [live.py args...]: Python reads and writes of Session attributes, by caller.

State part 3, sub-part 3 (the Session/solver boundary; OWED [100], [106]): which Python code still reads `Session.solver`
(and the other attributes named in SESSION_READERS) during one live.py pass, filed by the reading frame (`file:function`)
and by the query it ran under (`converted`, `kept:<reason>`, `noquery`, read from term_live's stack top as pycalls.py does).
Each attribute becomes a class-level property storing in the instance's `__dict__` under `_sr_<name>`, before any session.
"""
import json
import os
import runpy
import sys
from collections import Counter

NAMES = os.environ.get('SESSION_READERS', 'solver:truncated:verdict').split(':')


def main():
    out, rest = sys.argv[1], sys.argv[2:]
    if 'rust' in rest[1:2] and os.environ.get('SLICE_TRANSFER') != 'py':    # live.py's own first step, idempotent
        import p_install
        p_install.install()
    from satassume import engine
    reads, writes = Counter(), Counter()

    def state():
        m = getattr(sys.modules.get('term_live'), '_local', None)
        st = getattr(m, 'stack', None)
        if not st:
            return 'noquery'
        k = st[-1].kept
        return 'converted' if k is None else 'kept:' + str(k)

    def where():
        f = sys._getframe(2)
        return os.path.basename(f.f_code.co_filename) + ':' + f.f_code.co_qualname

    def prop(n):
        key = '_sr_' + n

        def get(self):
            reads[(n, where(), state())] += 1
            try:
                return self.__dict__[key]
            except KeyError:
                raise AttributeError(n) from None

        def set_(self, v):
            writes[(n, where(), state())] += 1
            self.__dict__[key] = v
        return property(get, set_)
    for n in NAMES:
        assert n not in engine.Session.__dict__, n
        setattr(engine.Session, n, prop(n))
    sys.argv = ['live.py'] + rest
    try:
        runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'live.py'), run_name='__main__')
    except SystemExit:
        pass

    def table(c):
        return [[n, w, s, k] for (n, w, s), k in sorted(c.items(), key=lambda t: (-t[1], t[0]))]
    with open(out, 'w') as fh:
        json.dump({'argv': rest, 'reads': table(reads), 'writes': table(writes)}, fh, indent=1)


if __name__ == '__main__':
    main()
