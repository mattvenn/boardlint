"""Two boards that plug together: a baseboard and a carrier (or mezzanine, shield, module).

Three things are done here:

1. `find_mating`: lay the carrier's connector pads over the baseboard's.  KiCad stores every board
   as seen from its top side, so a carrier that sits face up on a baseboard needs only a shift and
   a turn to line up, never a mirror; one that sits face down needs a mirror.  Pads are paired by
   where they are, not by their numbers, because a board-to-board connector joins the contacts
   that are above one another whatever the footprints call them.
2. `mate_findings`: for every pair of pads, compare what each board puts there: ground against
   ground, the same rail voltage, a signal against a signal with a matching name and bit number.
3. `merge`: one design made of both boards with the paired nets joined, so that every other check
   (levels, pull-ups, bus addresses, supply budget) sees the whole system.
"""
from __future__ import annotations
import math
import re
from collections import defaultdict
from .model import Design, Net, Finding

F = Finding
TAG = 'carrier/'


def connector_pads(d, refs=None, min_pads=16):
    """[(component, pin)] for the pads of board-to-board candidates: named connectors, or every
    connector with at least `min_pads` pads that have a position."""
    out = []
    for c in d.components.values():
        if refs is not None:
            if c.ref not in refs:
                continue
        elif c.kind != 'CONN' or c.dnp:
            continue
        pads = [p for p in c.pins.values() if p.pos]
        if refs is None and len(pads) < min_pads:
            continue
        out += [(c, p) for p in pads]
    return out


def _pitch(pts):
    """Smallest centre distance between two pads, from a sample."""
    best = 1e9
    s = pts[:400]
    for i, a in enumerate(s):
        for b in s[i + 1:]:
            dd = math.hypot(a[0] - b[0], a[1] - b[1])
            if 1e-6 < dd < best:
                best = dd
    return best if best < 1e8 else 1.0


def find_mating(base, carrier, base_refs=None, carrier_refs=None):
    """Best overlay of the carrier's connector pads on the baseboard's.  Returns a dict:
    pairs [(base pin, carrier pin)], rot (degrees), mirrored, shift, counts, residual (mm),
    unmatched_base, unmatched_carrier, ambiguous; or None if nothing lines up."""
    bp = connector_pads(base, base_refs)
    cp = connector_pads(carrier, carrier_refs)
    if not bp or not cp:
        return None
    bxy = [p.pos for _, p in bp]
    tol = min(0.3 * min(_pitch(bxy), _pitch([p.pos for _, p in cp])), 0.5)
    cell = max(tol, 0.05)
    grid = defaultdict(list)
    for i, (x, y) in enumerate(bxy):
        grid[(int(math.floor(x / cell)), int(math.floor(y / cell)))].append(i)

    def near(x, y):
        best = None
        gi, gj = int(math.floor(x / cell)), int(math.floor(y / cell))
        for i in range(gi - 1, gi + 2):
            for j in range(gj - 1, gj + 2):
                for k in grid.get((i, j), ()):
                    dd = math.hypot(bxy[k][0] - x, bxy[k][1] - y)
                    if dd <= tol and (best is None or dd < best[0]):
                        best = (dd, k)
        return best

    def klass(d, p):
        n = d.net_of(p)
        return 'none' if n is None else 'gnd' if n.is_ground else 'pwr' if n.is_power else 'sig'

    # anchors: a few carrier pads tried against every baseboard pad
    by_comp = defaultdict(list)
    for c, p in cp:
        by_comp[c.ref].append(p)
    anchors = [ps[0] for ps in sorted(by_comp.values(), key=len, reverse=True)[:3]]
    cands = []
    for mirrored in (False, True):
        for rot in (0, 90, 180, 270):
            ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))

            def tf(pos):
                x, y = (-pos[0], pos[1]) if mirrored else pos
                return x * ca - y * sa, x * sa + y * ca
            cxy = [tf(p.pos) for _, p in cp]
            seen = set()
            for a in anchors:
                ax, ay = tf(a.pos)
                for (bx, by) in bxy:
                    dx, dy = bx - ax, by - ay
                    key = (round(dx / cell), round(dy / cell))
                    if key in seen:
                        continue
                    seen.add(key)
                    hits = [(near(x + dx, y + dy), j) for j, (x, y) in enumerate(cxy)]
                    hits = [(h[1], j, h[0]) for h, j in hits if h is not None]
                    if len(hits) < 4:
                        continue
                    used = {}
                    for k, j, dd in hits:                       # one carrier pad per baseboard pad
                        if k not in used or dd < used[k][1]:
                            used[k] = (j, dd)
                    agree = sum(1 for k, (j, _) in used.items() if klass(base, bp[k][1]) == klass(carrier, cp[j][1]) != 'none')
                    cands.append((len(used), agree, not mirrored, -rot, mirrored, rot, dx, dy, used))
    if not cands:
        return None
    cands.sort(key=lambda c: c[:4], reverse=True)
    n, agree, _, _, mirrored, rot, dx, dy, used = cands[0]
    rivals = [c for c in cands[1:] if c[0] == n and (c[4], c[5]) != (mirrored, rot)]
    pairs = [(bp[k][1], cp[j][1]) for k, (j, _) in sorted(used.items())]
    mb, mc = {id(p) for p, _ in pairs}, {id(q) for _, q in pairs}
    # only connectors that took part count when listing what was left over
    brefs, crefs = {p.comp.ref for p, _ in pairs}, {q.comp.ref for _, q in pairs}
    return {'pairs': pairs, 'rot': rot, 'mirrored': mirrored, 'shift': (dx, dy), 'tol': tol,
            'residual': max(dd for _, dd in used.values()),
            'unmatched_base': [p for c, p in bp if c.ref in brefs and id(p) not in mb],
            'unmatched_carrier': [p for c, p in cp if c.ref in crefs and id(p) not in mc],
            'base_refs': sorted(brefs), 'carrier_refs': sorted(crefs), 'class_agree': agree,
            'ambiguous': bool(rivals and rivals[0][1] == agree),
            'best_other': max([c[0] for c in cands[1:] if (c[4], c[5]) != (mirrored, rot)] or [0])}


