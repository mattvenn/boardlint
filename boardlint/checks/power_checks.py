"""Supply ranges, pin voltages, logic levels, regulators, current budget, component ratings."""
from __future__ import annotations
import re
from collections import defaultdict
from . import check, F
from .common import can_drive, io, model_basis, supply_v, names, PASSIVE_KINDS
from ..classify import pulls, fmt_r, fmt_c, package_of, parse_voltage_rating, signal_group, group_pins, pin_aliases
from ..library import supply_spec
from ..power import supply_net_of, rail_loads, downstream, power_links, _pins_named


@check('power.rails', 'power', doc='Lists the rails found and how each voltage was inferred')
def rails(d):
    known = [n for n in d.nets.values() if n.is_power and n.vmin is not None]
    unknown = [n for n in d.nets.values() if n.is_power and n.vmin is None and not n.is_ground]
    if known:
        yield F('power.rails', 'info', f"{len(known)} supply rail(s) with a known voltage",
                '; '.join(f"{n.name} {n.vmin:g}-{n.vmax:g} V ({n.vsrc})" for n in sorted(known, key=lambda n: n.name)),
                nets=[n.name for n in known], confidence='medium',
                basis='regulator models, net names, boardlint.yaml; override with rails: in boardlint.yaml')
    if unknown:
        yield F('power.rails', 'warning', f"{len(unknown)} supply net(s) have no known voltage",
                f"{', '.join(sorted(n.name for n in unknown))}: voltage-dependent checks skip them. "
                f"Declare them under rails: in boardlint.yaml.", nets=[n.name for n in unknown], confidence='high')


@check('power.supply_range', 'power', doc="Each part's supply is inside its operating range and below its absolute maximum")
def supply_range(d):
    done = {}
    for c in sorted(d.components.values(), key=lambda c: (c.prefix, len(c.ref), c.ref)):
        if c.dnp or not c.model:
            continue
        for p in c.pins.values():
            s = supply_spec(c, p)
            n = d.net_of(p)
            if s is None or n is None or n.vmin is None:
                continue
            if (id(s), n.name) in done:
                if c.ref not in done[(id(s), n.name)]:
                    done[(id(s), n.name)].append(c.ref)
                continue
            done[(id(s), n.name)] = same = [c.ref]
            ev = {'rail': f"{n.name} {n.vmin:g}-{n.vmax:g} V ({n.vsrc})",
                  'part': f"{s.get('vmin', '?')}-{s.get('vmax', '?')} V, abs max {s.get('abs_max', '?')} V"}
            if s.get('abs_max') is not None and n.vmax > float(s['abs_max']):
                yield F('power.supply_range', 'error', f"{c.value} {p.name}: {n.name} can reach {n.vmax:g} V, absolute maximum is {s['abs_max']:g} V",
                        c.model.get("description", c.value) + ".", refs=same, nets=[n.name], evidence=ev, basis=model_basis(c), confidence='high')
            elif s.get('vmax') is not None and n.vmax > float(s['vmax']) + 1e-6 and \
                    not (c.model.get('class') == 'tvs' and n.vmax <= float(s['vmax']) * 1.06):
                yield F('power.supply_range', 'warning', f"{c.value} {p.name}: {n.name} can reach {n.vmax:g} V, above the operating maximum of {s['vmax']:g} V",
                        c.model.get("description", c.value) + ".", refs=same, nets=[n.name], evidence=ev, basis=model_basis(c), confidence='high')
            if s.get('vmin') is not None and n.vmin < float(s['vmin']) - 1e-6:
                yield F('power.supply_range', 'warning', f"{c.value} {p.name}: {n.name} can fall to {n.vmin:g} V, below the operating minimum of {s['vmin']:g} V",
                        c.model.get("description", c.value) + ": out of specification over the bottom part of the rail's range.",
                        refs=same, nets=[n.name], evidence=ev, basis=model_basis(c), confidence='high')


