runs 104, digest mismatches: none

## dev: base 0.578 s (range 0.576-0.587), None 0.362 s, definite 0.215 s; n 1985, None 892

| mode | median s | vs base, paired | range s |
|---|---:|---:|---|
| base | 0.578 | +0.0% | 0.576-0.587 |
| bdry | 0.583 | +1.2% | 0.578-0.588 |
| fn | 0.603 | +4.2% | 0.600-0.605 |
| enc | 0.606 | +5.0% | 0.604-0.612 |
| dbl | 0.588 | +1.6% | 0.582-0.591 |
| samp | 0.613 | +6.2% | 0.612-0.618 |
| mon | 1.210 | +109.7% | 1.204-1.238 |

boundary calls {'ask': 776, 'is_': 275, 'is_many': 0, 'verdict': 64} = 1115, 0.56 per query

mon: interval inside 0.190 s, calibrated 0.095 s; interval outside 0.041 s. T(mon)-T(base) 0.633 s. calib ns: outer_iv 199, outer_all 1051, nested_all 413. n_outer in 282,918, nested in 89,125; n_outer out 28,793, unbalanced 0

overhead check: model 0.375 s, real 0.633 s, ratio 1.69. Interval inside minus the scaled charge: 0.033 s = 5.7% of base

| asked inside | calls | interval s | calibrated s | share of base |
|---|---:|---:|---:|---:|
| hash | 249,497 | 0.090 | 0.036 | 6.3% |
| eq | 3,726 | 0.004 | 0.003 | 0.5% |
| read | 14,596 | 0.007 | 0.003 | 0.6% |
| walk | 9,759 | 0.058 | 0.030 | 5.2% |
| construct | 1,215 | 0.010 | 0.007 | 1.2% |
| evaluate | 2,112 | 0.006 | 0.004 | 0.6% |
| order | 2,004 | 0.015 | 0.011 | 1.9% |
| other | 9 | 0.000 | 0.000 | 0.0% |

other: [('sympy/functions/elementary/exponential.py:ExpMeta.__instancecheck__', 1e-05)] 

behind the cache wrapper (side, function, calls, interval s): [[1, 'Basic.has', 2042, 0.01509], [1, 'AssocOp.__new__', 144, 0.00231], [0, 'Basic.has', 236, 0.00056], [1, 'Integer.__new__', 283, 0.0002]] 

top entries inside (function, calls, interval s, nested):
  sympy/core/basic.py:Basic.__hash__ 207,135 0.072 1,066
  sympy/core/basic.py:Basic.free_symbols 4,195 0.023 25,779
  sympy/core/cache.py:__cacheit.<locals>.func_wrapper.<locals>.wrapper 2,469 0.018 18,759
  sympy/core/expr.py:Expr.is_number 3,014 0.015 15,796
  sympy/core/sorting.py:default_sort_key 2,004 0.014 7,250
  sympy/core/numbers.py:Integer.__hash__ 36,843 0.010 0
  sympy/core/numbers.py:NumberSymbol.__hash__ 3,899 0.004 3,899
  sympy/core/assumptions.py:make_property.<locals>.getit 1,656 0.004 2,684
  sympy/core/basic.py:Basic.atoms 144 0.004 2,843
  sympy/core/basic.py:Basic.__eq__ 3,081 0.004 1,167
  sympy/assumptions/relation/binrel.py:BinaryRelation.__call__ 214 0.003 1,712
  sympy/core/numbers.py:Rational.__hash__ 1,256 0.002 2,512

thin call: hash layer calls 283,625; T(dbl)-T(base) 9.5 ms = 33 ns per call (one extra Python layer). hot hash(e) net of hash(int): Basic 36 ns, Integer 37 ns. Floor for hash inside: 249,497 x 36 ns = 0.009 s; calibrated 0.036 s

sampler, 3,495 samples: inside the boundary 92.7%; SymPy frames inside: raw 8.6%, corrected 3.7% (None 7.5/3.1, definite 10.3/4.7)

