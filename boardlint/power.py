"""Rail discovery: which nets are ground / supplies, at what voltage, fed from where."""
from __future__ import annotations
import re
from .model import Design, Net, Component
from .classify import is_ground_name, parse_value
from .library import supply_spec

# name -> (vmin, vmax).  Used only when nothing better (config, regulator model) is known.
_NAME_V = [
    (re.compile(r'(?<![\d.])(\d+)V(\d+)(?!\d)', re.I), lambda m: float(m.group(1) + '.' + m.group(2))),
    (re.compile(r'(?<![\d.])(\d+(?:\.\d+)?)\s*V(?![A-Z0-9])', re.I), lambda m: float(m.group(1))),
    (re.compile(r'^\+(\d+(?:\.\d+)?)V[A-Z]{1,3}$', re.I), lambda m: float(m.group(1))),      # +3.3VP, +5VA
]
_SPECIAL = [
    (re.compile(r'VBUS|USB_?5V|VUSB', re.I), (4.4, 5.5, 'USB VBUS range (name)')),
    (re.compile(r'V?BAT|LIPO|LI_?ION|VCELL', re.I), (3.0, 4.2, 'single Li-ion cell assumed (name)')),
]


def voltage_from_name(name: str):
    base = name.split('/')[-1]
    for rx, v in _SPECIAL:
        if rx.search(base):
            return v
    if not re.match(r'^[+\-]?\d|^V(CC|DD|IN|OUT|SYS|REF)?[_+]?\d|^P\d+V|^PWR', base, re.I) and not re.search(r'\dV\d|\d+V$|^\+\d+(\.\d+)?V[A-Z]{1,3}$', base, re.I):
        return None
    for rx, f in _NAME_V:
        m = rx.search(base)
        if m:
            v = f(m)
            if 0.5 <= v <= 60:
                return (round(v * 0.95, 3), round(v * 1.05, 3), 'net name')
    return None


def _set(n: Net, vmin, vmax, src):
    n.is_power, n.vmin, n.vmax, n.vsrc = True, vmin, vmax, src


