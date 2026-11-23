"""Do the right signals arrive at the right pins?  MCU / FPGA pin capabilities, clocks, resets, straps."""
from __future__ import annotations
import re
from collections import defaultdict
from . import check, F
from .common import can_drive, model_basis, names, supply_v, io, PASSIVE_KINDS
from ..classify import signal_group, group_pins, pulls, caps_to_ground, fmt_r, fmt_c, pin_aliases, norm_pin_name, is_analog_name

_ROLE_USE = {'i2c_sda': 'I2C SDA', 'i2c_scl': 'I2C SCL', 'uart_tx': 'UART (receives)', 'uart_rx': 'UART (transmits)',
             'led_din': 'addressable-LED data out', 'spi_sck': 'SPI clock', 'spi_sdi': 'SPI data out',
             'spi_sdo': 'SPI data in', 'spi_cs': 'SPI chip select', 'usb_dp': 'USB D+', 'usb_dm': 'USB D-',
             'irq': 'interrupt in', 'touch': 'touch electrode', 'enable': 'enable out', 'reset': 'reset out',
             'spi_mosi': 'SPI MOSI', 'spi_miso': 'SPI MISO'}
_ANALOG = re.compile(r'SENS|ADC|MON|MEAS|AIN|VREF|NTC|TEMP|VBAT|ISENSE|POT', re.I)
_DIGITAL = re.compile(r'(^|_)(DET|DETECT|PRESENT|OK|PG|PGOOD|STAT|STATUS|FAULT|FLT)($|_)', re.I)
_IRQ = re.compile(r'^(N?INT\d*|N?IRQ\d*|ALERT|DRDY|RDY|INT_?N|INTB)$', re.I)


def _programmable(c):
    return c.model and (c.model.get('class') in ('mcu', 'mcu_module', 'fpga') or c.model.get('gpio_pattern'))


def _num_set(spec):
    """'IO0 to IO21' or a list of names -> set of names."""
    if isinstance(spec, (list, tuple)):
        return {str(x) for x in spec}
    m = re.match(r'^([A-Za-z_]+)(\d+)\s+to\s+[A-Za-z_]*(\d+)$', str(spec or ''))
    if m:
        return {f"{m.group(1)}{i}" for i in range(int(m.group(2)), int(m.group(3)) + 1)}
    return set()


def pin_use(d, p):
    """(label, kind) for what a programmable pin is used for, from the rest of its net.
    kind: analog | irq | bus | out | in | io | test | none."""
    if not p.net:
        return 'unused', 'none'
    n = d.nets[p.net]
    if n.is_power or n.is_ground:
        return f"tied to {n.name}", 'none'
    nets, through = signal_group(d, p.net)
    others = [q for q in group_pins(d, nets) if q is not p]
    real = [q for q in others if q.comp.kind not in ('TP', 'MECH')]
    for q in real:
        if q.role in _ROLE_USE:
            return f"{_ROLE_USE[q.role]} ({q.comp.ref})", 'irq' if q.role == 'irq' else 'bus'
    for q in real:
        if q.comp.kind == 'IC' and any(_IRQ.match(a) for a in pin_aliases(q.name)):
            return f"interrupt in ({q.label})", 'irq'
    div = None
    for nn in nets:
        div = div or getattr(d.nets[nn], 'divider', None)
    named_analog = any(is_analog_name(nn) for nn in nets)
    named_digital = any(_DIGITAL.search(nn.split('/')[-1]) for nn in nets)
    if named_analog:
        return 'analog in' + (f" ({div[2].name} through {div[0].ref}/{div[1].ref})" if div else ''), 'analog'
    if div is not None and 'high =' not in div[3][2] and not named_digital:
        return f"level of {div[2].name} through {div[0].ref}/{div[1].ref} (analog or digital)", 'analog?'
    if div is not None:
        return f"digital in (divided from {div[2].name})", 'in'
    if not real:
        return ('test point only' if others else 'unused'), 'test'
    drivers = [q for q in real if can_drive(q) and q.role != 'gpio']
    conns = [q for q in real if q.comp.kind == 'CONN']
    loads = [q for q in real if q.comp.kind in ('Q', 'LED', 'OTHER') or (q.comp.kind == 'IC' and q.etype == 'input')]
    if drivers:
        return f"digital in (from {drivers[0].label})", 'in'
    if loads and not conns:
        what = 'FET gate' if loads[0].comp.kind == 'Q' else loads[0].label
        return f"digital out (to {what})", 'out'
    if conns:
        return f"to connector {conns[0].label}", 'io'
    if any(q.comp.kind == 'SW' for q in real):
        return 'button', 'in'
    return f"to {real[0].label}", 'io'