| group behind the boundary | calls (outermost) | None s | definite s | share of pass |
|---|---:|---:|---:|---:|
| templates | 4,964 | 0.002 | 0.001 | 0.5% |
| lra_read | 4,340 | 0.002 | 0.001 | 0.5% |
| euf_read | 3,595 | 0.005 | 0.004 | 1.6% |
| relation_read | 10,113 | 0.009 | 0.008 | 2.9% |
| struct | 3,515 | 0.089 | 0.038 | 21.0% |
| total | | 0.106 | 0.053 | 26.4% |

prepare_query all-in 0.098 s (16.2%, behind the boundary). Callbacks: facts_for 24, node_facts 0; Session._custom atoms 1,507 (not callbacks)

monfn: SymPy inside under fn groups 0.070 s (100,106 entries), not under them 0.027 s (182,812 entries): 27% not under

| encode what | s | share of base | per boundary call us | bytes per call | nodes per call |
|---|---:|---:|---:|---:|---:|
| q | 0.0053 | 0.92% | 4.8 | 132 | 3.1 |
| intern | 0.0029 | 0.51% | 2.6 | 57 | 0.2 |
| cl | 0.0067 | 1.16% | 6.0 | 121 | 4.0 |

### dev whole pass

| row | S | ceiling 1/S | at 10x | at 50x | k for 2x |
|---|---:|---:|---:|---:|---:|
| S0 outside the boundary only | 7.8% | 12.9x | 5.88x | 10.39x | 2.2 |
| S1 as it stands, low (sampler corrected) | 12.4% | 8.1x | 4.72x | 7.06x | 2.3 |
| S1 as it stands, sampler raw | 17.3% | 5.8x | 3.91x | 5.28x | 2.5 |
| S1 as it stands, high (calibrated) | 25.2% | 4.0x | 3.06x | 3.75x | 3.0 |
| S1 high + 50 ns per ask | 27.6% | 3.6x | 2.87x | 3.44x | 3.2 |
| S1 high + 200 ns per ask | 35.0% | 2.9x | 2.41x | 2.76x | 4.3 |
| S2 resolved, all asks free | 8.9% | 11.2x | 5.54x | 9.29x | 2.2 |
| S3 resolved, non-hash asks stay | 18.6% | 5.4x | 3.74x | 4.95x | 2.6 |
| S4 fn groups stay in Python | 39.6% | 2.5x | 2.19x | 2.45x | 5.8 |

### dev None answers

| row | S | ceiling 1/S | at 10x | at 50x | k for 2x |
|---|---:|---:|---:|---:|---:|
| S0 outside the boundary only | 8.3% | 12.1x | 5.73x | 9.89x | 2.2 |
| S1 as it stands, low (sampler corrected) | 12.1% | 8.3x | 4.78x | 7.21x | 2.3 |
| S1 as it stands, sampler raw | 16.5% | 6.1x | 4.02x | 5.50x | 2.5 |
| S1 as it stands, high (calibrated) | 23.8% | 4.2x | 3.18x | 3.95x | 2.9 |
| S1 high + 50 ns per ask | 25.9% | 3.9x | 3.00x | 3.65x | 3.1 |
| S1 high + 200 ns per ask | 32.1% | 3.1x | 2.57x | 2.99x | 3.8 |
| S2 resolved, all asks free | 9.3% | 10.7x | 5.44x | 8.98x | 2.2 |
| S3 resolved, non-hash asks stay | 18.0% | 5.6x | 3.82x | 5.10x | 2.6 |
| S4 fn groups stay in Python | 41.9% | 2.4x | 2.10x | 2.32x | 7.2 |

### dev definite answers

| row | S | ceiling 1/S | at 10x | at 50x | k for 2x |
|---|---:|---:|---:|---:|---:|
| S0 outside the boundary only | 6.7% | 15.0x | 6.25x | 11.71x | 2.2 |
| S1 as it stands, low (sampler corrected) | 12.6% | 8.0x | 4.70x | 6.99x | 2.3 |
| S1 as it stands, sampler raw | 18.1% | 5.5x | 3.80x | 5.05x | 2.6 |
| S1 as it stands, high (calibrated) | 27.2% | 3.7x | 2.90x | 3.49x | 3.2 |
| S1 high + 50 ns per ask | 30.3% | 3.3x | 2.68x | 3.16x | 3.5 |
| S1 high + 200 ns per ask | 39.5% | 2.5x | 2.20x | 2.46x | 5.7 |
| S2 resolved, all asks free | 8.0% | 12.5x | 5.81x | 10.14x | 2.2 |
| S3 resolved, non-hash asks stay | 19.3% | 5.2x | 3.65x | 4.77x | 2.6 |
| S4 fn groups stay in Python | 35.8% | 2.8x | 2.37x | 2.70x | 4.5 |

