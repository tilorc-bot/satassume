"""P7 review (issue #97): every fixed invariant repro still replays.

``EngineConfig.from_dict`` drops the settings removed in #97 P7 from a
recorded ``config``, but an I7 repro also names the setting in its
``variant`` (``check_I7`` does ``config.replace(**{name: value})`` and
``setattr(engine, name, value)``), so a recorded variant over a removed
setting raises ``TypeError`` instead of replaying.  Seen on
``harness/repros/invariants/fixed/I7-setting-changed-after-history-known.json``
at 511bd1c.
"""
import glob
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXED = sorted(glob.glob(os.path.join(ROOT, "harness", "repros", "invariants", "fixed", "*.json")))


@pytest.mark.parametrize("path", FIXED, ids=[os.path.basename(p)[:-5] for p in FIXED])
def test_fixed_invariant_repro_replays(path):
    from harness.invariants import replay
    sev, base, other = replay(path)      # must not raise; a fixed repro has no violation
    assert sev is None, (sev, base, other)
