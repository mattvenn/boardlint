"""Thin ngspice batch runner."""
from __future__ import annotations
import os
import re
import shutil
import subprocess
import tempfile


def available() -> bool:
    return shutil.which('ngspice') is not None


def run(netlist: str, keep_as: str | None = None, timeout: int = 60):
    """Runs a netlist in batch mode; returns ({measurement: value}, raw stdout)."""
    wd = tempfile.mkdtemp(prefix='boardlint-spice-')
    path = os.path.join(wd, 'sim.cir')
    with open(path, 'w') as f:
        f.write(netlist)
    if keep_as:
        os.makedirs(os.path.dirname(os.path.abspath(keep_as)), exist_ok=True)
        shutil.copy(path, keep_as)
    try:
        p = subprocess.run(['ngspice', '-b', path], capture_output=True, text=True, timeout=timeout, cwd=wd)
    except subprocess.TimeoutExpired:
        return {}, 'timeout'
    out = p.stdout + p.stderr
    meas = {}
    for m in re.finditer(r'^\s*([a-z_][a-z0-9_]*)\s*=\s*([-+0-9.eE]+)', out, re.M):
        try:
            meas[m.group(1)] = float(m.group(2))
        except ValueError:
            pass
    shutil.rmtree(wd, ignore_errors=True)
    return meas, out
