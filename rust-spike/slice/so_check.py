"""`-p so_check`: which sa_solver a run loaded, so a plant's column can't be void."""
import hashlib, os
def pytest_sessionfinish(session):
    import sa_solver
    d = os.environ.get('SLICE_SUITE_OUT')
    if d:
        with open(os.path.join(d, 'so.%d.txt' % os.getpid()), 'w') as f:
            f.write(sa_solver.__file__ + ' ' + hashlib.sha256(open(sa_solver.__file__, 'rb').read()).hexdigest() + '\n')
