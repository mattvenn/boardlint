"""KiCad 6-10 board reader: footprints/pads/nets plus copper geometry."""
from __future__ import annotations
import math
from .sexpr import load, children, child, value, fnum
from .model import Component, Pin, Board, Track, Via, Zone


def load_board(path: str):
    """Returns (components, Board, notes).  Components carry pad nets and positions."""
    doc = load(path)
    notes = []
    netnames = {}
    for n in children(doc, 'net'):
        if len(n) >= 3:
            netnames[str(n[1])] = str(n[2])

    def netname(node):
        n = child(node, 'net')
        if n is None:
            return None
        if len(n) >= 3:
            return str(n[2]) or None
        v = str(n[1])
        if type(n[1]) is str and v in netnames:      # bare number: old-style net code
            return netnames[v] or None
        return v or None

    board = Board(path=path)
    lay = child(doc, 'layers')
    if lay:
        board.copper_layers = [str(l[1]) for l in lay[1:] if isinstance(l, list) and str(l[1]).endswith('.Cu')]
    gen = child(doc, 'general')
    if gen:
        board.thickness = fnum(value(gen, 'thickness'), 1.6)
    setup = child(doc, 'setup')
    stack = child(setup, 'stackup') if setup else None
    if stack:
        for l in children(stack, 'layer'):
            if str(value(l, 'type', '')) == 'copper' and value(l, 'thickness'):
                board.copper_um = fnum(value(l, 'thickness')) * 1000
                break

    comps = {}
    for fp in children(doc, 'footprint') + children(doc, 'module'):
        props = {str(p[1]): str(p[2]) for p in children(fp, 'property') if len(p) > 2}
        for t in children(fp, 'fp_text'):
            if len(t) > 2 and t[1] in ('reference', 'value'):
                props.setdefault(t[1].capitalize(), str(t[2]))
        ref = props.get('Reference', '')
        if not ref:
            continue
        at = child(fp, 'at')
        fx, fy = fnum(at[1]), fnum(at[2])
        rot = fnum(at[3]) if len(at) > 3 else 0.0
        layer = str(value(fp, 'layer', 'F.Cu'))
        attr = child(fp, 'attr') or []
        if ref in comps:
            notes.append(f"duplicate reference {ref} on the board")
            continue
        c = Component(ref=ref, value=props.get('Value', ''), footprint=str(fp[1]), props=props,
                      pos=(fx, fy), side='B' if layer.startswith('B') else 'F',
                      dnp='dnp' in attr)
        a = math.radians(rot)
        for pad in children(fp, 'pad'):
            num = str(pad[1])
            pat = child(pad, 'at')
            px, py = fnum(pat[1]), fnum(pat[2])
            ax = fx + px * math.cos(a) + py * math.sin(a)
            ay = fy - px * math.sin(a) + py * math.cos(a)
            net = netname(pad)
            layers = tuple(str(x) for x in (child(pad, 'layers') or [])[1:])
            pf = value(pad, 'pinfunction')
            pt = value(pad, 'pintype')
            if num == '' and net is None:
                continue
            if num in c.pins:
                # several pads with one number (shield tabs, thermal pads): keep the first, prefer a net
                if c.pins[num].net is None and net:
                    c.pins[num].net = net
                continue
            c.pins[num] = Pin(comp=c, number=num, name=str(pf) if pf else '', etype=str(pt).split('+')[0] if pt else '',
                              net=net, pos=(ax, ay), layers=layers)
        comps[ref] = c

    for s in children(doc, 'segment') + children(doc, 'arc'):
        st, en = child(s, 'start'), child(s, 'end')
        board.tracks.append(Track(net=netname(s) or '', layer=str(value(s, 'layer', '')),
                                  x1=fnum(st[1]), y1=fnum(st[2]), x2=fnum(en[1]), y2=fnum(en[2]),
                                  width=fnum(value(s, 'width'), 0.2)))
    for v in children(doc, 'via'):
        at = child(v, 'at')
        board.vias.append(Via(net=netname(v) or '', x=fnum(at[1]), y=fnum(at[2]),
                              size=fnum(value(v, 'size'), 0.6), drill=fnum(value(v, 'drill'), 0.3)))
    unfilled = 0
    for g in children(doc, 'gr_poly') + children(doc, 'gr_rect'):
        layer = str(value(g, 'layer', ''))
        net = netname(g)
        if not layer.endswith('.Cu') or not net:
            continue
        if g[0] == 'gr_rect':
            s, e = child(g, 'start'), child(g, 'end')
            pts = [(fnum(s[1]), fnum(s[2])), (fnum(e[1]), fnum(s[2])), (fnum(e[1]), fnum(e[2])), (fnum(s[1]), fnum(e[2]))]
        else:
            pts = [(fnum(p[1]), fnum(p[2])) for p in children(child(g, 'pts'), 'xy')]
        if len(pts) >= 3:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            board.zones.append(Zone(net=net, layer=layer, polys=[pts], bbox=(min(xs), min(ys), max(xs), max(ys))))
    for z in children(doc, 'zone'):
        if child(z, 'keepout') is not None:
            continue                      # a rule area, not copper
        zn = value(z, 'net_name')
        net = str(zn) if zn is not None else (netname(z) or '')
        fills = children(z, 'filled_polygon')
        if not fills:
            unfilled += 1
        bylayer = {}
        for f in fills:
            pts = [(fnum(p[1]), fnum(p[2])) for p in children(child(f, 'pts'), 'xy')]
            if len(pts) >= 3:
                bylayer.setdefault(str(value(f, 'layer', value(z, 'layer', ''))), []).append(pts)
        for layer, polys in bylayer.items():
            xs = [p[0] for poly in polys for p in poly]
            ys = [p[1] for poly in polys for p in poly]
            board.zones.append(Zone(net=net, layer=layer, polys=polys,
                                    bbox=(min(xs), min(ys), max(xs), max(ys))))
    if unfilled:
        notes.append(f"{unfilled} zone(s) are saved unfilled: plane-dependent layout checks see no copper there "
                     f"(refill zones in KiCad and save)")
    return comps, board, notes
