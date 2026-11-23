"""Supply droop: a small ngspice model of each regulated rail under its worst load step.

What is modelled (and nothing more):
  source      upstream rail at its minimum and nominal voltage, behind the series resistance of the
              power path we can see (fuse, FET, jumpers) plus an assumed source resistance
  regulator   LDO as a PI current loop crossing over at ``bw_khz``, with a current limit and a
              dropout resistance from the datasheet's dropout figure
  capacitors  every capacitor on the input and output rails, DC-bias derated, with package ESR/ESL
  copper      one R-L branch from the regulator output to the load, from the board geometry
  load        the rail's modelled parts stepping from typical to maximum current, plus anything
              else that shares the regulator's input rail switching on at the same instant
"""
from __future__ import annotations
import math
import os
from . import check, F
from .common import dist, model_basis
from .decoupling import effective_c
from .power_checks import total_load, _summ
from ..classify import caps_to_ground, package_of, fmt_c
from ..library import supply_spec
from ..power import _pins_named, power_links, rail_loads
from ..sim import ngspice

_ESL = {'0201': 0.3e-9, '0402': 0.45e-9, '0603': 0.6e-9, '0805': 0.8e-9, '1206': 1.0e-9}


def _cap_lines(d, net, tag, node, lines, pos=None, split=None):
    """Adds every capacitor on ``net``.  With ``split`` (pos_a, pos_b, node_b) caps nearer b go there."""
    n = 0
    for k, kp in caps_to_ground(d, net.name):
        c_eff, _ = effective_c(k, net.vmax)
        if not c_eff:
            continue
        pkg = package_of(k) or '0603'
        esr = 0.03 if c_eff < 0.5e-6 else 0.008
        nd = node
        if split and kp.pos and split[0] and split[1]:
            if dist(kp.pos, split[1]) < dist(kp.pos, split[0]):
                nd = split[2]
        n += 1
        lines += [f"C{tag}{n} {nd} {tag}c{n} {c_eff:.4g}", f"R{tag}{n} {tag}c{n} {tag}l{n} {esr}",
                  f"L{tag}{n} {tag}l{n} 0 {_ESL.get(pkg, 0.7e-9):.3g}"]
    return n


def source_path(d, net):
    """Series resistance between this rail and where its power enters the board.
    Returns (ohms, [descriptions])."""
    cfg = (d.config.get('sources') or {})
    seen, todo = {net.name}, [(net, 0.0, [])]
    best = None
    while todo:
        n, r, path = todo.pop(0)
        if n.name in cfg:
            return r + float(cfg[n.name].get('r', 0)), path + [f"{n.name} source {cfg[n.name].get('r', 0)} ohm (boardlint.yaml)"]
        if any(p.comp.kind in ('CONN', 'BATT') for p in n.pins) and best is None and path:
            best = (r, path, n)
        for p in n.pins:
            c = p.comp
            for a, b, _, _ in power_links(c):
                if p is not a and p is not b:
                    continue
                on = d.net_of(b if p is a else a)
                if on is None or on.is_ground or on.name in seen:
                    continue
                if any(q.comp.kind == 'LED' or (q.comp.model or {}).get('serial_led') for q in on.pins):
                    continue            # a load branch, not the way to the source
                m = c.model or {}
                if m.get('fuse'):
                    rr, what = float(m['fuse'].get('r_max', 0.2)), f"{c.ref} fuse {m['fuse'].get('r_max', 0.2)} ohm max"
                elif m.get('fet'):
                    rds = sorted(m['fet'].get('rds_on') or [], key=lambda x: abs(float(x.get('vgs', 0))))
                    rr = float(rds[0]['mohm']) / 1000 if rds else 0.1
                    what = f"{c.ref} Rds(on) {rr * 1000:.0f} mohm at |Vgs| {abs(float(rds[0]['vgs'])):g} V" if rds else f"{c.ref} 0.1 ohm assumed"
                elif c.kind == 'FUSE':
                    rr, what = 0.2, f"{c.ref} fuse 0.2 ohm assumed"
                elif c.kind == 'Q':
                    rr, what = 0.1, f"{c.ref} FET 0.1 ohm assumed"
                else:
                    rr, what = 0.01, f"{c.ref} 10 mohm"
                seen.add(on.name)
                todo.append((on, r + rr, path + [what]))
    if best:
        r, path, n = best
        batt = 'BAT' in net.name.upper() or 'BAT' in n.name.upper()
        rs = 0.15 if batt else 0.1
        return r + rs, path + [f"{'cell and its protection circuit' if batt else 'source and cable'} {rs} ohm assumed"]
    return 0.1, ['source 0.1 ohm assumed']


