# Augmenting declarations for the optional compiled build (setup.py): Cython
# reads this next to lra.py; pure Python ignores it.  Types only, no logic.
import cython

cdef class LRATheory:
    cdef dict __dict__          # subclass and test attributes
    cdef public object eager, _cagg
    cdef public bint gave_up, exhausted, branched_rational, _fields
    cdef public dict _cert, _var_of, _slack_of, _forms, _rows, _atoms, _ground
    cdef public dict _assigned, _ints, _ints_on, _int_memo, stats
    cdef public list _key, _lo, _up, _lo_r, _up_r, _vq, _vd, _cols, _atoms_on
    cdef public list _diseqs, _int_lits, _trail, _lims, _pending_ground
    cdef public set _dirty

    @cython.locals(trail=list, n=Py_ssize_t, tag=Py_ssize_t)
    cpdef _undo_to(self, Py_ssize_t n)

    @cython.locals(rows=dict, lo=list, up=list, vq=list, vd=list, row=dict,
                   leave=Py_ssize_t, below=bint, b=Py_ssize_t, enter=Py_ssize_t,
                   j=Py_ssize_t, inc=bint, expl=list)
    cpdef _simplex(self)

    @cython.locals(rows=dict, cols=list, row=dict, newrow=dict, cj=set, rr=dict,
                   k=Py_ssize_t, r=Py_ssize_t)
    cpdef _pivot_rational(self, Py_ssize_t b, Py_ssize_t j)

    @cython.locals(out=list, assigned=dict, ints_on=dict, v=Py_ssize_t,
                   a=Py_ssize_t, lit=Py_ssize_t)
    cpdef propagate(self)

    @cython.locals(a=Py_ssize_t)
    cpdef assert_lit(self, Py_ssize_t literal)
