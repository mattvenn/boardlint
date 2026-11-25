"""Protocol connectivity: UART, I2C, SPI/QSPI, addressable LEDs, USB."""
from __future__ import annotations
import re
from collections import defaultdict
from . import check, F
from .common import role_groups, is_controller_pin, names, supply_v, io, can_drive, model_basis, PASSIVE_KINDS
from ..classify import pulls, fmt_r, signal_group, group_pins, pin_aliases, norm_pin_name
from ..power import supply_net_of, _pins_named


# ----------------------------------------------------------------------------- UART
@check('uart.direction', 'protocol', doc='UART TX must meet RX, never TX-TX or RX-RX')
def uart_direction(d):
    for nets, pins, _ in role_groups(d, ('uart_tx', 'uart_rx')):
        tx = [p for p in pins if p.role == 'uart_tx']
        rx = [p for p in pins if p.role == 'uart_rx']
        other = [p for p in pins if p.role not in ('uart_tx', 'uart_rx') and p.comp.kind not in PASSIVE_KINDS]
        net = sorted(nets)[0]
        if len({p.comp.ref for p in tx}) >= 2:
            yield F('uart.direction', 'error', f"UART TX wired to TX on {net}",
                    f"{names(tx)} are both transmitters and share a net" +
                    (f" (receivers on it: {names(rx)})" if rx else "; no receiver is on it") +
                    ". Two push-pull outputs fight, and neither device hears the other. Cross the pair: "
                    "each TX goes to the other part's RX.", refs=[p.comp.ref for p in tx], nets=nets,
                    basis='pin functions from the symbols / part models', confidence='high')
        elif len({p.comp.ref for p in rx}) >= 2 and not tx and not any(can_drive(p) or p.comp.kind == 'CONN' for p in other):
            yield F('uart.direction', 'error', f"UART RX wired to RX on {net}",
                    f"{names(rx)} are all receivers and nothing on the net transmits.",
                    refs=[p.comp.ref for p in rx], nets=nets, basis='pin functions from the symbols / part models',
                    confidence='high')
        elif (tx or rx) and not other and len(tx) + len(rx) == 1:
            continue
        # net named from the other end's point of view: worth one look when it leaves the board
        conns = [p for p in other if p.comp.kind == 'CONN']
        for p in tx + rx:
            want = 'RX' if p.role == 'uart_tx' else 'TX'
            mine = 'TX' if p.role == 'uart_tx' else 'RX'
            if any(re.search(rf'(^|[_/\-]){want}D?\d*($|[_/\-])', n, re.I) and not re.search(rf'(^|[_/\-]){mine}D?\d*($|[_/\-])', n, re.I)
                   for n in nets) and (conns or len(pins) > 1):
                yield F('uart.direction', 'info', f"{p.label} ({mine}) is on a net named like {want}",
                        f"Net {net} carries {p.label}. If the name is from the far end's point of view this is "
                        f"right; if it was meant from {p.comp.ref}'s, TX and RX are swapped.",
                        refs=[p.comp.ref] + [c.comp.ref for c in conns], nets=nets,
                        basis='net name against pin function (heuristic)', confidence='low')


# ----------------------------------------------------------------------------- I2C
def i2c_line(p):
    """'i2c_sda' / 'i2c_scl' for a pin with that role, or for a free MCU pin on a net named SDA / SCL."""
    if p.role in ('i2c_sda', 'i2c_scl'):
        return p.role
    if p.role == 'gpio' and p.net:
        s = _signal_id(p.net)
        if s and s[1] in ('SDA', 'SCL'):
            return 'i2c_' + s[1].lower()
    return ''


def i2c_buses(d):
    """[{sda: nets, scl: nets, devices: {ref: (sda pin, scl pin)}}] found from pin roles and,
    for freely assignable MCU pins, from net names."""
    grp = {}
    for c in d.components.values():
        if c.dnp:
            continue
        for p in c.pins.values():
            if i2c_line(p) and p.net and p.net not in grp:
                nets, _ = signal_group(d, p.net)
                entry = (frozenset(nets), group_pins(d, nets))
                for n in nets:
                    grp[n] = entry
    buses = {}
    for c in d.components.values():
        if c.dnp:
            continue
        sda = [p for p in c.pins.values() if i2c_line(p) == 'i2c_sda' and p.net]
        scl = [p for p in c.pins.values() if i2c_line(p) == 'i2c_scl' and p.net]
        for s in sda:
            for k in scl:
                key = (grp[s.net][0], grp[k.net][0])
                b = buses.setdefault(key, {'sda': key[0], 'scl': key[1], 'devices': {}})
                b['devices'][c.ref] = (s, k)
    return list(buses.values()), grp