## fuzz: base 8.133 s (range 8.045-8.324), None 6.793 s, definite 1.339 s; n 3000, None 2387

| mode | median s | vs base, paired | range s |
|---|---:|---:|---|
| base | 8.133 | +0.0% | 8.045-8.324 |
| bdry | 8.126 | -0.2% | 8.055-8.168 |
| fn | 8.665 | +6.6% | 8.572-8.696 |
| enc | 8.302 | +1.8% | 8.196-8.378 |
| dbl | 8.206 | +0.7% | 8.166-8.380 |
| samp | 8.551 | +5.4% | 8.428-8.615 |
| mon | 19.883 | +144.6% | 19.689-20.020 |

boundary calls {'ask': 2812, 'is_': 169, 'is_many': 0, 'verdict': 315} = 3296, 1.10 per query

mon: interval inside 3.955 s, calibrated 1.931 s; interval outside 0.271 s. T(mon)-T(base) 11.751 s. calib ns: outer_iv 199, outer_all 1060, nested_all 416. n_outer in 5,946,572, nested in 1,947,625; n_outer out 126,779, unbalanced 0

overhead check: model 7.323 s, real 11.751 s, ratio 1.60. Interval inside minus the scaled charge: 0.756 s = 9.3% of base

| asked inside | calls | interval s | calibrated s | share of base |
|---|---:|---:|---:|---:|
| hash | 5,048,969 | 1.804 | 0.709 | 8.7% |
| eq | 172,391 | 0.352 | 0.195 | 2.4% |
| read | 410,716 | 0.155 | 0.066 | 0.8% |
| walk | 230,997 | 1.064 | 0.539 | 6.6% |
| construct | 20,607 | 0.289 | 0.207 | 2.5% |
| evaluate | 10,764 | 0.016 | 0.011 | 0.1% |
| order | 52,126 | 0.275 | 0.210 | 2.6% |
| other | 0 | 0.000 | 0.000 | 0.0% |

behind the cache wrapper (side, function, calls, interval s): [[1, 'Basic.has', 45434, 0.26719], [0, 'Basic.has', 196, 0.00072], [1, 'Integer.__new__', 142, 0.0001]] 

top entries inside (function, calls, interval s, nested):
  sympy/core/basic.py:Basic.__hash__ 3,975,266 1.383 22,425
  sympy/core/expr.py:Expr.is_number 74,174 0.399 429,163
  sympy/core/basic.py:Basic.free_symbols 88,384 0.354 371,490
  sympy/core/basic.py:Basic.__eq__ 114,934 0.292 266,956
  sympy/core/numbers.py:Integer.__hash__ 996,489 0.276 0
  sympy/core/sorting.py:default_sort_key 52,126 0.272 130,255
  sympy/core/cache.py:__cacheit.<locals>.func_wrapper.<locals>.wrapper 45,576 0.267 312,576
  sympy/core/decorators.py:_SympifyWrapper.make_wrapped.<locals>._func 3,098 0.183 130,097
  sympy/core/numbers.py:Rational.__hash__ 77,064 0.130 154,128
  sympy/core/basic.py:Basic.args 212,596 0.059 0
  sympy/assumptions/relation/binrel.py:BinaryRelation.__call__ 2,908 0.047 23,264
  sympy/utilities/decorator.py:memoize_property.<locals>.accessor 65,877 0.035 0

thin call: hash layer calls 5,405,315; T(dbl)-T(base) 59.4 ms = 11 ns per call (one extra Python layer). hot hash(e) net of hash(int): Basic 36 ns, Integer 36 ns. Floor for hash inside: 5,048,969 x 36 ns = 0.183 s; calibrated 0.709 s

sampler, 50,619 samples: inside the boundary 97.4%; SymPy frames inside: raw 12.4%, corrected 5.3% (None 12.0/5.1, definite 14.4/6.3)

