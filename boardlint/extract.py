"""Resistive extraction of one net's copper: tracks, vias and filled zones become a resistor
network, which is solved for the voltage at every pad.

What it models: every track segment (resistivity x length / cross-section), every via barrel,
filled zones as a square mesh of sheet resistance, pads as the points where those meet.
What it does not: thermal-relief spokes (a zone is taken as solid up to the pad), skin effect,
temperature rise of the copper, zones that are saved unfilled.
"""
from __future__ import annotations
import math
from collections import defaultdict
from .tline import Stack

RHO = 1.72e-5           # copper resistivity, ohm*mm at 20 C
PLATING = 0.020         # via barrel plating, mm
TIE = 1e-7              # ohm: two things that are the same piece of copper

try:                    # optional: about fifty times faster on boards with large pours
    import numpy as _np
except Exception:       # pragma: no cover
    _np = None


def _q(v):
    return int(round(v * 1000))


def _in_poly(x, y, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _seg_dist(x, y, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    u = 0.0 if l2 <= 0 else max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / l2))
    return math.hypot(x - (a[0] + u * dx), y - (a[1] + u * dy))


class CopperNet:
    def __init__(self, d, net_name, max_cells=None):
        self.d, self.net = d, net_name
        b = d.board
        self.stack = Stack(b)
        self.layers = self.stack.layers or ['F.Cu', 'B.Cu']
        self.key = {}                 # node key -> index
        self.xy = []                  # index -> (x, y, layer)
        self.edges = []               # (a, b, ohms, meta)
        self.pin_nodes = {}           # (ref, number) -> [node]
        self.counts = defaultdict(int)
        self.grid = None
        self._build(max_cells or (20000 if _np is not None else 6000))

    # ------------------------------------------------------------------ building
    def _node(self, layer, x, y, tag=None):
        k = (layer, _q(x), _q(y)) if tag is None else tag
        i = self.key.get(k)
        if i is None:
            i = self.key[k] = len(self.xy)
            self.xy.append((x, y, layer))
        return i

    def _edge(self, a, b, r, meta=('tie',)):
        if a != b:
            self.edges.append((a, b, max(r, TIE), meta))

    def _pad_layers(self, pin):
        out = []
        for l in pin.layers:
            if l == '*.Cu':
                out += self.layers
            elif l == 'F&B.Cu':
                out += [x for x in ('F.Cu', 'B.Cu') if x in self.layers]
            elif l.endswith('.Cu') and l in self.layers:
                out.append(l)
        return list(dict.fromkeys(out))

    def _build(self, max_cells):
        d, b = self.d, self.d.board
        tracks = [t for t in b.tracks if t.net == self.net and t.length > 1e-6 and t.layer in self.layers]
        vias = [v for v in b.vias if v.net == self.net]
        net = d.nets.get(self.net)
        pins = [p for p in (net.pins if net else []) if p.pos]
        # points that may land on a track: (x, y, layer, reach, node)
        poi = []
        for t in tracks:
            for (x, y) in ((t.x1, t.y1), (t.x2, t.y2)):
                poi.append((x, y, t.layer, 0.0, self._node(t.layer, x, y), t))
        for v in vias:
            span = self.layers
            if len(v.layers) == 2 and all(l in self.layers for l in v.layers):
                i, j = sorted(self.layers.index(l) for l in v.layers)
                span = self.layers[i:j + 1]
            nodes = [self._node(l, v.x, v.y) for l in span]
            circ = math.pi * (v.drill + PLATING) * PLATING          # barrel cross-section
            for la, lb, na, nb in zip(span, span[1:], nodes, nodes[1:]):
                h = self.stack.between(la, lb)[0]
                self._edge(na, nb, RHO * h / circ, ('via', v))
            self.counts['vias'] += 1
            for l, n in zip(span, nodes):
                poi.append((v.x, v.y, l, v.size / 2, n, None))
        for p in pins:
            ls = self._pad_layers(p)
            nodes = [self._node(l, p.pos[0], p.pos[1], tag=('pad', p.comp.ref, p.number, l)) for l in ls]
            self.pin_nodes[(p.comp.ref, p.number)] = nodes
            for na, nb in zip(nodes, nodes[1:]):
                self._edge(na, nb, 5e-4, ('pad',))                # plated hole
            reach = max(p.size) / 2 if p.size else 0.4
            for l, n in zip(ls, nodes):
                poi.append((p.pos[0], p.pos[1], l, reach, n, None))
        # spatial hash of tracks
        cell = 2.0
        grid = defaultdict(list)
        for ti, t in enumerate(tracks):
            x0, x1 = sorted((t.x1, t.x2))
            y0, y1 = sorted((t.y1, t.y2))
            for i in range(int(x0 // cell) - 1, int(x1 // cell) + 2):
                for j in range(int(y0 // cell) - 1, int(y1 // cell) + 2):
                    grid[(t.layer, i, j)].append(ti)
        splits = defaultdict(list)            # track index -> [(u, node)]
        for (x, y, layer, reach, node, own) in poi:
            for ti in grid.get((layer, int(x // cell), int(y // cell)), ()):
                t = tracks[ti]
                if t is own:
                    continue
                dx, dy = t.x2 - t.x1, t.y2 - t.y1
                l2 = dx * dx + dy * dy
                u = max(0.0, min(1.0, ((x - t.x1) * dx + (y - t.y1) * dy) / l2))
                px, py = t.x1 + u * dx, t.y1 + u * dy
                if math.hypot(x - px, y - py) > reach + t.width / 2 + 0.005:
                    continue
                if u * t.length < 0.002:
                    self._edge(node, self._node(layer, t.x1, t.y1), TIE)
                elif (1 - u) * t.length < 0.002:
                    self._edge(node, self._node(layer, t.x2, t.y2), TIE)
                else:
                    n2 = self._node(layer, px, py)
                    self._edge(node, n2, TIE)
                    splits[ti].append((u, n2))
        for ti, t in enumerate(tracks):
            tcu = self.stack.copper(t.layer)
            pts = sorted([(0.0, self._node(t.layer, t.x1, t.y1))] + splits.get(ti, []) +
                         [(1.0, self._node(t.layer, t.x2, t.y2))], key=lambda x: x[0])
            for (ua, na), (ub, nb) in zip(pts, pts[1:]):
                ln = (ub - ua) * t.length
                if na != nb and ln > 0:
                    self._edge(na, nb, RHO * ln / (t.width * tcu), ('track', t, ln))
            self.counts['segments'] += 1
        self._zones(max_cells)

    def _zones(self, max_cells):
        zones = [z for z in self.d.board.zones if z.net == self.net and z.layer in self.layers]
        if not zones:
            return
        def poly_area(p):
            return abs(sum(p[k][0] * p[(k + 1) % len(p)][1] - p[(k + 1) % len(p)][0] * p[k][1] for k in range(len(p)))) / 2
        area = sum(poly_area(p) for z in zones for p in z.polys)
        g = self.grid = max(0.4, math.sqrt(area / max_cells))
        cells = {}
        polys = []                                  # (layer, bbox, points, [cell nodes])
        for z in zones:
            for poly in z.polys:
                if len(poly) < 3:
                    continue
                xs_, ys = [p[0] for p in poly], [p[1] for p in poly]
                own = []
                polys.append((z.layer, (min(xs_), min(ys), max(xs_), max(ys)), poly, own))
                j0, j1 = int(math.ceil(min(ys) / g)), int(math.floor(max(ys) / g))
                n = len(poly)
                for j in range(j0, j1 + 1):
                    y = j * g + 1e-7
                    xs = []
                    for k in range(n):
                        (xa, ya), (xb, yb) = poly[k], poly[(k + 1) % n]
                        if (ya > y) != (yb > y):
                            xs.append(xa + (y - ya) * (xb - xa) / (yb - ya))
                    xs.sort()
                    for a, b_ in zip(xs[0::2], xs[1::2]):
                        for i in range(int(math.ceil(a / g)), int(math.floor(b_ / g)) + 1):
                            k = ('cell', z.layer, i, j)
                            if k not in cells:
                                cells[k] = self._node(z.layer, i * g, j * g, tag=k)
                            own.append(cells[k])
        for (_, layer, i, j), n in cells.items():
            rs = RHO / self.stack.copper(layer)
            for k2 in (('cell', layer, i + 1, j), ('cell', layer, i, j + 1)):
                if k2 in cells:
                    self._edge(n, cells[k2], rs, ('sheet', layer))
        self.counts['cells'] = len(cells)
        by_layer = defaultdict(list)
        for idx, pl in enumerate(polys):
            by_layer[pl[0]].append(idx)
        islands = {}

        def island(idx):
            # a piece of pour too small to hold a grid point: one node, no internal resistance
            if idx not in islands:
                layer, bb, _, _ = polys[idx]
                islands[idx] = self._node(layer, (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, tag=('island', idx))
                self.counts['islands'] += 1
            return islands[idx]

        def nearest_cell(own, x, y):
            return min(own, key=lambda c: (self.xy[c][0] - x) ** 2 + (self.xy[c][1] - y) ** 2)

        # everything else that sits in zone copper joins the mesh there
        for k, n in list(self.key.items()):
            if k[0] in ('cell', 'island'):
                continue
            x, y, layer = self.xy[n]
            if layer not in by_layer:
                continue
            i0, j0 = int(round(x / g)), int(round(y / g))
            c = None
            # 1. inside a piece of pour too small for the grid
            for idx in by_layer[layer]:
                _, bb, poly, own = polys[idx]
                if not own and bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3] and _in_poly(x, y, poly):
                    c = island(idx)
                    break
            # 2. a grid point right here
            if c is None:
                c = cells.get(('cell', layer, i0, j0))
            # 3. inside a meshed piece of pour, but near its edge
            if c is None:
                for idx in by_layer[layer]:
                    _, bb, poly, own = polys[idx]
                    if own and bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3] and _in_poly(x, y, poly):
                        c = nearest_cell(own, x, y)
                        break
            # 4, 5. A pad on thermal relief has no fill under its centre: the fill starts a clearance
            # away and reaches it through spokes, which are not modelled, so pour copper within
            # about a millimetre counts as joined.
            if c is None:
                for idx in by_layer[layer]:
                    _, bb, poly, own = polys[idx]
                    if not own and bb[0] - 0.8 <= x <= bb[2] + 0.8 and bb[1] - 0.8 <= y <= bb[3] + 0.8 and \
                            min(_seg_dist(x, y, poly[q], poly[(q + 1) % len(poly)]) for q in range(len(poly))) <= 0.8:
                        c = island(idx)
                        break
            if c is None:
                reach = 1.0 + 0.71 * g
                span = int(math.ceil(reach / g))
                best = None
                for i in range(i0 - span, i0 + span + 1):
                    for j in range(j0 - span, j0 + span + 1):
                        cc = cells.get(('cell', layer, i, j))
                        if cc is not None:
                            dd = math.hypot(i * g - x, j * g - y)
                            if dd <= reach and (best is None or dd < best[0]):
                                best = (dd, cc)
                c = best[1] if best else None
            if c is not None:
                rs = RHO / self.stack.copper(layer)
                a = 0.25                               # contact radius of a via or track end, mm
                self._edge(n, c, max(rs / (2 * math.pi) * math.log(max(0.2 * g / a, 1.0)), TIE), ('contact',))

    # ------------------------------------------------------------------ solving
    def reachable(self, sources):
        adj = defaultdict(list)
        for a, b, _, _ in self.edges:
            adj[a].append(b)
            adj[b].append(a)
        seen, todo = set(sources), list(sources)
        while todo:
            n = todo.pop()
            for m in adj[n]:
                if m not in seen:
                    seen.add(m)
                    todo.append(m)
        return seen

    def solve(self, sources, sinks, tol=1e-10):
        """sources: nodes held at 0 V.  sinks: {node: amps drawn}.  Returns (V list with None where
        not connected to a source, [sink nodes that are not connected])."""
        comp = self.reachable(sources)
        lost = [s for s in sinks if s not in comp]
        V = [None] * len(self.xy)
        # nodes joined by a tie (a pad and the track end on it) are one unknown: merging them keeps
        # the matrix well conditioned
        rep = list(range(len(self.xy)))

        def find(i):
            while rep[i] != i:
                rep[i] = rep[rep[i]]
                i = rep[i]
            return i
        for a, b, r, _ in self.edges:
            if r <= 10 * TIE:
                ra, rb = find(a), find(b)
                if ra != rb:
                    rep[ra] = rb
        src = {find(s) for s in sources}
        idx = {}
        for nd in sorted(comp):
            f = find(nd)
            if f not in src and f not in idx:
                idx[f] = len(idx)
        n = len(idx)
        self.last_solve = {'unknowns': n, 'iterations': 0, 'residual': 0.0}
        x = []
        if n:
            ea, eb, eg, diag, rhs = [], [], [], [0.0] * n, [0.0] * n
            for a, b, r, _ in self.edges:
                if a not in comp or r <= 10 * TIE:
                    continue
                fa, fb = find(a), find(b)
                if fa == fb:
                    continue
                g = 1.0 / r
                ia, ib = idx.get(fa), idx.get(fb)
                if ia is not None:
                    diag[ia] += g
                if ib is not None:
                    diag[ib] += g
                if ia is not None and ib is not None:
                    ea.append(ia)
                    eb.append(ib)
                    eg.append(g)
            for s_, amps in sinks.items():
                i = idx.get(find(s_)) if s_ in comp else None
                if i is not None:
                    rhs[i] -= amps
            if not any(rhs):
                x = [0.0] * n                       # nothing draws current on the connected part
            else:
                cg = _cg_numpy if _np is not None else _cg_python
                x, its, res = cg(n, ea, eb, eg, diag, rhs, tol)
                self.last_solve.update(iterations=its, residual=res)
        for nd in comp:
            i = idx.get(find(nd))
            V[nd] = 0.0 if i is None else x[i]
        return V, lost

    def currents(self, V):
        """[(amps, meta)] for every track sub-segment, sign dropped."""
        out = []
        for a, b, r, meta in self.edges:
            if meta[0] == 'track' and r > 10 * TIE and V[a] is not None and V[b] is not None:
                out.append((abs(V[a] - V[b]) / r, meta))
        return out


def _cg_numpy(n, ea, eb, eg, diag, rhs, tol):
    ea, eb = _np.asarray(ea, dtype=_np.int64), _np.asarray(eb, dtype=_np.int64)
    eg, diag, b = _np.asarray(eg), _np.asarray(diag), _np.asarray(rhs)

    def mv(x):
        y = diag * x
        if len(eg):
            y -= _np.bincount(ea, weights=eg * x[eb], minlength=n)
            y -= _np.bincount(eb, weights=eg * x[ea], minlength=n)
        return y
    x = _np.zeros(n)
    r = b.copy()
    z = r / diag
    p = z.copy()
    rz = float(r @ z)
    bn = float(_np.linalg.norm(b)) or 1.0
    its, res = 0, 1.0
    for its in range(1, 20 * int(math.sqrt(n)) + 2001):
        ap = mv(p)
        alpha = rz / float(p @ ap)
        x += alpha * p
        r -= alpha * ap
        res = float(_np.linalg.norm(r)) / bn
        if res < tol:
            break
        z = r / diag
        rz2 = float(r @ z)
        p = z + (rz2 / rz) * p
        rz = rz2
    return x.tolist(), its, res


def _cg_python(n, ea, eb, eg, diag, rhs, tol):
    def mv(x):
        y = [diag[i] * x[i] for i in range(n)]
        for a, b, g in zip(ea, eb, eg):
            y[a] -= g * x[b]
            y[b] -= g * x[a]
        return y
    x = [0.0] * n
    r = list(rhs)
    z = [r[i] / diag[i] for i in range(n)]
    p = list(z)
    rz = sum(r[i] * z[i] for i in range(n))
    bn = math.sqrt(sum(v * v for v in rhs)) or 1.0
    its, res = 0, 1.0
    for its in range(1, 20 * int(math.sqrt(n)) + 2001):
        ap = mv(p)
        alpha = rz / sum(p[i] * ap[i] for i in range(n))
        for i in range(n):
            x[i] += alpha * p[i]
            r[i] -= alpha * ap[i]
        res = math.sqrt(sum(v * v for v in r)) / bn
        if res < tol:
            break
        z = [r[i] / diag[i] for i in range(n)]
        rz2 = sum(r[i] * z[i] for i in range(n))
        p = [z[i] + (rz2 / rz) * p[i] for i in range(n)]
        rz = rz2
    return x, its, res


def ipc2221_amps(width_mm, t_cu_mm, rise_c=10.0, inner=False):
    """Current for a given temperature rise (IPC-2221): I = k dT^0.44 A^0.725, A in square mils."""
    area = (width_mm / 0.0254) * (t_cu_mm / 0.0254)
    return (0.024 if inner else 0.048) * rise_c ** 0.44 * area ** 0.725


def resistance_between(d, net_name, pin_a, pin_b, cn=None):
    """(ohms, inductance nH, CopperNet) between two pads of a net through its copper, or (None, None, cn)."""
    from . import tline
    cn = cn or CopperNet(d, net_name)
    na = cn.pin_nodes.get((pin_a.comp.ref, pin_a.number))
    nb = cn.pin_nodes.get((pin_b.comp.ref, pin_b.number))
    if not na or not nb:
        return None, None, cn
    V, lost = cn.solve(na, {nb[0]: 1.0})
    if lost or V[nb[0]] is None:
        return None, None, cn
    r = -V[nb[0]]
    planes = tline.Planes(d)
    l = 0.0
    for amps, meta in cn.currents(V):
        if amps > 1e-4:
            l += tline.segment(cn.stack, planes, meta[1])['l'] * meta[2] * amps * amps     # energy-weighted
    return r, l, cn