def trace_rl(d, net, a, b):
    """R and L of the copper between two pads: straight-line distance x 1.4, narrowest track of the net."""
    if not d.board or not a or not b:
        return 0.02, 5e-9, 'no board: 20 mohm, 5 nH assumed'
    length = max(dist(a, b) * 1.4, 1.0)
    tr = [t for t in d.board.tracks if t.net == net.name and t.length > 0]
    ws = [t.width for t in tr]
    in_zone = any(z.net == net.name for z in d.board.zones)
    # width that gives the same resistance as the net's tracks laid end to end
    w = max(sum(t.length for t in tr) / sum(t.length / t.width for t in tr), 0.1) if tr else 1.0
    if in_zone and not ws:
        w = 3.0
    t = d.board.copper_um * 1e-3
    r = 1.72e-5 * length / (w * t)                                   # ohm, copper resistivity in ohm*mm
    l = 2e-10 * length * (math.log(2 * length / (w + t)) + 0.5)      # H, straight flat conductor
    return r, l, f"{length:.0f} mm (pad to pad x 1.4) of {w:.2f} mm track: {r * 1000:.0f} mohm, {l * 1e9:.0f} nH"


def build_netlist(p):
    """p: dict of parameters (see droop()).  Returns the netlist text."""
    L = [f"* boardlint droop model: {p['title']}",
         f"Vsrc src 0 DC {p['vsrc']}",
         f"Rsrc src vin {p['rsrc']:.4g}"]
    L += p['cin_lines']
    L += p['cout_lines']
    L += [
        # PI current loop: proportional gain sets crossover with the output capacitance, the
        # integrator removes the static error.  Pass current is limited by the current limit and
        # by what the dropout resistance lets through.
        f"Bint 0 int I = {p['vset']} - v(out)",
        f"Cint int 0 {1.0 / p['ki']:.4g}",
        "Rint int 0 1e9",
        f"Bpass vin out I = max(0, min(min({p['ilim']}, (v(vin) - v(out)) / {p['rdo']:.4g}), "
        f"{p['gm']:.4g} * ({p['vset']} - v(out)) + v(int)))",
        "Rleak out 0 1e6",
        f"Rtr out lmid {p['rtr']:.4g}",
        f"Ltr lmid load {p['ltr']:.4g}",
        f"Iload load 0 PWL(0 {p['i0']} {p['t0']} {p['i0']} {p['t0'] + p['tr']:.4g} {p['i1']})",
        f"Iagg vin 0 PWL(0 0 {p['t0']} 0 {p['t0'] + p['tr']:.4g} {p['iagg']})",
        f".ic v(out)={p['vset']} v(load)={p['vset']} v(vin)={p['vsrc']}",
        f".tran {p['tstep']:.3g} {p['tstop']:.3g} uic",
        ".control", "run",
        f"meas tran vpre avg v(load) from={p['t0'] * 0.8:.4g} to={p['t0'] * 0.99:.4g}",
        f"meas tran vmin min v(load) from={p['t0']:.4g} to={p['tstop']:.4g}",
        f"meas tran vend avg v(load) from={p['tstop'] * 0.95:.4g} to={p['tstop']:.4g}",
        f"meas tran vinmin min v(vin) from={p['t0']:.4g} to={p['tstop']:.4g}",
        ".endc", ".end"]
    return '\n'.join(L) + '\n'


