"""Part models: per-component facts extracted from datasheets, stored as YAML."""
from __future__ import annotations
import fnmatch
import glob
import os
import yaml
from ..model import Design, Component
from ..classify import pin_aliases, norm_pin_name, guess_role

PARTS_DIR = os.path.join(os.path.dirname(__file__), 'parts')


def load_models(extra_dirs=()):
    models = []
    for dname in [PARTS_DIR, *extra_dirs]:
        for f in sorted(glob.glob(os.path.join(dname, '**', '*.yaml'), recursive=True)):
            with open(f) as fh:
                for doc in yaml.safe_load_all(fh):
                    if doc:
                        doc['_file'] = os.path.relpath(f, os.path.dirname(PARTS_DIR))
                        models.append(doc)
    return models


def _match(model, c: Component) -> int:
    """0 = no match; higher = more specific."""
    m = model.get('match', {})
    lcsc = c.props.get('LCSC') or c.props.get('LCSC Part') or c.props.get('JLCPCB') or ''
    if lcsc and lcsc in (m.get('lcsc') or []):
        return 4
    fields = [c.value, c.props.get('MPN', ''), c.props.get('Part Number', ''), c.props.get('Mfr. Part', ''),
              c.props.get('Manufacturer_Part_Number', '')]
    for pat in m.get('value') or []:
        if any(f and fnmatch.fnmatchcase(f.upper(), pat.upper()) for f in fields):
            return 3
    part = c.lib_id.split(':')[-1]
    for pat in m.get('lib') or []:
        if fnmatch.fnmatchcase(part.upper(), pat.upper()) or fnmatch.fnmatchcase(c.lib_id.upper(), pat.upper()):
            return 2 if c.value.upper() == part.upper() or not (m.get('value')) else 1
    return 0


def find_pin_spec(model, pin):
    specs = model.get('pins') or {}
    if pin.number in specs and isinstance(specs[pin.number], dict) and specs[pin.number].get('_by') == 'number':
        return specs[pin.number]
    aliases = pin_aliases(pin.name)
    for key, spec in specs.items():
        k = str(key)
        if k.startswith('#'):
            if k[1:] == pin.number:
                return spec
            continue
        if norm_pin_name(k) in aliases or (pin_aliases(k) & aliases):
            return spec
    return None


def apply_models(d: Design, models):
    unmatched = []
    for c in d.components.values():
        best, score = None, 0
        for m in models:
            s = _match(m, c)
            if s > score:
                best, score = m, s
        c.model = best
        if best and best.get('kind'):
            c.kind = best['kind']
        for p in c.pins.values():
            spec = find_pin_spec(best, p) if best else None
            if spec:
                p.spec = spec
                p.role = spec.get('role', '')
            elif not best or best.get('guess_roles', False):
                p.role = guess_role(p)
        if best is None and c.kind == 'IC':
            for p in c.pins.values():
                p.role = p.role or guess_role(p)
            unmatched.append(c)
    return unmatched


def supply_spec(c: Component, pin):
    """The model's supply entry that covers this pin, if any."""
    if not c.model:
        return None
    aliases = pin_aliases(pin.name)
    for s in c.model.get('supplies') or []:
        for name in s.get('pins', []):
            n = str(name)
            if (n.startswith('#') and n[1:] == pin.number) or norm_pin_name(n) in aliases:
                return s
    return None