def _pin_limit(d, c, p):
    """(limit volts, explanation) for a non-supply pin."""
    lim = p.spec.get('abs_max')
    if lim is not None:
        return float(lim), 'pin absolute maximum'
    m = (c.model or {}).get('io') or {}
    if m.get('tolerant_5v'):
        return 5.5, '5 V tolerant'
    sv = supply_v(d, c)
    if m.get('abs_max') is not None and sv is None:
        return float(m['abs_max']), 'I/O absolute maximum'
    if sv is None:
        return None, ''
    over = m.get('abs_max_over_supply')
    if over is not None:
        lim = sv[0] + float(over)
        if m.get('abs_max') is not None:
            lim = min(lim, float(m['abs_max']))
        return lim, f"supply ({sv[2]} at its minimum {sv[0]:g} V) + {over:g} V"
    if m.get('abs_max') is not None:
        return float(m['abs_max']), 'I/O absolute maximum'
    if c.model:
        return None, ''
    return sv[1] + 0.3, f"supply ({sv[2]}) + 0.3 V rule of thumb"


def net_levels(d, n, exclude=None, exclude_rail=None):
    """Highest voltage that can appear on a signal net and where it comes from.
    ``exclude``: a component whose own outputs do not count; ``exclude_rail``: a rail name that
    does not count (a pin cannot be over-driven by its own supply)."""
    if n.vmin is not None and n.is_power:
        return (None, None, '') if n.name == exclude_rail else (n.vmax, n.vmin, n.vsrc)
    div = getattr(n, 'divider', None)
    if div is not None:
        if div[2].name == exclude_rail or (exclude is not None and exclude.ref in div[3][2]):
            return None, None, ''
        return n.vmax, n.vmin, n.vsrc
    best = (None, None, '')
    for p in n.pins:
        c = p.comp
        if c is exclude or c.kind in PASSIVE_KINDS or c.kind in ('CONN', 'SW') or not can_drive(p):
            continue
        sv = supply_v(d, c)
        if sv and sv[2] != exclude_rail and (best[0] is None or sv[1] > best[0]):
            best = (sv[1], sv[0], f"driven by {p.label} from {sv[2]}")
    ups, _ = pulls(d, n.name)
    for r, rail in ups:
        if rail.vmax is not None and rail.name != exclude_rail and (best[0] is None or rail.vmax > best[0]):
            best = (rail.vmax, rail.vmin, f"pulled up to {rail.name} by {r.ref}")
    return best


@check('power.pin_voltage', 'power', doc='No pin sees more than its absolute maximum (5 V into 3.3 V parts, dividers, pull-ups)')
def pin_voltage(d):
    for n in d.nets.values():
        if n.is_ground:
            continue
        for p in n.pins:
            c = p.comp
            if c.dnp or c.kind in PASSIVE_KINDS or c.kind in ('CONN', 'SW', 'Q', 'LED') and not c.model:
                continue
            own = supply_net_of(d, c)
            vmax, vmin, src = net_levels(d, n, exclude=c, exclude_rail=own.name if own is not None else None)
            if vmax is None:
                continue
            if supply_spec(c, p) is not None or p.etype in ('power_in', 'power_out') or p.role in ('power_out', 'gnd', 'nc', 'power_in'):
                continue
            if (c.model or {}).get('fet') or (c.model or {}).get('diode') or (c.model or {}).get('fuse') or (c.model or {}).get('switch'):
                continue
            if not c.model and re.match(r'^(VBUS|VIN|VCC|VDD|VBAT|VSYS|VS|V\+|VOUT|PWR|VPP|HV|SENSE)', p.name or '', re.I):
                continue          # no model: a pin named like a supply or sense input is meant to see that rail
            lim, why = _pin_limit(d, c, p)
            if lim is None:
                continue
            if vmax > lim + 0.005:
                marginal = vmax <= lim + 0.31
                div = getattr(n, 'divider', None)
                ups_ = pulls(d, n.name)[0] if not n.is_power else []
                rsrc = div[0].num if div else (min(r.num for r, _ in ups_) if ups_ and 'pulled up' in src else None)
                inj = (((div[3][1] if div else vmax) - lim) / rsrc * 1e6) if rsrc else None
                weak = inj is not None and inj < 100
                m_drv = re.match(r'driven by ([^.]+)\.', src or '')
                guessed = bool(m_drv) and m_drv.group(1) in d.components and not d.components[m_drv.group(1)].model
                yield F('power.pin_voltage', 'info' if (weak and marginal) or guessed else 'warning' if marginal or weak or not c.model else 'error',
                        f"{p.label} can see {vmax:g} V; its limit is {lim:.2f} V",
                        f"Net {n.name} ({src}). Limit: {why}. " +
                        ("The excess is within a few hundred millivolts: it arises when the two supplies are at "
                         "opposite ends of their ranges. " if marginal else "") +
                        (f"The source impedance ({fmt_r(rsrc)}) limits the current into the pin's protection diode "
                         f"to about {inj:.0f} uA: outside the datasheet limit, harmless in practice. Also note the "
                         f"pin is driven while the part is unpowered if this source comes up first."
                         if weak else "Current then flows into the pin's protection diode."),
                        refs=[c.ref], nets=[n.name], evidence={'net_vmax': vmax, 'pin_limit': round(lim, 3)},
                        basis=model_basis(c) if c.model else 'supply + 0.3 V rule of thumb (no part model)',
                        confidence='high' if c.model else 'low')