# ----------------------------------------------------------------------------- comparing the two sides
_KEYWORDS = ('clk', 'clock', 'rst', 'reset', 'ena', 'en', 'inc', 'sel', 'sda', 'scl', 'tx', 'rx', 'mosi', 'miso',
             'sck', 'cs', 'cts', 'rts', 'dp', 'dm', 'irq', 'int')


def _label(d, p):
    """What the board calls this contact: the connector's pin name when it has one, else the net."""
    nm = (p.name or '').strip()
    if nm and nm != p.number and not re.fullmatch(r'(Pin_)?\d+|[A-Z]?\d+', nm):
        return nm
    return (p.net or '').split('/')[-1]


def _split(label):
    """('uio', 3) from 'uio[3]', '/uio3' or 'uio_3'; ('an', 0) from 'anA'; (stem, None) otherwise."""
    s = re.sub(r'[\[\]{}~()]', '', label).strip('/')
    m = re.fullmatch(r'(.*?)[_\-.]?(\d+)', s)
    if m and m.group(1):
        return m.group(1).lower().rstrip('_'), int(m.group(2))
    m = re.fullmatch(r'(.*[a-z])([A-Z])', s)
    if m:
        return m.group(1).lower(), ord(m.group(2)) - 65
    return s.lower(), None


def _words(label):
    return set(re.findall(r'[a-z]+', re.sub(r'([a-z])([A-Z])', r'\1_\2', label).lower()))


def _driven(d, n):
    from .checks.common import can_drive
    return [p for p in n.pins if p.comp.kind == 'IC' and can_drive(p) and p.spec.get('drive') not in ('open_drain', 'input', 'analog')
            and p.role not in ('gpio', '')]


