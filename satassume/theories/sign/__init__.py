"""Class propagators for ``Add`` and ``Mul`` of any arity (issue #149).
:mod:`.lattice` is the shared SymPy-free machinery (a lattice of atoms with
an operation table, and the theory over it); :mod:`.sign` is SIGN (sign x
zero x finiteness, proposal T1) and :mod:`.closure` CLOSURE (membership in
``Z``, ``Q``, the algebraic numbers, ``R``, ``C``, proposal T3);
:mod:`.sign_adapter` and :mod:`.closure_adapter` map session nodes onto
them."""
