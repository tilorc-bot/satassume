import json, sys
d = json.load(open(sys.argv[1]))
print(d['n'], 'queries', round(d['seconds'], 3), 's; None', d['n_none'], round(d['none_s'], 3), 's')
for s, v in sorted(d['agg'].items()):
    print(s)
    for k in ('pc', 'pf', 'fr', 'dn'):
        g = lambda x: v.get(k + '_' + x, 0)
        if not g('units'):
            continue
        print(f"  {k}: units {int(g('units'))} t {g('t'):.4f}s in {int(g('in'))} stored {int(g('stored'))} "
              f"emitted {int(g('emitted'))} ({g('emitted')/max(1,g('in')):.1%}) t_unemitted {g('t_unemitted'):.4f} "
              f"units_unhit {int(g('units_unhit'))} t_unit_unhit {g('t_unit_unhit'):.4f}"
              + (f" need_opt {int(g('need_opt'))} need_exact {int(g('need_exact'))} t_skip_opt {g('t_skip_opt'):.4f} t_skip_exact {g('t_skip_exact'):.4f}" if k in ('fr', 'dn') else ''))
