# Augmenting declarations for the optional compiled build (setup.py): Cython
# reads this next to engine.py; pure Python ignores it.  Types only, no logic.
import cython

cdef class Session:
    cdef object __weakref__     # Relations keeps a weak reference to its session
    cdef public object engine, scope, solver, table, frontier, verdict, relations
    cdef public object assumption_formula, _a_raw, _a_zs, _a_under, _a_all, _a_atoms
    cdef public object xfer, sel, _neg_shared
    cdef public dict base, pending, pending_c, demand, literals, defvars, _dv, _dv_node
    cdef public dict _groups
    cdef public list deferred
    cdef public bint _link_pending, truncated
    cdef public Py_ssize_t n_hold

    @cython.locals(base_of=dict, demand=dict, bases=list, new=list, k=Py_ssize_t)
    cpdef _compile_patterns(self, node, compiled, demanded)
