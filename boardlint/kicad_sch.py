"""KiCad 6-10 schematic reader and netlister (no KiCad install needed).

Produces components (with pin names and electrical types from the embedded
``lib_symbols``) and nets by tracing wires, junctions, labels, power symbols
and hierarchical sheets.  Buses are not expanded (noted in ``Design.notes``).
"""
from __future__ import annotations
import math
import os
from collections import defaultdict
from .sexpr import load, children, child, value, fnum
from .model import Component, Pin


def _q(x: float) -> int:          # quantise to 0.01 mm
    return int(round(x * 100))


class _Lib:
    """Pins of every library symbol embedded in one schematic file."""

    def __init__(self, node):
        self.raw = {}
        for s in children(node, 'symbol') if node else []:
            self.raw[s[1]] = s
        self._cache = {}

    def get(self, name):
        if name in self._cache:
            return self._cache[name]
        s = self.raw.get(name)
        out = {'pins': [], 'power': False}
        if s is not None:
            ext = value(s, 'extends')
            if ext:
                lib = name.split(':')[0] + ':' if ':' in name else ''
                base = self.get(lib + ext) if (lib + ext) in self.raw else self.get(ext)
                out = {'pins': list(base['pins']), 'power': base['power']}
            if child(s, 'power') is not None:
                out['power'] = True
            for sub in children(s, 'symbol'):
                parts = sub[1].rsplit('_', 2)
                unit = int(parts[1]) if len(parts) == 3 and parts[1].isdigit() else 0
                style = int(parts[2]) if len(parts) == 3 and parts[2].isdigit() else 1
                for p in children(sub, 'pin'):
                    at = child(p, 'at')
                    out['pins'].append({
                        'number': str(value(p, 'number', '')), 'name': str(value(p, 'name', '')),
                        'etype': p[1], 'x': fnum(at[1]), 'y': fnum(at[2]), 'unit': unit, 'style': style,
                        'hidden': child(p, 'hide') is not None or 'hide' in p,
                    })
        self._cache[name] = out
        return out


def _xf(px, py, rot, mirror, order):
    """Library coords (y up) -> offset in sheet coords (y down)."""
    def mir(x, y):
        if mirror == 'x':
            return x, -y
        if mirror == 'y':
            return -x, y
        return x, y
    if order == 0:
        px, py = mir(px, py)
    a = math.radians(rot)
    x = px * math.cos(a) - py * math.sin(a)
    y = px * math.sin(a) + py * math.cos(a)
    if order == 1:
        x, y = mir(x, y)
    return x, -y


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        p = self.p
        p.setdefault(a, a)
        while p[a] != a:
            p[a] = p[p[a]]
            a = p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def find_root(project_dir: str):
    schs = sorted(f for f in os.listdir(project_dir) if f.endswith('.kicad_sch'))
    if not schs:
        return None
    pros = [f[:-10] for f in os.listdir(project_dir) if f.endswith('.kicad_pro')]
    for p in pros:
        if p + '.kicad_sch' in schs:
            return os.path.join(project_dir, p + '.kicad_sch')
    referenced = set()
    for f in schs:
        try:
            txt = open(os.path.join(project_dir, f), encoding='utf-8').read()
        except OSError:
            continue
        for g in schs:
            if g != f and ('"%s"' % g) in txt:
                referenced.add(g)
    roots = [f for f in schs if f not in referenced]
    return os.path.join(project_dir, (roots or schs)[0])