@check('power.logic_level', 'power', doc='A driven or divided-down signal reaches the receiver input-high threshold')
def logic_level(d):
    for n in d.nets.values():
        if n.is_ground or n.is_power:
            continue
        div = getattr(n, 'divider', None)
        if div is None:
            continue
        for p in n.pins:
            c = p.comp
            if c.kind in PASSIVE_KINDS or c.dnp or not c.model:
                continue
            sv = supply_v(d, c)
            vih = io(c, p, 'vih')
            frac = io(c, p, 'vih_frac')
            if vih is None and frac is not None and sv:
                vih = float(frac) * sv[1]
            if vih is None:
                continue
            mcu = (c.model or {}).get('mcu') or {}
            adc = p.name in (mcu.get('adc1_pins') or []) + (mcu.get('adc2_pins') or [])
            from ..classify import is_analog_name
            analog_name = is_analog_name(n.name)
            from_output = 'high =' in div[3][2]
            if analog_name or (n.vmax < vih and adc and not from_output):
                continue          # a measurement divider, not a logic level
            ev = {'divider': f"{div[0].ref} {fmt_r(div[0].num)} / {div[1].ref} {fmt_r(div[1].num)} from {div[2].name}",
                  'net_v': f"{n.vmin:g}-{n.vmax:g} V", 'vih': round(float(vih), 3)}
            if n.vmax < vih:
                yield F('power.logic_level', 'error', f"{n.name} never reaches a logic high at {p.label}",
                        f"The divider gives at most {n.vmax:g} V; the input needs {vih:.2f} V.",
                        refs=[c.ref, div[0].ref, div[1].ref], nets=[n.name], evidence=ev, basis=model_basis(c, 'VIH'),
                        confidence='high')
            elif n.vmin < vih:
                yield F('power.logic_level', 'warning', f"{n.name} is not a guaranteed logic high at {p.label} when {div[2].name} is low",
                        f"The divider gives {n.vmin:g} V with {div[2].name} at {div[3][0]:g} V; the input needs {vih:.2f} V.",
                        refs=[c.ref, div[0].ref, div[1].ref], nets=[n.name], evidence=ev, basis=model_basis(c, 'VIH'),
                        confidence='medium')


def total_load(d, net, seen=None, through_regs=True):
    """(typ mA, max mA, breakdown) drawn from a rail including everything downstream of it."""
    seen = seen if seen is not None else set()
    if net.name in seen:
        return 0.0, 0.0, []
    seen.add(net.name)
    typ = mx = 0.0
    parts = []
    for c, it, im, _ in rail_loads(d, net):
        typ += it
        mx += im
        if im:
            parts.append((c.ref, im))
    for p in net.pins:
        c = p.comp
        if c.dnp:
            continue
        reg = (c.model or {}).get('regulator')
        if reg and through_regs and p in _pins_named(c, reg.get('vin')):
            for o in _pins_named(c, reg.get('vout')):
                on = d.net_of(o)
                if on is not None:
                    t, m, pr = total_load(d, on, seen)
                    k = 1.0 if reg.get('type', 'ldo') == 'ldo' else (on.vmax or 0) / max(net.vmin or 1, 0.1) / 0.85
                    typ, mx, parts = typ + t * k, mx + m * k, parts + pr
        for a, b, _, _ in power_links(c):
            if p is a or p is b:
                o = b if p is a else a
                on = d.net_of(o)
                dep = getattr(d, 'power_depth', {})
                if on is not None and not on.is_ground and dep.get(on.name, 99) > dep.get(net.name, -1):
                    t, m, pr = total_load(d, on, seen)
                    typ, mx, parts = typ + t, mx + m, parts + pr
    return typ, mx, parts


