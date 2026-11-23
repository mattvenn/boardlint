"""Unit tests that need no KiCad files."""
import math
from boardlint import sexpr
from boardlint.classify import parse_value, is_ground_name, norm_pin_name, guess_role
from boardlint.model import Design, Component, Pin
from boardlint import faults as fz
from boardlint.classify import classify_components
from boardlint.engine import run
from boardlint.checks.layout import cps_c_per_mm
from boardlint.power import voltage_from_name


def test_sexpr_roundtrip():
    t = sexpr.loads('(a (b "x y" 1.5) (c "q\\"z") d)')
    assert t[0] == 'a' and t[1] == ['b', 'x y', '1.5'] and t[2][1] == 'q"z'
    assert isinstance(t[1][1], sexpr.QStr) and not isinstance(t[1][2], sexpr.QStr)


def test_values():
    assert parse_value('4k7', 'R') == 4700
    assert parse_value('470R', 'R') == 470
    assert parse_value('0R', 'R') == 0
    assert parse_value('1M', 'R') == 1e6
    assert parse_value('75k 1%', 'R') == 75e3
    assert math.isclose(parse_value('100nF', 'C'), 100e-9)
    assert math.isclose(parse_value('10uF 16V', 'C'), 10e-6)
    assert math.isclose(parse_value('4.7u', 'C'), 4.7e-6)
    assert parse_value('DNP', 'R') is None


def test_names():
    assert is_ground_name('GND') and is_ground_name('AGND') and is_ground_name('/power/GND')
    assert not is_ground_name('SDA') and not is_ground_name('+3V3')
    assert norm_pin_name('~{CS}') == 'CS' and norm_pin_name('V_{DD}') == 'VDD'
    assert voltage_from_name('+3V3')[0:2] == (3.135, 3.465)
    assert voltage_from_name('SDA') is None


def test_cps_capacitance_is_sane():
    # 0.15 mm traces 0.2 mm apart on FR4: a few hundredths of a pF per mm
    c = cps_c_per_mm(0.15, 0.2) * 1e12
    assert 0.02 < c < 0.06
    assert cps_c_per_mm(0.15, 1.0) < cps_c_per_mm(0.15, 0.2)


def _mini():
    """MCU + two unmodelled parts, built in memory."""
    d = Design(name='mini')
    fz.add_part(d, 'U1', 'SOMEMCU', {'1': ('VDD', 'power_in', '+3V3'), '2': ('GND', 'power_in', 'GND'),
                                      '3': ('TXD', 'output', 'A'), '4': ('RXD', 'input', 'B'),
                                      '5': ('SDA', 'bidirectional', 'SDA'), '6': ('SCL', 'output', 'SCL')})
    fz.add_part(d, 'U2', 'CH340C', {'1': ('VCC', 'power_in', '+3V3'), '2': ('GND', 'power_in', 'GND'),
                                     '3': ('TXD', 'output', 'A'), '4': ('RXD', 'input', 'B')})
    fz.add_part(d, 'U3', 'SOMESENSOR', {'1': ('VDD', 'power_in', '+3V3'), '2': ('GND', 'power_in', 'GND'),
                                         '3': ('SDA', 'bidirectional', 'SCL'), '4': ('SCL', 'input', 'SDA')})
    for c in d.components.values():
        c.lib_id = ''
    fz.reanalyse(d)
    return d


def test_uart_and_i2c_swaps_by_pin_name_alone():
    d = _mini()
    fs, log = run(d, no_sim=True)
    assert not [l for l in log if l[1] == 'crashed'], log
    titles = [f.title for f in fs if f.severity == 'error']
    assert any('TX wired to TX' in t for t in titles)
    assert any('RX wired to RX' in t for t in titles)
    assert any('SDA and SCL are crossed' in t for t in titles)
    assert any('No pull-up on I2C' in t for t in titles)


