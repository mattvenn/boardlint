"""Copper extraction and line formulas against cases with a known answer."""
import math
import pytest
from boardlint.model import Design, Component, Pin, Net, Board, Track, Via, Zone
from boardlint.kicad_pcb import default_stackup
from boardlint.extract import CopperNet, RHO, resistance_between, ipc2221_amps
from boardlint import tline

T = 0.035


def board(tracks=(), vias=(), zones=(), layers=('F.Cu', 'B.Cu'), pads=()):
    """pads: [(ref, x, y, layers)] all on net N."""
    d = Design(name='t')
    b = Board(tracks=list(tracks), vias=list(vias), zones=list(zones), copper_layers=list(layers))
    b.stackup = default_stackup(list(layers), 1.6, T)
    d.board = b
    n = d.nets['N'] = Net(name='N')
    for ref, x, y, ls in pads:
        c = d.components[ref] = Component(ref=ref, kind='TP')
        p = c.pins['1'] = Pin(comp=c, number='1', net='N', pos=(x, y), layers=ls, size=(1.0, 1.0))
        n.pins.append(p)
    return d


def r_between(d, a, b):
    r, l, cn = resistance_between(d, 'N', d.components[a].pins['1'], d.components[b].pins['1'])
    return r, l, cn


def test_straight_track():
    d = board([Track('N', 'F.Cu', 0, 0, 100, 0, 0.5)], pads=[('A', 0, 0, ('F.Cu',)), ('B', 100, 0, ('F.Cu',))])
    r, l, _ = r_between(d, 'A', 'B')
    assert r == pytest.approx(RHO * 100 / (0.5 * T), rel=1e-3)        # 98.3 mohm
    assert 40 < l < 200                                               # 100 mm with no plane: order of 100 nH


def test_two_layers_in_parallel_through_vias():
    tr = [Track('N', 'F.Cu', 0, 0, 100, 0, 0.5), Track('N', 'B.Cu', 0, 0, 100, 0, 0.5)]
    vias = [Via('N', 0, 0, 0.6, 0.3), Via('N', 100, 0, 0.6, 0.3)]
    d = board(tr, vias, pads=[('A', 0, 0, ('F.Cu',)), ('B', 100, 0, ('F.Cu',))])
    r, _, _ = r_between(d, 'A', 'B')
    one = RHO * 100 / (0.5 * T)
    assert one / 2 < r < one / 2 * 1.05                               # half, plus two via barrels


def test_t_junction_in_the_middle_of_a_track():
    tr = [Track('N', 'F.Cu', 0, 0, 100, 0, 0.5), Track('N', 'F.Cu', 50, 0, 50, 10, 0.25)]
    d = board(tr, pads=[('A', 0, 0, ('F.Cu',)), ('C', 50, 10, ('F.Cu',))])
    r, _, _ = r_between(d, 'A', 'C')
    assert r == pytest.approx(RHO * 50 / (0.5 * T) + RHO * 10 / (0.25 * T), rel=1e-3)


def test_unconnected_pad_is_reported_not_solved():
    d = board([Track('N', 'F.Cu', 0, 0, 10, 0, 0.5)], pads=[('A', 0, 0, ('F.Cu',)), ('B', 50, 50, ('F.Cu',))])
    r, _, cn = r_between(d, 'A', 'B')
    assert r is None
    V, lost = cn.solve(cn.pin_nodes[('A', '1')], {cn.pin_nodes[('B', '1')][0]: 1.0})
    assert lost


def test_zone_sheet_resistance():
    z = Zone('N', 'F.Cu', [[(0, 0), (40, 0), (40, 4), (0, 4)]], bbox=(0, 0, 40, 4))
    d = board(zones=[z], pads=[('A', 2, 2, ('F.Cu',)), ('B', 38, 2, ('F.Cu',))])
    r, _, cn = r_between(d, 'A', 'B')
    uniform = RHO / T * 36 / 4                                        # 4.4 mohm if the current filled the width at once
    assert uniform < r < 2.0 * uniform                                # plus spreading from two small contacts
    assert cn.counts['cells'] > 100


def test_pure_python_solver_agrees(monkeypatch):
    import boardlint.extract as ex
    d = board([Track('N', 'F.Cu', 0, 0, 100, 0, 0.5), Track('N', 'F.Cu', 50, 0, 50, 10, 0.25)],
              pads=[('A', 0, 0, ('F.Cu',)), ('C', 50, 10, ('F.Cu',))])
    a, _, _ = r_between(d, 'A', 'C')
    monkeypatch.setattr(ex, '_np', None)
    b, _, _ = r_between(d, 'A', 'C')
    assert a == pytest.approx(b, rel=1e-6)