def i2c_address(d, c):
    """7-bit address set by the straps, or (None, reason)."""
    m = (c.model or {}).get('i2c') or {}
    sda = next((p for p in c.pins.values() if p.role == 'i2c_sda'), None)
    scl = next((p for p in c.pins.values() if p.role == 'i2c_scl'), None)
    ap = m.get('address_pin')
    if ap:
        pin = (_pins_named(c, ap.get('pin')) or [None])[0]
        if pin is None or not pin.net:
            return None, f"{ap.get('pin')} is not connected"
        n = d.nets[pin.net]
        key = None
        if n.is_ground:
            key = ('GND', 'VSS', 'LOW', '0')
        elif sda is not None and pin.net == sda.net:
            key = ('SDA',)
        elif scl is not None and pin.net == scl.net:
            key = ('SCL',)
        elif n.is_power:
            key = ('VDD', 'VCC', 'HIGH', '1')
        for k, v in (ap.get('map') or {}).items():
            if key and str(k).upper() in key:
                return int(v), f"{pin.label} on {pin.net}"
        return None, f"cannot tell what {pin.label} on {pin.net} selects"
    ab = m.get('address_bits')
    if ab:
        addr = int(ab.get('base', 0))
        why = []
        for b in ab.get('pins') or []:
            pin = (_pins_named(c, b.get('pin')) or [None])[0]
            lvl = b.get('default')
            if pin is not None and pin.net:
                n = d.nets[pin.net]
                ups, downs = pulls(d, pin.net)
                if n.is_ground or (downs and not ups):
                    lvl = 0
                elif n.is_power or (ups and not downs):
                    lvl = 1
                why.append(f"{pin.label}={'?' if lvl is None else lvl}")
            if lvl is None:
                return None, f"level of {b.get('pin')} unknown"
            addr = (addr & ~(1 << int(b.get('bit', 0)))) | (int(lvl) << int(b.get('bit', 0)))
        return addr, ', '.join(why)
    al = m.get('addresses')
    if al and len(al) == 1:
        return int(al[0]), 'fixed'
    return None, 'no address in the part model' if c.model else 'no part model'


