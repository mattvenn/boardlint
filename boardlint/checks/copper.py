"""Checks built on the copper extraction (boardlint.extract) and the line formulas (boardlint.tline):
IR drop to every load, current in every track segment, and impedance / delay of fast nets."""
from __future__ import annotations
import math
import re
from collections import defaultdict
from . import check, F
from .common import can_drive
from .power_checks import total_load
from ..extract import CopperNet, ipc2221_amps
from ..library import supply_spec
from ..power import power_links, rail_loads, _pins_named
from .. import tline


def copper_net(d, name):
    cache = d.__dict__.setdefault('_copper', {})
    if name not in cache:
        cache[name] = CopperNet(d, name)
    return cache[name]


def flow_depth(d):
    """power.power_depth, extended to rails it does not reach: a rail fed through a diode from a net
    that is not itself a supply (a barrel jack behind a reverse-protection diode), then rails fed
    from a part's supply-output pin."""
    if '_flow_depth' in d.__dict__:
        return d.__dict__['_flow_depth']
    depth = dict(getattr(d, 'power_depth', {}))

    def spread(todo):
        while todo:
            n = todo.pop(0)
            for p in n.pins:
                c = p.comp
                if c.dnp:
                    continue
                nxt = []
                for a, b, _, _ in power_links(c):
                    if p is a or (p is b and c.kind != 'D'):
                        nxt.append(d.net_of(b if p is a else a))
                reg = (c.model or {}).get('regulator')
                if reg and p in _pins_named(c, reg.get('vin')):
                    nxt += [d.net_of(o) for o in _pins_named(c, reg.get('vout'))]
                for on in nxt:
                    if on is not None and not on.is_ground and on.name not in depth:
                        depth[on.name] = depth[n.name] + 1
                        todo.append(on)

    rails = [n for n in d.nets.values() if n.is_power and not n.is_ground]
    spread([n for n in rails if n.name in depth])
    for pick in ('diode', 'pin'):
        roots = []
        for n in sorted(rails, key=lambda n: n.name):
            if n.name in depth:
                continue
            ok = False
            for p in n.pins:
                if pick == 'diode' and p.comp.kind == 'D':
                    for a, b, _, _ in power_links(p.comp):
                        an = d.net_of(a)
                        ok |= p is b and an is not None and not an.is_ground and not an.is_power
                elif pick == 'pin':
                    ok |= p.role == 'power_out' or p.etype == 'power_out'
            if ok:
                depth[n.name] = 0
                roots.append(n)
        spread(roots)
    d.__dict__['_flow_depth'] = depth
    return depth


def sink_pins(d, net):
    """{pin: amps at maximum} for everything that takes current out of the net."""
    out = defaultdict(float)
    dep = flow_depth(d)
    for c, _, mx, _ in rail_loads(d, net):
        ps = [p for p in c.pins.values() if p.net == net.name and supply_spec(c, p) is not None]
        for p in ps:
            out[p] += mx / 1000 / len(ps)
    for p in net.pins:
        c = p.comp
        if c.dnp:
            continue
        reg = (c.model or {}).get('regulator')
        if reg and p in _pins_named(c, reg.get('vin')):
            for o in _pins_named(c, reg.get('vout')):
                on = d.net_of(o)
                if on is not None:
                    k = 1.0 if reg.get('type', 'ldo') == 'ldo' else (on.vmax or 0) / max(net.vmin or 1, 0.1) / 0.85
                    out[p] += total_load(d, on, {net.name})[1] * k / 1000
        for a, b, _, _ in power_links(c):
            if p is a or (p is b and c.kind != 'D'):
                on = d.net_of(b if p is a else a)
                if on is not None and not on.is_ground and dep.get(on.name, -1) > dep.get(net.name, 99):
                    out[p] += total_load(d, on, {net.name})[1] / 1000
    return {p: a for p, a in out.items() if a > 0}


