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


@check('sync.schematic_board', 'pins', needs_board=True, doc='Schematic and board describe the same design: nets, parts and footprints')
def schematic_board(d):
    s = getattr(d, 'sync', None)
    if not s:
        return
    src = 'board' if getattr(d, 'netlist_source', '') == 'pcb' else 'schematic'
    buses = any('uses buses' in n for n in d.notes)
    if buses and s['net_groups'] and not (s['fp'] or s['only_sch'] or s['only_pcb']):
        yield F('sync.schematic_board', 'info', f"{s['net_groups']} net(s) could not be compared between schematic and board",
                "The schematic passes signals between sheets as buses, which the built-in netlister does not expand, so those "
                "nets look different from the board's. This run uses the board's netlist. KiCad's own schematic-parity "
                "check is the one to trust here.", basis='comparison of the schematic netlist and the board file', confidence='low')
        return
    if s['net_groups'] or s['fp'] or s['only_sch'] or s['only_pcb']:
        bits = []
        if s['net_groups']:
            bits.append(f"{s['net_groups']} net(s) are connected differently" + (" (some of these because buses are not expanded)" if buses else ''))
        if s['fp']:
            bits.append("footprint differs for " + ', '.join(f"{r} (schematic {a.split(':')[-1]}, board {b.split(':')[-1]})" for r, a, b in s['fp'][:6])
                        + ('...' if len(s['fp']) > 6 else ''))
        if s['only_sch']:
            bits.append(f"in the schematic only: {', '.join(s['only_sch'][:12])}{'...' if len(s['only_sch']) > 12 else ''}")
        if s['only_pcb']:
            bits.append(f"on the board only: {', '.join(s['only_pcb'][:12])}{'...' if len(s['only_pcb']) > 12 else ''}")
        yield F('sync.schematic_board', 'warning', "The board is out of step with the schematic",
                '; '.join(bits) + f". This run uses the {src}'s netlist"
                + (" (pass --netlist-from sch to check the schematic instead)" if src == 'board' else
                   "; layout findings below describe the old board") + ". Update the board from the schematic "
                "before trusting either set of results for the other.",
                refs=[r for r, _, _ in s['fp']][:6] + s['only_sch'][:6] + s['only_pcb'][:6],
                basis='comparison of the schematic netlist, footprint fields and the board file', confidence='high')


@check('bom.value_mpn', 'pins', doc='The value written on a resistor or capacitor agrees with what its manufacturer part number says')
def value_mpn(d):
    from ..classify import mpn_value, fmt_r, fmt_c
    bad = {}
    for c in d.components.values():
        if c.kind not in ('R', 'C') or c.num is None:
            continue
        mv = mpn_value(c)
        if mv is None:
            continue
        v, mpn = mv
        if abs(v - c.num) > 0.02 * max(abs(v), abs(c.num), 1e-15):
            bad.setdefault((c.kind, c.value, mpn, v), []).append(c.ref)
    for (kind, value, mpn, v), refs in sorted(bad.items()):
        says = fmt_c(v) if kind == 'C' else fmt_r(v)
        refs = sorted(refs)
        yield F('bom.value_mpn', 'warning', f"{', '.join(refs[:6])}{'...' if len(refs) > 6 else ''}: the value says {value}, the part number {mpn} is {says}",
                f"The part number is what gets ordered and fitted; the value field is what a reader, and every "
                f"calculation in this report, goes by. One of the two is out of date.",
                refs=refs[:8], evidence={'value_field': value, 'part_number': mpn, 'part_number_decodes_to': says},
                basis='value codes in the part numbers of common resistor and capacitor series', confidence='medium')


@check('parts.no_model', 'pins', doc='Parts that have no part model, so only name-based rules were applied to them')
def no_model(d):
    miss = sorted((c for c in d.components.values() if not c.dnp and not c.model and c.kind in ('IC', 'Q')
                   and not c.ref.startswith(('carrier/STITCH', 'STITCH'))), key=lambda c: c.ref)
    if not miss:
        return
    kinds = {}
    for c in miss:
        kinds.setdefault(c.value or c.ref, []).append(c.ref)
    # a warning only when something with a supply pin is unmodelled; switches and encoders drawn as ICs are a note
    ics = [c for c in miss if c.kind == 'IC' and any(p.etype == 'power_in' or re.match(r'^(VCC|VDD|VIN|V\+|VS|AVDD|DVDD|VBAT)', p.name or '', re.I)
                                                     for p in c.pins.values())]
    yield F('parts.no_model', 'warning' if ics else 'info',
            f"{len(kinds)} kind(s) of part have no model: {', '.join(list(kinds)[:6])}{'...' if len(kinds) > 6 else ''}",
            "For these, supply ranges, pin limits, required connections, bus addresses and decoupling were not checked: "
            "only rules that work from pin names ran. " +
            '; '.join(f"{v} ({', '.join(r[:4])}{'...' if len(r) > 4 else ''})" for v, r in list(kinds.items())[:12]) +
            ". To add one: take the datasheet, the prompt in tools/extract_prompt.md and an existing model as an example, "
            "have an LLM write the YAML, check it, and pass its folder with --parts-dir. Steps: docs/adding-parts.md "
            "(https://github.com/mattvenn/boardlint/blob/main/docs/adding-parts.md).",
            refs=[c.ref for c in miss[:8]], basis='the part library and --parts-dir', confidence='high')
