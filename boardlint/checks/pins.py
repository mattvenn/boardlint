"""Per-pin requirements from part models, plus generic 'must not float' rules."""
from __future__ import annotations
from . import check, F
from .common import can_drive, model_basis, names, PASSIVE_KINDS, supply_v
from ..classify import pulls, caps_to_ground, parse_value, fmt_r, fmt_c, signal_group, group_pins
from ..power import supply_net_of


def _num(v, kind):
    if isinstance(v, (int, float)):
        return float(v)
    return parse_value(str(v), kind)


def _has_level(d, pin):
    """Something on the net defines a level when nobody is actively driving."""
    n = d.net_of(pin)
    if n is None:
        return False, 'not connected'
    if n.is_power or n.is_ground:
        return True, f"tied to {n.name}"
    ups, downs = pulls(d, n.name)
    if ups or downs:
        return True, 'pull resistor ' + ', '.join(c.ref for c, _ in ups + downs)
    nets, _ = signal_group(d, n.name)
    drivers = [p for p in group_pins(d, nets) if p is not pin and can_drive(p) and p.role != 'gpio']
    if drivers:
        return True, 'driven by ' + names(drivers)
    return False, 'only ' + (names([p for p in group_pins(d, nets) if p is not pin][:4]) or 'this pin') + ' on the net'


@check('pin.requirements', 'pins', doc="Connections a part's datasheet demands (straps, reference resistors, bypass pins)")
def pin_requirements(d):
    for c in d.components.values():
        if c.dnp or not c.model:
            continue
        for p in c.pins.values():
            for req in p.spec.get('require') or []:
                note = req.get('note', '')
                when = req.get('when')
                tail = (f" {note}." if note else '') + (f" Applies when: {when}." if when else '')
                sev = req.get('severity', 'info' if when else 'error')
                n = d.net_of(p)
                def out(title, detail):
                    return F('pin.requirements', sev, title, detail + tail, refs=[c.ref], nets=[p.net] if p.net else [],
                             basis=model_basis(c), confidence='high' if (c.model.get('provenance') or {}).get('verified') else 'medium')
                if req.get('not_floating'):
                    ok, why = _has_level(d, p)
                    if not ok:
                        yield out(f"{p.label} must not float", f"{c.desc}: {why}.")
                if 'tie' in req:
                    want = str(req['tie']).lower()
                    ok = False
                    if n is not None:
                        ups, downs = pulls(d, n.name)
                        if want in ('gnd', 'low', 'ground', 'vss'):
                            ok = n.is_ground or any(r.num <= 10e3 for r, _ in downs)
                        else:
                            ok = (n.is_power and not n.is_ground) or any(r.num <= 10e3 for r, _ in ups)
                    if not ok:
                        yield out(f"{p.label} should be tied to {want}",
                                  f"{c.desc}: it is {'on ' + n.name if n else 'not connected'}.")
                for key, kind, getter in (('cap_to_gnd', 'C', None), ('res_to_gnd', 'R', None)):
                    if key not in req:
                        continue
                    r = req[key] or {}
                    if n is None:
                        yield out(f"{p.label} needs a {'capacitor' if kind == 'C' else 'resistor'} to ground",
                                  f"{c.desc}: the pin is not connected.")
                        continue
                    if kind == 'C':
                        have = [(k, k.num) for k, _ in caps_to_ground(d, n.name) if k.num]
                        tot = sum(v for _, v in have)
                        mn, mx = _num(r.get('min', r.get('value', 0)), 'C'), _num(r.get('max', 0), 'C')
                        if not have or (mn and tot < mn * 0.8) or (mx and tot > mx * 1.2):
                            yield out(f"{p.label} needs {fmt_c(mn) if mn else 'a capacitor'} to ground",
                                      f"{c.desc}: found {', '.join(f'{k.ref} {fmt_c(v)}' for k, v in have) or 'none'} on {n.name}.")
                    else:
                        _, downs = pulls(d, n.name)
                        want = _num(r.get('value', 0), 'R')
                        tol = float(r.get('tol', 0.05)) + 0.011
                        lo = _num(r.get('min', 0), 'R') or (want * (1 - tol) if want else 0)
                        hi = _num(r.get('max', 0), 'R') or (want * (1 + tol) if want else float('inf'))
                        good = [k for k, _ in downs if lo <= k.num <= hi]
                        if not good:
                            yield out(f"{p.label} needs {fmt_r(want) if want else fmt_r(lo) + ' to ' + fmt_r(hi)} to ground",
                                      f"{c.desc}: found {', '.join(f'{k.ref} {fmt_r(k.num)}' for k, _ in downs) or 'no resistor to ground'} on {n.name}.")
                for key in ('pullup', 'pulldown'):
                    if key not in req:
                        continue
                    r = req[key] or {}
                    if n is None:
                        yield out(f"{p.label} needs a {key}", f"{c.desc}: the pin is not connected.")
                        continue
                    ups, downs = pulls(d, n.name)
                    have = ups if key == 'pullup' else downs
                    mn, mx = _num(r.get('min', 0), 'R') or 0, _num(r.get('max', 0), 'R') or 0
                    if not have:
                        tied = (n.is_power and key == 'pullup') or (n.is_ground and key == 'pulldown')
                        if not tied:
                            yield out(f"{p.label} needs a {key}", f"{c.desc}: none on {n.name}.")
                    else:
                        rp = 1 / sum(1 / max(k.num, 1e-3) for k, _ in have)
                        if (mn and rp < mn * 0.95) or (mx and rp > mx * 1.05):
                            yield out(f"{p.label} {key} is {fmt_r(round(rp))}, outside {fmt_r(mn) if mn else '0'} to {fmt_r(mx) if mx else 'any'}",
                                      f"{c.desc}: {', '.join(k.desc for k, _ in have)}.")