@check('mcu.pin_use', 'pins', doc='Each MCU / FPGA pin can do what the board asks of it: ADC inputs, wake-capable interrupts, input- or output-only pins')
def mcu_pin_use(d):
    for c in d.components.values():
        if c.dnp or not _programmable(c):
            continue
        mcu = c.model.get('mcu') or {}
        adc1, adc2 = _num_set(mcu.get('adc1_pins')), _num_set(mcu.get('adc2_pins'))
        rtc = _num_set(mcu.get('rtc_pins'))
        rows = []
        for p in sorted(c.pins.values(), key=lambda p: (len(p.number), p.number)):
            if p.role in ('gnd', 'power_in', 'power_out', 'nc') or p.etype in ('power_in', 'power_out', 'no_connect') or not p.net:
                continue
            use, kind = pin_use(d, p)
            if kind == 'none':
                continue
            al = pin_aliases(p.name)
            verdict = 'ok'
            if kind == 'analog?' and (adc1 or adc2):
                on1 = bool(al & {a.upper() for a in adc1})
                on2 = bool(al & {a.upper() for a in adc2})
                verdict = 'ok: ADC1' if on1 else 'ADC2 only: fine as a digital input' if on2 else 'no ADC here: digital only'
                if not on1:
                    yield F('mcu.pin_use', 'info', f"{p.label} can only read {p.net} as a digital level"
                            + (' reliably (ADC2 pin)' if on2 else ''),
                            f"{c.desc}: {use}. " + ("ADC2 is shared with the radio on ESP32-family parts. " if on2 else
                                                    "The pin has no ADC channel. ") +
                            f"Fine if firmware only tests high or low; to measure the voltage use one of "
                            f"{', '.join(sorted(adc1, key=lambda s: (len(s), s)))}.", refs=[c.ref], nets=[p.net],
                            basis=model_basis(c, 'ADC channel table'), confidence='medium')
            if kind == 'analog' and (adc1 or adc2):
                if not (al & {a.upper() for a in adc1 | adc2}):
                    verdict = 'NOT an ADC pin'
                    yield F('mcu.pin_use', 'error', f"{p.label} is used as an analog input but has no ADC channel",
                            f"{c.desc}: net {p.net} is {use}. ADC-capable pins on this part: "
                            f"{', '.join(sorted(adc1 | adc2, key=lambda s: (len(s), s)))}.", refs=[c.ref], nets=[p.net],
                            basis=model_basis(c, 'ADC channel table'), confidence='medium')
                elif adc1 and not (al & {a.upper() for a in adc1}):
                    verdict = 'ADC2 only'
                    yield F('mcu.pin_use', 'warning', f"{p.label} is an ADC2 pin used for an analog input",
                            f"{c.desc}: net {p.net} is {use}. On ESP32-family parts ADC2 is shared with the radio "
                            f"and readings fail or are restricted while Wi-Fi is on. Prefer an ADC1 pin: "
                            f"{', '.join(sorted(adc1, key=lambda s: (len(s), s)))}.", refs=[c.ref], nets=[p.net],
                            basis=model_basis(c, 'ADC channel table'), confidence='medium')
                else:
                    verdict = 'ok: ADC1'
            if kind == 'irq' and rtc:
                if al & {a.upper() for a in rtc}:
                    verdict = 'ok: can wake from deep sleep'
                else:
                    verdict = 'cannot wake from deep sleep'
                    yield F('mcu.pin_use', 'info', f"{p.label} takes an interrupt but is not a wake-capable pin",
                            f"{c.desc}: {use}. Only {mcu.get('rtc_pins')} can wake the part from deep sleep.",
                            refs=[c.ref], nets=[p.net], basis=model_basis(c), confidence='medium')
            if p.spec.get('user_input') is False and kind in ('in', 'io', 'bus'):
                nets, _ = signal_group(d, p.net)
                ext = [q for q in group_pins(d, nets) if q is not p and (q.comp.kind == 'CONN' or (can_drive(q) and q.comp.kind == 'IC'))]
                if ext:
                    verdict = 'cannot be read by the design'
                    yield F('mcu.pin_use', 'warning', f"{p.label} cannot be used as an input, and {names(ext[:3])} can drive it",
                            f"{c.desc}: {p.spec.get('note', 'this pin is output-only for user logic')} "
                            f"Net {p.net} also reaches {names(ext[:4])}: a signal arriving from there cannot be "
                            f"seen by the design. If an external controller is meant to talk to logic in this part "
                            f"over these wires, bring its clock to an ordinary I/O pin as well.",
                            refs=[c.ref] + sorted({q.comp.ref for q in ext})[:3], nets=[p.net],
                            basis=model_basis(c), confidence='medium')
            if p.spec.get('user_output') is False and kind == 'out':
                verdict = 'input-only pin'
                yield F('mcu.pin_use', 'error', f"{p.label} is input-only and nothing else drives {p.net}",
                        f"{c.desc}: {use}.", refs=[c.ref], nets=[p.net], basis=model_basis(c), confidence='medium')
            if p.role in ('usb_dp', 'usb_dm') and 'USB' not in use:
                verdict = 'USB pin used for something else'
            if p.role == 'boot_strap':
                verdict += '; strapping pin'
            rows.append((p.name or p.number, p.net, use, verdict))
        if rows:
            plain = [r for r in rows if r[3] == 'ok' and r[2].startswith('to connector')]
            shown = [r for r in rows if r not in plain] if len(rows) > 40 else rows
            yield F('mcu.pin_use', 'info', f"{c.ref} pin use: {len(rows)} pins in use"
                    + (f" ({len(plain)} plain connector I/O not listed)" if len(shown) < len(rows) else ''),
                    '; '.join(f"{nm} = {net}: {use} [{v}]" for nm, net, use, v in shown[:60])
                    + ('...' if len(shown) > 60 else ''), refs=[c.ref],
                    evidence={nm: f"{net}: {use} [{v}]" for nm, net, use, v in shown[:80]},
                    basis=model_basis(c, 'pin capabilities; use inferred from what else is on each net'), confidence='medium')