def feed_pins(d, net, sinks=()):
    """([pins where current enters the net], how we know)."""
    dep = flow_depth(d)
    for p in net.pins:
        reg = (p.comp.model or {}).get('regulator')
        if reg and p in _pins_named(p.comp, reg.get('vout')):
            return [p], f"{p.comp.ref} output"
    for p in net.pins:
        for a, b, _, _ in power_links(p.comp):
            on = d.net_of(b if p is a else a) if (p is a or p is b) else None
            if on is None or on.is_ground or p.comp.dnp:
                continue
            if p.comp.kind == 'D':
                if p is b:
                    return [p], f"{p.comp.ref} (from {on.name})"
            elif dep.get(on.name, 99) < dep.get(net.name, -1):
                return [p], f"{p.comp.ref} (from {on.name})"
    for p in net.pins:
        chg = (p.comp.model or {}).get('charger')
        if chg and p in _pins_named(p.comp, chg.get('vbat')) and not any(q.comp.kind in ('CONN', 'BATT') for q in net.pins):
            return [p], f"{p.comp.ref} output"
    sp = getattr(net, 'source_pin', None)
    if sp is not None and sp not in sinks:
        return [sp], f"{sp.comp.ref} {sp.name} pin"
    conns = [p for p in net.pins if p.comp.kind in ('CONN', 'BATT')]
    if conns:
        ref = conns[0].comp.ref
        return [p for p in conns if p.comp.ref == ref], f"connector {ref}"
    outs = [p for p in net.pins if (p.role == 'power_out' or p.etype == 'power_out') and p not in sinks]
    if outs:
        return [outs[0]], f"{outs[0].comp.ref} {outs[0].name} pin"
    return [], ''


_GNDNAME = re.compile(r'^[ADP]?(GND|VSS|VEE|EP|EPAD|PAD|COM|0V)[A-Z]?\d*$', re.I)


def _ground_pin(d, comp):
    """The pad a part returns its supply current through: a pin named or typed as ground, not one
    that merely happens to be tied to ground (an address strap, a FET gate)."""
    ps = [p for p in comp.pins.values() if p.net and d.nets[p.net].is_ground and p.pos]
    named = [p for p in ps if _GNDNAME.match(re.sub(r'[^A-Za-z0-9]', '', p.name or '')) or p.etype == 'power_in']
    if named:
        return named[0]
    if comp.kind in ('C', 'LED', 'CONN', 'BATT') and ps:
        real = [p for p in ps if not re.match(r'^(MP|MOUNT|SH|SHIELD|SHELL)', p.name or p.number, re.I)]
        return (real or ps)[0]
    return None


def return_pin(d, net, feeds, sinks):
    """The ground pad the rail's current returns to: the feeding part's own, or, when the rail is fed
    through a fuse, switch or diode, that of whatever feeds the rail before it (up to the connector)."""
    for _ in range(8):
        if not feeds:
            return None
        g = _ground_pin(d, feeds[0].comp)
        if g is not None:
            return g
        up = None
        for a, b, _, _ in power_links(feeds[0].comp):
            if feeds[0] is a or feeds[0] is b:
                up = d.net_of(b if feeds[0] is a else a)
        if up is None or up.is_ground or up is net:
            return None
        net = up
        feeds, _ = feed_pins(d, net, sinks)
    return None


