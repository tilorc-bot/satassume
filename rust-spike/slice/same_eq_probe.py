"""same_eq_probe.py: where wiring.py's Pow key met a base and an exponent that are equal and not one object (ruling Q1 (b),
issue 323, results/cbm-noid-cause.md). Before the ruling the key held `b is e` and the 'same' shape `a is not args[j]`; now
both are `==`, so exactly these events are where an answer can differ from the reference before the change. The only row
with a 'same' shape is Pow's (`_compiled_rows.py`), matched on the same two arguments, so the key's site covers both.

Reads wiring.py and changes nothing: `wiring.facts` is wrapped (the template looks the name up on each call).
  pytest -p same_eq_probe ...   one line per event with the test id, into $SLICE_SUITE_OUT/same_eq.PID.jsonl
  SAME_EQ_OUT=FILE python -c 'import same_eq_probe; same_eq_probe.install(); ...'   the same for a script (Python backend:
      under Rust, install only after the backend is in, as the pytest hook does)
The last line of each file is the totals: `pow` (Pow keys built: the probe was reached) and `events`."""
import atexit
import json
import os

STATE = dict(pow=0, events=0, out=None, on=False)


def _write(row):
    if STATE['out'] is None:
        path = os.environ.get('SAME_EQ_OUT') or os.path.join(os.environ['SLICE_SUITE_OUT'], f'same_eq.{os.getpid()}.jsonl')
        STATE['out'] = open(path, 'a', buffering=1)
    STATE['out'].write(json.dumps(row) + '\n')


def install():
    if STATE['on']:
        return
    STATE['on'] = True
    from satassume.knowledge.templates import wiring
    inner = wiring.facts

    def facts(key, build, consts, objs, n):
        if key and key[0] == 'pow':
            STATE['pow'] += 1
            if objs[0] is not objs[1] and objs[0] == objs[1]:
                STATE['events'] += 1
                _write(dict(test=os.environ.get('PYTEST_CURRENT_TEST', ''), base=str(objs[0]), cls=type(objs[0]).__name__,
                            same_class_object=type(objs[0]) is type(objs[1]), key_same=bool(key[3])))
        return inner(key, build, consts, objs, n)

    wiring.facts = facts
    atexit.register(lambda: _write(dict(total=dict(pow=STATE['pow'], events=STATE['events']))))


def pytest_sessionstart(session):
    install()
