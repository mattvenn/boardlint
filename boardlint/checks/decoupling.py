"""Decoupling: enough capacitors per supply pin, of the right value, and (with a board) close enough."""
from __future__ import annotations
from collections import defaultdict
from . import check, F
from .common import dist, model_basis, PASSIVE_KINDS
from ..classify import caps_to_ground, parse_value, fmt_c, package_of
from ..library import supply_spec

# Typical fraction of nominal capacitance a class-II MLCC of >= 1 uF keeps under DC bias.
# (package, at about 3.3 V, at about 5 V).  Typical 6.3-10 V parts; the maker's curve is the truth.
_BIAS = {'0201': (0.35, 0.2), '0402': (0.5, 0.35), '0603': (0.7, 0.55), '0805': (0.8, 0.7), '1206': (0.9, 0.85)}


def effective_c(cap, volts):
    """Capacitance left after DC-bias derating (rough), and whether derating was applied."""
    if cap.num is None:
        return 0.0, False
    pkg = package_of(cap)
    if cap.num < 0.9e-6 or pkg not in _BIAS or not volts:
        return cap.num, False
    f33, f5 = _BIAS[pkg]
    size_pen = 1.0 if cap.num <= 2.5e-6 else (0.8 if cap.num <= 5e-6 else 0.7)   # denser parts lose more
    if pkg in ('0805', '1206') and cap.num <= 10.5e-6:
        size_pen = max(size_pen, 0.85)
    frac = f33 if volts <= 3.6 else f5
    if volts < 2.0:
        frac = min(1.0, frac + 0.25)
    return cap.num * frac * size_pen, True


def _cnum(v):
    return float(v) if isinstance(v, (int, float)) else parse_value(str(v), 'C')


@check('decoupling.per_part', 'power', doc='Each supply pin has the decoupling its datasheet asks for (count, value, distance)')
def per_part(d):
    default_mm = float((d.config.get('decoupling') or {}).get('max_mm', 6.0))
    need_by_rail = defaultdict(list)       # rail -> [(component, c_min)] for the exclusivity count
    for c in d.components.values():
        if c.dnp or c.kind in PASSIVE_KINDS or c.kind in ('CONN', 'SW', 'Q'):
            continue
        groups = defaultdict(list)          # rail name -> [(pin, supply spec)]
        for p in c.pins.values():
            n = d.net_of(p)
            if n is None or n.is_ground:
                continue
            s = supply_spec(c, p)
            if s is not None or p.etype == 'power_in':
                groups[n.name].append((p, s))
        for rail, plist in groups.items():
            caps = caps_to_ground(d, rail)
            reqs = []
            seen = set()
            for p, s in plist:
                for r in (s or {}).get('decoupling') or []:
                    if id(r) not in seen:
                        seen.add(id(r))
                        reqs.append(r)
            modelled = bool(reqs)
            if not reqs and c.model and c.model.get('supplies'):
                continue                    # the datasheet was read and asks for nothing
            if not reqs:
                reqs = [{'c_min': '10n', 'count': 1, 'max_mm': default_mm, '_generic': True}]
            for r in reqs:
                cmin = _cnum(r.get('c_min', '100n')) or 100e-9
                cnt = int(r.get('count', 1))
                mm = float(r.get('max_mm', default_mm if cmin < 0.9e-6 else default_mm * 3))   # bulk can sit further away
                ok_val = [(k, kp) for k, kp in caps if k.num and k.num >= cmin * 0.79]
                need_by_rail[rail] += [(c, cmin)] * cnt
                basis = model_basis(c, r.get('note', '')) if modelled else \
                    'rule of thumb: one bypass capacitor per IC supply (no part model)'
                conf = 'high' if modelled else 'medium'
                if len(ok_val) < cnt:
                    tot = sum(k.num or 0 for k, _ in caps)
                    partly = tot >= 0.4 * cmin * cnt
                    summary = defaultdict(int)
                    for k, _ in caps:
                        summary[fmt_c(k.num)] += 1
                    met = tot >= cmin * cnt
                    yield F('decoupling.per_part', 'info' if met else 'error' if modelled and not partly else 'warning',
                            f"{c.ref} supply {rail}: needs {cnt} x {fmt_c(cmin)} or more, the rail has {len(ok_val)}"
                            + (f" ({fmt_c(round(tot, 9))} in total)" if partly else ''),
                            f"{c.desc} pins {', '.join(p.label for p, _ in plist)}. Capacitors on {rail}: "
                            f"{', '.join(f'{n_} x {v}' for v, n_ in summary.items()) or 'none'}.",
                            refs=[c.ref], nets=[rail], basis=basis, confidence=conf)
                    continue
                if d.board and all(p.pos for p, _ in plist):
                    near = []
                    for k, kp in ok_val:
                        if kp.pos:
                            dm = min(dist(kp.pos, p.pos) for p, _ in plist)
                            near.append((dm, k))
                    near.sort(key=lambda x: x[0])
                    within = [x for x in near if x[0] <= mm]
                    if near and len(within) < cnt:
                        yield F('decoupling.per_part', 'warning',
                                f"{c.ref} supply {rail}: nearest {fmt_c(cmin)}+ capacitor is {near[0][0]:.1f} mm away",
                                f"{c.desc} wants {cnt} within {mm:g} mm of its supply pin; closest are "
                                f"{', '.join(f'{k.ref} at {dm:.1f} mm' for dm, k in near[:3])} (pad to pad, straight line). "
                                f"Distance adds loop inductance: about 1 nH per mm of trace.",
                                refs=[c.ref, near[0][1].ref], nets=[rail],
                                evidence={'required_mm': mm, 'nearest_mm': round(near[0][0], 2)},
                                basis=basis + '; distance measured on the board', confidence=conf)
    # a capacitor can only be "the local capacitor" of so many parts
    for rail, needs in need_by_rail.items():
        caps = [k for k, _ in caps_to_ground(d, rail) if k.num and k.num >= 10e-9]
        parts = sorted({c.ref for c, _ in needs})
        if len(needs) >= 4 and len(caps) < len(needs) * 0.75:
            yield F('decoupling.per_part', 'warning', f"Rail {rail}: {len(caps)} capacitors for {len(needs)} required positions",
                    f"{len(parts)} parts on the rail ask for {len(needs)} local capacitors in total; sharing one "
                    f"between distant parts defeats it.", refs=parts[:6], nets=[rail], confidence='medium')


