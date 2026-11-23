"""KiCad 4/5 legacy schematics (.sch + -cache.lib): parts and pin names only.

The legacy schematic is not netlisted here.  A KiCad 5 project is still checkable when its
.kicad_pcb exists: the board gives the nets, this module gives every pin its name and type.
"""
from __future__ import annotations
import glob
import os
import re
import shlex
from .model import Component, Pin

_ETYPE = {'I': 'input', 'O': 'output', 'B': 'bidirectional', 'T': 'tri_state', 'P': 'passive', 'U': 'unspecified',
          'W': 'power_in', 'w': 'power_out', 'C': 'open_collector', 'E': 'open_emitter', 'N': 'no_connect'}


def _read_libs(pdir):
    syms = {}
    for f in glob.glob(os.path.join(pdir, '*-cache.lib')) + glob.glob(os.path.join(pdir, '*.lib')):
        cur, names = None, []
        try:
            lines = open(f, encoding='utf-8', errors='replace').read().splitlines()
        except OSError:
            continue
        for ln in lines:
            if ln.startswith('DEF '):
                cur, names = [], [ln.split()[1].lstrip('~')]
            elif ln.startswith('ALIAS ') and cur is not None:
                names += ln.split()[1:]
            elif ln.startswith('X ') and cur is not None:
                t = ln.split()
                if len(t) >= 12:
                    cur.append({'name': t[1], 'number': t[2], 'unit': int(t[9]) if t[9].isdigit() else 0,
                                'etype': _ETYPE.get(t[11], 'unspecified')})
            elif ln.startswith('ENDDEF') and cur is not None:
                for n in names:
                    syms.setdefault(n, cur)
                cur = None
    return syms


def find_root(pdir):
    pros = [f[:-4] for f in os.listdir(pdir) if f.endswith('.pro')]
    for p in pros:
        if os.path.exists(os.path.join(pdir, p + '.sch')):
            return os.path.join(pdir, p + '.sch')
    schs = sorted(f for f in os.listdir(pdir) if f.endswith('.sch'))
    return os.path.join(pdir, schs[0]) if schs else None


def load_legacy(root_path):
    """Returns (components with un-netted pins, notes)."""
    pdir = os.path.dirname(os.path.abspath(root_path))
    syms = _read_libs(pdir)
    comps, notes, seen = {}, [], set()
    todo = [os.path.abspath(root_path)]
    while todo:
        path = todo.pop()
        if path in seen or not os.path.exists(path):
            continue
        seen.add(path)
        text = open(path, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r'^F1 "([^"]+\.sch)"', text, re.M):
            todo.append(os.path.join(os.path.dirname(path), m.group(1)))
        for block in re.findall(r'^\$Comp\n(.*?)^\$EndComp', text, re.M | re.S):
            lm = re.search(r'^L (\S+) (\S+)', block, re.M)
            if not lm or lm.group(2).startswith('#'):
                continue
            lib_id, ref = lm.group(1), lm.group(2)
            um = re.search(r'^U (\d+)', block, re.M)
            unit = int(um.group(1)) if um else 1
            fields = {}
            for fm in re.finditer(r'^F (\d+) "([^"]*)"', block, re.M):
                fields[int(fm.group(1))] = fm.group(2)
            for am in re.finditer(r'^AR Path="[^"]*" Ref="([^"]+)"', block, re.M):
                ref = am.group(1)
            c = comps.get(ref)
            if c is None:
                c = comps[ref] = Component(ref=ref, value=fields.get(1, ''), footprint=fields.get(2, ''), lib_id=lib_id,
                                           props={'Reference': ref, 'Value': fields.get(1, ''), 'Footprint': fields.get(2, '')})
            sym = syms.get(lib_id.replace(':', '_')) or syms.get(lib_id.split(':')[-1])
            if sym is None:
                continue
            for p in sym:
                if p['unit'] in (0, unit) and p['number'] not in c.pins:
                    c.pins[p['number']] = Pin(comp=c, number=p['number'], name='' if p['name'] == '~' else p['name'],
                                              etype=p['etype'])
    notes.append("KiCad 5 legacy schematic: pin names read from the cache library, nets taken from the board "
                 "(the legacy schematic itself is not netlisted)")
    return comps, notes