@check('pin.strap_strength', 'pins', doc='A strap resistor is strong enough against the pin\'s internal pull')
def strap_strength(d):
    for c in d.components.values():
        if c.dnp or not c.model:
            continue
        for p in c.pins.values():
            pull = p.spec.get('internal_pull')
            if pull not in ('up', 'down') or not p.net:
                continue
            rint = p.spec.get('internal_pull_ohm') or (c.model.get('io') or {}).get('internal_pull_ohm')
            if not rint:
                continue
            from .pins import _num
            rint = _num(rint, 'R')
            n = d.nets[p.net]
            if n.is_power or n.is_ground:
                continue
            ups, downs = pulls(d, p.net)
            vdd = max([d.nets[q.net].vmax for q in c.pins.values() if q.net and d.nets[q.net].is_power
                       and d.nets[q.net].vmax is not None] or [0])
            if not vdd:
                continue
            against = downs if pull == 'up' else ups
            if not against or (ups and downs):
                continue
            rext = 1 / sum(1 / max(r.num, 1e-3) for r, _ in against)
            if pull == 'up':
                v = vdd * rext / (rext + rint)
                lim = float(p.spec.get('vil') or io(c, p, 'vil') or vdd * float(io(c, p, 'vil_frac', 0.25)))
                bad, marginal = v > lim, v > 0.6 * lim
                what = f"reads {v:.2f} V; a logic low must be below {lim:g} V"
            else:
                v = vdd * rint / (rext + rint)
                lim = float(p.spec.get('vih') or io(c, p, 'vih') or vdd * float(io(c, p, 'vih_frac', 0.75)))
                bad, marginal = v < lim, v < lim + 0.4 * (vdd - lim)
                what = f"reads {v:.2f} V; a logic high must be above {lim:g} V"
            if bad or marginal:
                yield F('pin.strap_strength', 'error' if bad else 'warning',
                        f"{p.label}: {fmt_r(rext)} strap against the internal pull-{pull} {what}",
                        f"{c.desc}: {', '.join(r.desc for r, _ in against)} pulls the pin {'down' if pull == 'up' else 'up'} "
                        f"against an internal pull-{pull} that can be as strong as {fmt_r(rint)} at {vdd:g} V. "
                        f"Use a much smaller resistor (1k or less) or tie the pin directly.",
                        refs=[c.ref] + [r.ref for r, _ in against], nets=[p.net],
                        evidence={'external': fmt_r(rext), 'internal_min': fmt_r(rint), 'pin_voltage': round(v, 2), 'threshold': lim},
                        basis=model_basis(c, 'weak pull current'), confidence='medium')


