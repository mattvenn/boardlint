"""Render findings as Markdown, plain text or JSON."""
from __future__ import annotations
import json
from collections import Counter
from . import __version__

_ICON = {'error': 'ERROR', 'warning': 'WARN', 'info': 'info'}


def to_json(d, findings, log):
    return json.dumps({
        'tool': 'boardlint', 'version': __version__, 'design': d.name, 'sources': d.sources,
        'netlist_source': getattr(d, 'netlist_source', ''), 'notes': d.notes,
        'summary': dict(Counter(f.severity for f in findings)),
        'checks': [{'id': c, 'status': s, 'detail': m} for c, s, m in log],
        'parts': [{'ref': c.ref, 'value': c.value, 'kind': c.kind, 'model': (c.model or {}).get('id')}
                  for c in sorted(d.components.values(), key=lambda c: c.ref) if c.kind in ('IC', 'LED', 'Q') or c.model],
        'findings': [{'check': f.check, 'severity': f.severity, 'title': f.title, 'detail': f.detail,
                      'refs': f.refs, 'nets': sorted(f.nets), 'evidence': f.evidence, 'basis': f.basis,
                      'confidence': f.confidence} for f in findings],
    }, indent=1, default=str)


def to_text(d, findings, log, verbose=False):
    out = []
    for f in findings:
        if f.severity == 'info' and not verbose:
            continue
        out.append(f"{_ICON[f.severity]:5} [{f.check}] {f.title}")
        if f.detail:
            out.append(f"      {f.detail}")
        if verbose and f.evidence:
            out.append(f"      evidence: {f.evidence}")
        if verbose and f.basis:
            out.append(f"      basis: {f.basis} (confidence {f.confidence})")
    c = Counter(f.severity for f in findings)
    out.append(f"\n{d.name}: {c['error']} error(s), {c['warning']} warning(s), {c['info']} note(s)"
               + ("" if verbose else " (notes hidden; -v shows them)"))
    crashed = [l for l in log if l[1] == 'crashed']
    for cid, _, msg in crashed:
        out.append(f"CHECK CRASHED: {cid}: {msg}")
    return '\n'.join(out)


def to_markdown(d, findings, log):
    c = Counter(f.severity for f in findings)
    o = [f"# boardlint review: {d.name}", '',
         f"**{c['error']} errors, {c['warning']} warnings, {c['info']} notes.** "
         f"{len(d.components)} components, {len(d.nets)} nets; netlist from the "
         f"{'board' if getattr(d, 'netlist_source', '') == 'pcb' else 'schematic'}.", '']
    for n in d.notes:
        if not n.startswith('check '):
            o.append(f"- {n}")
    crashed = [l for l in log if l[1] == 'crashed']
    for cid, _, msg in crashed:
        o.append(f"- **check `{cid}` crashed and reported nothing: {msg}**")
    o.append('')
    for sev, head in (('error', 'Errors'), ('warning', 'Warnings'), ('info', 'Notes')):
        fs = [f for f in findings if f.severity == sev]
        if not fs:
            continue
        o += [f"## {head}", '']
        for f in fs:
            o.append(f"### {f.title}")
            o.append('')
            o.append(f"`{f.check}`" + (f" · parts: {', '.join(f.refs[:8])}" if f.refs else '')
                     + (f" · nets: {', '.join(sorted(f.nets)[:6])}" if f.nets else '')
                     + f" · confidence: {f.confidence}")
            o.append('')
            if f.detail:
                o += [f.detail, '']
            if f.evidence:
                o.append('| | |')
                o.append('|---|---|')
                for k, v in f.evidence.items():
                    o.append(f"| {k} | {v} |")
                o.append('')
            if f.basis:
                o += [f"Basis: {f.basis}.", '']
    o += ['## Coverage', '', '| Check | Status | |', '|---|---|---|']
    for cid, st, msg in log:
        o.append(f"| `{cid}` | {st} | {msg} |")
    o.append('')
    parts = [c_ for c_ in sorted(d.components.values(), key=lambda c_: c_.ref)
             if c_.kind in ('IC', 'LED', 'Q', 'FUSE', 'SW', 'CONN') or c_.model]
    seen = {}
    for c_ in parts:
        key = (c_.value, (c_.model or {}).get('id'))
        seen.setdefault(key, []).append(c_)
    o += ['## Part models', '', '| Parts | Value | Model | Verified against datasheet |', '|---|---|---|---|']
    for (val, mid), cs in seen.items():
        m = cs[0].model or {}
        refs = ', '.join(c_.ref for c_ in cs[:4]) + (f" +{len(cs) - 4}" if len(cs) > 4 else '')
        o.append(f"| {refs} | {val} | {mid or '**none: heuristics only**'} | "
                 f"{'yes' if (m.get('provenance') or {}).get('verified') else ('no' if m else '')} |")
    waived = getattr(d, 'waived', [])
    if waived:
        o += ['', '## Waived', '']
        for f, why in waived:
            o.append(f"- `{f.check}` {f.title}: {why}")
    errata = [(c_, e) for c_ in {(c_.model or {}).get('id'): c_ for c_ in parts if c_.model}.values()
              for e in (c_.model.get('errata') or [])]
    if errata:
        o += ['', '## Known issues of the parts used', '',
              'From errata sheets and forums, recorded in the part models. Not checked against this design.', '']
        for c_, e in errata:
            o.append(f"- **{c_.value}** ({e.get('id', '')}): {e.get('summary', '')}"
                     + (f" Source: {e['source']}" if e.get('source') else ''))
    return '\n'.join(o) + '\n'