def _summ(parts, top=5):
    agg = defaultdict(float)
    for ref, ma in parts:
        agg[ref] += ma
    items = sorted(agg.items(), key=lambda x: -x[1])
    s = ', '.join(f"{r} {m:g} mA" for r, m in items[:top])
    return s + (f", +{len(items) - top} more" if len(items) > top else '')


@check('power.regulator', 'power', doc='Regulators: load within rating, dropout met at minimum input, junction temperature')
def regulator(d):
    ta = float((d.config.get('ambient_c') or 40))
    for c in d.components.values():
        reg = (c.model or {}).get('regulator')
        if not reg or c.dnp:
            continue
        vin = d.net_of((_pins_named(c, reg.get('vin')) or [None])[0]) if _pins_named(c, reg.get('vin')) else None
        vout = d.net_of((_pins_named(c, reg.get('vout')) or [None])[0]) if _pins_named(c, reg.get('vout')) else None
        if vout is None:
            continue
        typ, mx, parts = total_load(d, vout, set([vin.name]) if vin is not None else set())
        ev = {'load_max_mA': round(mx, 1), 'load_typ_mA': round(typ, 1), 'loads': _summ(parts)}
        imax = reg.get('i_max_ma')
        unmodelled = sorted({p.comp.ref for p in vout.pins if p.comp.kind == 'IC' and not p.comp.model})
        if unmodelled:
            ev['not_counted'] = ', '.join(unmodelled)
        if imax and mx > imax:
            yield F('power.regulator', 'error', f"{c.ref} load on {vout.name} is {mx:.0f} mA, rating {imax:g} mA",
                    f"{c.desc}. Largest loads: {_summ(parts)}.", refs=[c.ref], nets=[vout.name], evidence=ev,
                    basis=model_basis(c), confidence='medium')
        elif imax and mx > 0.8 * imax:
            yield F('power.regulator', 'warning', f"{c.ref} load on {vout.name} is {mx:.0f} mA, {mx / imax:.0%} of its {imax:g} mA rating",
                    f"{c.desc}. Largest loads: {_summ(parts)}.", refs=[c.ref], nets=[vout.name], evidence=ev,
                    basis=model_basis(c), confidence='medium')
        if vin is not None and vin.vmin is not None and reg.get('type', 'ldo') == 'ldo' and reg.get('vout_v'):
            do_mv = reg.get('dropout_mv')
            if do_mv:
                at = float(reg.get('dropout_at_ma') or imax or 100)
                if not mx:
                    yield F('power.regulator', 'info', f"{c.ref} load on {vout.name} is unknown",
                            f"No part on the rail has a current in its model ({', '.join(unmodelled) or 'no ICs'} not "
                            f"counted): dropout and thermal checks skipped.", refs=[c.ref], nets=[vout.name],
                            confidence='high')
                    continue
                iload = mx
                vdo = float(do_mv) / 1000 * min(iload / at, 1.5)
                need = float(reg['vout_v']) + vdo
                ev2 = dict(ev, vin=f"{vin.name} {vin.vmin:g}-{vin.vmax:g} V ({vin.vsrc})",
                           dropout=f"{do_mv:g} mV at {at:g} mA, scaled to {vdo * 1000:.0f} mV at {iload:.0f} mA",
                           vin_needed=round(need, 3))
                if vin.vmax < need:
                    yield F('power.regulator', 'error', f"{c.ref} can never regulate {reg['vout_v']:g} V from {vin.name}",
                            f"It needs {need:.2f} V in at {iload:.0f} mA; the input tops out at {vin.vmax:g} V.",
                            refs=[c.ref], nets=[vin.name, vout.name], evidence=ev2, basis=model_basis(c, 'dropout'),
                            confidence='high')
                elif vin.vmin < need:
                    cons = [(supply_spec(p.comp, p) or {}).get('vmin') for p in vout.pins]
                    cons = [(float(v), p.comp) for v, p in zip(cons, vout.pins) if v is not None]
                    worst = max(cons, key=lambda x: x[0]) if cons else None
                    msg = (f"{vin.name} spans {vin.vmin:g} to {vin.vmax:g} V. Below {need:.2f} V with {iload:.0f} mA "
                           f"drawn the output follows the input down, about {vdo * 1000:.0f} mV beneath it.")
                    sev = 'info'
                    if worst and vin.vmin - vdo < worst[0]:
                        sev = 'warning'
                        msg += (f" {worst[1].desc} needs {worst[0]:g} V: at peak load that is lost once {vin.name} "
                                f"is under {worst[0] + vdo:.2f} V, well before {vin.vmin:g} V. Expect brown-out "
                                f"resets on current peaks with a part-discharged source.")
                        ev2['brownout_below_vin'] = round(worst[0] + vdo, 2)
                    yield F('power.regulator', sev,
                            f"{c.ref} drops out of regulation when {vin.name} is below {need:.2f} V at peak load",
                            msg, refs=[c.ref] + ([worst[1].ref] if worst else []), nets=[vin.name, vout.name],
                            evidence=ev2, basis=model_basis(c, 'dropout; load is the sum of model maxima'),
                            confidence='medium')
            th = reg.get('theta_ja')
            if th and mx:
                # heat follows the average, not the peak: judge on the typical load when it is known
                i_th = typ if typ and typ < mx else mx
                pd = (vin.vmax - float(reg['vout_v'])) * i_th / 1000
                tj = ta + pd * float(th)
                pk = (vin.vmax - float(reg['vout_v'])) * mx / 1000
                tj_pk = ta + pk * float(th)
                tjm = float(reg.get('tj_max', 125))
                if tj <= tjm and tj_pk > tjm:
                    yield F('power.regulator', 'info', f"{c.ref} runs at about {tj:.0f} C at typical load, and would exceed {tjm:g} C if the peak load were sustained",
                            f"Typical: ({vin.vmax:g} - {reg['vout_v']:g}) V x {i_th:.0f} mA = {pd * 1000:.0f} mW. Peak: {mx:.0f} mA, "
                            f"{pk * 1000:.0f} mW, {tj_pk:.0f} C if it lasted. {th:g} C/W from {ta:g} C ambient, no heatsink.",
                            refs=[c.ref], evidence=dict(ev, p_typ_mw=round(pd * 1000), tj_typ=round(tj), tj_peak=round(tj_pk)),
                            basis=model_basis(c, 'theta_ja'), confidence='low')
                if tj > tjm:
                    yield F('power.regulator', 'warning',
                            f"{c.ref} would reach {tj:.0f} C at full load" if tj < 250 else
                            f"{c.ref} dissipates {pd * 1000:.0f} mW at full load, far beyond its package",
                            f"({vin.vmax:g} - {reg['vout_v']:g}) V x {i_th:.0f} mA = {pd * 1000:.0f} mW; "
                            f"{th:g} C/W from {ta:g} C ambient, no heatsink. "
                            + ("This is the typical load." if i_th < mx else "Worst case: every load at its maximum at once."),
                            refs=[c.ref], evidence=dict(ev, p_mw=round(pd * 1000), tj=round(tj)),
                            basis=model_basis(c, 'theta_ja'), confidence='low')


