#!/usr/bin/env python3
"""Inject classic first-spin mistakes into a known-good design and report which ones boardlint flags.

    python3 tools/fault_report.py /path/to/dino-board

The fault list is written for the DinoLight board (https://github.com/mo-seph/dino-board) at commit
4da182c: it names that revision's reference designators.  Check that commit out to reproduce it.  Each fault is one edit a tired designer could make.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from boardlint.engine import prepare, run            # noqa: E402
from boardlint import faults as fz                   # noqa: E402

FAULTS = [
    # (id, description, mutation, check ids that should fire with an error or warning)
    ('i2c-swap', 'U7 (MPR121) SDA and SCL swapped',
     lambda d: fz.swap_nets(d, fz.pin(d, 'U7', 'SDA'), fz.pin(d, 'U7', 'SCL')), ['i2c.bus', 'sim.i2c']),
    ('i2c-no-pullup', 'SDA pull-up R17 left off',
     lambda d: fz.remove(d, 'R17'), ['i2c.bus', 'sim.i2c']),
    ('i2c-strong-pullup', 'I2C pull-ups 470R instead of 4.7k',
     lambda d: (fz.set_value(d, 'R17', '470R'), fz.set_value(d, 'R18', '470R')), ['i2c.bus']),
    ('i2c-mode-pin', 'U5 (LIS2DH12) CS tied to ground instead of 3V3: part is in SPI mode',
     lambda d: fz.move_pin(d, fz.pin(d, 'U5', 'CS'), 'GND'), ['pin.requirements', 'sim.i2c']),
    ('i2c-clash', 'second MPR121 added with the same ADDR strap',
     lambda d: fz.add_part(d, 'U8', 'MPR121QR2', {
         '1': ('~{IRQ}', 'open_collector', None), '2': ('SCL', 'input', 'SCL'), '3': ('SDA', 'bidirectional', 'SDA'),
         '4': ('ADDR', 'input', 'GND'), '5': ('VREG', 'passive', 'MPR_VREG'), '6': ('VSS', 'power_in', 'GND'),
         '7': ('REXT', 'passive', 'MPR_REXT'), '20': ('VDD', 'power_in', '+3V3')}), ['i2c.bus', 'sim.i2c']),
    ('rext-value', 'MPR121 REXT 7.5k instead of 75k',
     lambda d: fz.set_value(d, 'R33', '7.5k'), ['pin.requirements']),
    ('led-reversed', 'D5 placed with DIN and DOUT exchanged',
     lambda d: fz.swap_nets(d, fz.pin(d, 'D5', 'DIN'), fz.pin(d, 'D5', 'DOUT')), ['led.chain', 'sim.led_chain']),
    ('led-5v', 'LED rail fed from VBUS (5 V) with 3.3 V data',
     lambda d: fz.move_pin(d, fz.pin(d, 'Q2', 'S'), 'VBUS'), ['led.chain', 'sim.led_chain']),
    ('usb-swap', 'USB D+ and D- swapped at the module',
     lambda d: fz.swap_nets(d, fz.pin(d, 'U4', 'USB_D+'), fz.pin(d, 'U4', 'USB_D-')), ['usb.wiring']),
    ('cc-missing', 'CC2 pull-down R2 left off',
     lambda d: fz.remove(d, 'R2'), ['usb.wiring']),
    ('cc-shared', 'CC1 and CC2 tied together on one 5.1k',
     lambda d: (fz.remove(d, 'R2'), fz.move_pin(d, fz.pin(d, 'J1', 'CC2'), 'CC1')), ['usb.wiring']),
    ('cc-value', 'CC pull-downs 10k instead of 5.1k',
     lambda d: (fz.set_value(d, 'R1', '10k'), fz.set_value(d, 'R2', '10k')), ['usb.wiring']),
    ('uart-tx-tx', 'USB-serial bridge added TX to TX, RX to RX',
     lambda d: fz.add_part(d, 'U9', 'CH340C', {
         '2': ('TXD', 'output', 'UART_TX'), '3': ('RXD', 'input', 'UART_RX'),
         '16': ('VCC', 'power_in', '+3V3'), '1': ('GND', 'power_in', 'GND')}), ['uart.direction']),
    ('ldo-no-cout', 'LDO output capacitor C4 left off',
     lambda d: fz.remove(d, 'C4'), ['decoupling.regulator_caps', 'decoupling.per_part']),
    ('prog-value', 'charger PROG resistor 1k (1 A, outside the 2k to 67k range)',
     lambda d: fz.set_value(d, 'R3', '1k'), ['pin.requirements']),
    ('divider-5v', 'VBUS_DET lower resistor 2M instead of 200k: 5 V reaches a 3.3 V pin',
     lambda d: fz.set_value(d, 'R9', '2M'), ['power.pin_voltage']),
    ('divider-low', 'CHG_STAT lower resistor 20k instead of 200k: never a logic high',
     lambda d: fz.set_value(d, 'R19', '20k'), ['power.logic_level']),
    ('en-floating', 'EN pull-up R16 left off',
     lambda d: fz.remove(d, 'R16'), ['pin.requirements', 'pin.floating_control']),
    ('strap-pulldown', '10k pull-down added on strapping pin IO0',
     lambda d: fz.add_part(d, 'R90', '10k', {'1': ('', 'passive', 'BOOT'), '2': ('', 'passive', 'GND')}, kind='R') and
     fz.set_value(d, 'R90', '10k'), ['mcu.strapping']),
    ('mcu-no-bypass', 'all 100 nF capacitors on +3V3 left off',
     lambda d: [fz.remove(d, c.ref) for c in list(d.components.values())
                if c.kind == 'C' and c.value.startswith('100n') and any(p.net == '+3V3' for p in c.pins.values())],
     ['decoupling.per_part']),
    ('ldo-5v-in', 'regulator input taken from a 12 V rail',
     lambda d: fz.move_pin(d, fz.pin(d, 'U3', 'VIN'), '+12V'), ['power.supply_range']),
    # two mistakes this board really had, found by its own design review and fixed before the first commit
    ('hist-divider-vih', 'as first drawn: CHG_STAT and VBUS_DET dividers 100k/100k (half of a sagging VBUS is below VIH)',
     lambda d: (fz.set_value(d, 'R9', '100k'), fz.set_value(d, 'R19', '100k')), ['power.logic_level']),
    ('hist-cap-bias', 'as first drawn: regulator capacitors C3, C4 were 1 uF 0402 (too little left under DC bias)',
     lambda d: [(fz.set_value(d, r, '1uF'), setattr(d.components[r], 'footprint', 'Capacitor_SMD:C_0402_1005Metric'))
                for r in ('C3', 'C4')], ['decoupling.regulator_caps']),
    ('adc-wrong-pin', 'battery-sense divider moved to IO21, which has no ADC channel',
     lambda d: fz.swap_nets(d, fz.pin(d, 'U4', 'IO10'), fz.pin(d, 'U4', 'IO21')), ['mcu.pin_use']),
    ('ldo-en-low', 'regulator enable tied to ground',
     lambda d: fz.move_pin(d, fz.pin(d, 'U3', 'CE'), 'GND'), ['pin.floating_control']),
    ('fet-gate', 'Q2 gate pull-down path removed (R13): P-FET never turns on',
     lambda d: fz.remove(d, 'R13'), ['ratings.fets', 'pin.floating_control', 'power.rails']),
    ('track-narrow', 'LED supply (VLED) routed at 0.15 mm instead of 0.4 mm',
     lambda d: [setattr(t, 'width', 0.15) for t in d.board.tracks if t.net == 'VLED'], ['layout.track_current', 'layout.ir_drop']),
    ('rail-thin', '3.3 V rail routed at 0.08 mm: too much resistance between the regulator and the module',
     lambda d: [setattr(t, 'width', 0.08) for t in d.board.tracks if t.net == '+3V3'], ['layout.ir_drop']),
]


def evaluate(project, only=None):
    base = prepare(project)
    base_f, _ = run(base)
    base_keys = {(f.check, f.title) for f in base_f if f.severity in ('error', 'warning')}
    rows = []
    for fid, desc, mut, expect in FAULTS:
        if only and fid not in only:
            continue
        d = prepare(project)
        mut(d)
        fz.reanalyse(d)
        fs, log = run(d)
        new = [f for f in fs if f.severity in ('error', 'warning') and (f.check, f.title) not in base_keys]
        hit = sorted({f.check for f in new if f.check in expect})
        other = sorted({f.check for f in new if f.check not in expect})
        crashed = [l[0] for l in log if l[1] == 'crashed']
        rows.append((fid, desc, expect, hit, other, new, crashed))
    return rows


if __name__ == '__main__':
    rows = evaluate(sys.argv[1], set(sys.argv[2:]) or None)
    caught = 0
    for fid, desc, expect, hit, other, new, crashed in rows:
        caught += bool(hit)
        print(f"{'CAUGHT' if hit else 'MISSED':6}  {fid:18} {desc}")
        for f in new:
            print(f"          {f.severity:7} [{f.check}] {f.title}")
        if crashed:
            print(f"          CRASHED: {crashed}")
    print(f"\n{caught} of {len(rows)} injected faults flagged by an expected check")
