"""Check registry.  A check is a function(design) -> iterable of Finding, registered with @check."""
from __future__ import annotations
import importlib
import pkgutil
from ..model import Finding

REGISTRY = {}


def check(id: str, family: str, needs_board: bool = False, doc: str = ''):
    def deco(fn):
        REGISTRY[id] = {'id': id, 'family': family, 'fn': fn, 'needs_board': needs_board,
                        'doc': doc or (fn.__doc__ or '').strip().split('\n')[0]}
        return fn
    return deco


def load_all():
    for m in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{m.name}")
    return REGISTRY


def F(check_id, severity, title, detail='', refs=(), nets=(), evidence=None, basis='', confidence='medium'):
    return Finding(check=check_id, severity=severity, title=title, detail=detail, refs=list(refs),
                   nets=list(nets), evidence=evidence or {}, basis=basis, confidence=confidence)
