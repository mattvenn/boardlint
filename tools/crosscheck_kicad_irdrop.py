#!/usr/bin/env python3
"""Run kicad-irdrop's solver (https://github.com/firedanceio/kicad-irdrop) on a list of cases, with a
chosen copper thickness, for comparison with tools/crosscheck_irdrop.py.  See docs/crosscheck.md.

Run it with KiCad's Python, with kicad-irdrop on the path:

    crosscheck_kicad_irdrop.py <board.kicad_pcb> <cases.json> <out.json> <copper mm | default> [grid mm]
"""
import json, sys, time
import pcbnew
from kicad_irdrop.solver import Rail, solve
from kicad_irdrop.stackup import read_stackup, Stackup, Layer

board_path, cases_path, out_path, inner = sys.argv[1:5]
grid = float(sys.argv[5]) if len(sys.argv) > 5 else 0.05
board = pcbnew.LoadBoard(board_path)
cu = [pcbnew.BOARD.GetStandardLayerName(l) for l in board.GetEnabledLayers().CuStack()]
stack = read_stackup(board_path, cu)
if inner != 'default':
    # same assumption as boardlint's default stack-up: every copper layer the given thickness,
    # 0.2 mm outer prepregs on a multilayer board, the rest in the middle
    t = float(inner)
    st = Stackup()
    n = len(cu)
    if n <= 2:
        gaps = [max(1.6 - 2 * t, 0.1)]
    else:
        mid = max(1.6 - n * t - 2 * 0.2, 0.1 * (n - 3)) / max(n - 3, 1)
        gaps = [0.2] + [mid] * (n - 3) + [0.2]
    for k, name in enumerate(cu):
        st.layers.append(Layer(name, 'copper', t))
        if k < n - 1:
            st.layers.append(Layer(f'd{k}', 'assumed', gaps[k], 4.5))
    stack = st
out = []
for c in json.load(open(cases_path)):
    t0 = time.time()
    spec = f"{c['net']}:{c['source']}:{c.get('amps', 1.0)}:{'+'.join(c['loads'])}"
    try:
        r = solve(board, stack, Rail.parse(spec), c.get('grid', grid))
        out.append(dict(c, ok=True, worst_mv=r.worst_mv, worst_pad=r.worst_pad, median_mv=r.median_mv, unreached=r.unreached,
                        vias=r.vias, grid=c.get('grid', grid), seconds=round(time.time() - t0, 1)))
    except Exception as e:
        out.append(dict(c, ok=False, error=f"{type(e).__name__}: {e}", seconds=round(time.time() - t0, 1)))
    print(out[-1], flush=True)
json.dump({'copper_layers': cu, 'copper_mm': {l.name: l.thickness for l in stack.copper}, 'cases': out}, open(out_path, 'w'), indent=1)