@check('power.budget', 'power', doc='Fuses, switches, FETs and connectors in the power path carry less than their rating')
def budget(d):
    for c in d.components.values():
        if c.dnp:
            continue
        m = c.model or {}
        chg = m.get('charger')
        if chg:
            pp = _pins_named(c, chg.get('prog'))
            if pp and pp[0].net:
                _, downs = pulls(d, pp[0].net)
                if downs and chg.get('ma_kohm'):
                    ich = float(chg['ma_kohm']) / (downs[0][0].num / 1000)
                    c.props['_i_charge_ma'] = ich
                    yield F('power.budget', 'info', f"{c.ref} charge current is {ich:.0f} mA",
                            f"{downs[0][0].desc} on {pp[0].label}. Check it against the cell (0.5 C is typical) and "
                            f"against what the USB source may supply.", refs=[c.ref, downs[0][0].ref],
                            basis=model_basis(c, 'charge-current formula'), confidence='high')
        limit = None
        if m.get('fuse'):
            limit = (float(m['fuse'].get('i_hold_a', 0)) * 1000, 'hold current')
        elif m.get('switch') and m['switch'].get('i_max_ma'):
            limit = (float(m['switch']['i_max_ma']), 'contact rating')
        elif m.get('fet') and m['fet'].get('id_max_a'):
            limit = (float(m['fet']['id_max_a']) * 1000, 'continuous drain current')
        if not limit or not limit[0]:
            continue
        links = power_links(c)
        if not links and m.get('switch'):
            ps = [p for p in c.pins.values() if p.net and not d.nets[p.net].is_ground]
            links = [(a, b, 0, 0) for i, a in enumerate(ps) for b in ps[i + 1:]]
        for a, b, _, _ in links:
            na, nb = d.net_of(a), d.net_of(b)
            if na is None or nb is None or not (na.is_power and nb.is_power):
                continue
            dep = getattr(d, 'power_depth', {})
            n = max((na, nb), key=lambda x: dep.get(x.name, -1))       # the side away from the source
            typ, mx, parts = total_load(d, n)
            if mx <= 0:
                continue
            ev = {'through_mA_max': round(mx), 'rating_mA': limit[0], 'loads': _summ(parts)}
            if mx > limit[0]:
                yield F('power.budget', 'warning', f"{c.ref} may carry {mx:.0f} mA; its {limit[1]} is {limit[0]:g} mA",
                        f"{c.desc} feeds {n.name}. Sum of the maximum currents of everything behind it: {_summ(parts)}. "
                        f"This is the all-on worst case; if firmware limits it, record the limit in boardlint.yaml.",
                        refs=[c.ref], nets=[na.name, nb.name], evidence=ev, basis=model_basis(c), confidence='medium')
            elif mx > 0.7 * limit[0]:
                yield F('power.budget', 'info', f"{c.ref} carries up to {mx:.0f} mA of its {limit[0]:g} mA {limit[1]}",
                        f"{c.desc}; loads: {_summ(parts)}.", refs=[c.ref], evidence=ev, basis=model_basis(c),
                        confidence='medium')


