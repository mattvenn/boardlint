"""Helpers shared by the checks."""
from __future__ import annotations
from ..model import Design, Pin, Component
from ..classify import signal_group, group_pins, pulls, is_series_part
from ..power import supply_net_of

PASSIVE_KINDS = ('R', 'C', 'L', 'FB', 'TP', 'JUMPER', 'MECH', 'FUSE', 'D')


def role_groups(d: Design, roles):
    """Signal groups (nets joined through series parts) that contain a pin with one of ``roles``.
    Yields (frozenset of net names, [pins in the group, series parts excluded], [series parts])."""
    seen = set()
    for c in d.components.values():
        if c.dnp:
            continue
        for p in c.pins.values():
            if p.role in roles and p.net and p.net not in seen:
                nets, through = signal_group(d, p.net)
                seen |= nets
                yield frozenset(nets), group_pins(d, nets), through


def is_controller_pin(p: Pin) -> bool:
    """A pin that could be the host side of a bus: MCU GPIO, or a connector pin (off-board host)."""
    if p.role == 'gpio' or p.role.startswith('spi_ctrl') or p.comp.kind == 'CONN' or \
            (p.comp.model or {}).get('class') in ('mcu', 'mcu_module'):
        return True
    # no model: a general-purpose pin of some IC may well be the host
    return p.comp.kind == 'IC' and not p.comp.model and not p.role and p.etype in ('bidirectional', 'output', 'tri_state', '', 'unspecified')


def is_active_pin(p: Pin) -> bool:
    return p.comp.kind not in PASSIVE_KINDS and p.comp.kind != 'SW'


def can_drive(p: Pin) -> bool:
    if p.comp.kind in PASSIVE_KINDS or p.comp.kind in ('SW', 'CONN'):
        return False
    drv = p.spec.get('drive')
    if drv:
        return drv in ('push_pull', 'tri_state')
    if p.role in ('gpio', 'uart_tx', 'spi_sdo', 'led_dout', 'spi_mosi', 'spi_ctrl_sck', 'spi_ctrl_cs'):
        return True
    return p.etype in ('output', 'bidirectional', 'tri_state')


def supply_v(d: Design, c: Component):
    """(vmin, vmax, net name) of the rail powering a part, or None."""
    n = supply_net_of(d, c)
    if n is None or n.vmin is None:
        return None
    if not (c.model and c.model.get('supplies')):
        rails = {q.net for q in c.pins.values() if q.etype == 'power_in' and q.net and not d.nets[q.net].is_ground}
        levels = {(d.nets[r].vmin, d.nets[r].vmax) for r in rails}
        if len(levels) > 1:
            return None          # level shifter, FPGA with several I/O banks...: cannot tell without a model
    return n.vmin, n.vmax, n.name


def io(c: Component, pin: Pin, key, default=None):
    """Per-pin electrical value with fall-back to the part's io defaults."""
    if key in pin.spec:
        return pin.spec[key]
    return ((c.model or {}).get('io') or {}).get(key, default)


def names(pins):
    return ', '.join(p.label for p in pins)


def dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def model_basis(c: Component, what=''):
    m = c.model or {}
    prov = m.get('provenance') or {}
    tag = 'verified against datasheet' if prov.get('verified') else 'NOT verified against datasheet'
    return f"part model {m.get('_file', '?')} ({tag}){': ' + what if what else ''}"