@check('pin.floating_control', 'pins', doc='Enable, reset and open-drain pins have a defined level')
def floating_control(d):
    for c in d.components.values():
        if c.dnp or c.kind in PASSIVE_KINDS or c.kind in ('CONN', 'SW'):
            continue
        for p in c.pins.values():
            if p.role in ('enable', 'reset') and not any('not_floating' in r for r in p.spec.get('require') or []):
                pull = p.spec.get('internal_pull')
                if pull in ('up', 'down'):
                    continue
                ok, why = _has_level(d, p)
                if not ok:
                    yield F('pin.floating_control', 'error' if c.model else 'warning',
                            f"{p.label} ({p.role}) has no defined level",
                            f"{c.desc}: {why}. A floating {p.role} pin makes the part start or stop at random; "
                            f"check the datasheet for an internal pull.", refs=[c.ref], nets=[p.net] if p.net else [],
                            basis=model_basis(c) if c.model else 'pin name (no part model)',
                            confidence='medium' if c.model else 'low')
            od = p.spec.get('drive') == 'open_drain' or p.etype in ('open_collector',)
            if od and p.net and p.role not in ('i2c_sda', 'i2c_scl'):
                n = d.net_of(p)
                ups, _ = pulls(d, n.name)
                if not ups and not n.is_power:
                    nets, _ = signal_group(d, n.name)
                    others = [q for q in group_pins(d, nets) if q is not p and q.comp.kind not in PASSIVE_KINDS]
                    mcu_only = others and all(q.role == 'gpio' for q in others)
                    yield F('pin.floating_control', 'info' if mcu_only else 'warning',
                            f"Open-drain output {p.label} has no pull-up",
                            f"Net {n.name} can only be pulled low. " +
                            (f"{names(others)} must enable its internal pull-up in firmware; that pull-up is off "
                             f"during reset and in deep sleep unless held." if mcu_only else "Nothing pulls it high."),
                            refs=[c.ref] + sorted({q.comp.ref for q in others}), nets=[n.name],
                            basis=model_basis(c) if c.model else 'pin type from the symbol',
                            confidence='medium')


@check('mcu.strapping', 'pins', doc='Boot-strap pins are not loaded by other circuits')
def strapping(d):
    for c in d.components.values():
        straps = ((c.model or {}).get('mcu') or {}).get('strapping') or {}
        for pname, spec in straps.items():
            spec = spec if isinstance(spec, dict) else {'note': str(spec)}
            from ..power import _pins_named
            for p in _pins_named(c, pname):
                if not p.net:
                    continue
                n = d.net_of(p)
                ups, downs = pulls(d, n.name)
                nets, _ = signal_group(d, n.name)
                others = [q for q in group_pins(d, nets) if q is not p and q.comp.kind not in ('TP', 'MECH')]
                want = str(spec.get('must_be', spec.get('normal', spec.get('default', '')))).lower()
                against = (downs if want in ('high', '1') else ups if want in ('low', '0') else [])
                tied_wrong = (n.is_ground and want in ('high', '1')) or (n.is_power and not n.is_ground and want in ('low', '0'))
                what = '; '.join(f"{k}: {v}" for k, v in spec.items())
                if tied_wrong or against:
                    yield F('mcu.strapping', 'error', f"Strapping pin {p.label} is pulled the wrong way",
                            f"{c.desc} samples this pin at reset ({what}). On this board it is "
                            + (f"tied to {n.name}" if tied_wrong else 'pulled by ' + ', '.join(k.desc for k, _ in against)) + ".",
                            refs=[c.ref], nets=[n.name], basis=model_basis(c), confidence='medium')
                elif others:
                    active = [q for q in others if q.comp.kind not in PASSIVE_KINDS and q.comp.kind != 'SW']
                    yield F('mcu.strapping', 'warning' if active else 'info',
                            f"Strapping pin {p.label} is used ({n.name})",
                            f"{c.desc} samples this pin at reset ({what}). Connected here: {names(others[:6])}. "
                            f"Whatever is attached must not hold the wrong level while the module comes out of reset.",
                            refs=[c.ref] + sorted({q.comp.ref for q in others})[:4], nets=[n.name],
                            basis=model_basis(c), confidence='medium')