def _has_source(d, net, seen):
    """True if a connector / battery / charger output is reachable on this side of the power path."""
    seen = set(seen)
    todo = [net]
    while todo:
        n = todo.pop()
        if n.name in seen:
            continue
        seen.add(n.name)
        for p in n.pins:
            c = p.comp
            if c.kind in ('CONN', 'BATT'):
                return True
            for a, b, _, _ in power_links(c):
                if p is a or p is b:
                    on = d.net_of(b if p is a else a)
                    if on is not None and not on.is_ground:
                        todo.append(on)
    return False


_R_POWER = {'0201': 0.05, '0402': 0.0625, '0603': 0.1, '0805': 0.125, '1206': 0.25, '1210': 0.5, '2010': 0.75, '2512': 1.0}


@check('ratings.passives', 'ratings', doc='Capacitor voltage ratings and resistor power against the rails they sit on')
def passives(d):
    no_rating = 0
    for c in d.components.values():
        if c.dnp or len(c.pins) != 2:
            continue
        a, b = [d.net_of(p) for p in c.pins.values()]
        if a is None or b is None:
            continue
        va = 0.0 if a.is_ground else a.vmax
        vb = 0.0 if b.is_ground else b.vmax
        if va is None or vb is None:
            continue
        lo_a = 0.0 if a.is_ground else a.vmin
        lo_b = 0.0 if b.is_ground else b.vmin
        dv = max(abs(va - lo_b), abs(vb - lo_a))
        if c.kind == 'C':
            vr = parse_voltage_rating(c)
            if vr is None:
                no_rating += 1 if dv > 0 else 0
                continue
            if dv > vr:
                yield F('ratings.passives', 'error', f"{c.ref} is rated {vr:g} V and sees {dv:g} V",
                        f"{c.desc} between {a.name} and {b.name}.", refs=[c.ref], nets=[a.name, b.name], confidence='high')
            elif dv > 0.8 * vr:
                yield F('ratings.passives', 'warning', f"{c.ref} runs at {dv / vr:.0%} of its {vr:g} V rating",
                        f"{c.desc} between {a.name} and {b.name}. Ceramic capacitors are usually derated to 80 % "
                        f"or less, and lose capacitance near their rating.", refs=[c.ref], nets=[a.name, b.name],
                        confidence='medium')
        elif c.kind == 'R' and c.num and (a.is_power or a.is_ground) and (b.is_power or b.is_ground):
            pw = dv * dv / c.num
            rating = _R_POWER.get(package_of(c) or '', None)
            if rating and pw > rating * 0.5:
                yield F('ratings.passives', 'error' if pw > rating else 'warning',
                        f"{c.ref} dissipates {pw * 1000:.0f} mW; a {package_of(c)} resistor is rated {rating * 1000:g} mW",
                        f"{c.desc} between {a.name} and {b.name} ({dv:g} V across it).", refs=[c.ref],
                        nets=[a.name, b.name], confidence='high')
    if no_rating:
        yield F('ratings.passives', 'info', f"{no_rating} capacitor(s) on known rails carry no voltage rating in the schematic",
                "Add a Voltage property (or put it in the value, e.g. '10uF 16V') and they will be checked.",
                confidence='high')