def mate_findings(base, carrier, m, expect_mirror=None):
    """Findings about the connector between two prepared designs.  `m` is find_mating's result."""
    if m is None:
        yield F('mate.geometry', 'error', 'The two boards have no connectors that line up',
                'No shift and turn, with or without a mirror, puts four or more connector pads of the carrier over '
                'pads of the baseboard. Name the connectors with --base-conn and --carrier-conn if they were not found.',
                basis='pad positions in the two board files', confidence='medium')
        return
    pairs = m['pairs']
    bside = {p.comp.side for p, _ in pairs}
    cside = {q.comp.side for _, q in pairs}
    if expect_mirror is None:
        # face up on top of the baseboard: the two connectors are on opposite sides.  Same side: face down.
        expect_mirror = bool(bside == cside and len(bside) == 1)
    how = f"turned {m['rot']} degrees" if m['rot'] else 'not turned'
    ev = {'pads_paired': len(pairs), 'baseboard_connectors': ', '.join(m['base_refs']), 'carrier_connectors': ', '.join(m['carrier_refs']),
          'carrier_orientation': how + (', mirrored' if m['mirrored'] else ''), 'largest_offset_mm': round(m['residual'], 3),
          'pairing_tolerance_mm': round(m['tol'], 3), 'baseboard_side': '/'.join(sorted(bside)), 'carrier_side': '/'.join(sorted(cside))}
    if m['mirrored'] != expect_mirror:
        yield F('mate.geometry', 'error', 'The connectors only line up if one board is mirrored',
                f"The carrier's pads fall on the baseboard's only {'with' if m['mirrored'] else 'without'} a mirror, but the "
                f"connectors are on side {ev['baseboard_side']} of the baseboard and side {ev['carrier_side']} of the carrier, "
                f"which needs the opposite. One footprint is drawn or numbered as seen from the wrong side, or it is on the wrong side.",
                refs=m['base_refs'] + [TAG + r for r in m['carrier_refs']], evidence=ev,
                basis='pad positions; both board files are stored as seen from the top', confidence='medium')
    left_b = [p for p in m['unmatched_base'] if p.net]
    left_c = [p for p in m['unmatched_carrier'] if p.net]
    yield F('mate.geometry', 'warning' if left_b or left_c else 'info',
            f"{len(pairs)} connector pads of the carrier line up with the baseboard's"
            + (f"; {len(left_b) + len(left_c)} connected pad(s) have no partner" if left_b or left_c else ''),
            f"Carrier {how}{', mirrored' if m['mirrored'] else ''}; pads paired by position, largest offset "
            f"{m['residual']:.3f} mm. " +
            (f"Baseboard pads with a net and no carrier pad over them: {', '.join(p.label for p in left_b[:10])}. " if left_b else '') +
            (f"Carrier pads with a net and no baseboard pad under them: {', '.join(p.label for p in left_c[:10])}. " if left_c else '') +
            ("Another orientation fits as many pads and agrees as well on ground and supply pads: the orientation is not "
             "fixed by the copper alone. " if m['ambiguous'] else ''),
            refs=m['base_refs'] + [TAG + r for r in m['carrier_refs']], evidence=ev,
            basis='pad positions in the two board files', confidence='high' if not m['ambiguous'] else 'low')

    shorts, rails, half, tied, rows = [], [], [], [], []
    groups = defaultdict(list)
    for bp, cp in pairs:
        nb, nc = base.net_of(bp), carrier.net_of(cp)
        lb, lc = _label(base, bp), _label(carrier, cp)
        rows.append((bp, cp, nb, nc, lb, lc))
        if nb is None or nc is None:
            if (nb or nc) is not None:
                half.append((bp, cp, nb, nc))
            continue
        if nb.is_ground and nc.is_ground:
            continue
        if nb.is_ground != nc.is_ground:
            g, o, od, op = (nb, nc, carrier, cp) if nb.is_ground else (nc, nb, base, bp)
            if o.is_power:
                shorts.append((bp, cp, nb, nc))
            else:
                tied.append((bp, cp, nb, nc, _driven(od, o)))
            continue
        if nb.is_power or nc.is_power:
            rails.append((bp, cp, nb, nc))
            continue
        groups[(_split(lb)[0], _split(lc)[0])].append((bp, cp, lb, lc))

    for bp, cp, nb, nc in shorts:
        rail, gnd = (nc, nb) if nb.is_ground else (nb, nc)
        yield F('mate.pins', 'error', f"Supply {rail.name} meets ground across the connector at {bp.label}",
                f"Baseboard {bp.label} is on {nb.name}; the carrier pad over it, {cp.label}, is on {nc.name}. "
                f"Plugging the boards together shorts the rail.", refs=[bp.comp.ref, TAG + cp.comp.ref], nets=[nb.name, nc.name],
                basis='paired pads and each board\'s netlist', confidence='high')
    bad_v, sig_pwr, okr = [], [], []
    for bp, cp, nb, nc in rails:
        if nb.is_power and nc.is_power:
            if nb.vnom and nc.vnom and abs(nb.vnom - nc.vnom) > 0.1 * max(nb.vnom, nc.vnom):
                bad_v.append((bp, cp, nb, nc))
            else:
                okr.append((bp, cp, nb, nc))
        else:
            sig_pwr.append((bp, cp, nb, nc))
    for bp, cp, nb, nc in bad_v:
        yield F('mate.pins', 'error', f"{nb.name} ({nb.vnom:g} V) on the baseboard meets {nc.name} ({nc.vnom:g} V) on the carrier",
                f"At {bp.label} / carrier {cp.label}. Two rails of different voltage are joined by the connector.",
                refs=[bp.comp.ref, TAG + cp.comp.ref], nets=[nb.name, nc.name],
                evidence={'baseboard': f"{nb.name}: {nb.vsrc}", 'carrier': f"{nc.name}: {nc.vsrc}"},
                basis='paired pads; rail voltages as inferred on each board', confidence='medium')
    seen = set()
    for bp, cp, nb, nc in sig_pwr:
        rail, sig, sd = (nb, nc, carrier) if nb.is_power else (nc, nb, base)
        if (rail.name, sig.name) in seen:
            continue
        seen.add((rail.name, sig.name))
        drv = _driven(sd, sig)
        yield F('mate.pins', 'warning' if drv else 'info',
                f"Supply {rail.name} on one board meets signal {sig.name} on the other",
                f"At {bp.label} / carrier {cp.label}. " + (f"{', '.join(p.label for p in drv[:3])} drives that signal: an output is tied to a rail. "
                                                              if drv else "Nothing on that board drives the signal, so it simply takes the rail's voltage. "),
                refs=[bp.comp.ref, TAG + cp.comp.ref], nets=[nb.name, nc.name], basis='paired pads and each board\'s netlist', confidence='medium')
    hard = [t for t in tied if t[4]]
    for bp, cp, nb, nc, drv in hard:
        sig = nc if nb.is_ground else nb
        yield F('mate.pins', 'warning', f"{sig.name} is driven on one board and grounded by the other",
                f"At {bp.label} / carrier {cp.label}: {', '.join(p.label for p in drv[:3])} can drive {sig.name}, and the pad it "
                f"meets is ground. If that output is ever driven high it is shorted.",
                refs=[bp.comp.ref, TAG + cp.comp.ref] + [p.comp.ref for p in drv[:2]], nets=[nb.name, nc.name],
                basis='paired pads and each board\'s netlist', confidence='medium')
    soft = [t for t in tied if not t[4]]
    if soft:
        yield F('mate.pins', 'info', f"{len(soft)} signal(s) of one board are grounded by the other",
                '; '.join(f"{(nc if nb.is_ground else nb).name} ({'baseboard' if nc.is_ground else 'carrier'}) at {bp.label}"
                          for bp, cp, nb, nc, _ in soft[:24]) + ('...' if len(soft) > 24 else '') +
                '. Nothing with a push-pull output drives them, so this is harmless: the usual reason is a signal the '
                'other board does not use.', refs=[m['base_refs'][0]], basis='paired pads and each board\'s netlist', confidence='medium')
    if half:
        used = [(bp, cp, nb, nc) for bp, cp, nb, nc in half]
        yield F('mate.pins', 'info', f"{len(used)} contact(s) are connected on one board only",
                '; '.join(f"{(nb or nc).name} at {(bp if nb else cp).label} ({'baseboard' if nb else 'carrier'} only)" for bp, cp, nb, nc in used[:24])
                + ('...' if len(used) > 24 else '') + '.', refs=[m['base_refs'][0]], basis='paired pads', confidence='high')

    # signals: bit numbers within a bus, then single signals by keyword
    for (sb, sc), items in sorted(groups.items()):
        idx = [(_split(lb)[1], _split(lc)[1], bp, cp, lb, lc) for bp, cp, lb, lc in items]
        num = [t for t in idx if t[0] is not None and t[1] is not None]
        if len(num) >= 2 and {t[0] for t in num} == {t[1] for t in num}:
            wrong = [t for t in num if t[0] != t[1]]
            if wrong:
                yield F('mate.pins', 'warning', f"Bus {sb} / {sc}: {len(wrong)} bit(s) meet a different bit number on the other board",
                        '; '.join(f"baseboard {lb} ({bp.label}) meets carrier {lc} ({cp.label})" for _, _, bp, cp, lb, lc in wrong[:12]) +
                        '. Both boards number this bus over the same range, so a crossed pair is likely a mistake.',
                        refs=[wrong[0][2].comp.ref, TAG + wrong[0][3].comp.ref], nets=[t[2].net for t in wrong[:8]],
                        basis='paired pads; names on each board', confidence='medium')
    for (sb, sc), items in sorted(groups.items()):
        num = [(_split(lb)[1], _split(lc)[1], lb, lc) for bp, cp, lb, lc in items if _split(lb)[1] is not None and _split(lc)[1] is not None]
        offs = {c - b for b, c, _, _ in num}
        if len(num) >= 2 and len(offs) == 1 and offs != {0} and {b for b, _, _, _ in num} != {c for _, c, _, _ in num} \
                and (sb == sc or sb.startswith(sc) or sc.startswith(sb)):
            num.sort()
            yield F('mate.pins', 'info', f"{sb} / {sc}: the two boards number the same signals {abs(offs.pop())} apart",
                    f"Baseboard {num[0][2]} to {num[-1][2]} meet carrier {num[0][3]} to {num[-1][3]}. The copper is one-to-one; "
                    f"only the names differ. Worth knowing when reading the two schematics or writing firmware against either.",
                    refs=[m['base_refs'][0]], basis='paired pads; names on each board', confidence='medium')
    singles = [(bp, cp, lb, lc) for (sb, sc), items in groups.items() for bp, cp, lb, lc in items
               if _split(lb)[1] is None or _split(lc)[1] is None]
    for bp, cp, lb, lc in singles:
        kb, kc = _words(lb) & set(_KEYWORDS), _words(lc) & set(_KEYWORDS)
        alias = {'clock': 'clk', 'reset': 'rst', 'en': 'ena'}
        kb, kc = {alias.get(k, k) for k in kb}, {alias.get(k, k) for k in kc}
        if kb and kc and not (kb & kc):
            yield F('mate.pins', 'warning', f"Baseboard {lb} meets carrier {lc}",
                    f"At {bp.label} / carrier {cp.label}. The two names say different things ({', '.join(sorted(kb))} against "
                    f"{', '.join(sorted(kc))}). Check that these two signals are meant to be joined.",
                    refs=[bp.comp.ref, TAG + cp.comp.ref], nets=[bp.net, cp.net], basis='paired pads; names on each board', confidence='low')
    # the whole map, for a person to read
    table = []
    for bp, cp, nb, nc, lb, lc in sorted(rows, key=lambda r: (r[0].comp.ref, len(r[0].number), r[0].number)):
        if nb is None and nc is None:
            continue
        if nb is not None and nc is not None and nb.is_ground and nc.is_ground:
            continue
        table.append(f"{bp.number} {nb.name if nb else '-'} = {cp.comp.ref}.{cp.number} {nc.name if nc else '-'}")
    yield F('mate.pins', 'info', f"Connector map: {len(table)} contacts other than ground",
            '; '.join(table), refs=[m['base_refs'][0]],
            evidence={'ground_contacts': sum(1 for r in rows if r[2] is not None and r[3] is not None and r[2].is_ground and r[3].is_ground),
                      'supply_contacts_agreeing': len(okr)},
            basis='paired pads and each board\'s netlist', confidence='high')