def test_role_guessing():
    c = Component(ref='U1', value='X', kind='IC')
    for name, role in (('TXD0', 'uart_tx'), ('SCL/SPC', 'i2c_scl'), ('~{CS}', 'spi_cs'), ('MISO', 'spi_miso'), ('SDO', 'spi_sdo'),
                       ('USB_D+', 'usb_dp'), ('EN', 'enable'), ('IO12', '')):
        assert guess_role(Pin(comp=c, number='1', name=name)) == role, name


def _spi(swap=False, share_cs=False):
    d = Design(name='spi')
    mosi, miso = ('MISO_N', 'MOSI_N') if swap else ('MOSI_N', 'MISO_N')
    fz.add_part(d, 'U1', 'SOMEMCU', {'1': ('VDD', 'power_in', '+3V3'), '2': ('GND', 'power_in', 'GND'),
                                      '3': ('MOSI', 'output', 'MOSI_N'), '4': ('MISO', 'input', 'MISO_N'),
                                      '5': ('SCK', 'output', 'SCK_N'), '6': ('PA4', 'bidirectional', 'CS1'),
                                      '7': ('PA5', 'bidirectional', 'CS1' if share_cs else 'CS2')})
    for ref, cs in (('U2', 'CS1'), ('U3', 'CS1' if share_cs else 'CS2')):
        fz.add_part(d, ref, 'FLASH', {'1': ('~{CS}', 'input', cs), '2': ('DO', 'output', miso), '5': ('DI', 'input', mosi),
                                      '6': ('CLK', 'input', 'SCK_N'), '8': ('VCC', 'power_in', '+3V3'), '4': ('GND', 'power_in', 'GND')})
    fz.reanalyse(d)
    return d


def test_spi_clean_swapped_and_shared_cs():
    errs = lambda d: [f.title for f in run(d, only=['spi.bus'])[0] if f.severity == 'error']
    assert errs(_spi()) == []
    assert any('swapped' in t for t in errs(_spi(swap=True)))
    assert any('share chip select' in t for t in errs(_spi(share_cs=True)))


def test_relay_without_flyback_diode():
    d = Design(name='relay')
    fz.add_part(d, 'K1', 'G5LE', {'1': ('A1', 'passive', '+5V'), '2': ('A2', 'passive', 'COIL_N')}, kind='OTHER')
    d.components['K1'].lib_id = 'Relay:G5LE-1'
    fz.add_part(d, 'Q1', '2N7002', {'1': ('G', 'input', 'DRV'), '2': ('S', 'passive', 'GND'), '3': ('D', 'passive', 'COIL_N')}, kind='Q')
    fz.reanalyse(d)
    errs = [f.title for f in run(d, only=['load.inductive'])[0] if f.severity == 'error']
    assert any('no flyback diode' in t for t in errs)
    fz.add_part(d, 'D1', '1N4148W', {'1': ('K', 'passive', '+5V'), '2': ('A', 'passive', 'COIL_N')}, kind='D')
    fz.reanalyse(d)
    assert not [f for f in run(d, only=['load.inductive'])[0] if f.severity == 'error']
    fz.swap_nets(d, fz.pin(d, 'D1', 'K'), fz.pin(d, 'D1', 'A'))
    fz.reanalyse(d)
    assert any('wrong way round' in f.title for f in run(d, only=['load.inductive'])[0])


def test_pin_name_against_net_name():
    d = Design(name='i2s')
    fz.add_part(d, 'U3', 'SOMECODEC', {'23': ('LRCLK', 'input', 'BCLK'), '24': ('BCLK', 'input', 'LRCLK'),
                                        '25': ('SDA', 'bidirectional', 'SDA'), '26': ('IO5/MOSI/SDA', 'bidirectional', 'SCL')})
    fz.reanalyse(d)
    errs = [f.title for f in run(d, only=['net.name_mismatch'])[0]]
    assert len(errs) == 2 and all('U3.2' in t for t in errs)      # the multi-function pin 26 is not judged
