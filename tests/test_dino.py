"""End-to-end tests on a real board: load, netlist agreement, a clean baseline, and fault injection."""
import pytest
from boardlint.engine import prepare, run
from boardlint import kicad_sch, kicad_pcb
import fault_report


def test_schematic_netlister_matches_board(dino):
    d = prepare(dino)
    assert any('netlists agree' in n for n in d.notes), d.notes
    assert len(d.components) == 144


def test_netlist_from_schematic_alone_gives_same_findings(dino):
    a, _ = run(prepare(dino), skip=['layout', 'simulation', 'decoupling.per_part'])
    b, _ = run(prepare(dino, netlist_from='sch'), skip=['layout', 'simulation', 'decoupling.per_part'])
    assert sorted(f.title for f in a if f.severity != 'info') == sorted(f.title for f in b if f.severity != 'info')


def test_no_check_crashes_and_models_match(dino):
    d = prepare(dino)
    fs, log = run(d)
    assert not [l for l in log if l[1] == 'crashed'], [l for l in log if l[1] == 'crashed']
    assert not d.unmodelled, [c.ref for c in d.unmodelled]
    # protocol connectivity of the reference board is clean
    assert not [f for f in fs if f.severity == 'error' and f.check.split('.')[0] in ('i2c', 'uart', 'spi', 'led', 'usb', 'sim')]


@pytest.mark.parametrize('fault', fault_report.FAULTS, ids=[f[0] for f in fault_report.FAULTS])
def test_injected_fault_is_flagged(dino, fault):
    rows = fault_report.evaluate(dino, {fault[0]})
    fid, desc, expect, hit, other, new, crashed = rows[0]
    assert not crashed
    assert hit, f"{desc}: expected one of {expect}, new findings: {[(f.check, f.title) for f in new]}"
