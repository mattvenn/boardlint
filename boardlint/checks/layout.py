"""Layout checks that need copper geometry: coupling between nets, return paths, track current."""
from __future__ import annotations
import math
import re
from collections import defaultdict
from . import check, F
from .common import PASSIVE_KINDS, names
from .power_checks import total_load, _summ
from ..classify import signal_group, pulls, caps_to_ground, fmt_r

EPS0 = 8.854e-15        # F/mm


# ----------------------------------------------------------------------------- geometry
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


def _in_zone(x, y, z):
    b = z.bbox
    if not (b[0] <= x <= b[2] and b[1] <= y <= b[3]):
        return False
    return any(_in_poly(x, y, p) for p in z.polys)


def _pt_seg(px, py, t):
    dx, dy = t.x2 - t.x1, t.y2 - t.y1
    l2 = dx * dx + dy * dy
    u = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - t.x1) * dx + (py - t.y1) * dy) / l2))
    return math.hypot(px - (t.x1 + u * dx), py - (t.y1 + u * dy))


def _pt_poly_edge(px, py, poly):
    best = 1e9
    j = len(poly) - 1
    for i in range(len(poly)):
        x1, y1 = poly[j]
        x2, y2 = poly[i]
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        u = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
        best = min(best, math.hypot(px - (x1 + u * dx), py - (y1 + u * dy)))
        j = i
    return best


def _samples(t, step):
    n = max(1, int(math.ceil(t.length / step)))
    dl = t.length / n
    for i in range(n):
        u = (i + 0.5) / n
        yield t.x1 + u * (t.x2 - t.x1), t.y1 + u * (t.y2 - t.y1), dl


def cps_c_per_mm(w, s, er=4.5):
    """Capacitance per mm between two coplanar strips of width w, gap s, on a dielectric half-space
    (conformal-mapping result; Hilberg's approximation for the elliptic-integral ratio)."""
    s = max(s, 0.02)
    k = s / (s + 2 * w)
    kp = math.sqrt(1 - k * k)
    if k <= 0.7071:
        ratio = math.log(2 * (1 + math.sqrt(kp)) / (1 - math.sqrt(kp))) / math.pi       # K(k')/K(k)
    else:
        ratio = math.pi / math.log(2 * (1 + math.sqrt(k)) / (1 - math.sqrt(k)))
    return EPS0 * (er + 1) / 2 * ratio