def solve_rail(d, net):
    """Solves one supply net at maximum load.  Returns a dict or None when there is nothing to solve."""
    cache = d.__dict__.setdefault('_rail', {})
    if net.name in cache:
        return cache[net.name]
    res = None
    allsinks = sink_pins(d, net)
    feeds, how = feed_pins(d, net, allsinks)
    sinks = {p: a for p, a in allsinks.items() if p.pos and p not in feeds}
    if feeds and sinks and all(p.pos for p in feeds) and d.board and (d.board.tracks or d.board.zones):
        cn = copper_net(d, net.name)
        src = [n for p in feeds for n in cn.pin_nodes.get((p.comp.ref, p.number), [])]
        snk = defaultdict(float)
        for p, a in sinks.items():
            if cn.pin_nodes.get((p.comp.ref, p.number)):
                snk[cn.pin_nodes[(p.comp.ref, p.number)][0]] += a
        if src and snk:
            V, lost = cn.solve(src, dict(snk))
            stat = dict(cn.last_solve)
            drop = {p: -V[cn.pin_nodes[(p.comp.ref, p.number)][0]] for p in sinks
                    if cn.pin_nodes.get((p.comp.ref, p.number)) and V[cn.pin_nodes[(p.comp.ref, p.number)][0]] is not None}
            unrouted = [p for p in sinks if p not in drop]
            # ground return for the same currents, if the feeding part has a ground pin
            rise, gnote, gbroken = {}, 'ground return not included (no ground pad found at the source)', []
            gpin = return_pin(d, net, feeds, allsinks)
            if gpin is not None:
                gcn = copper_net(d, gpin.net)
                gsrc = gcn.pin_nodes.get((gpin.comp.ref, gpin.number), [])
                gs, owner = defaultdict(float), {}
                for p, a in sinks.items():
                    g = _ground_pin(d, p.comp)
                    if g is not None and g.net == gpin.net and gcn.pin_nodes.get((g.comp.ref, g.number)):
                        node = gcn.pin_nodes[(g.comp.ref, g.number)][0]
                        gs[node] += a
                        owner[p] = (node, g)
                if not gs:
                    gnote = 'ground return not included (the loads here have no ground pad of their own)'
                if gsrc and gs:
                    GV, _ = gcn.solve(gsrc, dict(gs))
                    rise = {p: -GV[n] for p, (n, _) in owner.items() if GV[n] is not None}
                    gbroken = [(gpin, g) for p, (n, g) in owner.items() if GV[n] is None]
                    gnote = (f"ground return through {gpin.net} to {gpin.label} included ({gcn.counts.get('cells', 0)} pour cells, "
                             f"grid {gcn.grid or 0:.1f} mm)" if rise else
                             f"no copper path through {gpin.net} from {gpin.label} to the loads' ground pads")
            res = {'cn': cn, 'V': V, 'feeds': feeds, 'how': how, 'sinks': sinks, 'drop': drop, 'rise': rise,
                   'unrouted': unrouted, 'total': sum(sinks.values()), 'gnote': gnote, 'gbroken': gbroken, 'currents': cn.currents(V), 'solve': stat}
    cache[net.name] = res
    return res


@check('layout.ir_drop', 'layout', needs_board=True,
       doc='Voltage lost in the copper between each supply source and its loads, from a resistor-network solve of tracks, vias and pours')
def ir_drop(d):
    broken = {}
    for net in sorted(d.nets.values(), key=lambda n: n.name):
        if not net.is_power or net.is_ground:
            continue
        r = solve_rail(d, net)
        if r is None:
            continue
        for src, g in r['gbroken']:
            broken.setdefault((src.net, src.label), {})[g.label] = g
    for gnet in sorted({k[0] for k in broken}):
        pairs = sorted((src, g) for (n, src), pins in broken.items() if n == gnet for g in pins)
        refs = sorted({g.comp.ref for (n, _), pins in broken.items() if n == gnet for g in pins.values()})
        yield F('layout.ir_drop', 'warning', f"{gnet} is in separate pieces: {len(refs)} part(s) have no copper return path to their supply",
                f"No copper on {gnet} joins " + '; '.join(f"{g} to {src}" for src, g in pairs[:8]) +
                f"{'...' if len(pairs) > 8 else ''}. The supply current of those parts has no return path on the "
                f"board as drawn: the ground pour is in fragments, or it is saved unfilled. (A pad counts as joined "
                f"to a pour of its own net within about a millimetre.)", refs=refs[:8], nets=[gnet],
                evidence={'pairs_without_a_path': len(pairs)},
                basis='copper connectivity in the board file', confidence='medium')
    for net in sorted(d.nets.values(), key=lambda n: n.name):
        if not net.is_power or net.is_ground:
            continue
        r = solve_rail(d, net)
        if r is None or r['total'] < 0.03:
            continue
        cn = r['cn']
        if r['unrouted']:
            refs = sorted({p.comp.ref for p in r['unrouted']})
            yield F('layout.ir_drop', 'warning', f"{net.name}: {len(refs)} load(s) are not joined to the source by copper",
                    f"No copper path on {net.name} from {r['how']} to {', '.join(p.label for p in r['unrouted'][:8])}"
                    f"{'...' if len(r['unrouted']) > 8 else ''}. Either the connection is unrouted, or it runs "
                    f"through a zone that is saved unfilled.", refs=refs[:8], nets=[net.name],
                    basis='copper connectivity in the board file', confidence='medium')
        tot = {p: v + r['rise'].get(p, 0.0) for p, v in r['drop'].items()}
        if not tot:
            continue
        worst = max(tot, key=tot.get)
        top = sorted(tot.items(), key=lambda x: -x[1])[:4]
        vnom = net.vnom or 0
        lim = max(0.03 * vnom, 0.1) if vnom else 0.1
        ev = {'source': r['how'], 'total_load_A': round(r['total'], 3),
              'worst': f"{worst.label}: {tot[worst] * 1000:.0f} mV ({r['drop'][worst] * 1000:.0f} supply + {r['rise'].get(worst, 0) * 1000:.0f} return)",
              'next': '; '.join(f"{p.label} {v * 1000:.0f} mV" for p, v in top[1:]) or 'none',
              'copper': f"{cn.counts['segments']} track segments, {cn.counts['vias']} vias, {cn.counts.get('cells', 0)} pour cells",
              'ground': r['gnote'], 'stack_up': 'assumed' if cn.stack.assumed else 'from the board file'}
        yield F('layout.ir_drop', 'warning' if tot[worst] > lim else 'info',
                f"{net.name}: {tot[worst] * 1000:.0f} mV is lost in the copper on the way to {worst.label}"
                + (f" ({tot[worst] / vnom:.1%} of the rail)" if vnom else ''),
                f"With every load on {net.name} at its maximum ({r['total'] * 1000:.0f} mA in all), fed from {r['how']}. "
                f"Supply side {r['drop'][worst] * 1000:.0f} mV" +
                (f", ground return {r['rise'][worst] * 1000:.0f} mV. " if worst in r['rise'] else
                 "; the ground return is not included. ") +
                f"Solved on the routed copper: track resistance, via barrels and pours as a sheet-resistance mesh. "
                f"Copper at 20 C; thermal-relief spokes are not modelled.",
                refs=[worst.comp.ref, r['feeds'][0].comp.ref], nets=[net.name], evidence=ev,
                basis='resistor-network solve of the net\'s copper (boardlint/extract.py); loads are model maxima',
                confidence='medium')