@check('decoupling.regulator_caps', 'power', doc='Regulator input/output capacitance after DC-bias derating')
def regulator_caps(d):
    from ..power import _pins_named
    for c in d.components.values():
        reg = (c.model or {}).get('regulator')
        chg = (c.model or {}).get('charger')
        if c.dnp or not (reg or chg):
            continue
        items = []
        if reg:
            items += [(reg.get('vin'), reg.get('cin_min'), 'input'), (reg.get('vout'), reg.get('cout_min'), 'output')]
        if chg:
            items += [(chg.get('vin'), chg.get('cin_min'), 'input'), (chg.get('vbat'), chg.get('cout_min') or chg.get('cbat_min'), 'battery')]
        for pname, cmin, what in items:
            cmin = _cnum(cmin) if cmin else None
            pins = _pins_named(c, pname)
            if not cmin or not pins or not pins[0].net:
                continue
            n = d.nets[pins[0].net]
            caps = caps_to_ground(d, n.name)
            if d.board and pins[0].pos:
                local = [(k, kp) for k, kp in caps if kp.pos and dist(kp.pos, pins[0].pos) <= 10.0]
            else:
                local = caps
            v = n.vmax
            eff = [(k, *effective_c(k, v)) for k, _ in local]
            tot_nom = sum(k.num or 0 for k, _ in local)
            tot_eff = sum(e for _, e, _ in eff)
            ev = {'required': fmt_c(cmin), 'nominal': fmt_c(tot_nom), 'after_bias_est': fmt_c(round(tot_eff, 9)),
                  'bias_v': v, 'caps': {k.ref: f"{fmt_c(k.num)} {package_of(k) or ''}".strip() for k, _ in local}}
            if tot_nom < cmin * 0.8:
                yield F('decoupling.regulator_caps', 'error',
                        f"{c.ref} {what} capacitance {fmt_c(tot_nom)} is below the required {fmt_c(cmin)}",
                        f"{c.desc} on {n.name}" + (" (capacitors within 10 mm of the pin)" if d.board else "") + ".",
                        refs=[c.ref] + [k.ref for k, _ in local], nets=[n.name], evidence=ev, basis=model_basis(c),
                        confidence='high')
            elif tot_eff < cmin * 0.8:
                yield F('decoupling.regulator_caps', 'warning',
                        f"{c.ref} {what} capacitance may fall below {fmt_c(cmin)} under DC bias",
                        f"{fmt_c(tot_nom)} nominal on {n.name} is roughly {fmt_c(round(tot_eff, 9))} at {v:g} V in "
                        f"these package sizes. Use a larger package or value, or check the capacitor's bias curve.",
                        refs=[c.ref] + [k.ref for k, _ in local], nets=[n.name], evidence=ev,
                        basis=model_basis(c) + '; DC-bias derating is a typical-part estimate', confidence='low')