def analyse_power(d: Design):
    cfg_rails = (d.config.get('rails') or {})
    for n in d.nets.values():
        if is_ground_name(n.name) or n.name in (d.config.get('grounds') or []):
            n.is_ground = True
    # 1. explicit configuration wins
    for name, r in cfg_rails.items():
        n = d.nets.get(name)
        if n:
            _set(n, float(r.get('vmin', r.get('v', 0))), float(r.get('vmax', r.get('v', 0))), 'boardlint.yaml')
    # 2. regulator outputs from part models
    for c in d.components.values():
        reg = (c.model or {}).get('regulator')
        if not reg or c.dnp:
            continue
        outs = _pins_named(c, reg.get('vout'))
        v = reg.get('vout_v')
        if not v and reg.get('vref') and reg.get('fb'):
            v = _fb_voltage(d, c, reg)
        for p in outs:
            n = d.net_of(p)
            if n and v and n.vmin is None and not n.is_ground:
                tol = reg.get('tol', 0.03)
                _set(n, round(v * (1 - tol), 3), round(v * (1 + tol), 3), f"{c.ref} {c.value} output")
        chg = None
    for c in d.components.values():
        chg = (c.model or {}).get('charger')
        if chg and not c.dnp:
            for p in _pins_named(c, chg.get('vbat')):
                n = d.net_of(p)
                if n and n.vmin is None:
                    _set(n, 3.0, float(chg.get('v_float', 4.2)), f"{c.ref} charger float voltage; 3.0 V empty cell assumed")
    # 3. names
    for n in d.nets.values():
        if n.vmin is None and not n.is_ground:
            v = voltage_from_name(n.name)
            # a name alone is not enough: VBAT_SENSE and VBUS_DET are signals
            supplyish = n.name.split('/')[-1].startswith('+') or any(
                p.etype in ('power_in', 'power_out') or supply_spec(p.comp, p) is not None or
                (p.comp.kind == 'CONN' and re.match(r'^(VBUS|VCC|VDD|VIN|V\+|\+?\d+V\d*)$', p.name, re.I))
                for p in n.pins)
            if v and supplyish:
                _set(n, v[0], v[1], v[2])
    # 4. nets that feed power pins are rails even when we do not know the voltage
    for n in d.nets.values():
        if n.is_ground or n.is_power:
            continue
        if any(p.etype in ('power_in', 'power_out') or supply_spec(p.comp, p) for p in n.pins):
            n.is_power = True
    # 5. propagate along the power path (fuses, jumpers, ferrites, FET channels, diodes)
    changed = True
    while changed:
        changed = False
        for c in d.components.values():
            if c.dnp:
                continue
            for a, b, drop_min, drop_max in power_links(c):
                na, nb = d.net_of(a), d.net_of(b)
                if not na or not nb or na.is_ground or nb.is_ground:
                    continue
                for src, dst, directional in ((na, nb, False), (nb, na, drop_max > 0)):
                    if directional:
                        continue      # a diode only passes anode -> cathode
                    if src.vmin is not None and dst.vmin is None:
                        _set(dst, round(max(src.vmin - drop_max, 0), 3), round(src.vmax - drop_min, 3),
                             f"{src.name} through {c.ref}")
                        dst.feeds_from = (src.name, c.ref)
                        changed = True
    _depths(d)
    # 6. resistor dividers between a known level and ground give signal-level voltages
    for n in list(d.nets.values()) * 2:
        if n.is_power or n.is_ground or n.vmin is not None:
            continue
        up = dn = None
        other = 0
        for p in n.pins:
            c = p.comp
            if c.kind == 'R' and len(c.pins) == 2 and c.num is not None and not c.dnp:
                on = d.net_of(c.other_pin(p))
                if on is not None and on.is_ground:
                    dn = (c, on) if dn is None else dn
                    continue
                lv = driven_level(d, on) if on is not None else None
                if lv is not None:
                    up = (c, on, lv) if up is None else up
                    continue
            if p.etype in ('output', 'power_out', 'tri_state', 'open_collector', 'open_emitter') or \
                    p.spec.get('drive') in ('push_pull', 'open_drain', 'tri_state'):
                other += 1
        if up and dn and other == 0 and (up[0].num + dn[0].num) > 0:
            k = dn[0].num / (up[0].num + dn[0].num)
            n.vmin, n.vmax = round(up[2][0] * k, 3), round(up[2][1] * k, 3)
            n.vsrc = f"divider {up[0].ref}/{dn[0].ref} from {up[1].name} ({up[2][2]})"
            n.divider = (up[0], dn[0], up[1], up[2])


def _depths(d: Design):
    """Distance of every rail from where power enters the board, so 'downstream' has a direction."""
    reg_out = set()
    for c in d.components.values():
        m = c.model or {}
        for sec, key in (('regulator', 'vout'), ('charger', 'vbat')):
            if m.get(sec):
                reg_out |= {p.net for p in _pins_named(c, m[sec].get(key)) if p.net}
    depth = {}
    todo = []
    for n in d.nets.values():
        if n.is_power and not n.is_ground and n.name not in reg_out and \
                any(p.comp.kind in ('CONN', 'BATT') for p in n.pins):
            depth[n.name] = 0
            todo.append(n)
    while todo:
        n = todo.pop(0)
        for p in n.pins:
            c = p.comp
            if c.dnp:
                continue
            nxt = []
            for a, b, _, _ in power_links(c):
                if p is a or p is b:
                    nxt.append(d.net_of(b if p is a else a))
            reg = (c.model or {}).get('regulator')
            if reg and p in _pins_named(c, reg.get('vin')):
                nxt += [d.net_of(o) for o in _pins_named(c, reg.get('vout'))]
            for on in nxt:
                if on is not None and not on.is_ground and on.name not in depth:
                    depth[on.name] = depth[n.name] + 1
                    todo.append(on)
    d.power_depth = depth


def driven_level(d: Design, n: Net):
    """(vmin, vmax, how) of a net when it is high: a rail, or a push-pull / tri-state output's supply."""
    if n.is_ground:
        return None
    if n.vmin is not None and n.is_power:
        return n.vmin, n.vmax, n.vsrc
    for p in n.pins:
        c = p.comp
        if c.kind in ('R', 'C', 'L', 'FB', 'TP', 'JUMPER', 'CONN', 'SW', 'D', 'Q'):
            continue
        if p.spec.get('drive') in ('push_pull', 'tri_state') or (not p.spec.get('drive') and p.etype in ('output', 'tri_state')):
            s = supply_net_of(d, c)
            if s is not None and s.vmin is not None:
                return s.vmin, s.vmax, f"{p.label} high = {s.name}"
    return None