@check('i2c.bus', 'protocol', doc='I2C: SDA/SCL not swapped, pull-ups present and sized, levels compatible, addresses unique')
def i2c_bus(d):
    buses, grp = i2c_buses(d)
    done = set()
    for nets, pins in {id(v): v for v in grp.values()}.values():
        sda = [p for p in pins if p.role == 'i2c_sda']
        scl = [p for p in pins if p.role == 'i2c_scl']
        net = sorted(nets)[0]
        if sda and scl:
            minority, majority = (sda, scl) if len(sda) <= len(scl) else (scl, sda)
            yield F('i2c.bus', 'error', f"I2C SDA and SCL are crossed on {net}",
                    f"{names(minority)} share a net with {names(majority)}. One of them is on the wrong line.",
                    refs=sorted({p.comp.ref for p in sda + scl}), nets=nets,
                    basis='pin functions from the symbols / part models', confidence='high')
    for b in buses:
        for line in ('sda', 'scl'):
            nets = b[line]
            if nets in done:
                continue
            done.add(nets)
            pins = grp[sorted(nets)[0]][1]
            net = sorted(nets)[0]
            devs = sorted({p.comp.ref for p in pins if i2c_line(p)})
            ups, downs = pulls(d, net)
            has_ctrl = any(is_controller_pin(p) for p in pins)
            has_conn = any(p.comp.kind == 'CONN' for p in pins)
            if not has_ctrl:
                yield F('i2c.bus', 'warning', f"No controller on I2C {line.upper()} net {net}",
                        f"Only target devices are on it ({', '.join(devs)}): no MCU pin or connector.",
                        refs=devs, nets=nets, confidence='medium')
            if downs:
                yield F('i2c.bus', 'error', f"Pull-down on I2C net {net}",
                        f"{', '.join(c.desc for c, _ in downs)} pulls the open-drain line low.",
                        refs=[c.ref for c, _ in downs], nets=nets, confidence='high')
            if not ups:
                off_board_host = has_conn and not any(is_controller_pin(p) and p.comp.kind != 'CONN' for p in pins)
                yield F('i2c.bus', 'warning' if has_conn else 'error', f"No pull-up on I2C {line.upper()} net {net}",
                        f"Devices {', '.join(devs)} are open-drain; nothing on the board pulls the line high."
                        + (" The bus controller is off this board, through the connector: pull-ups normally sit "
                           "with the controller, so confirm the host provides them" if off_board_host else
                           " The bus leaves the board through a connector, so whatever plugs in may bring them: this "
                           "board cannot talk I2C on its own, and two boards without pull-ups cannot talk to each other" if has_conn else "")
                        + (". " if has_conn else " ") + "An MCU's internal pull-up (tens of kilohms) is too weak for 400 kHz.",
                        refs=devs, nets=nets, basis='I2C specification (UM10204) section 3.1.1', confidence='high')
                continue
            rails = {r.name: r for _, r in ups}
            rpar = 1.0 / sum(1.0 / max(c.num, 1e-3) for c, _ in ups)
            rail = max(rails.values(), key=lambda r: r.vmax or 0)
            ev = {'pullups': {c.ref: fmt_r(c.num) for c, _ in ups}, 'effective': fmt_r(round(rpar, 1)),
                  'rail': rail.name}
            if len(rails) > 1:
                yield F('i2c.bus', 'warning', f"I2C net {net} is pulled up to more than one rail",
                        f"Pull-ups go to {', '.join(sorted(rails))}: the rails are joined through the resistors.",
                        refs=[c.ref for c, _ in ups], nets=nets, evidence=ev, confidence='high')
            if rail.vmax is not None:
                rmin = (rail.vmax - 0.4) / 0.003
                # bus capacitance: 10 pF per device pin, plus copper if there is a board
                cb = 10e-12 * len([p for p in pins if p.comp.kind not in PASSIVE_KINDS]) + _copper_pf(d, nets) * 1e-12
                tr_board = 0.8473 * rpar * cb
                if has_conn:
                    cb += 50e-12        # allowance for a cable and one external module
                tr = 0.8473 * rpar * cb
                ev.update({'r_min_3mA': fmt_r(round(rmin)), 'bus_c_est_pF': round(cb * 1e12),
                           't_rise_ns': round(tr * 1e9)})
                if rpar < rmin * 0.98:
                    yield F('i2c.bus', 'error', f"I2C pull-up on {net} is too strong ({fmt_r(round(rpar))})",
                            f"Sink current at {rail.vmax:g} V is {(rail.vmax - 0.4) / rpar * 1000:.1f} mA; standard and "
                            f"fast-mode devices are only guaranteed to sink 3 mA (minimum {fmt_r(round(rmin))}).",
                            refs=[c.ref for c, _ in ups], nets=nets, evidence=ev,
                            basis='I2C specification (UM10204) table 10: VOL at 3 mA', confidence='high')
                elif tr > 1000e-9:
                    yield F('i2c.bus', 'error', f"I2C pull-up on {net} is too weak ({fmt_r(round(rpar))})",
                            f"Estimated rise time {tr * 1e9:.0f} ns with about {cb * 1e12:.0f} pF exceeds the "
                            f"1000 ns limit of 100 kHz mode.", refs=[c.ref for c, _ in ups], nets=nets, evidence=ev,
                            basis='I2C specification (UM10204) table 11: tr; bus capacitance is an estimate',
                            confidence='medium')
                elif tr > 300e-9:
                    yield F('i2c.bus', 'warning' if tr_board > 300e-9 else 'info',
                            f"I2C pull-up on {net} ({fmt_r(round(rpar))}) is too weak for 400 kHz"
                            + ('' if tr_board > 300e-9 else ' once a cable and module are plugged in'),
                            f"Estimated rise time {tr * 1e9:.0f} ns with about {cb * 1e12:.0f} pF"
                            + (f" (board alone: {tr_board * 1e9:.0f} ns; 50 pF allowed for the connector)" if has_conn else '')
                            + ": fine at 100 kHz (limit 1000 ns), over the 300 ns limit of fast mode.",
                            refs=[c.ref for c, _ in ups], nets=nets, evidence=ev,
                            basis='I2C specification (UM10204) table 11: tr; bus capacitance is an estimate',
                            confidence='medium')
                # level compatibility of every device on the line
                for p in pins:
                    if p.comp.kind in PASSIVE_KINDS or p.comp.kind == 'CONN':
                        continue
                    sv = supply_v(d, p.comp)
                    if not sv:
                        continue
                    lim = io(p.comp, p, 'abs_max')
                    if io(p.comp, p, 'tolerant_5v'):
                        lim = max(lim or 0, 5.5)
                    if lim is None:
                        lim = sv[1] + float(io(p.comp, p, 'abs_max_over_supply', 0.3))
                    if rail.vmax > lim + 1e-6:
                        yield F('i2c.bus', 'error', f"I2C pull-up rail {rail.name} is above what {p.label} tolerates",
                                f"The line idles at up to {rail.vmax:g} V; {p.comp.desc} runs from {sv[2]} "
                                f"({sv[1]:g} V max) and its pin limit is {lim:g} V.",
                                refs=[p.comp.ref] + [c.ref for c, _ in ups], nets=nets,
                                basis=model_basis(p.comp) if p.comp.model else 'supply + 0.3 V rule of thumb (no part model)',
                                confidence='high' if p.comp.model else 'medium')
            if has_conn and len(ups) >= 1:
                yield F('i2c.bus', 'info', f"I2C net {net} leaves the board with {fmt_r(round(rpar))} already fitted",
                        "Breakout modules usually carry their own pull-ups (2.2k to 10k each); every one plugged in "
                        "lowers the total. Budget for the 3 mA limit.", nets=nets, evidence=ev, confidence='medium')
        # every device needs both lines on the same bus
    by_dev = defaultdict(list)
    for b in buses:
        for ref in b['devices']:
            by_dev[ref].append(b)
    for b in buses:
        addrs = defaultdict(list)
        unknown = []
        for ref in b['devices']:
            c = d.components[ref]
            if any(is_controller_pin(p) for p in b['devices'][ref]) or (c.model or {}).get('class') == 'mcu':
                continue
            a, why = i2c_address(d, c)
            if a is None:
                unknown.append((c, why))
            else:
                addrs[a].append((c, why))
        for a, lst in addrs.items():
            if len(lst) > 1:
                yield F('i2c.bus', 'error', f"I2C address clash at 0x{a:02X}",
                        '; '.join(f"{c.desc} ({why})" for c, why in lst) + f" all answer on bus {sorted(b['sda'])[0]}.",
                        refs=[c.ref for c, _ in lst], nets=b['sda'], basis='address straps in the part models',
                        confidence='high')
        if addrs or unknown:
            yield F('i2c.bus', 'info', f"I2C bus {sorted(b['sda'])[0]} / {sorted(b['scl'])[0]} address map",
                    '; '.join([f"0x{a:02X} {c.ref} {c.value} ({why})" for a, l in sorted(addrs.items()) for c, why in l] +
                              [f"unknown: {c.ref} {c.value} ({why})" for c, why in unknown]),
                    refs=sorted(b['devices']), nets=b['sda'] | b['scl'],
                    confidence='high' if not unknown else 'medium')


