"""Find the files of a KiCad project and merge schematic + board into one Design."""
from __future__ import annotations
import os
import yaml
from .model import Design, Net, Pin
from . import kicad_sch, kicad_pcb, kicad_legacy


def load_project(path: str, pcb: str | None = None, sch: str | None = None, netlist_from: str = 'auto') -> Design:
    path = os.path.abspath(path)
    pdir = path if os.path.isdir(path) else os.path.dirname(path)
    if os.path.isfile(path):
        if path.endswith('.kicad_pcb'):
            pcb = pcb or path
        elif path.endswith('.kicad_sch'):
            sch = sch or path
        elif path.endswith('.kicad_pro'):
            stem = path[:-10]
            sch = sch or (stem + '.kicad_sch' if os.path.exists(stem + '.kicad_sch') else None)
            pcb = pcb or (stem + '.kicad_pcb' if os.path.exists(stem + '.kicad_pcb') else None)
    legacy = None
    if os.path.isfile(path) and path.endswith(('.pro', '.sch')) and not path.endswith('.kicad_sch'):
        legacy = path if path.endswith('.sch') else kicad_legacy.find_root(pdir)
    if sch is None and legacy is None:
        sch = kicad_sch.find_root(pdir)
        if sch is None:
            legacy = kicad_legacy.find_root(pdir)
    if pcb is None:
        stem = sch[:-10] if sch else (legacy[:-4] if legacy else None)
        if stem and os.path.exists(stem + '.kicad_pcb'):
            pcb = stem + '.kicad_pcb'
        else:
            cands = sorted(f for f in os.listdir(pdir) if f.endswith('.kicad_pcb'))
            pcb = os.path.join(pdir, cands[0]) if cands else None
    d = Design(name=os.path.basename(sch or legacy or pcb or pdir).rsplit('.', 1)[0])
    cfg = os.path.join(pdir, 'boardlint.yaml')
    if os.path.exists(cfg):
        d.config = yaml.safe_load(open(cfg)) or {}
        d.sources.append(cfg)

    scomps, snets = {}, {}
    if sch:
        scomps, snets, notes = kicad_sch.load_schematic(sch)
        d.notes += notes
        d.sources.append(sch)
    if legacy and not sch:
        scomps, notes = kicad_legacy.load_legacy(legacy)
        d.notes += notes
        d.sources.append(legacy)
        netlist_from = 'pcb'
    bcomps = {}
    if pcb:
        bcomps, d.board, notes = kicad_pcb.load_board(pcb)
        d.notes += notes
        d.sources.append(pcb)

    use_pcb_nets = bool(bcomps) and netlist_from in ('auto', 'pcb') and \
        any(p.net for c in bcomps.values() for p in c.pins.values())
    if netlist_from == 'sch' and scomps:
        use_pcb_nets = False
    if netlist_from == 'auto' and scomps and bcomps and not legacy:
        shared = len(set(scomps) & set(bcomps))
        if shared < 0.5 * len(scomps):
            use_pcb_nets = False
            d.notes.append(f"only {shared} of {len(scomps)} schematic parts are on the board: using the schematic's "
                           f"netlist and ignoring the board's")

    d.sync = {'fp': [], 'only_sch': [], 'only_pcb': [], 'net_groups': 0}
    if scomps and bcomps:
        for ref, sc in scomps.items():
            bc = bcomps.get(ref)
            want = sc.props.get('Footprint', '')
            if bc is None:
                if not sc.dnp and want:
                    d.sync['only_sch'].append(ref)
            elif want and bc.footprint and want.split(':')[-1] != bc.footprint.split(':')[-1]:
                d.sync['fp'].append((ref, want, bc.footprint))
        d.sync['only_pcb'] = [r for r in bcomps if r not in scomps and not r.startswith(('REF', 'G*', 'H', 'FID', 'MH', 'LOGO'))
                              and any(p.net for p in bcomps[r].pins.values())]
        # schematic gives pin names/types and properties; board gives positions (and, by default, nets)
        for ref, sc in scomps.items():
            bc = bcomps.get(ref)
            if bc is None:
                if not sc.dnp and sc.props.get('Footprint'):
                    d.notes.append(f"{ref} is in the schematic but not on the board")
                d.components[ref] = sc
                if use_pcb_nets:
                    for p in sc.pins.values():
                        p.net = None
                continue
            sc.pos, sc.side = bc.pos, bc.side
            sc.footprint = bc.footprint or sc.footprint
            if sc.pins:                      # no pins: the symbol was not found, nothing to compare
                sc.props['_sch_pins'] = sorted(sc.pins)
                sc.props['_fp_pads'] = sorted(bc.pins)
            for num, bp in bc.pins.items():
                sp = sc.pins.get(num)
                if sp is None:
                    sp = sc.pins[num] = Pin(comp=sc, number=num, name=bp.name, etype=bp.etype)
                    if not use_pcb_nets:
                        sp.net = None
                sp.pos, sp.layers, sp.size, sp.drill = bp.pos, bp.layers, bp.size, bp.drill
                if use_pcb_nets:
                    sp.net = bp.net
            if use_pcb_nets:
                for num, sp in sc.pins.items():
                    if num not in bc.pins:
                        sp.net = None
            d.components[ref] = sc
        for ref, bc in bcomps.items():
            if ref not in d.components:
                d.components[ref] = bc
        if snets:
            notes = _compare_netlists(scomps, snets, bcomps)
            import re as _re
            m = _re.search(r'differ in (\d+) net group', notes[0])
            d.sync['net_groups'] = int(m.group(1)) if m else 0
            if use_pcb_nets:
                d.notes += notes
            elif d.sync['net_groups']:
                d.notes.append(f"schematic and board netlists differ in {d.sync['net_groups']} net group(s); the schematic's is used")
    else:
        d.components = scomps or bcomps
    for c in d.components.values():
        for p in c.pins.values():
            if p.net:
                d.nets.setdefault(p.net, Net(name=p.net)).pins.append(p)
    d.netlist_source = 'pcb' if use_pcb_nets else 'sch'
    return d


def _compare_netlists(scomps, snets, bcomps):
    """Schematic and board should describe the same connectivity; say so when they do not."""
    def groups(pinmap):
        g = {}
        for (ref, num), net in pinmap.items():
            g.setdefault(net, set()).add((ref, num))
        return {frozenset(v) for v in g.values() if len(v) > 1}
    common = set(scomps) & set(bcomps)
    s = {(r, n): net for net, pins in snets.items() for r, n in pins if r in common and n in bcomps[r].pins}
    b = {(r, p.number): p.net for r in common for p in bcomps[r].pins.values() if p.net and p.number in scomps[r].pins}
    gs, gb = groups(s), groups(b)
    diff = len(gs ^ gb)
    if diff:
        return [f"schematic and board netlists differ in {diff} net group(s) "
                f"({len(gs & gb)} agree): the board may be out of date, or the built-in schematic "
                f"netlister mis-read something. Board nets are used; pass --netlist-from sch to use the schematic"]
    return [f"schematic and board netlists agree ({len(gb)} multi-pin nets)"]