| group behind the boundary | calls (outermost) | None s | definite s | share of pass |
|---|---:|---:|---:|---:|
| templates | 33,074 | 0.017 | 0.003 | 0.2% |
| lra_read | 105,863 | 0.047 | 0.011 | 0.7% |
| euf_read | 93,889 | 0.245 | 0.047 | 3.4% |
| relation_read | 215,896 | 0.318 | 0.071 | 4.5% |
| struct | 19,107 | 0.663 | 0.182 | 9.7% |
| total | | 1.290 | 0.314 | 18.5% |

prepare_query all-in 2.261 s (26.1%, behind the boundary). Callbacks: facts_for 0, node_facts 0; Session._custom atoms 36,397 (not callbacks)

monfn: SymPy inside under fn groups 1.418 s (2,232,504 entries), not under them 0.543 s (3,714,066 entries): 28% not under

| encode what | s | share of base | per boundary call us | bytes per call | nodes per call |
|---|---:|---:|---:|---:|---:|
| q | 0.0320 | 0.39% | 9.7 | 267 | 6.4 |
| intern | 0.0155 | 0.19% | 4.7 | 118 | 0.8 |
| cl | 0.0665 | 0.82% | 20.2 | 538 | 15.7 |

### fuzz whole pass

| row | S | ceiling 1/S | at 10x | at 50x | k for 2x |
|---|---:|---:|---:|---:|---:|
| S0 outside the boundary only | 2.6% | 37.9x | 8.08x | 21.80x | 2.1 |
| S1 as it stands, low (sampler corrected) | 8.3% | 12.0x | 5.72x | 9.86x | 2.2 |
| S1 as it stands, sampler raw | 15.4% | 6.5x | 4.19x | 5.84x | 2.4 |
| S1 as it stands, high (calibrated) | 26.8% | 3.7x | 2.93x | 3.54x | 3.2 |
| S1 high + 50 ns per ask | 30.4% | 3.3x | 2.67x | 3.14x | 3.6 |
| S1 high + 200 ns per ask | 41.4% | 2.4x | 2.12x | 2.35x | 6.8 |
| S2 resolved, all asks free | 3.5% | 28.9x | 7.63x | 18.55x | 2.1 |
| S3 resolved, non-hash asks stay | 16.1% | 6.2x | 4.08x | 5.62x | 2.5 |
| S4 fn groups stay in Python | 28.1% | 3.6x | 2.83x | 3.38x | 3.3 |

### fuzz None answers

| row | S | ceiling 1/S | at 10x | at 50x | k for 2x |
|---|---:|---:|---:|---:|---:|
| S0 outside the boundary only | 2.2% | 45.1x | 8.34x | 23.96x | 2.0 |
| S1 as it stands, low (sampler corrected) | 7.7% | 13.1x | 5.92x | 10.53x | 2.2 |
| S1 as it stands, sampler raw | 14.6% | 6.9x | 4.33x | 6.14x | 2.4 |
| S1 as it stands, high (calibrated) | 25.4% | 3.9x | 3.04x | 3.72x | 3.0 |
| S1 high + 50 ns per ask | 28.9% | 3.5x | 2.77x | 3.29x | 3.4 |
| S1 high + 200 ns per ask | 39.6% | 2.5x | 2.19x | 2.45x | 5.8 |
| S2 resolved, all asks free | 3.0% | 33.1x | 7.86x | 20.16x | 2.1 |
| S3 resolved, non-hash asks stay | 15.2% | 6.6x | 4.23x | 5.92x | 2.4 |
| S4 fn groups stay in Python | 26.8% | 3.7x | 2.93x | 3.54x | 3.2 |

### fuzz definite answers