def load_schematic(root_path: str):
    """Returns (components: dict ref->Component, nets: dict name->[(ref, pin number)], notes)."""
    uf = _UF()
    comps: dict = {}
    notes: list = []
    pin_nodes = []            # (node, ref, number, etype)
    names = defaultdict(list)  # node -> [(priority, name)]
    global_nodes = defaultdict(list)   # global/power name -> nodes
    cache = {}
    base_dir = os.path.dirname(os.path.abspath(root_path))

    def read(path):
        if path not in cache:
            cache[path] = load(path)
        return cache[path]

    def do_sheet(path, inst_path, human_path, depth=0):
        if depth > 12:
            return {}
        try:
            doc = read(path)
        except OSError as e:
            notes.append(f"cannot read sheet {path}: {e}")
            return {}
        lib = _Lib(child(doc, 'lib_symbols'))
        uuid = value(doc, 'uuid', '')
        if depth == 0:
            inst_path = '/' + str(uuid)
        sid = inst_path
        pts = {}                     # (x, y) -> node id
        def node(x, y):
            k = (_q(x), _q(y))
            pts.setdefault(k, (sid, k))
            return pts[k]
        wires = []
        for w in children(doc, 'wire'):
            xy = children(child(w, 'pts'), 'xy')
            a, b = (fnum(xy[0][1]), fnum(xy[0][2])), (fnum(xy[-1][1]), fnum(xy[-1][2]))
            uf.union(node(*a), node(*b))
            wires.append((_q(a[0]), _q(a[1]), _q(b[0]), _q(b[1])))
        if children(doc, 'bus') and not any('bus' in n for n in notes):
            notes.append("schematic uses buses: bus members are not expanded by the built-in netlister")
        for j in children(doc, 'junction'):
            at = child(j, 'at')
            node(fnum(at[1]), fnum(at[2]))
        labels = {}                  # local label name -> node
        hier = {}                    # hierarchical label name -> node
        for kind in ('label', 'global_label', 'hierarchical_label'):
            for l in children(doc, kind):
                at = child(l, 'at')
                n = node(fnum(at[1]), fnum(at[2]))
                nm = str(l[1])
                if kind == 'label':
                    if nm in labels:
                        uf.union(labels[nm], n)
                    labels[nm] = n
                    names[n].append((2, (human_path if human_path.endswith('/') else human_path + '/') + nm))
                elif kind == 'global_label':
                    global_nodes[nm].append(n)
                    names[n].append((0, nm))
                else:
                    if nm in hier:
                        uf.union(hier[nm], n)
                    hier[nm] = n
                    names[n].append((3, (human_path if human_path.endswith('/') else human_path + '/') + nm))
        # symbols
        for s in children(doc, 'symbol'):
            lib_id = str(value(s, 'lib_id', ''))
            lsym = lib.get(str(value(s, 'lib_name', '')) or lib_id)
            at = child(s, 'at')
            sx, sy, rot = fnum(at[1]), fnum(at[2]), fnum(at[3]) if len(at) > 3 else 0.0
            mirror = value(s, 'mirror')
            unit = int(fnum(value(s, 'unit', 1), 1))
            style = int(fnum(value(s, 'body_style', value(s, 'convert', 1)), 1))
            props = {str(p[1]): str(p[2]) for p in children(s, 'property') if len(p) > 2}
            ref = props.get('Reference', '?')
            inst = child(s, 'instances')
            if inst is not None:
                for proj in children(inst, 'project'):
                    for pth in children(proj, 'path'):
                        if str(pth[1]) == inst_path:
                            ref = str(value(pth, 'reference', ref))
            upins = [p for p in lsym['pins'] if p['unit'] in (0, unit) and p['style'] in (0, style)]
            placed = None
            if mirror and len(upins) > 1:
                # the file does not say whether mirror is applied before or after rotation in
                # a way that is stable across versions: pick the order whose pins hit wiring
                best = -1
                for order in (0, 1):
                    cand = [(_q(sx + dx), _q(sy + dy)) for dx, dy in
                            (_xf(p['x'], p['y'], rot, mirror, order) for p in upins)]
                    hits = sum(1 for c in cand if c in pts or _on_wire(c, wires))
                    if hits > best:
                        best, placed = hits, cand
            else:
                placed = [(_q(sx + dx), _q(sy + dy)) for dx, dy in
                          (_xf(p['x'], p['y'], rot, mirror, 0) for p in upins)]
            is_power = lsym['power'] or ref.startswith('#')
            dnp = str(value(s, 'dnp', 'no')) == 'yes' or str(value(s, 'on_board', 'yes')) == 'no'
            if not is_power:
                c = comps.get(ref)
                if c is None:
                    c = comps[ref] = Component(ref=ref, value=props.get('Value', ''),
                                               footprint=props.get('Footprint', ''), lib_id=lib_id,
                                               props=props, dnp=dnp, sheet=human_path)
            for p, (qx, qy) in zip(upins, placed):
                n = pts.setdefault((qx, qy), (sid, (qx, qy)))
                if is_power:
                    nm = props.get('Value', p['name'])
                    if 'PWR_FLAG' in lib_id or nm == 'PWR_FLAG':
                        continue          # an ERC marker, not a net
                    global_nodes[nm].append(n)
                    names[n].append((1, nm))
                else:
                    pin_nodes.append((n, ref, p['number'], p['name'], p['etype']))
        # anything that lands on the interior of a wire joins it
        for (qx, qy), n in list(pts.items()):
            for w in wires:
                if _on_seg(qx, qy, w):
                    uf.union(n, pts[(w[0], w[1])])
                    break
        # sub-sheets
        for sh in children(doc, 'sheet'):
            props = {str(p[1]): str(p[2]) for p in children(sh, 'property') if len(p) > 2}
            fname = props.get('Sheetfile') or props.get('Sheet file')
            sname = props.get('Sheetname') or props.get('Sheet name') or fname
            if not fname:
                continue
            sub_inst = inst_path + '/' + str(value(sh, 'uuid', ''))
            sub_h = do_sheet(os.path.join(os.path.dirname(path), fname), sub_inst,
                             (human_path if human_path.endswith('/') else human_path + '/') + str(sname), depth + 1)
            for sp in children(sh, 'pin'):
                at = child(sp, 'at')
                n = pts.setdefault((_q(fnum(at[1])), _q(fnum(at[2]))), (sid, (_q(fnum(at[1])), _q(fnum(at[2])))))
                for w in wires:
                    if _on_seg(n[1][0], n[1][1], w):
                        uf.union(n, pts[(w[0], w[1])])
                        break
                if str(sp[1]) in sub_h:
                    uf.union(n, sub_h[str(sp[1])])
        return hier

    do_sheet(os.path.abspath(root_path), '', '/')
    for nm, nodes in global_nodes.items():
        for n in nodes[1:]:
            uf.union(nodes[0], n)
    # name every connected group
    group_names = defaultdict(list)
    for n, lst in names.items():
        group_names[uf.find(n)].extend(lst)
    group_pins = defaultdict(list)
    for n, ref, num, pname, etype in pin_nodes:
        group_pins[uf.find(n)].append((ref, num, pname, etype))
    nets = {}
    for g, plist in group_pins.items():
        cands = sorted(group_names.get(g, []))
        if cands:
            name = cands[0][1]
        elif len(plist) == 1:
            name = None      # unconnected pin
        else:
            r, num, pname, _ = sorted(plist)[0]
            name = f"Net-({r}-{pname if pname and pname != '~' else 'Pad' + num})"
        for ref, num, pname, etype in plist:
            c = comps[ref]
            if num in c.pins and c.pins[num].net:     # stacked duplicate pin numbers
                continue
            c.pins[num] = Pin(comp=c, number=num, name=pname, etype=etype, net=name)
        if name is not None:
            base, k = name, 2
            while name in nets and nets[name] is not plist:
                name = f"{base}_{k}"
                k += 1
            nets[name] = plist
            for ref, num, *_ in plist:
                comps[ref].pins[num].net = name
    return comps, {k: [(r, n) for r, n, *_ in v] for k, v in nets.items()}, notes


def _on_seg(qx, qy, w):
    x1, y1, x2, y2 = w
    if (qx, qy) in ((x1, y1), (x2, y2)):
        return True
    if min(x1, x2) <= qx <= max(x1, x2) and min(y1, y2) <= qy <= max(y1, y2):
        return (x2 - x1) * (qy - y1) == (y2 - y1) * (qx - x1)
    return False


def _on_wire(c, wires):
    return any(_on_seg(c[0], c[1], w) for w in wires)