def _copper_pf(d, nets):
    """Track capacitance of a bus: from the stack-up where the tracks run over a plane, a small
    figure per millimetre where they do not.  20 pF when there is no board."""
    if not d.board:
        return 20.0
    from .. import tline
    s = tline.net_summary(d, set(nets))
    return s['c_pf'] if s else 0.0


# ----------------------------------------------------------------------------- SPI / QSPI
@check('spi.bus', 'protocol', doc='SPI: data directions match, every peripheral has a clock, a driven chip select of its own')
def spi_bus(d):
    def in_spi_mode(c):
        cs = [p for p in c.pins.values() if p.role == 'spi_cs']
        for p in cs:
            n = d.net_of(p)
            if n is not None and (n.is_power or n.is_ground):
                return False          # strapped: the part is not being used over SPI
        return True
    active = lambda pins: [p for p in pins if p.comp.kind not in PASSIVE_KINDS and in_spi_mode(p.comp)]
    cs_users = defaultdict(list)
    sdo_net = {}
    roles = ('spi_sdi', 'spi_sdo', 'spi_sck', 'spi_cs', 'spi_mosi', 'spi_miso', 'spi_ctrl_sck', 'spi_ctrl_cs')
    for nets, pins, _ in role_groups(d, roles):
        pins = active(pins)
        net = sorted(nets)[0]
        by = defaultdict(list)
        for p in pins:
            by[p.role].append(p)
        ctrl = [p for p in pins if is_controller_pin(p) or p.role in ('spi_mosi', 'spi_miso')]
        refs = sorted({p.comp.ref for p in pins if p.role in roles})
        # MOSI / MISO name a line, so they must never meet; SDI / SDO are from the part's own side
        if by['spi_mosi'] and by['spi_miso']:
            yield F('spi.bus', 'error', f"SPI MOSI and MISO are swapped on {net}",
                    f"{names(by['spi_mosi'])} and {names(by['spi_miso'])} share a net. MOSI goes to MOSI and MISO to "
                    f"MISO: the names are the same at both ends.", refs=refs, nets=nets, basis='pin functions',
                    confidence='high')
        if by['spi_mosi'] and by['spi_sdo'] and not by['spi_sdi']:
            yield F('spi.bus', 'error', f"SPI data lines are swapped on {net}",
                    f"{names(by['spi_sdo'])} is a data output and sits on the controller-out line with "
                    f"{names(by['spi_mosi'])}.", refs=refs, nets=nets, basis='pin functions', confidence='high')
        if by['spi_miso'] and by['spi_sdi'] and not by['spi_sdo']:
            yield F('spi.bus', 'error', f"SPI data lines are swapped on {net}",
                    f"{names(by['spi_sdi'])} is a data input and sits on the controller-in line with "
                    f"{names(by['spi_miso'])}.", refs=refs, nets=nets, basis='pin functions', confidence='high')
        both_models = lambda ps: all(p.comp.model for p in ps)
        if len({p.comp.ref for p in by['spi_sdi']}) >= 2 and not by['spi_sdo'] and not ctrl:
            yield F('spi.bus', 'error', f"SPI data inputs {names(by['spi_sdi'])} meet with nothing driving them",
                    f"Net {net} joins only inputs: no controller pin and no data output.", refs=refs, nets=nets,
                    basis='pin functions', confidence='medium')
        if len({p.comp.ref for p in by['spi_sdo']}) >= 2 and not by['spi_sdi'] and not ctrl:
            yield F('spi.bus', 'error', f"SPI data outputs {names(by['spi_sdo'])} meet with nothing listening",
                    f"Net {net} joins only outputs: no controller pin and no data input.", refs=refs, nets=nets,
                    basis='pin functions', confidence='medium')
        for role, what in (('spi_sck', 'clock'), ('spi_cs', 'chip select')):
            others = [p for p in pins if p.comp.kind not in PASSIVE_KINDS and
                      (p.role != role or p.comp is not by[role][0].comp and not p.comp.model)]
            multi = all(len(pin_aliases(p.name)) > 2 for p in by[role])     # multi-function pin, SPI not in use
            if by[role] and not others and not (multi and not by[role][0].comp.model):
                yield F('spi.bus', 'error' if by[role][0].comp.model else 'warning', f"SPI {what} {names(by[role])} is not driven",
                        f"Net {net} has nothing else on it.", refs=refs, nets=nets, basis='pin functions',
                        confidence='medium')
        for p in by['spi_sdo']:
            sdo_net[p.comp.ref] = nets
        if by['spi_cs']:
            cs_users[nets] += by['spi_cs']
            ups, downs = pulls(d, net)
            if ctrl and not ups and not downs:
                yield F('spi.bus', 'info', f"Chip select {net} has no pull-up",
                        f"{names(by['spi_cs'])} floats while the MCU is in reset or booting; a 10k pull-up keeps the "
                        f"part deselected. It matters most when the bus is shared.",
                        refs=sorted({p.comp.ref for p in by['spi_cs']}), nets=nets, confidence='medium')
    for nets, pins in cs_users.items():
        comps = sorted({p.comp.ref for p in pins})
        shared = [(a, b) for i, a in enumerate(comps) for b in comps[i + 1:]
                  if sdo_net.get(a) is not None and sdo_net.get(a) == sdo_net.get(b)]
        if shared:
            yield F('spi.bus', 'error', f"Peripherals share chip select {sorted(nets)[0]} and a data-out line",
                    f"{', '.join(comps)} are selected together and will drive MISO at the same time.",
                    refs=comps, nets=nets, basis='pin functions', confidence='high')
    # QSPI data lines must keep their index end to end
    for nets, pins, _ in role_groups(d, tuple(f'qspi_io{i}' for i in range(4))):
        idx = {p.role for p in pins if p.role.startswith('qspi_io')}
        if len(idx) > 1:
            yield F('spi.bus', 'error', f"QSPI data lines crossed on {sorted(nets)[0]}",
                    f"{names([p for p in pins if p.role.startswith('qspi_io')])} are different IO numbers on one net.",
                    refs=sorted({p.comp.ref for p in pins}), nets=nets, basis='pin functions', confidence='high')


