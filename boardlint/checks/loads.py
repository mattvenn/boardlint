"""Switched loads: buzzers, relays, motors and other coils."""
from __future__ import annotations
import re
from . import check, F
from .common import model_basis, PASSIVE_KINDS
from ..classify import fmt_r

_COIL = re.compile(r'relay|buzzer|motor|solenoid|speaker', re.I)


def _series_to_rail(d, pin):
    """Walk from a load terminal through series resistors to a rail.  Returns (rail Net, ohms, [resistors])."""
    net, r, used, seen = pin.net, 0.0, [], set()
    while net and net not in seen:
        seen.add(net)
        n = d.nets[net]
        if n.is_power or n.is_ground:
            return n, r, used
        rs = [q.comp for q in n.pins if q.comp.kind == 'R' and len(q.comp.pins) == 2 and q.comp.num is not None and q.comp is not pin.comp]
        nxt = {}
        for c in rs:
            o = [x for x in c.pins.values() if x.net != net]
            if o and o[0].net:
                nxt.setdefault(o[0].net, []).append(c)
        if len(nxt) != 1:
            return None, r, used
        net, group = next(iter(nxt.items()))
        r += 1 / sum(1 / max(c.num, 1e-3) for c in group)
        used += group
    return None, r, used


@check('load.inductive', 'power', doc='Buzzers, relays and motors: a flyback diode the right way round, and enough voltage across the coil')
def inductive(d):
    for c in d.components.values():
        m = c.model or {}
        bz = m.get('buzzer')
        coil = m.get('inductive_load') or (not c.model and _COIL.search(c.lib_id + ' ' + c.value) and c.kind not in PASSIVE_KINDS)
        if c.dnp or not (bz or coil):
            continue
        pins = [p for p in c.pins.values() if p.net]
        if len(pins) != 2:
            continue
        a, b = pins
        na, nb = d.nets[a.net], d.nets[b.net]
        sw = [q.comp for n in (na, nb) for q in n.pins if q.comp.kind == 'Q']
        if coil and sw:
            diodes = [q.comp for q in na.pins if q.comp.kind == 'D' and any(x.net == b.net for x in q.comp.pins.values())]
            if not diodes:
                yield F('load.inductive', 'error', f"{c.ref} is a coil switched by {sw[0].ref} with no flyback diode",
                        f"{c.desc}: when {sw[0].ref} turns off, the coil's current has nowhere to go and the voltage "
                        f"at the switch rises until something breaks down. Put a diode across the coil, cathode to "
                        f"the supply side.", refs=[c.ref, sw[0].ref], nets=[a.net, b.net],
                        basis=model_basis(c) if c.model else 'part type from its symbol name', confidence='medium')
            else:
                dd = diodes[0]
                k = next((p for p in dd.pins.values() if p.name.upper() in ('K', 'C', 'CATHODE')), None)
                # the switch side is the one the transistor is on; the cathode must be on the other
                sw_net = next((n.name for n in (na, nb) if any(q.comp.kind == 'Q' for q in n.pins)), None)
                low_side = any(q.comp.kind == 'Q' and (q.comp.model or {}).get('fet', {}).get('channel', 'n') == 'n'
                               for q in d.nets[sw_net].pins) if sw_net else True
                if k is not None and sw_net and ((k.net == sw_net) == low_side):
                    yield F('load.inductive', 'error', f"Flyback diode {dd.ref} across {c.ref} is the wrong way round",
                            f"Its cathode is on {k.net}, the switched side. It conducts whenever the load is on "
                            f"and does nothing when it turns off.", refs=[dd.ref, c.ref], nets=[a.net, b.net],
                            confidence='medium')
        if bz and bz.get('r_coil_ohm'):
            rail = rs = used = None
            for p in pins:
                n, r, u = _series_to_rail(d, p)
                if n is not None and n.is_power and n.vmin is not None:
                    rail, rs, used = n, r, u
            if rail is None:
                continue
            rc = float(bz['r_coil_ohm'])
            v = rail.vmin * rc / (rc + rs)
            i = rail.vmax / (rc + rs) * 1000
            ev = {'supply': f"{rail.name} {rail.vmin:g}-{rail.vmax:g} V", 'series_resistance': fmt_r(round(rs, 1)),
                  'coil': f"{rc:g} ohm", 'coil_voltage_dc': round(v, 2), 'peak_current_mA': round(i),
                  'rated': f"{bz.get('v_min', '?')}-{bz.get('v_max', '?')} V, {bz.get('i_max_ma', '?')} mA max"}
            if bz.get('v_min') and v < float(bz['v_min']):
                yield F('load.inductive', 'warning', f"{c.ref} gets about {v:.2f} V; it is specified from {bz['v_min']:g} V",
                        f"{c.desc}: {fmt_r(round(rs, 1))} in series ({', '.join(x.ref for x in used)}) with a {rc:g} ohm coil "
                        f"from {rail.name} leaves {v:.2f} V across it by its DC resistance; it will be much quieter "
                        f"than its rated sound level. The coil's impedance at {bz.get('f_res_hz', 0) / 1000:g} kHz is higher "
                        f"than its DC resistance, so the real figure is somewhat better: measure it. If the "
                        f"resistors are there to limit the current when the drive pin sticks high, a capacitor in "
                        f"series with the drive, or a time-limited driver, does that without costing volume.",
                        refs=[c.ref] + [x.ref for x in used], nets=[rail.name], evidence=ev, basis=model_basis(c),
                        confidence='medium')
            elif bz.get('i_max_ma') and i > float(bz['i_max_ma']) * 1.1:
                yield F('load.inductive', 'warning', f"{c.ref} can draw {i:.0f} mA; its maximum is {bz['i_max_ma']:g} mA",
                        f"{c.desc} from {rail.name} with {fmt_r(round(rs, 1))} in series, if the drive stays on.",
                        refs=[c.ref], evidence=ev, basis=model_basis(c), confidence='medium')
