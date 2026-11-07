"""fresh.py in rust mode with p_install ahead of it, as rust mode has, and the row cache's counts written after it.

Usage: fresh_arm.py WORKLOAD OUT_PREFIX. Switches come from the environment (SLICE_CONV_CACHE, SLICE_CONV_LAZY)."""
import json
import runpy
import sys

sys.path.insert(0, '.')
import p_install

p_install.install()
wl, pre = sys.argv[1], sys.argv[2]
sys.argv = ['fresh.py', wl, 'rust', f'{pre}.txt', '--term', 'terms', '--lra', '--term-out', f'{pre}.json',
            '--handlers', f'{pre}.handlers']
rc = 0
try:
    runpy.run_path('fresh.py', run_name='__main__')
except SystemExit as e:
    rc = e.code or 0
import convert

with open(f'{pre}.cache', 'w') as f:
    json.dump({'counts': convert.CACHE_COUNTS, 'size': len(convert._ROW_CACHE),
               'differs': [d[0] for d in convert.CACHE_DIFFERS[:50]],
               'epoch': convert.EPOCH[0]}, f)
sys.exit(rc)