| row | S | ceiling 1/S | at 10x | at 50x | k for 2x |
|---|---:|---:|---:|---:|---:|
| S0 outside the boundary only | 4.7% | 21.4x | 7.04x | 15.19x | 2.1 |
| S1 as it stands, low (sampler corrected) | 11.5% | 8.7x | 4.91x | 7.52x | 2.3 |
| S1 as it stands, sampler raw | 19.6% | 5.1x | 3.62x | 4.71x | 2.6 |
| S1 as it stands, high (calibrated) | 33.7% | 3.0x | 2.48x | 2.86x | 4.1 |
| S1 high + 50 ns per ask | 37.9% | 2.6x | 2.27x | 2.55x | 5.1 |
| S1 high + 200 ns per ask | 50.6% | 2.0x | 1.80x | 1.94x | inf |
| S2 resolved, all asks free | 5.6% | 18.0x | 6.66x | 13.42x | 2.1 |
| S3 resolved, non-hash asks stay | 20.7% | 4.8x | 3.49x | 4.48x | 2.7 |
| S4 fn groups stay in Python | 34.7% | 2.9x | 2.43x | 2.78x | 4.3 |

second batch: runs 30, digest mismatches: none

### dev: out 0.593 s, vs base paired +2.9%

| outside the boundary | calls | None s | definite s | share of pass |
|---|---:|---:|---:|---:|
| conversion | 2,004 | 0.0061 | 0.0035 | 1.63% |
| relevance | 989 | 0.0042 | 0.0051 | 1.56% |
| consistency | 106 | 0.0001 | 0.0002 | 0.06% |
| precheck | 1,221 | 0.0029 | 0.0032 | 1.03% |
| rest (ask, memo lookups, replay loop) | | | | 4.59% |
| total outside | | | | 8.86% |

inside, any depth: [('Basic.__new__', 431), ('AppliedPredicate.__new__', 214), ('AssocOp.__new__', 26), ('Float.__new__', 26), ('DefinedFunction.__new__', 14), ('Application.__new__', 14), ('Integer._eval_is_odd', 6), ('Rational.__new__', 5), ('Integer._eval_is_prime', 4), ('Expr._eval_is_extended_positive_negative', 4)] 

top callers inside: [('<string>:__create_fn__.<locals>.__hash__', 'Basic.__hash__', 61553), ('<string>:__create_fn__.<locals>.__hash__', 'Integer.__hash__', 24532), ('engine.py:Session.ensure', 'Basic.__hash__', 17530), ('engine.py:Session.node', 'Basic.__hash__', 16278), ('sat/theory.py:EqualitySharing.update', 'Basic.__hash__', 9742), ('engine.py:Session._compile_patterns', 'Basic.__hash__', 8480), ('knowledge/compile.py:VarTable.node_base', 'Basic.__hash__', 8008), ('engine.py:Session._discover', 'Basic.__hash__', 7028)] 

### fuzz: out 8.156 s, vs base paired +1.3%

| outside the boundary | calls | None s | definite s | share of pass |
|---|---:|---:|---:|---:|
| conversion | 6,068 | 0.0521 | 0.0143 | 0.81% |
| relevance | 2,938 | 0.0471 | 0.0139 | 0.75% |
| consistency | 315 | 0.0007 | 0.0003 | 0.01% |
| precheck | 2,998 | 0.0225 | 0.0055 | 0.34% |
| rest (ask, memo lookups, replay loop) | | | | 1.05% |
| total outside | | | | 2.97% |

inside, any depth: [('Basic.__new__', 9457), ('AppliedPredicate.__new__', 2908), ('AssocOp.__new__', 1829), ('Integer.__new__', 33), ('Float.__new__', 16), ('DefinedFunction.__new__', 10), ('Application.__new__', 10), ('Expr._eval_is_extended_positive_negative', 10), ('Number._eval_evalf', 10), ('Expr._eval_is_extended_positive', 9)] 

top callers inside: [('<string>:__create_fn__.<locals>.__hash__', 'Basic.__hash__', 1136802), ('<string>:__create_fn__.<locals>.__hash__', 'Integer.__hash__', 653949), ('engine.py:Session.ensure', 'Basic.__hash__', 319646), ('engine.py:Session.node', 'Basic.__hash__', 255688), ('sat/theory.py:EqualitySharing.update', 'Basic.__hash__', 226857), ('theories/lra/lra.py:LRATheory._lin', 'Basic.__hash__', 187821), ('theories/lra/lra_adapter.py:_memoized', 'Basic.__hash__', 169950), ('relations.py:Relations._tsource', 'Basic.__hash__', 157354)] 