@check('layout.track_current', 'layout', needs_board=True,
       doc='Current in every supply track segment, from the same solve, against IPC-2221 for its width')
def track_current(d):
    rise = float((d.config.get('track') or {}).get('temp_rise_c', 10))
    for net in sorted(d.nets.values(), key=lambda n: n.name):
        if not net.is_power or net.is_ground:
            continue
        r = solve_rail(d, net)
        if r is None:
            continue
        cn = r['cn']
        worst = None
        over_mm = 0.0
        for amps, (_, t, ln) in r['currents']:
            inner = t.layer not in (cn.layers[0], cn.layers[-1])
            cap = ipc2221_amps(t.width, cn.stack.copper(t.layer), rise, inner)
            ratio = amps / cap
            if ratio > 1.0:
                over_mm += ln
            if worst is None or ratio > worst[0]:
                worst = (ratio, amps, cap, t, inner)
        if worst is None or worst[0] < 0.7:
            continue
        ratio, amps, cap, t, inner = worst
        where = f"({(t.x1 + t.x2) / 2:.1f}, {(t.y1 + t.y2) / 2:.1f}) mm on {t.layer}"
        ev = {'segment': where, 'width_mm': t.width, 'current_A': round(amps, 3), 'ipc2221_A': round(cap, 2),
              'length_over_limit_mm': round(over_mm, 1), 'net_total_A': round(r['total'], 3)}
        neck = ratio > 1.0 and over_mm < 3.0
        yield F('layout.track_current', 'warning' if ratio > 1.0 and not neck else 'info',
                f"{net.name}: a {t.width:g} mm segment carries {amps * 1000:.0f} mA; IPC-2221 gives {cap * 1000:.0f} mA for a {rise:g} C rise",
                f"At {where}{', an inner layer' if inner else ''}. {over_mm:.1f} mm of the net's track is over its "
                f"limit with every load at maximum. " +
                ("That is a short neck: the wider copper at each end cools it, so it runs cooler than the "
                 "formula says, but it is the first place to widen. " if neck else "") +
                f"This is the current that segment actually carries in the solved network, not the net's total.",
                nets=[net.name], evidence=ev,
                basis='IPC-2221 formula; segment current from the resistor-network solve; loads are model maxima',
                confidence='medium')


