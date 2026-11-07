"""A wrong cached class row: fresh.py in rust mode with SLICE_CONV_CACHE=1, one field of one class's cached row corrupted when it's
stored. The query that built the row sends the true one, so a planted row reaches Rust only by being served from the cache across
queries; `plant_hits` counts that. Usage: plant_row.py WORKLOAD OUT_PREFIX FIELD CLASSNAME."""
import json
import runpy
import sys

sys.path.insert(0, '.')
import p_install

p_install.install()
wl, pre, field, target = sys.argv[1:5]
import convert as C

assert C._CACHE == '1', 'run with SLICE_CONV_CACHE=1'
T_TUPLE, T_INT, T_TRUE, T_FALSE, T_RAT = C.T_TUPLE, C.T_INT, C.T_TRUE, C.T_FALSE, C.T_RAT


def skip(t, i):
    k = t[i]
    if k in (C.T_NONE, C.T_TRUE, C.T_FALSE, C.T_MISS):
        return i + 1
    if k == T_TUPLE:
        n, i = t[i + 1], i + 2
        for _ in range(n):
            i = skip(t, i)
        return i
    if k == T_RAT:
        return skip(t, skip(t, i + 1))
    return i + 2


def spans(t):
    """[start, end) of the row's 8 fields."""
    assert t[0] == T_TUPLE and t[1] == 8
    out, i = [], 2
    for _ in range(8):
        j = skip(t, i)
        out.append((i, j))
        i = j
    return out


NAMES = ('name', 'kind', 'rank', 'flags', 'class_key', 'templates', 'structural', 'custom_content')
FLAG_PLANTS = {'flags_number': 1 << 4, 'flags_plain_ops': C._PLAIN_OPS, 'flags_symbol': 1 << 8, 'flags_commfixed': 1 << 13}


def corrupt(e):
    tokens, patches = list(e[0]), list(e[1])
    s = spans(tokens)
    f = 'flags' if field in FLAG_PLANTS else field
    a, b = s[NAMES.index(f)]
    if f == 'name':
        patches = [(p, text + '_x') if p == a + 1 else (p, text) for p, text in patches]
    elif f == 'kind':
        tokens[a + 1] = C._KIND_INDEX['Other'] if tokens[a + 1] != C._KIND_INDEX['Other'] else C._KIND_INDEX['Add']
    elif f == 'rank':
        tokens[a + 1] += 1
    elif f == 'flags':
        tokens[a + 1] ^= FLAG_PLANTS[field]
    elif f == 'class_key':      # its first int
        assert tokens[a] == T_TUPLE and tokens[a + 2] == T_INT, tokens[a:b]
        tokens[a + 3] += 1
    elif f == 'templates':      # no templates
        tokens[a:b] = [T_TUPLE, 0]
        patches = [(p - (b - a - 2) if p >= b else p, x) for p, x in patches if not a <= p < b]
    else:
        tokens[a] = T_FALSE if tokens[a] == T_TRUE else T_TRUE
    return tokens, patches


real_store = C._store_row
planted = [0]


def store(cls, e):
    if cls.__name__ == target:
        planted[0] += 1
        e = corrupt(e)
    real_store(cls, e)


C._store_row = store


class Counting(dict):
    hits = 0

    def get(self, k, d=None):
        v = dict.get(self, k, d)
        if v is not None and k.__name__ == target:
            Counting.hits += 1
        return v


C._ROW_CACHE = Counting()
sys.argv = ['fresh.py', wl, 'rust', f'{pre}.txt', '--term', 'terms', '--lra', '--term-out', f'{pre}.json', '--handlers', f'{pre}.handlers']
rc, crash = 0, ''
try:
    runpy.run_path('fresh.py', run_name='__main__')
except SystemExit as e:
    rc = e.code or 0
except BaseException as e:
    rc, crash = 1, f'{type(e).__name__}: {e}'[:200]
json.dump(dict(field=field, target=target, wl=wl, stored=planted[0], plant_hits=Counting.hits, rc=rc, crash=crash), open(f'{pre}.plant', 'w'))
