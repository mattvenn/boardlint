"""Digital bus simulation (Icarus Verilog): the board's own wiring with behavioural part models."""
from __future__ import annotations
import os
from collections import defaultdict
from . import check, F
from .buses import i2c_buses, i2c_address, led_chains, _compress
from .common import can_drive, supply_v, io
from ..classify import signal_group, group_pins
from ..sim import busgen


def _keep(d, name):
    k = (d.config.get('sim') or {}).get('keep_dir') or os.environ.get('BOARDLINT_SIM_DIR')
    return os.path.join(k, name) if k else None


@check('sim.i2c', 'simulation', doc='Icarus Verilog: scan each I2C bus as wired and read every modelled target\'s ID register')
def sim_i2c(d):
    if not busgen.available():
        yield F('sim.i2c', 'info', 'iverilog not installed: I2C simulation skipped', confidence='high')
        return
    buses, _ = i2c_buses(d)
    merged = {}
    def _score(b):       # majority orientation first; on a tie, the one whose net names agree
        named = sum('SDA' in n.upper() for n in b['sda']) + sum('SCL' in n.upper() or 'SCK' in n.upper() for n in b['scl'])
        return -(10 * len(b['devices']) + named)
    for bus in sorted(buses, key=_score):
        key = frozenset((bus['sda'], bus['scl']))
        if key in merged:                 # same two nets the other way round: a device with SDA/SCL crossed
            merged[key]['devices'].update(bus['devices'])
        else:
            merged[key] = {'sda': bus['sda'], 'scl': bus['scl'], 'devices': dict(bus['devices'])}
    for n, bus in enumerate(merged.values()):
        tb, targets = busgen.i2c_testbench(d, bus, lambda c: i2c_address(d, c)[0])
        if not tb:
            continue
        name = f"{sorted(bus['sda'])[0]} / {sorted(bus['scl'])[0]}"
        res, raw = busgen._run(tb, _keep(d, f"i2c_{n}.v"))
        if res is None:
            d.notes.append(f"I2C testbench for {name} did not compile: {raw[:300]}")
            continue
        idle = next((r for r in res if r[1] == 'idle'), None)
        acks = {int(r[2]): int(r[3]) for r in res if r[1] == 'ack'}
        ids = defaultdict(list)
        for r in res:
            if r[1] == 'id':
                ids[r[2]].append((int(r[3]), r[4], int(r[5])))
        refs = [t[0] for t in targets]
        basis = ('behavioural Verilog models (boardlint/sim/verilog/i2c_target.v) wired from the netlist; '
                 'ID registers from the part models')
        if idle and (idle[2] != 'scl=1' or idle[3] != 'sda=1'):
            yield F('sim.i2c', 'error', f"I2C bus {name} does not idle high in simulation ({idle[2]}, {idle[3]})",
                    "With every device released, a line that is not 1 has no pull-up (z) or is held low (0). "
                    "No transfer can start.", refs=refs, nets=bus['sda'] | bus['scl'], basis=basis, confidence='high')
        for a, nsel in sorted(acks.items()):
            if nsel > 1:
                yield F('sim.i2c', 'error', f"{nsel} devices acknowledge address 0x{a:02X} on {name} in simulation",
                        "They answer the same transfers and corrupt each other's data.", refs=refs,
                        nets=bus['sda'], basis=basis, confidence='high')
        ok = []
        for ref, u, reg, val in targets:
            got = ids.get(ref, [])
            good = [g for g in got if g[1].isdigit() and int(g[1], 2) == g[2]]
            static = i2c_address(d, d.components[ref])[0]
            if not got:
                yield F('sim.i2c', 'error', f"{ref} never answers on {name} in simulation",
                        f"{d.components[ref].desc} did not acknowledge any address from 0x08 to 0x77. Its supply, "
                        f"ground, address strap or mode pins are not wired so that it can respond, or the bus "
                        f"cannot signal.", refs=[ref], nets=bus['sda'] | bus['scl'], basis=basis, confidence='high')
            elif not good:
                yield F('sim.i2c', 'error', f"{ref} acknowledges at 0x{got[0][0]:02X} but its ID register reads back wrong",
                        f"Register 0x{reg:02X} read {got[0][1]} (binary), expected 0x{val:02X}. Another device is "
                        f"driving the bus at the same time, or the data line is not shared correctly.",
                        refs=[ref], nets=bus['sda'], basis=basis, confidence='high')
            else:
                ok.append(f"{ref} at 0x{good[0][0]:02X} (register 0x{reg:02X} = 0x{val:02X})")
                if static is not None and static != good[0][0]:
                    yield F('sim.i2c', 'warning', f"{ref}: simulation finds it at 0x{good[0][0]:02X}, the strap analysis says 0x{static:02X}",
                            "The two methods disagree: check the part model.", refs=[ref], basis=basis, confidence='medium')
        if ok:
            yield F('sim.i2c', 'info', f"I2C bus {name}: {len(ok)} of {len(targets)} modelled target(s) answer in simulation",
                    '; '.join(ok) + f". Full address scan found {len(acks)} responder(s).", refs=refs,
                    nets=bus['sda'] | bus['scl'], basis=basis, confidence='high')