# ----------------------------------------------------------------------------- addressable LEDs
def led_chains(d):
    """Returns (leds, chains, problems).  leds: ref -> (din pin, dout pin)."""
    leds = {}
    for c in d.components.values():
        if c.dnp:
            continue
        din = [p for p in c.pins.values() if p.role == 'led_din']
        dout = [p for p in c.pins.values() if p.role == 'led_dout']
        if din:
            leds[c.ref] = (din[0], dout[0] if dout else None)
    return leds


@check('led.chain', 'protocol', doc='Addressable LEDs: chain direction, one driver per input, logic level of the first input')
def led_chain(d):
    leds = led_chains(d)
    if not leds:
        return
    feeds = {}            # led ref -> ('led', ref) | ('pin', Pin) | None
    heads = defaultdict(list)
    for ref, (din, dout) in leds.items():
        if not din.net:
            yield F('led.chain', 'error', f"{din.label} is not connected", "The LED's data input floats.",
                    refs=[ref], confidence='high')
            continue
        nets, through = signal_group(d, din.net)
        pins = group_pins(d, nets)
        douts = [p for p in pins if p.role == 'led_dout']
        dins = [p for p in pins if p.role == 'led_din']
        drivers = [p for p in pins if p.role not in ('led_din', 'led_dout') and can_drive(p)]
        conns = [p for p in pins if p.comp.kind == 'CONN']
        if len(douts) > 1:
            yield F('led.chain', 'error', f"Two LED data outputs are shorted on {din.net}",
                    f"{names(douts)} both drive {names(dins)}.", refs=sorted({p.comp.ref for p in douts}),
                    nets=nets, basis='pin functions', confidence='high')
        if douts and drivers:
            yield F('led.chain', 'error', f"LED data net {din.net} has two drivers",
                    f"{names(douts)} (previous LED) and {names(drivers)} both drive it.",
                    refs=sorted({p.comp.ref for p in douts + drivers}), nets=nets, confidence='high')
        if douts and douts[0].comp.ref == ref:
            yield F('led.chain', 'error', f"{ref} DOUT feeds its own DIN", "", refs=[ref], nets=nets, confidence='high')
        if douts:
            feeds[ref] = ('led', douts[0].comp.ref)
        elif drivers or conns:
            feeds[ref] = ('pin', (drivers or conns)[0], through, nets)
            heads[frozenset(nets)].append(ref)
        else:
            feeds[ref] = None
            others = [p for p in dins if p.comp.ref != ref]
            yield F('led.chain', 'error', f"Nothing drives {din.label}",
                    f"Net {din.net} has no LED output, MCU pin or connector on it"
                    + (f"; it only joins other inputs ({names(others)}): DIN wired to DIN, the chain direction is "
                       f"probably reversed here" if others else "") + ".",
                    refs=[ref] + [p.comp.ref for p in others], nets=nets, basis='pin functions', confidence='high')
    # walk each chain from its head
    nxt = defaultdict(list)
    for ref, f in feeds.items():
        if f and f[0] == 'led':
            nxt[f[1]].append(ref)
    reached = set()
    for nets, hrefs in heads.items():
        chain, todo = [], list(hrefs)
        while todo:
            r = todo.pop(0)
            if r in reached:
                continue
            reached.add(r)
            chain.append(r)
            todo += nxt[r]
        _, drv, through, _ = feeds[hrefs[0]]
        first = d.components[hrefs[0]]
        m = (first.model or {}).get('serial_led') or {}
        det = f"{len(chain)} LED(s): {_compress(chain)}; driven by {drv.label}"
        det += f" through {', '.join(c.desc for c in through)}" if through else " directly"
        yield F('led.chain', 'info', f"LED chain on {sorted(nets)[0]}", det + ".", refs=chain[:1] + [drv.comp.ref],
                nets=nets, confidence='high')
        if len(hrefs) > 1:
            yield F('led.chain', 'info', f"{len(hrefs)} LED inputs share {sorted(nets)[0]}",
                    f"{', '.join(hrefs)} receive the same data and will always show the same colour.", refs=hrefs,
                    nets=nets, confidence='high')
        # logic level of the first LED
        led_sv = supply_v(d, first)
        drv_sv = supply_v(d, drv.comp) if drv.comp.kind != 'CONN' else None
        if led_sv and drv_sv:
            vih_frac = m.get('vih_frac', 0.7)
            vih_abs = m.get('vih')
            voh = drv_sv[0] * float(io(drv.comp, drv, 'voh_frac', 0.8) or 0.8)
            vih_hi = vih_abs if vih_abs else led_sv[1] * vih_frac
            vih_lo = vih_abs if vih_abs else led_sv[0] * vih_frac
            ev = {'driver_rail': f"{drv_sv[2]} {drv_sv[0]:g}-{drv_sv[1]:g} V", 'driver_voh_min': round(voh, 2),
                  'led_rail': f"{led_sv[2]} {led_sv[0]:g}-{led_sv[1]:g} V",
                  'led_vih': f"{vih_lo:.2f}-{vih_hi:.2f} V" + ('' if vih_abs else f" ({vih_frac:g} x VDD)")}
            basis = (model_basis(first, 'VIH') if first.model else 'VIH = 0.7 x VDD assumed (no part model)')
            if voh < vih_lo:
                yield F('led.chain', 'error', f"{drv.label} cannot drive {first.ref} DIN high enough",
                        f"Guaranteed output high is {voh:.2f} V; the LED needs {vih_lo:.2f} V or more even at its "
                        f"lowest supply. Add a level shifter (74AHCT1G125 or similar) or lower the first LED's supply.",
                        refs=[drv.comp.ref, first.ref], nets=nets, evidence=ev, basis=basis,
                        confidence='high' if first.model else 'medium')
            elif voh < vih_hi:
                light = drv_sv[0] - 0.1         # a CMOS output driving only a CMOS input sits near its rail
                ok_light = light >= vih_hi
                yield F('led.chain', 'info' if ok_light else 'warning',
                        f"{drv.label} to {first.ref} DIN: logic high is met in practice, not by the datasheet numbers"
                        if ok_light else f"{drv.label} to {first.ref} DIN has no logic-level margin at high LED supply",
                        f"The LED input threshold rises to {vih_hi:.2f} V when {led_sv[2]} is at {led_sv[1]:g} V. The "
                        f"driver's guaranteed output high is {voh:.2f} V, but that figure is at its rated load "
                        f"current; into a CMOS input it sits near {light:.2f} V."
                        + ("" if ok_light else " Even that is below the threshold: add a level shifter."),
                        refs=[drv.comp.ref, first.ref], nets=nets, evidence=ev, basis=basis,
                        confidence='high' if first.model else 'medium')
            else:
                yield F('led.chain', 'info', f"{first.ref} DIN logic level is met",
                        f"Output high {voh:.2f} V against a threshold of at most {vih_hi:.2f} V.",
                        refs=[drv.comp.ref, first.ref], nets=nets, evidence=ev, basis=basis, confidence='high')
        if not through and drv.comp.kind != 'CONN':
            yield F('led.chain', 'info', f"No series resistor between {drv.label} and {first.ref} DIN",
                    "33 to 470 ohm near the driver damps ringing and protects the first LED's input.",
                    refs=[drv.comp.ref, first.ref], nets=nets, confidence='medium')
    lost = [r for r, f in feeds.items() if f and r not in reached]
    if lost:
        yield F('led.chain', 'error', f"{len(lost)} LED(s) are not reachable from any driver",
                f"{_compress(sorted(lost))} sit in a loop or behind an undriven LED.", refs=sorted(lost)[:8],
                confidence='high')


