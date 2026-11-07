"""live.py's own run with the shadow on: term_shadow_live.py SHADOW.json WL py OUT [live.py args].
The answers sha it prints must equal live.py's without the shadow, which is what shows the reads don't move the query."""
import os
import runpy
import sys

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
import term_shadow

out = sys.argv[1]
term_shadow.install()
sys.argv = ['live.py'] + sys.argv[2:]
try:
    runpy.run_path(os.path.join(here, 'live.py'), run_name='__main__')
finally:
    term_shadow.report(out)