class _Grid:
    def __init__(self, tracks, cell=2.0):
        self.cell = cell
        self.g = defaultdict(list)
        for t in tracks:
            x0, x1 = sorted((t.x1, t.x2))
            y0, y1 = sorted((t.y1, t.y2))
            for i in range(int(x0 // cell) - 1, int(x1 // cell) + 2):
                for j in range(int(y0 // cell) - 1, int(y1 // cell) + 2):
                    self.g[(i, j)].append(t)

    def near(self, x, y):
        return self.g.get((int(x // self.cell), int(y // self.cell)), ())


# ----------------------------------------------------------------------------- net classes
_CLK = re.compile(r'^(.*_)?(M?CLK|BCLK|XTAL|OSC|XIN|XOUT|SCK|SCLK|PWM)\d*(_.*)?$', re.I)
_SWN = re.compile(r'^(SW|LX|PH|PHASE|BOOT|BST)\d*$', re.I)
_ANA = re.compile(r'SENS|ADC|MON|MEAS|AIN|VREF|NTC|TEMP|MIC|AUDIO|_FB$', re.I)


def classify_nets(d):
    """Returns (aggressors: net -> (reason, swing V), victims: net -> (kind, reason))."""
    agg, vic = {}, {}
    cfg = d.config.get('net_classes') or {}

    def swing(pins):
        from .common import supply_v, can_drive
        v = [supply_v(d, p.comp) for p in pins if p.comp.kind not in PASSIVE_KINDS and can_drive(p) and p.comp.kind == 'IC']
        v = [x[1] for x in v if x]
        return max(v) if v else 3.3

    for c in d.components.values():
        if c.dnp:
            continue
        for p in c.pins.values():
            n = d.net_of(p)
            if n is None or n.is_ground or n.is_power:
                continue
            reason = None
            if p.role in ('led_din', 'led_dout'):
                reason = 'addressable-LED data (800 kHz, nanosecond edges)'
            elif p.role in ('usb_dp', 'usb_dm'):
                reason = 'USB data'
            elif p.role in ('spi_sck', 'spi_ctrl_sck', 'spi_sdi', 'spi_sdo'):
                reason = 'SPI'
            elif p.role in ('uart_tx',):
                reason = 'UART'
            elif c.kind == 'IC' and _SWN.match(p.name or '') and (c.model or {}).get('regulator', {}).get('type') in ('buck', 'boost', None) \
                    and re.match(r'^(SW|LX|PH|PHASE)', p.name or '', re.I):
                reason = 'switching-regulator switch node'
            elif _CLK.match(n.name.split('/')[-1]) or (c.kind == 'IC' and _CLK.match(p.name or '')):
                reason = 'clock'
            if reason:
                nets, _ = signal_group(d, n.name)
                for nn in nets:
                    agg.setdefault(nn, (reason, swing(n.pins)))
            vkind = None
            if p.role == 'touch':
                vkind = ('touch', f"capacitive-touch electrode of {c.ref}")
            elif p.role == 'analog_in' or _ANA.search(n.name):
                vkind = ('analog', 'analog / measurement node')
            elif c.kind == 'XTAL':
                vkind = ('analog', 'crystal')
            elif p.role in ('enable', 'reset') or (c.model or {}).get('regulator', {}).get('fb') == p.name:
                ups, downs = pulls(d, n.name)
                rs = [r.num for r, _ in ups + downs]
                if rs and min(rs) >= 47e3 and not any(q.etype == 'output' and q.comp.kind == 'IC' and q is not p
                                                      and q.spec.get('drive') not in ('open_drain',) and q.etype != 'open_collector'
                                                      for q in n.pins):
                    vkind = ('highz', f"{p.role} of {c.ref}, held only by {fmt_r(min(rs))}")
            if vkind:
                nets, _ = signal_group(d, n.name, max_ohm=10e3)
                for nn in nets:
                    vic.setdefault(nn, vkind)
    for nn in cfg.get('aggressor') or []:
        if nn in d.nets:
            agg.setdefault(nn, ('boardlint.yaml', 3.3))
    for nn in cfg.get('victim') or []:
        if nn in d.nets:
            vic.setdefault(nn, ('analog', 'boardlint.yaml'))
    for nn in list(agg):
        vic.pop(nn, None) if nn in vic and vic[nn][0] != 'touch' else None
    return agg, vic


@check('layout.coupling', 'layout', needs_board=True,
       doc='Aggressor / victim: fast nets running beside or across sensitive nets (estimated coupling capacitance)')
def coupling(d):
    b = d.board
    agg, vic = classify_nets(d)
    if not agg or not vic or not b.tracks:
        return
    nl = max(len(b.copper_layers), 2)
    h_adj = b.thickness / (nl - 1)                         # dielectric between neighbouring copper layers
    order = {l: i for i, l in enumerate(b.copper_layers)}
    vt = [t for t in b.tracks if t.net in vic]
    grids = {}
    for layer in {t.layer for t in vt}:
        grids[layer] = _Grid([t for t in vt if t.layer == layer])
    vz = [z for z in b.zones if z.net in vic]
    max_gap = float((d.config.get('coupling') or {}).get('max_gap_mm', 1.5))
    pair = defaultdict(lambda: {'edge_mm': 0.0, 'over_mm': 0.0, 'c': 0.0, 'gap': 1e9, 'shielded_mm': 0.0})
    gz = [z for z in b.zones if z.net in d.nets and d.nets[z.net].is_ground]
    layers = b.copper_layers or ['F.Cu', 'B.Cu']
    for t in b.tracks:
        if t.net not in agg:
            continue
        li = layers.index(t.layer) if t.layer in layers else 0
        adj = [layers[j] for j in (li - 1, li + 1) if 0 <= j < len(layers)]
        for x, y, dl in _samples(t, 0.25):
            hit = {}
            plane = any(z.layer in adj and _in_zone(x, y, z) for z in gz)
            for v in grids.get(t.layer, _Grid([])).near(x, y):
                if v.net == t.net:
                    continue
                gap = _pt_seg(x, y, v) - (t.width + v.width) / 2
                if gap < max_gap and gap < hit.get(v.net, (1e9,))[0]:
                    hit[v.net] = (gap, (t.width + v.width) / 2)
            for net, (gap, w) in hit.items():
                cpm = cps_c_per_mm(w, max(gap, 0.05))
                pr = pair[(t.net, net)]
                if plane:
                    cpm /= 1 + (max(gap, 0.05) / h_adj) ** 2          # ground on the next layer pulls the field in
                    pr['shielded_mm'] += dl
                pr['edge_mm'] += dl
                pr['c'] += cpm * dl
                pr['gap'] = min(pr['gap'], gap)
            for z in vz:
                if z.net == t.net:
                    continue
                bb = z.bbox
                if not (bb[0] - max_gap <= x <= bb[2] + max_gap and bb[1] - max_gap <= y <= bb[3] + max_gap):
                    continue
                inside = any(_in_poly(x, y, p) for p in z.polys)
                if z.layer == t.layer:
                    if inside:
                        continue
                    gap = min(_pt_poly_edge(x, y, p) for p in z.polys) - t.width / 2
                    if gap < max_gap:
                        cpm = cps_c_per_mm(t.width * 2, max(gap, 0.05))
                        pr = pair[(t.net, z.net)]
                        if plane:
                            cpm /= 1 + (max(gap, 0.05) / h_adj) ** 2
                            pr['shielded_mm'] += dl
                        pr['edge_mm'] += dl
                        pr['c'] += cpm * dl
                        pr['gap'] = min(pr['gap'], gap)
                elif inside:
                    steps = abs(order.get(z.layer, 0) - order.get(t.layer, 0)) or 1
                    h = h_adj * steps
                    cpm = EPS0 * 4.5 * (t.width + 2 * 0.3 * h) / h      # parallel plate with a fringe allowance
                    pr = pair[(t.net, z.net)]
                    pr['over_mm'] += dl
                    pr['c'] += cpm * dl
    # roll up per (aggressor group, victim)
    out = []
    for (a, v), pr in pair.items():
        if pr['c'] <= 0:
            continue
        kind, why = vic[v]
        c_pf = pr['c'] * 1e12
        reason, sw = agg[a]
        ev = {'coupled_C_est_pF': round(c_pf, 3), 'side_by_side_mm': round(pr['edge_mm'], 1),
              'min_gap_mm': round(pr['gap'], 2) if pr['gap'] < 1e8 else None,
              'crossing_over_mm': round(pr['over_mm'], 1),
              'of_which_over_ground_mm': round(pr['shielded_mm'], 1), 'aggressor': f"{a}: {reason}, {sw:g} V swing",
              'victim': f"{v}: {why}"}
        sev, detail = None, ''
        if kind == 'touch':
            if c_pf >= 0.05:
                sev = 'warning' if c_pf >= 0.3 else 'info'
                detail = (f"A fingertip changes an electrode by around a picofarad or less. {c_pf:.2f} pF to a line "
                          f"toggling {sw:g} V can show up as touch noise or false touches while that line is active.")
        else:
            cnode = sum(k.num or 0 for k, _ in caps_to_ground(d, v)) + 5e-12
            dv = sw * pr['c'] / (pr['c'] + cnode)
            ev['victim_node_C_pF'] = round(cnode * 1e12, 1)
            ev['injected_step_est_mV'] = round(dv * 1000, 1)
            lim = 0.3 if kind == 'highz' else 0.02
            if dv >= lim / 3:
                sev = 'warning' if dv >= lim else 'info'
                detail = (f"Each aggressor edge kicks the victim by about {dv * 1000:.0f} mV "
                          f"(capacitive divider against {cnode * 1e12:.0f} pF on the node).")
        if sev:
            geo = []
            if pr['edge_mm'] >= 0.5:
                geo.append(f"{pr['edge_mm']:.0f} mm side by side on one layer, down to {max(pr['gap'], 0):.2f} mm apart")
            if pr['over_mm'] >= 0.5:
                geo.append(f"{pr['over_mm']:.0f} mm directly above or below it")
            out.append((c_pf, F('layout.coupling', sev, f"{a} couples into {v} ({why.split(',')[0]})",
                                f"{a} ({reason}) runs {' and '.join(geo)}. {detail} Estimated {c_pf:.2f} pF; "
                                f"closed-form estimate, not a field solve.", nets=[a, v], evidence=ev,
                                basis='coplanar-strip and parallel-plate capacitance formulas on the board geometry; '
                                      'net classes from pin roles (override in boardlint.yaml net_classes:)',
                                confidence='low')))
    out.sort(key=lambda x: -x[0])
    for _, f in out[:12]:
        yield f
    if len(out) > 12:
        yield F('layout.coupling', 'info', f"{len(out) - 12} more coupled pairs below the top 12", confidence='low')
    yield F('layout.coupling', 'info', f"Net classes used for coupling: {len(agg)} aggressor, {len(vic)} victim net(s)",
            "Aggressors: " + ', '.join(sorted(agg)[:14]) + ('...' if len(agg) > 14 else '') +
            ". Victims: " + ', '.join(sorted(vic)[:20]) + ('...' if len(vic) > 20 else '') + ".",
            confidence='medium')


@check('layout.return_path', 'layout', needs_board=True,
       doc='Fast nets should run over unbroken ground copper on the neighbouring layer')
def return_path(d):
    b = d.board
    gz = [z for z in b.zones if z.net in d.nets and d.nets[z.net].is_ground]
    if not gz:
        yield F('layout.return_path', 'info', 'No filled ground zones on the board: return-path check skipped',
                'Fill the zones in KiCad and save, or the board has no ground pour.', confidence='high')
        return
    agg, _ = classify_nets(d)
    layers = b.copper_layers or ['F.Cu', 'B.Cu']
    for net, (reason, _) in sorted(agg.items()):
        tot = unc = 0.0
        gaps = 0
        for t in b.tracks:
            if t.net != net or t.layer not in layers:
                continue
            i = layers.index(t.layer)
            adj = [layers[j] for j in (i - 1, i + 1) if 0 <= j < len(layers)]
            prev = True
            for x, y, dl in _samples(t, 0.5):
                cov = any(z.layer in adj and _in_zone(x, y, z) for z in gz)
                tot += dl
                if not cov:
                    unc += dl
                    if prev:
                        gaps += 1
                prev = cov
        if tot >= 10 and unc / tot >= 0.25:
            yield F('layout.return_path', 'warning' if unc / tot >= 0.5 and tot >= 30 else 'info',
                    f"{net}: {unc / tot:.0%} of its {tot:.0f} mm has no ground copper on the other layer",
                    f"{net} ({reason}). Where the reference copper is missing the return current detours, the loop "
                    f"area grows, and the trace both radiates and picks up more. {gaps} stretch(es) without cover.",
                    nets=[net], evidence={'length_mm': round(tot, 1), 'uncovered_mm': round(unc, 1), 'stretches': gaps},
                    basis='filled ground zones in the board file, sampled every 0.5 mm along the tracks',
                    confidence='medium')


@check('layout.track_current', 'layout', needs_board=True,
       doc='Supply tracks wide enough for the current behind them (IPC-2221, 10 C rise)')
def track_current(d):
    b = d.board
    rise = float((d.config.get('track') or {}).get('temp_rise_c', 10))
    over = defaultdict(list)
    for n in d.nets.values():
        if not n.is_power or n.is_ground:
            continue
        _, mx, parts = total_load(d, n)
        if mx < 50:
            continue
        tr = [t for t in b.tracks if t.net == n.name and t.length >= 1.0]
        if not tr:
            continue
        w = min(t.width for t in tr)
        narrow = sum(t.length for t in tr if t.width <= w * 1.05)
        area_mil2 = (w / 0.0254) * (b.copper_um / 25.4)
        cap_a = 0.048 * rise ** 0.44 * area_mil2 ** 0.725
        r_mohm = 1.72e-5 * narrow / (w * b.copper_um * 1e-3) * 1000
        ev = {'narrowest_mm': w, 'length_at_that_width_mm': round(narrow, 1), 'capacity_A': round(cap_a, 2),
              'load_max_mA': round(mx), 'loads': _summ(parts), 'drop_mV_at_max': round(r_mohm * mx / 1000, 1)}
        if mx / 1000 > cap_a:
            over[(w, round(cap_a, 2))].append((n.name, mx, narrow, ev))
        elif r_mohm * mx / 1000 > 100 and n.vmax:
            yield F('layout.track_current', 'info', f"{n.name}: about {r_mohm * mx / 1000:.0f} mV lost in {narrow:.0f} mm of {w:g} mm track at {mx:.0f} mA",
                    f"If that length is in series with the load, it is {r_mohm:.0f} mohm.", nets=[n.name], evidence=ev,
                    basis='copper resistivity; assumes the narrow segments are in series', confidence='low')
    for (w, cap_a), lst in over.items():
        lst.sort(key=lambda x: -x[1])
        yield F('layout.track_current', 'warning',
                f"{w:g} mm supply tracks carry up to {lst[0][1]:.0f} mA ({', '.join(x[0] for x in lst)})",
                f"IPC-2221 gives {cap_a:.2f} A for a {rise:g} C rise at this width in {b.copper_um:g} um copper. "
                + '; '.join(f"{nm}: {mx:.0f} mA, {nar:.0f} mm at this width" for nm, mx, nar, _ in lst)
                + ". Not every segment carries a net's whole current: check the ones between the source and the "
                  "loads, and widen or pour them. The resistance also costs voltage: see the droop result.",
                nets=[x[0] for x in lst], evidence=lst[0][3],
                basis='IPC-2221 external-layer formula; load is the sum of model maxima, all on at once',
                confidence='low')