def _compress(refs):
    if len(refs) <= 6:
        return ', '.join(refs)
    return f"{refs[0]}, {refs[1]}, ... {refs[-1]}"


# ----------------------------------------------------------------------------- USB
@check('usb.wiring', 'protocol', doc='USB: D+/D- not swapped, Type-C CC resistors, both D+ / D- pad pairs joined')
def usb_wiring(d):
    for nets, pins, _ in role_groups(d, ('usb_dp', 'usb_dm')):
        _ = _ or []
        dp = [p for p in pins if p.role == 'usb_dp']
        dm = [p for p in pins if p.role == 'usb_dm']
        if dp and dm:
            via = [c for c in _ if (c.model or {}).get('internal_links')]
            yield F('usb.wiring', 'error', f"USB D+ and D- are swapped or shorted on {sorted(nets)[0]}",
                    f"{names(dp)} share a net with {names(dm)}"
                    + (f", joined through {', '.join(c.desc for c in via)} (its paired pins are one node inside "
                       f"the part: each pair belongs to one line)" if via and len(nets) > 1 else '') + ".",
                    refs=sorted({p.comp.ref for p in dp + dm} | {c.ref for c in via}),
                    nets=nets, basis='pin functions', confidence='high')
    for c in d.components.values():
        part = c.lib_id.split(':')[-1].upper()
        is_c = ((c.model or {}).get('connector') or {}).get('type') == 'usb_c_receptacle' or \
            ('USB_C' in part and 'RECEPTACLE' in part) or 'TYPE-C' in c.value.upper() or 'USB-C' in c.value.upper()
        if not is_c or c.dnp:
            continue
        cc = [p for p in c.pins.values() if norm_pin_name(p.name) in ('CC1', 'CC2')]
        ccnets = {p.net for p in cc if p.net}
        has_ctrl = any(q.comp.kind == 'IC' for n in ccnets for q in d.nets[n].pins)
        if len(cc) == 2 and not has_ctrl:
            if len(ccnets) == 1:
                yield F('usb.wiring', 'error', f"{c.ref}: CC1 and CC2 are tied together",
                        "With one shared pull-down, an e-marked cable's Ra (about 1k) on the other CC pin parallels "
                        "it and the source no longer sees a sink: no VBUS. Each CC pin needs its own 5.1k.",
                        refs=[c.ref], nets=ccnets, basis='USB Type-C specification, sink Rd termination',
                        confidence='high')
            for p in cc:
                if not p.net:
                    yield F('usb.wiring', 'error', f"{p.label} is not connected",
                            "A Type-C source only turns VBUS on when it sees 5.1k to ground on CC. C-to-C cables "
                            "will not power the board in one or both orientations.", refs=[c.ref],
                            basis='USB Type-C specification, sink Rd termination', confidence='high')
                    continue
                ups, downs = pulls(d, p.net)
                vals = [r.num for r, _ in downs]
                if not downs:
                    yield F('usb.wiring', 'error', f"{p.label} has no pull-down",
                            "A Type-C source only turns VBUS on when it sees Rd = 5.1k to ground on CC.",
                            refs=[c.ref], nets=[p.net], basis='USB Type-C specification, sink Rd termination',
                            confidence='high')
                elif not any(4590 <= v <= 5610 for v in vals):
                    yield F('usb.wiring', 'error', f"{p.label} pull-down is {fmt_r(vals[0])}, not 5.1k",
                            "Rd must be 5.1k (10 % allowed with a 5 % source); other values are read as a "
                            "different device type or not at all.", refs=[c.ref] + [r.ref for r, _ in downs],
                            nets=[p.net], basis='USB Type-C specification, sink Rd termination', confidence='high')
        for nm in ('D+', 'D-'):
            ps = [p for p in c.pins.values() if p.name.upper() in (nm, 'D' + ('P' if nm == 'D+' else 'N'))]
            if len(ps) == 2 and len({p.net for p in ps}) == 2:
                yield F('usb.wiring', 'warning' if all(p.net for p in ps) else 'error',
                        f"{c.ref}: the two {nm} pins ({names(ps)}) are not joined",
                        "USB 2.0 data then works in only one plug orientation.", refs=[c.ref], confidence='high')
        vb = [p for p in c.pins.values() if norm_pin_name(p.name) == 'VBUS' and p.net]
        if vb:
            from ..classify import caps_to_ground, fmt_c
            tot = sum(k.num or 0 for k, _ in caps_to_ground(d, vb[0].net))
            if tot > 10.5e-6:
                yield F('usb.wiring', 'warning', f"{fmt_c(tot)} directly on {vb[0].net}",
                        "USB limits the capacitance a device presents at plug-in to 10 uF (inrush). Put bulk "
                        "capacitance behind a soft-start switch or the regulator.", refs=[c.ref], nets=[vb[0].net],
                        basis='USB 2.0 specification section 7.2.4.1', confidence='high')