_CLK_CAPABLE = re.compile(r'PCLK|GCLK|GBIN|MRCC|SRCC|CLKIN|XIN|XTAL|OSC_?IN|^OSC|CLK_?IN|GR_PCLK|^XI$|^X1$', re.I)
_XTAL_PIN = re.compile(r'X(TAL)?_?(IN|OUT|I|O|1|2|32[KN]?_?[PN]?)$|OSC(32)?_?(IN|OUT|I|O)?$|XTAL|^XI$|^XO$|^X[12]$|XC[12]', re.I)


@check('clock.source', 'pins', doc='Oscillator outputs reach clock-capable pins; crystals have both load capacitors and sit on oscillator pins')
def clock_source(d):
    for c in d.components.values():
        if c.dnp:
            continue
        if c.kind == 'OSC':
            outs = [p for p in c.pins.values() if p.net and (p.etype == 'output' or norm_pin_name(p.name) in ('OUT', 'CLK', 'CLKOUT', 'OUTPUT'))]
            for o in outs:
                nets, through = signal_group(d, o.net)
                dests = [q for q in group_pins(d, nets) if q.comp is not c and q.comp.kind == 'IC']
                if not dests:
                    yield F('clock.source', 'warning', f"Oscillator {c.ref} output goes nowhere",
                            f"{c.desc}: net {o.net} reaches no IC.", refs=[c.ref], nets=[o.net], confidence='high')
                for q in dests:
                    pat = (q.comp.model or {}).get('clock_pattern')
                    rx = re.compile(pat) if pat else _CLK_CAPABLE
                    part_has = any(rx.search(x.name or '') for x in q.comp.pins.values())
                    ok = bool(rx.search(q.name or ''))
                    if part_has and not ok:
                        good = sorted({x.name for x in q.comp.pins.values() if rx.search(x.name or '') and not x.net})[:6]
                        yield F('clock.source', 'error', f"Clock from {c.ref} arrives at {q.label}, which is not a clock input",
                                f"{q.comp.desc} has dedicated clock-capable pins and this is not one of them: the clock "
                                f"would be routed on general fabric, with skew and jitter, or not usable at all. "
                                f"Free clock pins include {', '.join(good) or 'none left'}.",
                                refs=[c.ref, q.comp.ref], nets=nets,
                                basis=model_basis(q.comp) if pat else 'pin names of the receiving part', confidence='medium')
                    else:
                        yield F('clock.source', 'info', f"Clock: {c.ref} ({c.value}) -> {q.label}"
                                + (' (clock-capable pin)' if ok else ''),
                                (f"Through {', '.join(t.desc for t in through)}. " if through else "No series resistor: "
                                 "22 to 33 ohm at the source tames edges on a long trace. "),
                                refs=[c.ref, q.comp.ref], nets=nets, confidence='medium')
            en = [p for p in c.pins.values() if norm_pin_name(p.name) in ('OE', 'EN', 'ST', 'E/D', 'STBY', 'ENABLE')]
            for p in en:
                n = d.net_of(p)
                if n is not None and n.is_ground:
                    yield F('clock.source', 'error', f"Oscillator {c.ref} is disabled: {p.label} is tied to ground",
                            f"{c.desc}: output-enable pins are active high on almost every oscillator; check the datasheet.",
                            refs=[c.ref], confidence='medium')
        elif c.kind == 'XTAL':
            sig = [p for p in c.pins.values() if p.net and not d.nets[p.net].is_ground]
            if len(sig) != 2:
                continue
            caps, ics = [], []
            for p in sig:
                cs = [k for k, _ in caps_to_ground(d, p.net) if k.num]
                caps.append(cs)
                ics += [q for q in d.nets[p.net].pins if q.comp.kind == 'IC']
            icrefs = {q.comp.ref for q in ics}
            if len(icrefs) > 1:
                yield F('clock.source', 'warning', f"Crystal {c.ref} is connected to more than one IC ({', '.join(sorted(icrefs))})",
                        "A crystal belongs across one oscillator's two pins.", refs=[c.ref] + sorted(icrefs), confidence='medium')
            for q in ics:
                named = any(x.name and _XTAL_PIN.search(x.name) for x in q.comp.pins.values())
                if named and not _XTAL_PIN.search(q.name or '') and q.role != 'gpio':
                    yield F('clock.source', 'error', f"Crystal {c.ref} is on {q.label}, which is not an oscillator pin",
                            f"{q.comp.desc} has pins named for a crystal and this is not one of them.",
                            refs=[c.ref, q.comp.ref], confidence='medium')
            if caps[0] and caps[1]:
                c1, c2 = sum(k.num for k in caps[0]), sum(k.num for k in caps[1])
                cl = c1 * c2 / (c1 + c2)
                m = re.search(r'(\d+(?:\.\d+)?)\s*pF', c.value + ' ' + ' '.join(str(v) for v in c.props.values()), re.I)
                spec = float(m.group(1)) * 1e-12 if m else None
                ev = {'load_caps': f"{fmt_c(c1)} + {fmt_c(c2)}", 'series_value': fmt_c(round(cl, 13)),
                      'with_3_to_5pF_stray': f"{(cl + 3e-12) * 1e12:.1f} to {(cl + 5e-12) * 1e12:.1f} pF"}
                if spec and not (cl + 2e-12 <= spec <= cl + 7e-12):
                    yield F('clock.source', 'warning', f"Crystal {c.ref}: load capacitors give about {(cl + 4e-12) * 1e12:.0f} pF, the crystal asks for {spec * 1e12:g} pF",
                            f"CL = C1 x C2 / (C1 + C2) + stray. For {spec * 1e12:g} pF use about "
                            f"{2 * (spec - 4e-12) * 1e12:.0f} pF each. The frequency is pulled off otherwise.",
                            refs=[c.ref] + [k.ref for k in caps[0] + caps[1]], evidence=ev,
                            basis='crystal load-capacitance formula; 4 pF stray assumed', confidence='medium')
                else:
                    yield F('clock.source', 'info', f"Crystal {c.ref}: load capacitance about {(cl + 4e-12) * 1e12:.0f} pF with stray",
                            "Compare with the CL in the crystal's datasheet" + ('' if spec else ' (not stated in the schematic)') + '.',
                            refs=[c.ref], evidence=ev, confidence='medium')
            elif not (ics and ics[0].comp.model and (ics[0].comp.model.get('mcu') or {}).get('xtal_internal_caps')):
                yield F('clock.source', 'warning', f"Crystal {c.ref} has no load capacitor on {' and '.join(p.net for p, cs in zip(sig, caps) if not cs)}",
                        "Without both load capacitors a crystal runs off frequency or does not start, unless the "
                        "IC provides them internally (check its datasheet).", refs=[c.ref], confidence='medium')