def test_microstrip_and_stripline_are_in_the_textbook_range():
    z, e = tline.microstrip(0.35, 0.2, 4.4, T)
    assert 45 < z < 55 and 3.0 < e < 3.6                             # about 50 ohm
    z2, _ = tline.microstrip(0.15, 0.2, 4.4, T)
    assert z2 > z                                                    # narrower = higher
    zs, _ = tline.stripline(0.15, 0.2, 0.2, 4.4, T)
    assert 35 < zs < 60
    assert tline.diff_microstrip(50, 0.2, 0.2) < 100                 # coupling lowers the differential impedance


def test_ipc2221():
    assert 1.0 < ipc2221_amps(0.4, T) < 1.5                          # 0.4 mm, 1 oz, 10 C: about 1.2 A
    assert ipc2221_amps(0.4, T, inner=True) == pytest.approx(ipc2221_amps(0.4, T) / 2)


def test_current_is_conserved_and_ties_do_not_spoil_the_solve():
    # source A feeds two loads through a T; a pad sits on every track end (ties)
    tr = [Track('N', 'F.Cu', 0, 0, 50, 0, 0.3), Track('N', 'F.Cu', 50, 0, 100, 0, 0.3), Track('N', 'F.Cu', 50, 0, 50, 40, 0.2)]
    d = board(tr, pads=[('A', 0, 0, ('F.Cu',)), ('B', 100, 0, ('F.Cu',)), ('C', 50, 40, ('F.Cu',))])
    cn = CopperNet(d, 'N')
    node = lambda r: cn.pin_nodes[(r, '1')][0]
    V, lost = cn.solve([node('A')], {node('B'): 0.3, node('C'): 0.2})
    assert not lost and cn.last_solve['residual'] < 1e-9
    cur = {(round(t.x1), round(t.x2), round(t.y2)): a for a, (_, t, _) in cn.currents(V)}
    assert cur[(0, 50, 0)] == pytest.approx(0.5, rel=1e-6)            # the trunk carries both loads
    assert cur[(50, 100, 0)] == pytest.approx(0.3, rel=1e-6)
    assert cur[(50, 50, 40)] == pytest.approx(0.2, rel=1e-6)
    assert -V[node('B')] == pytest.approx(RHO * 50 / (0.3 * T) * (0.5 + 0.3), rel=1e-6)


def test_custom_pad_takes_its_size_from_the_drawn_shape(tmp_path):
    from boardlint.kicad_pcb import load_board
    f = tmp_path / 'b.kicad_pcb'
    f.write_text("""(kicad_pcb (version 20240108) (general (thickness 1.6)) (layers (0 "F.Cu" signal) (31 "B.Cu" signal))
      (net 0 "") (net 1 "N")
      (footprint "x" (layer "F.Cu") (at 10 10) (property "Reference" "U1")
        (pad "1" smd custom (at 0 0) (size 0.1 0.1) (layers "F.Cu") (net 1 "N")
          (primitives (gr_poly (pts (xy -0.06 -0.4) (xy 0.06 -0.4) (xy 0.06 0.4) (xy -0.06 0.4)) (width 0.08) (fill yes))))))""")
    comps, board_ = load_board(str(f))[:2]
    assert comps['U1'].pins['1'].size == pytest.approx((0.2, 0.88))


def test_small_pour_fragment_still_connects_what_sits_on_it():
    # a 1.5 x 3 mm piece of pour, far smaller than the grid forced by the large zone beside it,
    # is the only thing joining pad A to the track that leads to pad B
    big = Zone('N', 'B.Cu', [[(0, 0), (300, 0), (300, 300), (0, 300)]], bbox=(0, 0, 300, 300))
    frag = Zone('N', 'F.Cu', [[(11.0, 10), (12.4, 10), (12.4, 12.6), (11.0, 12.6)]], bbox=(11.0, 10, 12.4, 12.6))
    d = board([Track('N', 'F.Cu', 11.7, 12.2, 30, 12.2, 0.3)], zones=[big, frag],
              pads=[('A', 11.6, 10.4, ('F.Cu',)), ('B', 30, 12.2, ('F.Cu',))])
    cn = CopperNet(d, 'N', max_cells=20000)          # grid 2.12 mm: no grid point falls in the fragment
    r, _, _ = resistance_between(d, 'N', d.components['A'].pins['1'], d.components['B'].pins['1'], cn)
    assert cn.grid > 2.0 and cn.counts['islands'] == 1
    assert r == pytest.approx(RHO * 18.3 / (0.3 * T), rel=0.05)


def test_pad_on_thermal_relief_joins_the_pour_around_it():
    # the fill has a 0.5 mm gap around the pad (spokes are not in the polygon test point)
    ring = [(0, 0), (20, 0), (20, 20), (0, 20), (0, 0), (9, 9), (9, 11), (11, 11), (11, 9), (9, 9)]
    z = Zone('N', 'F.Cu', [ring], bbox=(0, 0, 20, 20))
    d = board(zones=[z], pads=[('A', 10, 10, ('F.Cu',)), ('B', 2, 2, ('F.Cu',))])
    r, _, _ = r_between(d, 'A', 'B')
    assert r is not None and 0 < r < 0.01