# ----------------------------------------------------------------------------- MCU fixed functions
_NET_ROLE = [('i2c_sda', re.compile(r'(^|[_/\-.])SDA\d*($|[_/\-.])', re.I)), ('i2c_scl', re.compile(r'(^|[_/\-.])SCL\d*($|[_/\-.])', re.I))]
_FAMILY = {'i2c_sda': 'i2c', 'i2c_scl': 'i2c', 'uart_tx': 'uart', 'uart_rx': 'uart', 'spi_mosi': 'spi',
           'spi_miso': 'spi', 'spi_ctrl_sck': 'spi', 'spi_ctrl_cs': 'spi'}
_WANT = {'i2c_sda': 'i2c_sda', 'i2c_scl': 'i2c_scl', 'uart_rx': 'uart_tx', 'uart_tx': 'uart_rx',
         'spi_sdi': 'spi_mosi', 'spi_sdo': 'spi_miso', 'spi_mosi': 'spi_mosi', 'spi_miso': 'spi_miso',
         'spi_sck': 'spi_ctrl_sck'}
_NICE = {'i2c_sda': 'I2C SDA', 'i2c_scl': 'I2C SCL', 'uart_tx': 'UART TX', 'uart_rx': 'UART RX',
         'spi_mosi': 'SPI TX (MOSI)', 'spi_miso': 'SPI RX (MISO)', 'spi_ctrl_sck': 'SPI SCK', 'spi_ctrl_cs': 'SPI CSn'}


