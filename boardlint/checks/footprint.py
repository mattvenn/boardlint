"""Symbol against footprint, and polarity of polarised parts."""
from __future__ import annotations
import re
from . import check, F
from .common import model_basis

_MECH = re.compile(r'^(MP|SH|S\d*|SHIELD|EP|PAD|MH\d*|NC\d*|G\d*|)$', re.I)


@check('footprint.pin_map', 'pins', needs_board=True,
       doc='Every symbol pin has a pad of the same number, and every numbered pad has a pin')
def pin_map(d):
    for c in d.components.values():
        sp, fp = c.props.get('_sch_pins'), c.props.get('_fp_pads')
        if sp is None or fp is None or c.dnp:
            continue
        missing = [n for n in sp if n not in fp]
        extra = [n for n in fp if n not in sp and not _MECH.match(n)]
        if missing:
            wired = [n for n in missing if c.pins[n].name or True]
            yield F('footprint.pin_map', 'error', f"{c.ref}: symbol pin(s) {', '.join(missing[:8])} have no pad on the footprint",
                    f"{c.desc}, symbol {c.lib_id}, footprint {c.footprint}. Footprint pads: {', '.join(fp[:12])}"
                    f"{'...' if len(fp) > 12 else ''}. The symbol and footprint number their pins differently, or the "
                    f"wrong footprint is assigned: those pins are not connected on the board.",
                    refs=[c.ref], basis='pin numbers in the schematic symbol against pad numbers in the board file',
                    confidence='high')
        if extra:
            yield F('footprint.pin_map', 'warning' if len(extra) <= max(2, len(fp) // 2) and c.kind != 'CONN' else 'info',
                    f"{c.ref}: footprint pad(s) {', '.join(extra[:8])} have no pin on the symbol",
                    f"{c.desc}, symbol {c.lib_id}, footprint {c.footprint}. They are unconnected on the board. Fine "
                    f"for mounting tabs; a mistake if the part has a function there (exposed pad, second row).",
                    refs=[c.ref], basis='pin numbers in the schematic symbol against pad numbers in the board file',
                    confidence='medium')


@check('polarity.polarised_parts', 'ratings', doc='Polarised capacitors have their + terminal on the higher rail')
def polarised(d):
    for c in d.components.values():
        if c.dnp or c.kind != 'C' or len(c.pins) != 2:
            continue
        plus = [p for p in c.pins.values() if p.name in ('+', 'A', 'P')]
        minus = [p for p in c.pins.values() if p.name in ('-', 'K', 'N')]
        if 'polar' not in c.lib_id.lower() and not (plus and minus):
            continue
        if not plus:
            plus = [c.pins['1']] if '1' in c.pins else []
            minus = [p for p in c.pins.values() if p not in plus]
        if not plus or not minus:
            continue
        np_, nm = d.net_of(plus[0]), d.net_of(minus[0])
        if np_ is None or nm is None:
            continue
        vp = 0.0 if np_.is_ground else np_.vmin
        vm = 0.0 if nm.is_ground else nm.vmax
        if vp is None or vm is None:
            continue
        if vp < vm - 1e-6:
            yield F('polarity.polarised_parts', 'error', f"{c.ref} is reverse-biased: + on {np_.name}, - on {nm.name}",
                    f"{c.desc}: the + terminal sits at {vp:g} V and the - terminal at up to {vm:g} V. Polarised "
                    f"capacitors fail, sometimes violently, when reversed.", refs=[c.ref], nets=[np_.name, nm.name],
                    basis='pin names of the polarised symbol against rail voltages', confidence='high')