@check('ratings.fets', 'ratings', doc='FETs: Vds / Vgs limits and whether the gate drive actually turns them on')
def fets(d):
    for c in d.components.values():
        f = (c.model or {}).get('fet')
        if not f or c.dnp:
            continue
        g = next((p for p in c.pins.values() if p.name.upper() == 'G'), None)
        s = next((p for p in c.pins.values() if p.name.upper() == 'S'), None)
        dr = next((p for p in c.pins.values() if p.name.upper() == 'D'), None)
        if not (g and s and dr) or not (g.net and s.net and dr.net):
            continue
        ng, ns, nd = d.nets[g.net], d.nets[s.net], d.nets[dr.net]
        vs = (0.0, 0.0) if ns.is_ground else (ns.vmin, ns.vmax)
        rail_hi = max([v for v in (ns.vmax, nd.vmax) if v is not None] or [None]) if not (ns.vmax is None and nd.vmax is None) else None
        if rail_hi is None:
            ups, _ = pulls(d, nd.name)
            rail_hi = max([r.vmax for _, r in ups if r.vmax is not None] or [0]) or None
        if rail_hi and f.get('vds_max') and rail_hi > float(f['vds_max']):
            yield F('ratings.fets', 'error', f"{c.ref} Vds can reach {rail_hi:g} V; rating {f['vds_max']:g} V",
                    c.desc, refs=[c.ref], basis=model_basis(c), confidence='high')
        # gate drive
        if ng.is_ground:
            gate = (0.0, 0.0, 'tied to ground')
        else:
            hi, lo, src = net_levels(d, ng)
            gate = (lo, hi, src) if hi is not None else None
        if gate is None or vs[0] is None:
            continue
        p_ch = str(f.get('channel', 'n')).lower().startswith('p')
        # magnitude of the on-state gate drive, worst case (lowest)
        if p_ch:
            _, downs = pulls(d, ng.name)
            nets_g, _ = signal_group(d, ng.name, max_ohm=1e6)
            gp = [q for nn in nets_g for q in d.nets[nn].pins if q.comp is not c]
            pulled_low = ng.is_ground or bool(downs) or any(q.comp.kind == 'Q' or d.nets[q.net].is_ground for q in gp)
            driven = any(can_drive(q) or q.role == 'gpio' or q.comp.kind in ('SW', 'CONN') for q in gp)
            if not pulled_low and not driven:
                if ns.is_power and vs[0]:
                    yield F('ratings.fets', 'error', f"{c.ref} (P-channel) has nothing that can pull its gate low",
                            f"{c.desc}: gate net {ng.name} connects only to {names(gp[:5]) or 'nothing'}. With the gate "
                            f"at the source voltage the FET stays off and {nd.name} is never powered.",
                            refs=[c.ref], nets=[ng.name, nd.name], basis=model_basis(c), confidence='medium')
                continue
            if not pulled_low:
                continue
            von_min, von_max = vs[0], vs[1]
            how = f"gate pulled to ground, source on {ns.name} at {vs[0]:g}-{vs[1]:g} V"
        else:
            if gate[1] is None:
                continue
            von_min, von_max = (gate[0] or gate[1]) - vs[1], gate[1] - vs[0]
            how = f"gate {gate[2]} ({gate[0]:g}-{gate[1]:g} V)"
        if f.get('vgs_max') and von_max > float(f['vgs_max']):
            yield F('ratings.fets', 'error', f"{c.ref} gate sees {von_max:g} V; Vgs rating is {f['vgs_max']:g} V",
                    f"{c.desc}: {how}.", refs=[c.ref], basis=model_basis(c), confidence='high')
        spec = sorted((float(r['vgs']) for r in f.get('rds_on') or [] if r.get('vgs')), key=abs)
        vth = f.get('vgs_th_max')
        ev = {'vgs_on_min': round(von_min, 2), 'rds_on_specified_at_V': spec, 'vgs_th_max': vth}
        # how much current does it have to switch?
        others = [q.comp for q in nd.pins if q.comp is not c and q.comp.kind != 'TP']
        light = bool(others) and not nd.is_power and all(o.kind == 'R' and (o.num or 0) >= 4700 for o in others)
        if vth and von_min <= abs(float(vth)):
            yield F('ratings.fets', 'info' if light else 'error',
                    f"{c.ref} gate drive ({von_min:.2f} V) is not above its maximum threshold ({abs(float(vth)):g} V)",
                    f"{c.desc}: {how}. " + ("It only sinks a pull-up resistor here, so a weakly-on FET is enough, "
                                            "but the margin is by luck, not by datasheet." if light else
                                            "It may not turn on at all."),
                    refs=[c.ref], evidence=ev, basis=model_basis(c), confidence='medium')
        elif spec and von_min < abs(spec[0]) - 0.05:
            yield F('ratings.fets', 'info' if light else 'warning',
                    f"{c.ref} is driven with {von_min:.2f} V; Rds(on) is only specified down to {abs(spec[0]):g} V",
                    f"{c.desc}: {how}. Below the lowest specified gate voltage the on-resistance is not guaranteed"
                    + (" (it only switches a pull-up here, so it hardly matters)." if light else
                       " and rises steeply; expect extra voltage drop and heat at high current."),
                    refs=[c.ref], evidence=ev, basis=model_basis(c), confidence='medium')