@check('power.droop', 'simulation', doc='ngspice: regulated rails under their worst load step, at minimum and nominal input')
def droop(d):
    if not ngspice.available():
        yield F('power.droop', 'info', 'ngspice not installed: droop simulation skipped', confidence='high')
        return
    keep = (d.config.get('sim') or {}).get('keep_dir') or os.environ.get('BOARDLINT_SIM_DIR')
    for c in d.components.values():
        reg = (c.model or {}).get('regulator')
        if not reg or c.dnp or reg.get('type', 'ldo') != 'ldo' or not reg.get('vout_v'):
            continue
        pin_in = (_pins_named(c, reg.get('vin')) or [None])[0]
        pin_out = (_pins_named(c, reg.get('vout')) or [None])[0]
        if not pin_in or not pin_out or not pin_in.net or not pin_out.net:
            continue
        vin, vout = d.nets[pin_in.net], d.nets[pin_out.net]
        if vin.vmin is None:
            continue
        loads = rail_loads(d, vout)
        i_typ = sum(l[1] for l in loads) / 1000
        i_max = sum(l[2] for l in loads) / 1000
        if i_max <= 0:
            continue
        big = max(loads, key=lambda l: l[2])[0]
        big_pin = next((p for p in big.pins.values() if p.net == vout.name), None)
        need = [(float(supply_spec(p.comp, p)['vmin']), p.comp) for p in vout.pins
                if supply_spec(p.comp, p) and supply_spec(p.comp, p).get('vmin') is not None]
        vneed, who = max(need, key=lambda x: x[0]) if need else (float(reg['vout_v']) * 0.9, None)
        # everything else hanging off the regulator's input rail (LED strings and the like)
        _, agg_ma, agg_parts = total_load(d, vin, {vout.name}, through_regs=False)
        agg_ma -= sum(l[2] for l in rail_loads(d, vin) if l[0] is c)
        rsrc, rpath = source_path(d, vin)
        rtr, ltr, trdesc = trace_rl(d, vout, pin_out.pos, big_pin.pos if big_pin else None)
        cin, cout = [], []
        _cap_lines(d, vin, 'i', 'vin', cin)
        ncout = _cap_lines(d, vout, 'o', 'out', cout, split=(pin_out.pos, big_pin.pos if big_pin else None, 'load'))
        if not ncout:
            continue
        ctot = sum(effective_c(k, vout.vmax)[0] for k, _ in caps_to_ground(d, vout.name))
        bw = float(reg.get('bw_khz', 50)) * 1e3
        gm = 2 * math.pi * bw * ctot
        at = float(reg.get('dropout_at_ma') or reg.get('i_max_ma') or 100) / 1000
        rdo = float(reg.get('dropout_mv', 300)) / 1000 / at
        base = dict(vset=float(reg['vout_v']), rsrc=rsrc, cin_lines=cin, cout_lines=cout, gm=gm, ki=gm * 2 * math.pi * bw / 10,
                    ilim=float(reg.get('i_limit_ma') or 1.3 * float(reg.get('i_max_ma', 1000))) / 1000, rdo=rdo,
                    rtr=rtr, ltr=ltr, i0=max(i_typ, 1e-4), i1=i_max, t0=2e-3, tr=float((d.config.get('sim') or {}).get('load_tr_us', 10)) * 1e-6,
                    tstep=2e-7, tstop=6e-3)
        results = []
        for label, vsrc, iagg in (('nominal input, this rail only', (vin.vmin + vin.vmax) / 2, 0.0),
                                  ('minimum input, this rail only', vin.vmin, 0.0),
                                  ('nominal input, everything switching', (vin.vmin + vin.vmax) / 2, agg_ma / 1000),
                                  ('minimum input, everything switching', vin.vmin, agg_ma / 1000)):
            if iagg == 0.0 and agg_ma <= 0 and 'everything' in label:
                continue
            if 'everything' in label and agg_ma <= 0:
                continue
            p = dict(base, vsrc=vsrc, iagg=iagg, title=f"{c.ref} {vout.name}, {label}")
            nl = build_netlist(p)
            meas, raw = ngspice.run(nl, keep_as=os.path.join(keep, f"droop_{c.ref}_{len(results)}.cir") if keep else None)
            if 'vmin' not in meas:
                d.notes.append(f"droop simulation of {c.ref} did not converge ({label})")
                continue
            results.append((label, vsrc, iagg, meas))
        if not results:
            continue
        ev = {'load_step': f"{i_typ * 1000:.0f} -> {i_max * 1000:.0f} mA in {base['tr'] * 1e6:g} us ({_summ([(l[0].ref, l[2]) for l in loads])})",
              'source_path': f"{rsrc:.2f} ohm: " + '; '.join(rpath),
              'output_caps_effective': fmt_c(round(ctot, 9)), 'copper': trdesc,
              'regulator_model': f"PI loop, {bw / 1e3:g} kHz crossover{'' if reg.get('bw_khz') else ' (assumed)'}, "
                                 f"dropout {rdo:.2f} ohm, limit {base['ilim'] * 1000:.0f} mA"}
        if agg_ma > 0:
            ev['other_loads_on_input'] = f"{agg_ma:.0f} mA ({_summ(agg_parts)})"
        for label, vsrc, iagg, m in results:
            ev[label] = (f"Vin {vsrc:.2f} V: {vout.name} min {m['vmin']:.3f} V, settles {m.get('vend', 0):.3f} V; "
                         f"{vin.name} min {m.get('vinmin', 0):.3f} V")
        worst = min(results, key=lambda r: r[3]['vmin'])
        nominal_alone = results[0][3]['vmin']
        fails = [r for r in results if r[3]['vmin'] < vneed]
        basis = (model_basis(c, 'dropout, current limit') + '; simplified ngspice model, see docs/simulation.md. '
                 'Source resistance and loop bandwidth are assumptions unless set in boardlint.yaml')
        if not fails:
            yield F('power.droop', 'info', f"{vout.name} holds {worst[3]['vmin']:.2f} V or better through its worst load step",
                    f"{c.desc}. {who.desc + ' needs ' + format(vneed, 'g') + ' V. ' if who else ''}"
                    f"Simulated in {len(results)} corner(s).", refs=[c.ref], nets=[vout.name, vin.name],
                    evidence=ev, basis=basis, confidence='low')
        else:
            only_combined = all('everything' in r[0] for r in fails)
            only_min = all('minimum' in r[0] for r in fails)
            cond = ' and '.join(x for x in (f"{vin.name} is near its minimum" if only_min else '',
                                            'the other loads on its input switch on at the same moment' if only_combined else '') if x)
            yield F('power.droop', 'warning' if only_min else 'error',
                    f"{vout.name} sags to {worst[3]['vmin']:.2f} V under load" + (f" when {cond}" if cond else ''),
                    f"{who.desc if who else 'The load'} needs {vneed:g} V. Worst corner: {worst[0]} "
                    f"(source at {worst[1]:.2f} V): {vout.name} dips to {worst[3]['vmin']:.2f} V and settles at "
                    f"{worst[3].get('vend', 0):.2f} V, with {vin.name} pulled down to {worst[3].get('vinmin', 0):.2f} V "
                    f"across {rsrc:.2f} ohm of source path. At nominal input on its own the rail holds {nominal_alone:.2f} V.",
                    refs=[c.ref] + ([who.ref] if who else []), nets=[vout.name, vin.name], evidence=ev, basis=basis,
                    confidence='low')