@check('sim.led_chain', 'simulation', doc='Icarus Verilog: clock a frame down every addressable-LED chain and see which LEDs latch data')
def sim_led(d):
    leds = led_chains(d)
    if not leds:
        return
    if not busgen.available():
        yield F('sim.led_chain', 'info', 'iverilog not installed: LED chain simulation skipped', confidence='high')
        return
    heads, level_ok = defaultdict(list), {}
    for ref, (din, dout) in leds.items():
        if not din.net:
            continue
        nets, _ = signal_group(d, din.net)
        pins = group_pins(d, nets)
        if any(p.role == 'led_dout' for p in pins):
            continue
        drv = [p for p in pins if p.role not in ('led_din', 'led_dout') and (can_drive(p) or p.comp.kind == 'CONN')]
        if drv:
            heads[din.net].append(ref)
            c = d.components[ref]
            m = (c.model or {}).get('serial_led') or {}
            lv, dv = supply_v(d, c), supply_v(d, drv[0].comp) if drv[0].comp.kind != 'CONN' else None
            if lv and dv:
                vih = m.get('vih') or lv[1] * float(m.get('vih_frac', 0.7))
                level_ok[ref] = (dv[0] - 0.1) >= vih
    if not heads:
        return
    tb = busgen.led_testbench(d, leds, heads, level_ok)
    res, raw = busgen._run(tb, _keep(d, 'led_chain.v'))
    if res is None:
        d.notes.append(f"LED testbench did not compile: {raw[:300]}")
        return
    got = {r[2]: (r[3] == '1', int(r[4]) if r[4].isdigit() else -1) for r in res if r[1] == 'led'}
    dark = sorted(r for r, (g, _) in got.items() if not g)
    basis = 'behavioural Verilog model (boardlint/sim/verilog/serial_led.v) wired from the netlist'
    if dark:
        yield F('sim.led_chain', 'error', f"{len(dark)} of {len(got)} addressable LED(s) receive no data in simulation",
                f"{_compress(dark)} never latch a colour when a frame is clocked into every chain head. Their data "
                f"input is not reachable from a driver, the chain is broken or reversed before them, they have no "
                f"supply or ground, or the logic level at the first input is too low.", refs=dark[:10], basis=basis,
                confidence='high')
    lit = {r: pos for r, (g, pos) in got.items() if g}
    if lit:
        # group by chain: follow each LED back to the head it hangs off
        feeder = {}
        for ref, (din, _) in leds.items():
            if din.net:
                nets, _t = signal_group(d, din.net)
                up = [p.comp.ref for p in group_pins(d, nets) if p.role == 'led_dout' and p.comp.ref != ref]
                feeder[ref] = up[0] if up else None
        def head(r, n=0):
            return r if feeder.get(r) is None or n > len(leds) else head(feeder[r], n + 1)
        chains = defaultdict(list)
        for r, pos in lit.items():
            chains[head(r)].append((pos, r))
        yield F('sim.led_chain', 'info', f"{len(lit)} of {len(got)} addressable LED(s) latch data in simulation",
                'Position along each data line, as simulated: ' +
                '; '.join(f"from {h}: {_compress([r for _, r in sorted(ch)])}" for h, ch in sorted(chains.items()))
                + '.', refs=sorted(chains)[:4], basis=basis, confidence='high')
