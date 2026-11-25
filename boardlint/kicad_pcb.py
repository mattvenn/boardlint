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
        for l in children(stack, 'layer'):
            typ = str(value(l, 'type', '')).lower()
            th = fnum(value(l, 'thickness'), 0.0)
            if typ == 'copper':
                board.stackup.append((str(l[1]), 'copper', th or 0.035, 1.0))
            elif typ in ('core', 'prepreg') and th:
                board.stackup.append((str(l[1]), 'dielectric', th, fnum(value(l, 'epsilon_r'), 4.5)))
        names = [s[0] for s in board.stackup if s[1] == 'copper']
        if names == board.copper_layers and any(s[1] == 'dielectric' for s in board.stackup):
            board.stackup_assumed = False
        else:
            board.stackup = []
    if not board.stackup:
        board.stackup = default_stackup(board.copper_layers or ['F.Cu', 'B.Cu'], board.thickness, board.copper_um / 1000)

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
            psz = child(pad, 'size')
            drl = child(pad, 'drill')
            dval = 0.0
            if drl is not None:
                nums = [fnum(x, 0.0) for x in drl[1:] if not isinstance(x, list) and str(x) != 'oval']
                dval = max(nums) if nums else 0.0
            size = (fnum(psz[1]), fnum(psz[2])) if psz is not None and len(psz) > 2 else None
            prim = child(pad, 'primitives')
            anchor, polys = None, []
            if size and prim is not None:
                # custom pad: the copper is the anchor plus the drawn shapes; (size) is only the anchor
                anchor = size
                ex = ey = 0.0
                for g in prim[1:]:
                    if not isinstance(g, list):
                        continue
                    w = fnum(value(g, 'width'), 0.0)
                    pts = child(g, 'pts')
                    xy = [q for q in (pts or [])[1:] if isinstance(q, list) and q and str(q[0]) == 'xy']
                    if str(g[0]) == 'gr_poly' and len(xy) >= 3:
                        polys.append(tuple((fnum(q[1]), fnum(q[2])) for q in xy))
                    xy += [q for q in g[1:] if isinstance(q, list) and q and str(q[0]) in ('start', 'end', 'center')]
                    for q in xy:
                        ex, ey = max(ex, abs(fnum(q[1])) + w / 2), max(ey, abs(fnum(q[2])) + w / 2)
                size = (max(size[0], 2 * ex), max(size[1], 2 * ey))
            c.pins[num] = Pin(comp=c, number=num, name=str(pf) if pf else '', etype=str(pt).split('+')[0] if pt else '',
                              net=net, pos=(ax, ay), layers=layers, size=size, drill=dval,
                              angle=fnum(pat[3]) if len(pat) > 3 and not isinstance(pat[3], list) else 0.0,
                              shape=str(pad[3]) if len(pad) > 3 and not isinstance(pad[3], list) else '',
                              anchor=anchor, polys=tuple(polys))
        comps[ref] = c

    for s in children(doc, 'segment') + children(doc, 'arc'):
        st, en = child(s, 'start'), child(s, 'end')
        board.tracks.append(Track(net=netname(s) or '', layer=str(value(s, 'layer', '')),
                                  x1=fnum(st[1]), y1=fnum(st[2]), x2=fnum(en[1]), y2=fnum(en[2]),
                                  width=fnum(value(s, 'width'), 0.2)))
    for v in children(doc, 'via'):
        at = child(v, 'at')
        vl = child(v, 'layers')
        board.vias.append(Via(net=netname(v) or '', x=fnum(at[1]), y=fnum(at[2]),
                              size=fnum(value(v, 'size'), 0.6), drill=fnum(value(v, 'drill'), 0.3),
                              layers=tuple(str(x) for x in vl[1:]) if vl is not None else ()))
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


def default_stackup(copper_layers, thickness, t_cu=0.035, t_inner=0.0175):
    """A plausible stack-up when the board file gives none: thin prepreg under the outer layers of
    a multilayer board, the rest shared between the cores; 1 oz copper outside and 0.5 oz inside,
    which is what low-cost fabricators supply unless asked otherwise.  Same list form as a real one."""
    n = len(copper_layers)
    out = []
    if n <= 1:
        return [(copper_layers[0] if copper_layers else 'F.Cu', 'copper', t_cu, 1.0)]
    cu = [t_cu] + [t_inner] * (n - 2) + [t_cu]
    if n == 2:
        gaps = [max(thickness - sum(cu), 0.1)]
    else:
        outer = 0.2
        inner = max(thickness - sum(cu) - 2 * outer, 0.1 * (n - 3)) / max(n - 3, 1)
        gaps = [outer] + [inner] * (n - 3) + [outer]
    for i, name in enumerate(copper_layers):
        out.append((name, 'copper', cu[i], 1.0))
        if i < n - 1:
            out.append((f"dielectric {i + 1}", 'dielectric', gaps[i], 4.5))
    return out
