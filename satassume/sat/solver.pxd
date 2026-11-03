# Augmenting declarations for the optional compiled build (setup.py): Cython
# reads this next to solver.py; pure Python ignores it.  Types only, no logic.
import cython

cdef class Solver:
    cdef dict __dict__          # tunables set per instance; subclass attributes
    # per literal / per variable
    cdef public list _val, _watches, _level, _reason, _act, _polarity, _hpos, _seen
    cdef public list _heap, _trail, _trail_lim, _clauses, _learnts, _conflict
    cdef public list _rb_base, _rb_mask, _rb_ment, _rb_saved, _rb_cl, _rb_undo, _rb_ulim
    cdef public list _theories, _tprops, _tdecides, _rb_bases, _ring
    cdef public dict _tmap, _cowner, _uowner, _cante
    cdef public bytearray _ment, _lazy
    cdef public object _assumptions, _mvals, _mdict, _witness, _acache, _held
    cdef public object _tmodels, _rbc, _rb_clauses, owner, _max_learnts
    cdef public bint _ok, _tpending, track_owners
    cdef public double _var_inc, _cla_inc
    cdef public Py_ssize_t _qhead, _nvars, _stamp, _scan, _thead, _uid
    cdef public Py_ssize_t _rb_n, _rb_blocks, _rb_nclauses
    cdef public Py_ssize_t _n_props, _n_conflicts, _n_decisions, _n_learned
    cdef public Py_ssize_t _n_restarts, _n_reductions, _n_late, _n_late_written
    cdef public Py_ssize_t _n_ring_hits, _n_tdecisions, _n_registered

    @cython.locals(hpos=list, heap=list)
    cpdef _heap_insert(self, Py_ssize_t v)

    @cython.locals(heap=list, hpos=list, act=list, v=Py_ssize_t, a=double,
                   p=Py_ssize_t, pv=Py_ssize_t)
    cpdef _heap_up(self, Py_ssize_t i)

    @cython.locals(heap=list, hpos=list, act=list, n=Py_ssize_t, v=Py_ssize_t,
                   a=double, c=Py_ssize_t, r=Py_ssize_t, cv=Py_ssize_t)
    cpdef _heap_down(self, Py_ssize_t i)

    @cython.locals(heap=list, hpos=list, v=Py_ssize_t, last=Py_ssize_t)
    cpdef _heap_pop(self)

    @cython.locals(act=list, a=double, u=Py_ssize_t)
    cpdef _bump_var(self, Py_ssize_t v)

    @cython.locals(val=list, level=list, out=list, l=Py_ssize_t)
    cpdef _add_lits(self, raw, bint clean)

    # m is both a block mask and a clause length here: left a Python object
    @cython.locals(val=list, watches=list, trail=list, level=list, reason=list,
                   rb_base=list, rb_mask=list, rb_ment=list, rb_saved=list,
                   rb_undo=list, rb_cl=list, memo=dict, bits=dict, BIT=tuple,
                   uid=Py_ssize_t, qhead=Py_ssize_t, dl=Py_ssize_t, nprops=Py_ssize_t,
                   p=Py_ssize_t, pv=Py_ssize_t, fl=Py_ssize_t, ws=list, n=Py_ssize_t,
                   i=Py_ssize_t, j=Py_ssize_t, k=Py_ssize_t, l=Py_ssize_t,
                   first=Py_ssize_t, v=Py_ssize_t)
    cpdef _propagate(self)

    @cython.locals(val=list, watches=list, trail=list, level=list, reason=list,
                   qhead=Py_ssize_t, dl=Py_ssize_t, nprops=Py_ssize_t,
                   p=Py_ssize_t, fl=Py_ssize_t, ws=list, n=Py_ssize_t,
                   i=Py_ssize_t, j=Py_ssize_t, k=Py_ssize_t, m=Py_ssize_t,
                   l=Py_ssize_t, first=Py_ssize_t, v=Py_ssize_t)
    cpdef _propagate_clauses(self)

    @cython.locals(trail_lim=list, trail=list, val=list, pol=list, hpos=list,
                   start=Py_ssize_t, i=Py_ssize_t, l=Py_ssize_t, v=Py_ssize_t,
                   undo=list, k=Py_ssize_t, rb_mask=list, rb_cl=list, b=Py_ssize_t)
    cpdef _backtrack(self, Py_ssize_t lvl)
