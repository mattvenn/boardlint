"""Fault injection: edit a loaded design in memory the way a schematic mistake would, then re-run
the checks.  Used by the test-suite and by ``tools/fault_report.py`` to measure what is caught."""
from __future__ import annotations
from .model import Design, Component, Pin, Net
from .classify import classify_components, guess_role, parse_value
from .power import analyse_power


def move_pin(d: Design, pin: Pin, net):
    if pin.net and pin.net in d.nets:
        d.nets[pin.net].pins = [p for p in d.nets[pin.net].pins if p is not pin]
    pin.net = net
    if net:
        d.nets.setdefault(net, Net(name=net)).pins.append(pin)


def swap_nets(d: Design, a: Pin, b: Pin):
    na, nb = a.net, b.net
    move_pin(d, a, nb)
    move_pin(d, b, na)


def pin(d: Design, ref: str, name: str) -> Pin:
    c = d.components[ref]
    for p in c.pins.values():
        if p.number == name or p.name == name or name in p.name.replace('~{', '').replace('}', '').split('/'):
            return p
    raise KeyError(f"{ref} has no pin {name}")


def remove(d: Design, ref: str):
    c = d.components.pop(ref)
    for p in c.pins.values():
        if p.net and p.net in d.nets:
            d.nets[p.net].pins = [q for q in d.nets[p.net].pins if q is not p]


def set_value(d: Design, ref: str, value: str):
    c = d.components[ref]
    c.value = value
    c.num = parse_value(value, c.kind)


def add_part(d: Design, ref: str, value: str, pins: dict, kind='IC'):
    """pins: {number: (name, etype, net)}"""
    c = Component(ref=ref, value=value, kind=kind)
    for num, (name, etype, net) in pins.items():
        p = Pin(comp=c, number=str(num), name=name, etype=etype)
        c.pins[str(num)] = p
        move_pin(d, p, net)
        p.role = guess_role(p)
    d.components[ref] = c
    from .library import load_models, apply_models
    shim = Design(components={ref: c})
    apply_models(shim, load_models())
    return c


def reanalyse(d: Design):
    for n in d.nets.values():
        n.is_ground = n.is_power = False
        n.vmin = n.vmax = None
        n.vsrc = ''
        for attr in ('divider', 'feeds_from'):
            if hasattr(n, attr):
                delattr(n, attr)
    d.nets = {k: v for k, v in d.nets.items() if v.pins}
    analyse_power(d)
    return d