def power_links(c: Component):
    """(pin a, pin b, min drop, max drop) for parts that pass supply current a -> b."""
    pins = list(c.pins.values())
    if c.kind in ('FUSE', 'FB') and len(pins) == 2:
        return [(pins[0], pins[1], 0.0, 0.0)]
    if c.kind == 'R' and len(pins) == 2 and c.num is not None and c.num <= 1.0:
        return [(pins[0], pins[1], 0.0, 0.0)]
    if c.kind == 'JUMPER':
        return [(c.pins[a], c.pins[b], 0.0, 0.0) for a, b in c.props.get('_bridged', []) if a in c.pins and b in c.pins]
    if c.kind == 'Q' and (c.model or {}).get('fet') or (c.kind == 'Q' and {'S', 'D', 'G'} <= {p.name for p in pins}):
        s = [p for p in pins if p.name.upper() == 'S']
        dr = [p for p in pins if p.name.upper() == 'D']
        if s and dr:
            return [(s[0], dr[0], 0.0, 0.0)]
    if c.kind == 'D' and len(pins) == 2:
        a = [p for p in pins if p.name.upper() in ('A', 'ANODE')]
        k = [p for p in pins if p.name.upper() in ('K', 'C', 'CATHODE')]
        if a and k:
            vf = float(((c.model or {}).get('diode') or {}).get('vf', 0.7))
            return [(a[0], k[0], min(0.2, vf), vf)]
    return []


def _pins_named(c: Component, name):
    if not name:
        return []
    from .classify import pin_aliases, norm_pin_name
    names = name if isinstance(name, list) else [name]
    out = []
    for p in c.pins.values():
        al = pin_aliases(p.name)
        for nm in names:
            nm = str(nm)
            if (nm.startswith('#') and nm[1:] == p.number) or norm_pin_name(nm) in al or (pin_aliases(nm) & al):
                out.append(p)
                break
    return out


def _fb_voltage(d: Design, c: Component, reg):
    """Vout of an adjustable regulator from its feedback divider."""
    fb = _pins_named(c, reg.get('fb'))
    outs = _pins_named(c, reg.get('vout'))
    if not fb or not fb[0].net:
        return None
    top = bot = None
    for p in d.nets[fb[0].net].pins:
        r = p.comp
        if r.kind == 'R' and r.num is not None and len(r.pins) == 2:
            on = d.net_of(r.other_pin(p))
            if on is not None and on.is_ground:
                bot = r
            elif on is not None:
                top = r
    if top and bot and bot.num:
        return round(float(reg['vref']) * (1 + top.num / bot.num), 3)
    return None


def supply_net_of(d: Design, c: Component, pin=None):
    """The rail that powers a part (or one of its pins)."""
    best = None
    for p in c.pins.values():
        n = d.net_of(p)
        if n is None or n.is_ground:
            continue
        s = supply_spec(c, p)
        if s is not None or p.etype == 'power_in':
            if best is None or (n.vmin is not None and (best.vmin is None or n.vmax > best.vmax)):
                best = n                 # several domains: I/O pins are judged against the highest one
    return best


def rail_loads(d: Design, net: Net):
    """[(Component, i_typ_ma, i_max_ma, i_step_ma)] of parts with a modelled supply on this rail."""
    out, seen = [], set()
    for p in net.pins:
        s = supply_spec(p.comp, p)
        if s and p.comp.ref not in seen and not p.comp.dnp:
            seen.add(p.comp.ref)
            out.append((p.comp, s.get('i_typ_ma') or 0.0, s.get('i_max_ma') or s.get('i_typ_ma') or 0.0,
                        s.get('i_step_ma') or 0.0))
    return out


def downstream(d: Design, net: Net, _seen=None):
    """Rails fed from this rail through switches/fuses (not regulators): [(Net, via Component)]."""
    out = []
    seen = _seen if _seen is not None else {net.name}
    for n in d.nets.values():
        f = getattr(n, 'feeds_from', None)
        if f and f[0] == net.name and n.name not in seen:
            seen.add(n.name)
            out.append((n, d.components[f[1]]))
            out += downstream(d, n, seen)
    return out
