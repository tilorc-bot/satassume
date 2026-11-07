"""tests_offline.py: component D. Reproducible across hash seeds, read whole by Rust, refused on any mismatch."""
import hashlib, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sa_solver, sympy  # noqa: E402
import gen_offline_data as G  # noqa: E402

FILE, ROOT, V = G.DEFAULT_OUT, G.ROOT, sympy.__version__


def refused(path, root=ROOT, ver=V):
    try:
        sa_solver.OfflineData(path, root, ver)
    except ValueError as e:
        return str(e)
    return None


def main():
    n = 0
    for seed in ("0", "1", "2", "3", "77", "4242"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        r = subprocess.run([sys.executable, os.path.join(HERE, "gen_offline_data.py"), "--check"], env=env,
                           capture_output=True, text=True)
        assert r.returncode == 0, (seed, r.stdout, r.stderr[-300:])
        n += 1
    print("reproducible: same bytes as the committed file under", n, "hash seeds")
    for s in (b"", b"abc", b"x" * 119, b"y" * 1000):
        assert sa_solver.sha256_hex(s) == hashlib.sha256(s).hexdigest()
    d = sa_solver.OfflineData(FILE, ROOT, V)
    raw = open(FILE, "rb").read().split(b"\n")
    assert d.roundtrip().encode() == raw[1], "Rust didn't read the whole body back"
    from satassume.knowledge.rules import BASIS
    assert tuple(d.basis()) == BASIS
    print("read: Rust wrote back", len(raw[1]), "body bytes identically; BASIS agrees")
    tmp = tempfile.mkdtemp()
    try:
        def variant(name, f):
            p = os.path.join(tmp, name)
            with open(p, "wb") as o:
                o.write(f(open(FILE, "rb").read()))
            return p
        h = json.loads(raw[0])
        cases = {
            "one body byte": variant("a", lambda b: b[:-2] + bytes([b[-2] ^ 1]) + b[-1:]),
            "format": variant("b", lambda b: b.replace(b'"format":1', b'"format":2', 1)),
            "body hash": variant("c", lambda b: b.replace(h["body_sha256"].encode(), b"0" * 64, 1)),
            "source list": variant("d", lambda b: b.replace(h["sources"][0][1].encode(), b"0" * 64, 1)),
            "truncated": variant("e", lambda b: b[:len(b) // 2]),
            "no header": variant("f", lambda b: b""),
        }
        for name, p in cases.items():
            why = refused(p)
            assert why, name
            print(f"refused, {name}: {why}")
        assert "SymPy" in refused(FILE, ver="0.0"), "a different SymPy"
        print("refused, other SymPy")
        # a changed source, with the file itself untouched
        rel = h["sources"][0][0]
        root = os.path.join(tmp, "root")
        for r, _ in h["sources"]:
            os.makedirs(os.path.dirname(os.path.join(root, r)), exist_ok=True)
            shutil.copy(os.path.join(ROOT, r), os.path.join(root, r))
        assert refused(FILE, root) is None
        with open(os.path.join(root, rel), "ab") as o:
            o.write(b"\n# edited\n")
        why = refused(FILE, root)
        assert why and rel in why
        print("refused, source edited:", why)
    finally:
        shutil.rmtree(tmp)
    print("ALL PASS")


main()
