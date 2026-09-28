#!/usr/bin/env python

from functools import partial, reduce
from itertools import repeat

def safe_call(f, x):
    return f(x) if x is not None else None

def apply(x, f):
    return safe_call(f, x)

def sequential(funcs):
    return partial(reduce, apply, funcs)

def juxt(funcs, x):
    def inner(x):
        return tuple(map(apply, repeat(x), funcs))
    return safe_call(inner, x)

def parallel(funcs):
    return partial(juxt, funcs)

def branch(pred, f, g):
    def h(x):
        def choose(x):
            if pred(x):
                return f(x)
            return g(x)
        return safe_call(choose, x)
    return h
