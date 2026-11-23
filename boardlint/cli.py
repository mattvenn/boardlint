"""Command line: boardlint check <project>."""
from __future__ import annotations
import argparse
import sys
from . import __version__
from .engine import prepare, run
from . import report


def main(argv=None):
    ap = argparse.ArgumentParser(prog='boardlint', description='Design-review checks for KiCad projects, beyond ERC/DRC.')
    ap.add_argument('--version', action='version', version=__version__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name, hlp in (('check', 'run the checks'), ('parts', 'list parts and the models matched to them'),
                      ('rails', 'list supply rails and inferred voltages'), ('checks', 'list available checks')):
        p = sub.add_parser(name, help=hlp)
        if name == 'checks':
            continue
        p.add_argument('project', help='project directory, .kicad_pro, .kicad_sch or .kicad_pcb')
        p.add_argument('--parts-dir', action='append', default=[], help='extra directory of part models (YAML)')
        p.add_argument('--netlist-from', choices=('auto', 'pcb', 'sch'), default='auto')
        if name == 'check':
            p.add_argument('-f', '--format', choices=('text', 'md', 'json'), default='text')
            p.add_argument('-o', '--output', help='write the report to this file')
            p.add_argument('--only', action='append', default=[], help='check id glob or family (repeatable)')
            p.add_argument('--skip', action='append', default=[], help='check id glob or family (repeatable)')
            p.add_argument('--no-sim', action='store_true', help='skip ngspice / Verilog simulations')
            p.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd == 'checks':
        from . import checks
        for cid, c in sorted(checks.load_all().items()):
            print(f"{cid:28} {c['family']:11} {'board ' if c['needs_board'] else '      '}{c['doc']}")
        return 0
    d = prepare(a.project, parts_dirs=a.parts_dir, netlist_from=a.netlist_from)
    if a.cmd == 'parts':
        for c in sorted(d.components.values(), key=lambda c: (c.kind, c.ref)):
            if c.kind in ('IC', 'LED', 'Q', 'CONN', 'SW', 'FUSE', 'D') or c.model:
                m = c.model or {}
                print(f"{c.ref:6} {c.kind:5} {c.value:24} {m.get('id', '-'):26} "
                      f"{'verified' if (m.get('provenance') or {}).get('verified') else ''}")
        return 0
    if a.cmd == 'rails':
        for n in sorted(d.nets.values(), key=lambda n: n.name):
            if n.is_ground or n.is_power or n.vmin is not None:
                v = f"{n.vmin:g}-{n.vmax:g} V" if n.vmin is not None else 'unknown'
                print(f"{n.name:16} {'GND' if n.is_ground else 'rail' if n.is_power else 'signal':6} {v:14} {n.vsrc}")
        return 0
    findings, log = run(d, only=a.only, skip=a.skip, no_sim=a.no_sim)
    text = {'text': lambda: report.to_text(d, findings, log, a.verbose), 'md': lambda: report.to_markdown(d, findings, log),
            'json': lambda: report.to_json(d, findings, log)}[a.format]()
    if a.output:
        with open(a.output, 'w') as f:
            f.write(text)
        print(report.to_text(d, findings, log).splitlines()[-1])
    else:
        print(text)
    if any(l[1] == 'crashed' for l in log):
        return 2
    return 1 if any(f.severity == 'error' for f in findings) else 0


if __name__ == '__main__':
    sys.exit(main())