def _first(spec, *keys):
    for k in keys:
        if spec.get(k) is not None:
            return float(spec[k])
    return None


@check('power.source_pin', 'power', doc="A part's supply-output pin (module 3V3 pin, internal regulator output) is not asked for more than it can give")
def source_pin(d):
    for c in d.components.values():
        if c.dnp or not c.model:
            continue
        for p in c.pins.values():
            if p.spec.get('role') != 'power_out' or not p.net:
                continue
            lim = _first(p.spec, 'i_out_max_ma', 'i_max_ma', 'i_load_max_ma', 'i_ext_max_ma', 'source_i_max_ma')
            n = d.nets[p.net]
            usb = False
            if lim is None and pin_aliases(str((c.model.get('module') or {}).get('usb_vbus_pin', '\x00'))) & pin_aliases(p.name):
                lim, usb = 500.0, True      # the pad is the USB port's VBUS: a USB 2.0 port owes a device 500 mA
            loads = [(x, im) for x, _, im, _ in rail_loads(d, n) if x is not c and im]
            leds = [q.comp for q in n.pins if q.comp.kind == 'LED' and not q.comp.model]
            tot = sum(im for _, im in loads)
            unknown = sorted({q.comp.ref for q in n.pins if q.comp.kind == 'IC' and q.comp is not c and not q.comp.model})
            ev = {'pin': p.label, 'limit_mA': lim, 'load_max_mA': round(tot, 1), 'loads': _summ([(x.ref, im) for x, im in loads]),
                  'not_counted': ', '.join(unknown) or 'none'}
            if lim is None:
                continue
            if tot > lim:
                yield F('power.source_pin', 'warning' if usb or tot <= 1.5 * lim else 'error',
                        f"{p.label} supplies {n.name}: up to {tot:.0f} mA is drawn, " +
                        (f"and it is the USB port's VBUS (500 mA from a USB 2.0 port)" if usb else f"it is good for {lim:g} mA"),
                        f"{c.desc}. Loads on {n.name}: {_summ([(x.ref, im) for x, im in loads])}. This is every load at "
                        f"its maximum at once." + (" The module's own current comes on top. A USB-C charger or a port "
                        "that advertises 1.5 A or 3 A gives more; a plain USB 2.0 port may shut down or droop. Limit "
                        "the current in firmware or add a hardware limit." if usb else '')
                        + (f" Not counted (no model): {', '.join(unknown)}." if unknown else ''),
                        refs=[c.ref] + [x.ref for x, _ in loads][:4], nets=[n.name], evidence=ev, basis=model_basis(c),
                        confidence='medium')
            elif tot or leds or unknown:
                yield F('power.source_pin', 'info', f"{p.label} supplies {n.name}: {tot:.0f} of {lim:g} mA accounted for",
                        f"{c.desc}." + (f" Not counted (no model): {', '.join(unknown)}." if unknown else ''),
                        refs=[c.ref], nets=[n.name], evidence=ev, basis=model_basis(c), confidence='medium')
