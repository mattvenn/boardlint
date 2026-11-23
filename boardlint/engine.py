"""Load a project, run the checks, collect findings."""
from __future__ import annotations
import fnmatch
import time
import traceback
from .loader import load_project
from .classify import classify_components
from .library import load_models, apply_models
from .power import analyse_power
from . import checks as _checks
from .model import Finding


def prepare(path, parts_dirs=(), **kw):
    d = load_project(path, **kw)
    for c in d.components.values():
        for p in c.pins.values():
            if p.net and p.net.startswith('unconnected-('):
                p.net = None
    d.nets = {k: v for k, v in d.nets.items() if not k.startswith('unconnected-(')}
    classify_components(d)
    models = load_models(parts_dirs)
    d.unmodelled = apply_models(d, models)
    import re
    for c in d.components.values():           # gpio_pattern: MCU pins that take any role
        pat = (c.model or {}).get('gpio_pattern')
        if pat:
            rx = re.compile(pat)
            for p in c.pins.values():
                if not p.role and rx.match(p.name):
                    p.role = 'gpio'
    analyse_power(d)
    return d


def run(d, only=(), skip=(), no_sim=False):
    reg = _checks.load_all()
    findings, log = [], []
    for cid, c in sorted(reg.items()):
        sel = (not only or any(fnmatch.fnmatch(cid, o) or o == c['family'] for o in only)) and \
            not any(fnmatch.fnmatch(cid, s) or s == c['family'] for s in skip)
        if not sel:
            log.append((cid, 'skipped', 'not selected'))
            continue
        if c['needs_board'] and d.board is None:
            log.append((cid, 'skipped', 'no .kicad_pcb'))
            continue
        if no_sim and c['family'] == 'simulation':
            log.append((cid, 'skipped', '--no-sim'))
            continue
        t = time.time()
        try:
            out = list(c['fn'](d) or [])
            findings += out
            log.append((cid, 'ran', f"{len(out)} finding(s), {time.time() - t:.2f} s"))
        except Exception as e:                      # one broken check must not hide the others
            log.append((cid, 'crashed', f"{type(e).__name__}: {e}"))
            d.notes.append(f"check {cid} crashed: {type(e).__name__}: {e}\n{traceback.format_exc(limit=4)}")
    findings = _waive(d, findings)
    findings.sort(key=Finding.key)
    return findings, log


def _waive(d, findings):
    waivers = d.config.get('waive') or []
    out = []
    d.waived = []
    for f in findings:
        w = next((w for w in waivers if fnmatch.fnmatch(f.check, w.get('check', '*')) and
                  (not w.get('refs') or set(w['refs']) & set(f.refs)) and
                  (not w.get('title') or w['title'].lower() in f.title.lower())), None)
        if w:
            d.waived.append((f, w.get('reason', '')))
        else:
            out.append(f)
    return out
