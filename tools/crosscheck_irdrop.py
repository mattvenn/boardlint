#!/usr/bin/env python3
"""Solve point-to-point cases with boardlint's copper extraction, in the form another DC solver
(kicad-irdrop) uses, so the two can be compared: one source part held at 0 V, a current shared
equally between every pad of the load parts on the net.

    python3 tools/crosscheck_irdrop.py <project dir> <cases.json> [--inner-cu MM] [--out result.json]

cases.json: [{"net": "+3V3", "source": "U3", "loads": ["U4"], "amps": 1.0}, ...]
See docs/crosscheck.md.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from boardlint.engine import prepare            # noqa: E402
from boardlint.extract import CopperNet          # noqa: E402


def solve_case(d, c, cache, max_cells=None):
    net = d.nets.get(c['net'])
    if net is None:
        return dict(c, ok=False, error='net not on the board')
    if c['net'] not in cache:
        cache[c['net']] = CopperNet(d, c['net'], max_cells=max_cells)
    cn = cache[c['net']]
    src = [n for p in net.pins if p.comp.ref == c['source'] for n in cn.pin_nodes.get((p.comp.ref, p.number), [])]
    pads = [p for p in net.pins if p.comp.ref in c['loads'] and cn.pin_nodes.get((p.comp.ref, p.number))]
    if not src or not pads:
        return dict(c, ok=False, error='source or load has no pad on the net')
    amps = float(c.get('amps', 1.0))
    reach = cn.reachable(src)
    live = [p for p in pads if cn.pin_nodes[(p.comp.ref, p.number)][0] in reach]
    if not live:
        return dict(c, ok=False, error='no load pad is connected to the source')
    sinks = {}
    for p in live:
        n = cn.pin_nodes[(p.comp.ref, p.number)][0]
        sinks[n] = sinks.get(n, 0.0) + amps / len(live)
    V, _ = cn.solve(src, sinks)
    drops = sorted(((-V[cn.pin_nodes[(p.comp.ref, p.number)][0]] * 1000, f"{p.comp.ref}.{p.number}") for p in live), reverse=True)
    return dict(c, ok=True, worst_mv=drops[0][0], worst_pad=drops[0][1], median_mv=drops[len(drops) // 2][0],
                unreached=[f"{p.comp.ref}.{p.number}" for p in pads if p not in live],
                cells=cn.counts.get('cells', 0), grid=cn.grid, iterations=cn.last_solve['iterations'])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('project')
    ap.add_argument('cases')
    ap.add_argument('--inner-cu', type=float, help='copper thickness of inner layers in mm (default: what boardlint assumes)')
    ap.add_argument('--max-cells', type=int, help='pour mesh budget per net')
    ap.add_argument('--out')
    a = ap.parse_args()
    d = prepare(a.project)
    if a.inner_cu:
        cu = [i for i, l in enumerate(d.board.stackup) if l[1] == 'copper']
        for i in cu[1:-1]:
            name, kind, _, er = d.board.stackup[i]
            d.board.stackup[i] = (name, kind, a.inner_cu, er)
    out, cache = [], {}
    for c in json.load(open(a.cases)):
        t0 = time.time()
        r = solve_case(d, c, cache, a.max_cells)
        r['seconds'] = round(time.time() - t0, 1)
        out.append(r)
        if r['ok']:
            print(f"{c['net']:10s} {c['source']:>5s} -> {'+'.join(c['loads']):10s} worst {r['worst_mv']:8.2f} mV at {r['worst_pad']}"
                  + (f"  not connected: {', '.join(r['unreached'])}" if r['unreached'] else ''))
        else:
            print(f"{c['net']:10s} {c['source']:>5s} -> {'+'.join(c['loads']):10s} {r['error']}")
    if a.out:
        json.dump({'copper_mm': {l[0]: l[2] for l in d.board.stackup if l[1] == 'copper'}, 'cases': out}, open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    main()
