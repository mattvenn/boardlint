"""Transmission-line estimates for one track segment from the stack-up: impedance, delay,
capacitance and inductance per millimetre.

Closed-form formulas (Hammerstad for microstrip, the IPC-2141 form for stripline).  They are
good to several percent for ordinary geometries; they are not a field solve, and they ignore
solder mask, etch shape and neighbouring copper on the same layer.
"""
from __future__ import annotations
import math

C0 = 299.792458          # speed of light, mm/ns
Z_FREE = 376.730         # ohm
MU0_NH_MM = 0.4 * math.pi  # nH/mm


def microstrip(w, h, er, t=0.035):
    """(Z0 ohm, effective permittivity) of a track of width w, height h above a plane."""
    # thickness correction to the width (Wheeler / Hammerstad)
    if t > 0 and w > 0:
        w = w + (t / math.pi) * (1 + math.log(max(2 * h / t, 1.0001)))
    u = max(w / h, 1e-3)
    eeff = (er + 1) / 2 + (er - 1) / 2 * ((1 + 12 / u) ** -0.5 + (0.04 * (1 - u) ** 2 if u < 1 else 0.0))
    if u <= 1:
        z0 = 60 / math.sqrt(eeff) * math.log(8 / u + u / 4)
    else:
        z0 = Z_FREE / (math.sqrt(eeff) * (u + 1.393 + 0.667 * math.log(u + 1.444)))
    return z0, eeff


def stripline(w, h1, h2, er, t=0.035):
    """(Z0 ohm, permittivity) of a track between two planes h1 above and h2 below (offset stripline:
    the two halves in parallel)."""
    def half(h):
        b = 2 * h + t
        return 60 / math.sqrt(er) * math.log(4 * b / (0.67 * math.pi * (0.8 * w + t)))
    za, zb = max(half(h1), 1.0), max(half(h2), 1.0)
    return 2 * za * zb / (za + zb), er


def diff_microstrip(z0, s, h):
    """Differential impedance of an edge-coupled microstrip pair with gap s (IPC-2141 form)."""
    return 2 * z0 * (1 - 0.48 * math.exp(-0.96 * s / h))


class Stack:
    """Copper layers in order with the dielectric between neighbours."""

    def __init__(self, board):
        self.layers, self.t_cu, self.gaps = [], {}, []      # gaps[i] = (thickness, er) between layer i and i+1
        pend = None
        for name, kind, th, er in board.stackup:
            if kind == 'copper':
                if self.layers:
                    self.gaps.append(pend or (0.2, 4.5))
                self.layers.append(name)
                self.t_cu[name] = th or 0.035
                pend = None
            else:
                pend = (th + (pend[0] if pend else 0.0), er)
        self.assumed = board.stackup_assumed
        self.index = {n: i for i, n in enumerate(self.layers)}

    def between(self, a, b):
        """(distance mm, permittivity) between two copper layers, or None."""
        if a not in self.index or b not in self.index or a == b:
            return None
        i, j = sorted((self.index[a], self.index[b]))
        h = sum(self.gaps[k][0] for k in range(i, j)) + sum(self.t_cu[self.layers[k]] for k in range(i + 1, j))
        er = sum(self.gaps[k][1] * self.gaps[k][0] for k in range(i, j)) / max(sum(self.gaps[k][0] for k in range(i, j)), 1e-9)
        return h, er

    def copper(self, layer):
        return self.t_cu.get(layer, 0.035)


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


class Planes:
    """Where there is plane copper (a filled zone of a ground or supply net) on each layer."""

    def __init__(self, d):
        self.by_layer = {}
        for z in d.board.zones:
            n = d.nets.get(z.net)
            if n is not None and (n.is_ground or n.is_power):
                self.by_layer.setdefault(z.layer, []).append(z)

    def at(self, layer, x, y, not_net=None):
        for z in self.by_layer.get(layer, ()):
            if z.net == not_net:
                continue
            b = z.bbox
            if b[0] <= x <= b[2] and b[1] <= y <= b[3] and any(_in_poly(x, y, p) for p in z.polys):
                return z.net
        return None


def segment(stack: Stack, planes: Planes, t):
    """Line parameters of one Track.  Returns a dict: kind ('microstrip' | 'stripline' | 'none'),
    z0, eeff, tpd (ps/mm), c (pF/mm), l (nH/mm), ref (net names of the reference planes), h."""
    mx, my = (t.x1 + t.x2) / 2, (t.y1 + t.y2) / 2
    i = stack.index.get(t.layer)
    tcu = stack.copper(t.layer)
    refs = []
    if i is not None:
        for j in (i - 1, i + 1):
            if 0 <= j < len(stack.layers):
                net = planes.at(stack.layers[j], mx, my, not_net=t.net)
                if net:
                    h, er = stack.between(t.layer, stack.layers[j])
                    refs.append((h, er, net))
    if len(refs) == 2:
        er = (refs[0][1] + refs[1][1]) / 2
        z0, eeff = stripline(t.width, refs[0][0], refs[1][0], er, tcu)
        kind, h = 'stripline', min(refs[0][0], refs[1][0])
    elif len(refs) == 1:
        z0, eeff = microstrip(t.width, refs[0][0], refs[0][1], tcu)
        if 0 < i < len(stack.layers) - 1:
            eeff = (eeff + refs[0][1]) / 2          # buried: dielectric on both sides
            z0 *= math.sqrt(microstrip(t.width, refs[0][0], refs[0][1], tcu)[1] / eeff)
        kind, h = 'microstrip', refs[0][0]
    else:
        # no plane next to it: a lone conductor.  Typical partial inductance and a weak capacitance.
        l = 0.2 * (math.log(2 * 50.0 / (t.width + tcu)) + 0.5)
        c = 0.035
        return {'kind': 'none', 'z0': None, 'eeff': None, 'tpd': math.sqrt(l * c) * 31.623, 'c': c, 'l': l,      # sqrt(nH x pF) = 31.6 ps
                'ref': [], 'h': None}
    tpd = math.sqrt(eeff) / C0 * 1000           # ps/mm
    return {'kind': kind, 'z0': z0, 'eeff': eeff, 'tpd': tpd, 'c': tpd / z0, 'l': z0 * tpd / 1000,
            'ref': [r[2] for r in refs], 'h': h}


def net_summary(d, net_names, stack=None, planes=None):
    """Length-weighted line parameters over all tracks of the given nets."""
    stack = stack or Stack(d.board)
    planes = planes or Planes(d)
    tot = ref_len = c = delay = 0.0
    zsum = 0.0
    widths, layers = {}, {}
    for t in d.board.tracks:
        if t.net not in net_names or t.length <= 0:
            continue
        p = segment(stack, planes, t)
        tot += t.length
        c += p['c'] * t.length
        delay += p['tpd'] * t.length
        widths[t.width] = widths.get(t.width, 0) + t.length
        layers[t.layer] = layers.get(t.layer, 0) + t.length
        if p['z0']:
            ref_len += t.length
            zsum += p['z0'] * t.length
    if tot <= 0:
        return None
    return {'length': tot, 'c_pf': c, 'delay_ps': delay, 'z0': zsum / ref_len if ref_len else None,
            'referenced': ref_len / tot, 'width': max(widths, key=widths.get), 'layer': max(layers, key=layers.get),
            'vias': sum(1 for v in d.board.vias if v.net in net_names)}