@check('mcu.alt_function', 'protocol', doc='MCU pins with fixed peripheral functions are used for a function they have')
def alt_function(d):
    for c in d.components.values():
        if c.dnp or not c.model:
            continue
        for p in c.pins.values():
            alt = p.spec.get('alt')
            if not alt or not p.net:
                continue
            nets, _ = signal_group(d, p.net)
            wants = {}
            for q in group_pins(d, nets):
                if q.comp is not c and q.role in _WANT:
                    wants[_WANT[q.role]] = f"{q.label} is on the net"
            if not wants:
                for role, rx in _NET_ROLE:
                    if any(rx.search(n) for n in nets):
                        wants[role] = f"the net is called {sorted(nets)[0]}"
            for want, why in wants.items():
                if want in alt:
                    continue
                fam = _FAMILY.get(want)
                same = [a for a in alt if _FAMILY.get(a) == fam]
                if same:
                    yield F('mcu.alt_function', 'error',
                            f"{p.label} is wired as {_NICE.get(want, want)} but can only be {_NICE.get(same[0], same[0])}",
                            f"{c.desc}: {why}. On this MCU the pin's {fam.upper()} function is "
                            f"{_NICE.get(same[0], same[0])}; the two lines are swapped at the MCU, or the wrong pin "
                            f"was chosen. Only a software (bit-banged) bus would work here.",
                            refs=[c.ref], nets=nets, basis=model_basis(c, 'pin function table'), confidence='medium')


# ----------------------------------------------------------------------------- names that contradict
# Signals that are easy to cross.  TX / RX are left out on purpose: a net is often named from the
# far end's point of view, so "TX pin on a net called RX" is normal.
_CONFUSABLE = [
    {'LRCLK': 'LRCLK', 'LRCK': 'LRCLK', 'WCLK': 'LRCLK', 'WS': 'LRCLK', 'FS': 'LRCLK', 'BCLK': 'BCLK', 'BCK': 'BCLK',
     'SCLK': 'BCLK', 'MCLK': 'MCLK', 'SCKI': 'MCLK'},
    {'SDA': 'SDA', 'SCL': 'SCL'},
    {'MOSI': 'MOSI', 'COPI': 'MOSI', 'MISO': 'MISO', 'CIPO': 'MISO'},
    {'D+': 'D+', 'DP': 'D+', 'USB_DP': 'D+', 'USBDP': 'D+', 'D-': 'D-', 'DM': 'D-', 'DN': 'D-', 'USB_DM': 'D-', 'USBDM': 'D-'},
    {'CANH': 'CANH', 'CAN_H': 'CANH', 'CANL': 'CANL', 'CAN_L': 'CANL'},
    {'SWDIO': 'SWDIO', 'SWCLK': 'SWCLK', 'SWDCLK': 'SWCLK'},
    {'TDI': 'TDI', 'TDO': 'TDO', 'TCK': 'TCK', 'TMS': 'TMS'},
]


def _signal_id(name):
    """(group index, canonical signal) if a pin or net name is one of the confusable signals."""
    n = (name or '').split('/')[-1].upper().strip()
    n = re.sub(r'^(I2C|I2S|SPI|USB|CAN|JTAG|SAI)\d*_', '', n)
    n = re.sub(r'\d+$', '', n) if not n.endswith(('D+', 'D-')) else n
    for i, grp in enumerate(_CONFUSABLE):
        if n in grp:
            return i, grp[n]
    return None


@check('net.name_mismatch', 'protocol', doc='A pin named for one signal sits on a net named for its partner (LRCLK on BCLK, SDA on SCL, MOSI on MISO)')
def name_mismatch(d):
    seen = set()
    for c in d.components.values():
        if c.dnp or c.kind in PASSIVE_KINDS or c.kind in ('CONN', 'SW'):
            continue
        for p in c.pins.values():
            if not p.net or not p.name:
                continue
            ids = [x for x in (_signal_id(a) for a in pin_aliases(p.name)) if x]
            net = _signal_id(p.net)
            if not ids or not net or len(pin_aliases(p.name)) > 2:
                continue            # multi-function pins take whatever role the net gives them
            pid = ids[0]
            if pid[0] == net[0] and pid[1] != net[1] and (c.ref, p.net) not in seen:
                seen.add((c.ref, p.net))
                yield F('net.name_mismatch', 'error', f"{p.label} is on the net called {p.net}",
                        f"{c.desc}: the pin is {pid[1]} and the net is named for {net[1]}. Either the two lines are "
                        f"crossed at this part or the net label is wrong.", refs=[c.ref], nets=[p.net],
                        basis='pin name against net name', confidence='medium')
