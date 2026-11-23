"""Load a project, run the checks, collect findings."""
from __future__ import annotations
import fnmatch
import time
import traceback
from .loader import load_project
from .classify import classify_components, split_resistor_packs
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
    for k, n in list(d.nets.items()):
        if len(n.pins) == 1 and k.startswith('Net-('):
            n.pins[0].net = None
            del d.nets[k]
    classify_components(d)
    split_resistor_packs(d)
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
    findings = _collapse(_waive(d, findings))
    findings.sort(key=Finding.key)
    return findings, log


def _collapse(findings, at_least=4):
    """One finding instead of forty when the same thing is said about forty parts."""
    import re
    groups = {}
    for f in findings:
        t = f.title
        for r in sorted(f.refs, key=len, reverse=True):
            t = re.sub(rf'(?<![A-Za-z0-9_]){re.escape(r)}(?![A-Za-z0-9_])', '{ref}', t)
        t = re.sub(r'\d+(\.\d+)?', '#', t)
        groups.setdefault((f.check, f.severity, t), []).append(f)
    out = []
    for (check, sev, t), fs in groups.items():
        if len(fs) < at_least or '{ref}' not in t:
            out += fs
            continue
        first = fs[0]
        refs = []
        for f in fs:
            for r in f.refs[:1]:
                if r not in refs:
                    refs.append(r)
        first.title = f"{first.title}  (and {len(fs) - 1} more like it)"
        first.detail = (first.detail + f" The same finding applies to {len(fs)} parts: {', '.join(refs[:40])}"
                        + ('...' if len(refs) > 40 else '') + '.').strip()
        first.refs = refs
        first.nets = sorted({n for f in fs for n in f.nets})
        first.evidence = dict(first.evidence, occurrences=len(fs))
        out.append(first)
    return out


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
