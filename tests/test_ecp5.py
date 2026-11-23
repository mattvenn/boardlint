"""A KiCad 5 FPGA board with two documented errata: both must be found, and a moved clock must be caught."""
from boardlint.engine import prepare, run
from boardlint import faults as fz


def test_documented_errata_are_found(ecp5):
    d = prepare(ecp5)
    fs, log = run(d, no_sim=True)
    assert not [l for l in log if l[1] == 'crashed'], log
    titles = {(f.check, f.severity): f.title for f in fs}
    straps = [f for f in fs if f.check == 'pin.strap_strength' and f.severity == 'error']
    assert {r for f in straps for r in f.refs if r.startswith('U')} == {'U1'} and len(straps) == 2      # CFG_0, CFG_2 via 10k
    assert any(f.check == 'mcu.pin_use' and 'CCLK' in f.title and f.severity == 'warning' for f in fs)   # SPI clock into CCLK
    assert any(f.check == 'clock.source' and 'clock-capable' in f.title for f in fs)                    # oscillator on a PCLK pin
    assert not [f for f in fs if f.check == 'power.pin_voltage']                                        # I/O judged against VCCIO


def test_clock_on_a_non_clock_pin_is_caught(ecp5):
    d = prepare(ecp5)
    u1 = d.components['U1']
    plain = next(p for p in u1.pins.values() if p.name.startswith('PT') and 'PCLK' not in p.name and p.net and p.role == 'gpio')
    clk = next(p for p in u1.pins.values() if p.net == 'clk')
    fz.swap_nets(d, plain, clk)
    fz.reanalyse(d)
    fs, _ = run(d, only=['clock.source'])
    assert any(f.severity == 'error' and 'not a clock input' in f.title for f in fs)