# ----------------------------------------------------------------------------- impedance and delay
def end_to_end(d, name):
    """Longest pad-to-pad distance along the copper of one net (mm): what a signal edge travels,
    as opposed to the total routed length, which counts every branch.  None if it cannot be traced."""
    import heapq
    cn = copper_net(d, name)
    adj = defaultdict(list)
    for a, b, _, meta in cn.edges:
        ln = meta[2] if meta and meta[0] in ('track', 'inpad') else 0.0
        adj[a].append((b, ln))
        adj[b].append((a, ln))
    pads = {ns[0] for ns in cn.pin_nodes.values() if ns}
    if len(pads) < 2:
        return None
    best = 0.0
    for src in pads:
        dist = {src: 0.0}
        heap = [(0.0, src)]
        while heap:
            dd, u = heapq.heappop(heap)
            if dd > dist.get(u, 1e18):
                continue
            for v, ln in adj[u]:
                if dd + ln < dist.get(v, 1e18):
                    dist[v] = dd + ln
                    heapq.heappush(heap, (dd + ln, v))
        best = max([best] + [dist[p] for p in pads if p in dist])
    return best or None


@check('layout.impedance', 'layout', needs_board=True,
       doc='Impedance, delay and capacitance of fast nets from the stack-up; nets long enough to need termination; USB pair')