# ----------------------------------------------------------------------------- one design from two
def merge(base, carrier, m, tag=TAG):
    """A design holding both prepared boards, with the nets of paired pads joined.  Baseboard
    references and net names are kept; the carrier's get `tag` in front.  It has no board: layout
    checks are run on each board by itself."""
    from .power import analyse_power
    parent = {}

    def find(k):
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for n in base.nets:
        find(('b', n))
    for n in carrier.nets:
        find(('c', n))
    for bp, cp in (m['pairs'] if m else []):
        if bp.net and cp.net:
            ra, rb = find(('b', bp.net)), find(('c', cp.net))
            if ra != rb:
                parent[rb] = ra
    members = defaultdict(list)
    for k in list(parent):
        members[find(k)].append(k)
    name_of = {}
    for root, ks in members.items():
        bnames = sorted(n for s, n in ks if s == 'b')
        cnames = sorted(n for s, n in ks if s == 'c')
        if bnames:
            # prefer a name the power analysis understood
            pick = next((n for n in bnames if base.nets[n].is_ground), None) or \
                next((n for n in bnames if base.nets[n].is_power), None) or bnames[0]
        else:
            pick = tag + cnames[0]
        for k in ks:
            name_of[k] = pick
    d = Design(name=f"{base.name} + {carrier.name}")
    d.config = dict(base.config)
    for key in ('rails', 'sources'):                      # the carrier's own declarations, under its merged names
        for n, v in (carrier.config.get(key) or {}).items():
            d.config.setdefault(key, {})
            d.config[key] = dict(d.config[key])
            d.config[key].setdefault(name_of.get(('c', n), tag + n), v)
    d.sources = list(base.sources) + list(carrier.sources)
    d.notes = [f"{len(m['pairs']) if m else 0} connector contacts join the two boards"]
    d.sync = {'fp': [], 'only_sch': [], 'only_pcb': [], 'net_groups': 0}
    for side, src, pre in (('b', base, ''), ('c', carrier, tag)):
        for c in src.components.values():
            c.ref = pre + c.ref
            d.components[c.ref] = c
            for p in c.pins.values():
                if p.net:
                    p.net = name_of[(side, p.net)]
                    d.nets.setdefault(p.net, Net(name=p.net)).pins.append(p)
    d.unmodelled = list(getattr(base, 'unmodelled', [])) + list(getattr(carrier, 'unmodelled', []))
    d.board = None
    analyse_power(d)
    return d