@check('reset.circuit', 'pins', doc='Reset / enable pins of MCUs and FPGAs: pull-up, delay, who can drive them, and conflicts')
def reset_circuit(d):
    for c in d.components.values():
        if c.dnp or c.kind != 'IC':
            continue
        prog = _programmable(c) or (not c.model and re.search(r'mcu|fpga|cpld', c.lib_id, re.I))
        for p in c.pins.values():
            nm = norm_pin_name(p.name)
            is_reset = p.role == 'reset' or (prog and (p.role == 'enable' or nm in ('PROGRAMN', 'NRST', 'RESET', 'RST', 'RUN', 'CHIP_PU', 'MCLR')))
            if not is_reset or not p.net or not prog:
                continue
            n = d.nets[p.net]
            if n.is_power or n.is_ground:
                continue
            nets, through = signal_group(d, p.net, max_ohm=10e3)
            pins = [q for q in group_pins(d, nets) if q is not p]
            ups, downs = [], []
            for nn in nets:
                u, dn = pulls(d, nn)
                ups += [x for x in u if x not in ups]
                downs += [x for x in dn if x not in downs]
            caps = [k for nn in nets for k, _ in caps_to_ground(d, nn) if k.num]
            buttons = [q for q in pins if q.comp.kind == 'SW']
            od = [q for q in pins if q.spec.get('drive') == 'open_drain' or q.etype == 'open_collector']
            pp = [q for q in pins if q.comp.kind == 'IC' and q not in od and can_drive(q) and q.role != 'gpio']
            conns = [q for q in pins if q.comp.kind == 'CONN']
            tps = [q for q in pins if q.comp.kind == 'TP']
            gp = [q for q in pins if q.role == 'gpio']
            parts = []
            rp = 1 / sum(1 / max(r.num, 1e-3) for r, _ in ups) if ups else None
            ctot = sum(k.num for k in caps)
            if rp:
                parts.append(f"pull-up {fmt_r(round(rp))} ({', '.join(r.ref for r, _ in ups)})")
            elif p.spec.get('internal_pull') == 'up':
                parts.append('internal pull-up only')
            if ctot:
                parts.append(f"{fmt_c(ctot)} to ground" + (f", time constant {rp * ctot * 1000:.3g} ms" if rp else ''))
            for lst, what in ((od, 'open-drain'), (pp, 'push-pull'), (buttons, 'button'), (conns, 'connector'), (gp, 'MCU pin')):
                if lst:
                    parts.append(f"{what} {names(lst[:3])}")
            if through:
                parts.append('through ' + ', '.join(t.desc for t in through))
            yield F('reset.circuit', 'info', f"Reset of {c.ref}: {p.label} on {p.net}", '; '.join(parts) + '.',
                    refs=[c.ref], nets=nets, evidence={'pull_up': fmt_r(round(rp)) if rp else 'none', 'capacitance': fmt_c(ctot) if ctot else 'none',
                                                       'tau_ms': round(rp * ctot * 1000, 3) if rp and ctot else None},
                    confidence='high')
            direct = lambda q: q.net == p.net or not any(t.num and t.num >= 100 for t in through if any(x.net in (q.net, p.net) for x in t.pins.values()))
            for q in pp:
                clash = [b for b in buttons + od if b.net == q.net]
                if clash:
                    yield F('reset.circuit', 'warning', f"{q.label} drives {q.net} push-pull while {names(clash[:2])} can pull it low",
                            "Pressing the button (or the open-drain part asserting) shorts a driven-high output to "
                            "ground. Put a resistor in series with the push-pull output, or use an open-drain driver.",
                            refs=[q.comp.ref] + [b.comp.ref for b in clash[:2]], nets=[q.net], confidence='medium')
            if downs and not ups and p.spec.get('active', 'low') == 'low' and not (pp or od or gp):
                yield F('reset.circuit', 'error', f"{p.label} is pulled low by {', '.join(r.desc for r, _ in downs)} and nothing releases it",
                        f"{c.desc} stays in reset.", refs=[c.ref], nets=[p.net], confidence='medium')
            if not (buttons or conns or tps or od or pp or gp):
                yield F('reset.circuit', 'info', f"{p.label} cannot be reached from outside",
                        f"No button, connector, test point or supervisor is on {p.net}: there is no way to reset "
                        f"{c.ref} without cycling power.", refs=[c.ref], nets=[p.net], confidence='medium')