def impedance(d):
    from .layout import classify_nets
    from ..classify import signal_group, group_pins
    b = d.board
    if not b.tracks:
        return
    stack, planes = tline.Stack(b), tline.Planes(d)
    agg, _ = classify_nets(d)
    rise_ns = float((d.config.get('signals') or {}).get('rise_ns', 2.0))
    rows, done = [], set()
    for net in sorted(agg):
        if net in done:
            continue
        nets, through = signal_group(d, net)
        done |= nets
        s = tline.net_summary(d, nets, stack, planes)
        if s is None or s['length'] < 5:
            continue
        reason = agg[net][0]
        pins = group_pins(d, nets)
        drivers = [p for p in pins if can_drive(p) and p.comp.kind == 'IC']
        led_internal = reason.startswith('addressable') and not drivers
        z = f"{s['z0']:.0f} ohm" if s['z0'] else 'no reference plane'
        rows.append((s['length'], f"{sorted(nets)[0]}: {s['length']:.0f} mm, {s['width']:g} mm on {s['layer']}, {z}, "
                                  f"{s['delay_ps']:.0f} ps, {s['c_pf']:.1f} pF, {s['referenced']:.0%} over a plane, {s['vias']} vias"))
        usb = reason == 'USB data'
        tr = 4.0 if usb else rise_ns
        ends = [end_to_end(d, n) for n in sorted(nets) if any(t.net == n for t in b.tracks)]
        far = min(sum(ends), s['length']) if ends and all(ends) else s['length']
        delay = s['delay_ps'] * far / s['length']
        # open-drain buses rise through their pull-up in hundreds of nanoseconds: never "long"
        i2c = any(p.role.startswith('i2c') for p in pins)
        # ringing matters where an edge is what is acted on: clocks and self-clocked LED data
        edge = reason == 'clock' or reason.startswith('addressable') or any(p.role in ('spi_sck', 'spi_ctrl_sck') for p in pins)
        if not led_internal and not i2c and delay > tr * 1000 / 6:
            series = [c for c in through if c.kind == 'R' and (c.num or 0) >= 10]
            crit = tr * 1000 / 6 / (s['delay_ps'] / s['length'])
            yield F('layout.impedance', 'warning' if edge and not series and not usb else 'info',
                    f"{sorted(nets)[0]} is electrically long: {far:.0f} mm end to end, {delay:.0f} ps one way",
                    f"{reason}. {far:.0f} mm between its furthest pads ({s['length']:.0f} mm routed in all). "
                    f"For a {tr:g} ns edge a trace acts as a transmission line beyond about {crit:.0f} mm "
                    f"(delay over one sixth of the rise time). " +
                    (f"It has {', '.join(c.desc for c in series)} in series, which damps the reflection."
                     if series else "USB receivers tolerate this at full speed." if usb else
                     "Nothing terminates it: expect overshoot and ringing at the far end. " +
                     ("On a clock that can be seen as a second edge. A 22 to 47 ohm resistor at the driver is the usual fix."
                      if edge else "This is a data line sampled after it settles, so it matters less than on a clock.")) +
                    (f" Line impedance about {s['z0']:.0f} ohm." if s['z0'] else " It has no reference plane, so its impedance is not controlled."),
                    refs=[p.comp.ref for p in drivers[:2]], nets=nets,
                    evidence={'end_to_end_mm': round(far, 1), 'routed_mm': round(s['length'], 1), 'delay_ps': round(delay), 'z0': s['z0'] and round(s['z0']),
                              'assumed_rise_ns': tr, 'stack_up': 'assumed' if stack.assumed else 'from the board file'},
                    basis='microstrip / stripline formulas on the stack-up; rise time is an assumption (signals: rise_ns in boardlint.yaml)',
                    confidence='low')
    # USB pair
    dp = {p.net for c in d.components.values() for p in c.pins.values() if p.role == 'usb_dp' and p.net}
    dm = {p.net for c in d.components.values() for p in c.pins.values() if p.role == 'usb_dm' and p.net}
    if dp and dm:
        dp = set().union(*(signal_group(d, n)[0] for n in dp))
        dm = set().union(*(signal_group(d, n)[0] for n in dm))
        sp, sm = tline.net_summary(d, dp, stack, planes), tline.net_summary(d, dm, stack, planes)
        if sp and sm:
            tp = [t for t in b.tracks if t.net in dp]
            tm = [t for t in b.tracks if t.net in dm]
            gaps, zs, hs = [], [], []
            for t in tp:
                mx, my = (t.x1 + t.x2) / 2, (t.y1 + t.y2) / 2
                best = None
                for o in tm:
                    if o.layer != t.layer:
                        continue
                    dx, dy = o.x2 - o.x1, o.y2 - o.y1
                    l2 = dx * dx + dy * dy or 1e-12
                    u = max(0.0, min(1.0, ((mx - o.x1) * dx + (my - o.y1) * dy) / l2))
                    g = math.hypot(mx - (o.x1 + u * dx), my - (o.y1 + u * dy)) - (t.width + o.width) / 2
                    best = g if best is None or g < best else best
                p = tline.segment(stack, planes, t)
                if best is not None and best < 1.0 and p['z0']:
                    gaps.append((best, t.length))
                    zs.append(p['z0'])
                    hs.append(p['h'])
            coupled = sum(l for _, l in gaps)
            ev = {'d_plus_mm': round(sp['length'], 1), 'd_minus_mm': round(sm['length'], 1),
                  'mismatch_mm': round(abs(sp['length'] - sm['length']), 1), 'routed_as_a_pair_mm': round(coupled, 1),
                  'stack_up': 'assumed' if stack.assumed else 'from the board file'}
            msg = (f"D+ {sp['length']:.0f} mm, D- {sm['length']:.0f} mm (mismatch {abs(sp['length'] - sm['length']):.1f} mm). ")
            zd = None
            if gaps and coupled > 0.3 * min(sp['length'], sm['length']):
                gap = sorted(g for g, _ in gaps)[len(gaps) // 2]
                zd = tline.diff_microstrip(sum(zs) / len(zs), max(gap, 0.05), sum(hs) / len(hs))
                ev.update({'gap_mm': round(gap, 2), 'z_diff': round(zd)})
                msg += f"Routed as a pair for {coupled:.0f} mm at a {gap:.2f} mm gap: about {zd:.0f} ohm differential; USB asks for 90 ohm +/- 15 %. "
            else:
                msg += "The two lines are not routed side by side over a plane for most of their length, so there is no controlled differential impedance. "
            msg += "At full speed (12 Mbit/s) this is tolerant; at high speed (480 Mbit/s) both the impedance and a mismatch over about 1 mm matter."
            yield F('layout.impedance', 'info', "USB pair: " + (f"about {zd:.0f} ohm differential" if zd else "not a controlled pair")
                    + f", {abs(sp['length'] - sm['length']):.1f} mm length mismatch", msg, nets=dp | dm, evidence=ev,
                    basis='edge-coupled microstrip formula on the stack-up', confidence='low')
    if rows:
        rows.sort(key=lambda x: -x[0])
        yield F('layout.impedance', 'info', f"Line parameters of {len(rows)} fast net(s)",
                '; '.join(r for _, r in rows[:10]) + ('...' if len(rows) > 10 else '') + '.',
                evidence={'stack_up': ('assumed: ' if stack.assumed else '') + ', '.join(
                    f"{stack.layers[i]} / {stack.gaps[i][0]:g} mm er {stack.gaps[i][1]:g}" for i in range(len(stack.gaps))) + f" / {stack.layers[-1]}"},
                basis='microstrip / stripline formulas on the stack-up', confidence='low')
