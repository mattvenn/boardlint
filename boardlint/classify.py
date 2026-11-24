"""Heuristics that need no part model: component kinds, passive values, pin roles, net helpers."""
from __future__ import annotations
import re
from .model import Design, Component, Pin

_PREFIX_KIND = {
    'R': 'R', 'RN': 'R', 'C': 'C', 'L': 'L', 'FB': 'FB', 'D': 'D', 'LED': 'LED', 'Q': 'Q', 'T': 'Q',
    'U': 'IC', 'IC': 'IC', 'J': 'CONN', 'P': 'CONN', 'CN': 'CONN', 'X': 'CONN', 'SW': 'SW', 'S': 'SW',
    'BTN': 'SW', 'F': 'FUSE', 'TP': 'TP', 'JP': 'JUMPER', 'SJ': 'JUMPER', 'Y': 'XTAL', 'H': 'MECH',
    'MH': 'MECH', 'FID': 'MECH', 'BT': 'BATT', 'E': 'TP', 'A': 'IC', 'M': 'IC', 'RV': 'R', 'TH': 'R',
}
_MULT = {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'µ': 1e-6, 'μ': 1e-6, 'm': 1e-3, 'k': 1e3, 'K': 1e3,
         'M': 1e6, 'meg': 1e6, 'G': 1e9, 'R': 1.0, 'r': 1.0, 'E': 1.0, '': 1.0}
_VAL = re.compile(r'^\s*(\d+(?:[.,]\d+)?)\s*(meg|[pnuµμmkKMGRrE]?)\s*(\d*)\s*(?:ohms?|Ω|F|H)?\b', re.I)


def parse_value(text: str, kind: str):
    """'4k7' -> 4700.0, '100nF' -> 1e-7, '0R' -> 0.0.  None if it does not parse."""
    if not text:
        return None
    t = text.strip().replace('Ω', 'R')
    m = re.match(r'^\s*(\d+(?:[.,]\d+)?)\s*(meg|[pnuµμmkKMGRrE]?)(\d*)', t)
    if not m:
        return None
    num, unit, frac = m.group(1).replace(',', '.'), m.group(2), m.group(3)
    if unit.lower() == 'meg':
        unit = 'M'
    if frac and '.' not in num:
        num = num + '.' + frac            # 4k7 notation
    if kind == 'R' and unit == 'm':
        mult = 1e-3
    elif kind in ('C', 'L') and unit in ('R', 'r', 'E', 'k', 'K', 'M', 'G'):
        return None
    elif kind == 'C' and unit == '':
        v = float(num)
        return v * 1e-12 if v >= 1 else v * 1e-6    # bare '100' on a cap is pF, '0.1' is uF
    else:
        mult = _MULT.get(unit, 1.0)
    return float(num) * mult


def parse_voltage_rating(c: Component):
    for k in ('Voltage', 'voltage', 'Vrated', 'Rating'):
        if k in c.props:
            m = re.search(r'(\d+(?:\.\d+)?)\s*V', c.props[k])
            if m:
                return float(m.group(1))
    m = re.search(r'(?<![\d.])(\d+(?:\.\d+)?)\s*V\b', c.value)
    return float(m.group(1)) if m else None


def package_of(c: Component):
    m = re.search(r'_(01005|0201|0402|0603|0805|1206|1210|1812|2010|2512)_', c.footprint + '_')
    return m.group(1) if m else None


def fmt_r(v):
    if v is None:
        return '?'
    for m, s in ((1e6, 'M'), (1e3, 'k')):
        if v >= m:
            return f"{v / m:g}{s}"
    return f"{v:g}R"


def fmt_c(v):
    if v is None:
        return '?'
    for m, s in ((1e-6, 'uF'), (1e-9, 'nF'), (1e-12, 'pF')):
        if v >= m * 0.999:
            return f"{v / m:g}{s}"
    return f"{v:g}F"


def classify_components(d: Design):
    for c in d.components.values():
        lib = c.lib_id.lower()
        part = lib.split(':')[-1]
        kind = _PREFIX_KIND.get(c.prefix.upper(), '')
        if 'testpoint' in lib:
            kind = 'TP'
        elif 'solderjumper' in lib or part.startswith('jumper'):
            kind = 'JUMPER'
        elif lib.startswith('device:') and part.split('_')[0] in ('r', 'c', 'l', 'd', 'led'):
            kind = {'r': 'R', 'c': 'C', 'l': 'L', 'd': 'D', 'led': 'LED'}[part.split('_')[0]]
        elif 'polyfuse' in lib or part.startswith('fuse'):
            kind = 'FUSE'
        elif 'ferritebead' in lib or part.startswith('fb'):
            kind = 'FB'
        elif 'mountinghole' in lib or 'fiducial' in lib:
            kind = 'MECH'
        elif part.startswith('crystal') or part.startswith('resonator'):
            kind = 'XTAL'
        elif lib.startswith(('oscillator:', 'clock:')) or re.match(r'^(sit\d|asfl|ase-|asdm|dsc\d|sg-\d|ecs-.*osc|osc)', part):
            kind = 'OSC'
        if not kind:
            kind = 'IC' if len(c.pins) > 3 else 'OTHER'
        c.kind = kind
        if kind in ('R', 'C', 'L', 'FB'):
            c.num = parse_value(c.value, 'R' if kind == 'FB' else kind)
        if kind == 'JUMPER':
            c.props['_bridged'] = _jumper_bridges(c)


def split_resistor_packs(d: Design):
    """A resistor network becomes one two-pin resistor per element, so every check sees plain resistors."""
    for c in list(d.components.values()):
        if c.kind != 'R' or len(c.pins) <= 2 or len(c.pins) % 2:
            continue
        pins = list(c.pins.values())
        pairs = {}
        named = [re.match(r'^R(\d+)\.([12])$', p.name or '') for p in pins]
        if all(named):
            for p, m in zip(pins, named):
                pairs.setdefault(m.group(1), []).append(p)
        elif all(p.number.isdigit() for p in pins):
            n = len(pins)
            byn = {int(p.number): p for p in pins}
            for i in range(1, n // 2 + 1):
                if i in byn and (n + 1 - i) in byn:
                    pairs[str(i)] = [byn[i], byn[n + 1 - i]]
        if len(pairs) * 2 != len(pins) or any(len(v) != 2 for v in pairs.values()):
            continue
        del d.components[c.ref]
        for k, (a, b) in sorted(pairs.items()):
            sub_ = Component(ref=f"{c.ref}.{k}", value=c.value, footprint=c.footprint, lib_id=c.lib_id, props=dict(c.props),
                             dnp=c.dnp, pos=c.pos, side=c.side, kind='R', num=c.num, sheet=c.sheet)
            for i, p in enumerate((a, b), 1):
                p.comp = sub_
                sub_.pins[str(i)] = p
                p.name = ''
            d.components[sub_.ref] = sub_


def _jumper_bridges(c: Component):
    """Pairs of pin numbers a jumper connects in its as-built state."""
    name = (c.lib_id + ' ' + c.footprint)
    m = re.search(r'Bridged(\d+)', name)
    if m:
        digs = m.group(1)
        pairs = [(digs[i], digs[i + 1]) for i in range(0, len(digs) - 1, 2)]
        return pairs
    if re.search(r'Bridged|Closed', name) and len(c.pins) == 2:
        return [tuple(c.pins.keys())]
    return []


_GND = re.compile(r'^/?(?:.*/)?(?:[ADP]?GND[A-Z0-9_]*|GNDREF|VSS[A-Z]?|0V|EARTH|PGND|AGND|DGND)$', re.I)


def is_ground_name(name: str) -> bool:
    return bool(name and _GND.match(name))


def norm_pin_name(name: str) -> str:
    """'~{CS}' -> 'CS', 'V_{DD}' -> 'VDD'."""
    n = re.sub(r'~\{([^}]*)\}', r'\1', name or '')
    n = re.sub(r'[_^]\{([^}]*)\}', r'\1', n)
    n = re.sub(r'\[\d+\]$', '', n)              # 'GND[27]' style pin stacks
    return n.replace('~', '').strip().upper()


def pin_aliases(name: str):
    n = norm_pin_name(name)
    out = {n}
    out.update(a for a in re.split(r'[/|,]', n) if a)
    return out


# pin-name role guesses for parts that have no model.  Order matters.
_ROLE_PATTERNS = [
    ('i2c_sda', r'^(I2C\d*_?)?SDA\d*$|^SDI/SDA$|^SDA/SDI.*$'),
    ('i2c_scl', r'^(I2C\d*_?)?SCL\d*$|^SCK/SCL$|^SCL/SPC$'),
    ('uart_tx', r'^(U?S?ART\d*_?)?TXD?\d*$|^U\d*TXD?$|^TXD?\d*/.*$|^TXO$|^TX_?OUT$'),
    ('uart_rx', r'^(U?S?ART\d*_?)?RXD?\d*$|^U\d*RXD?$|^RXD?\d*/.*$|^RXI$|^RX_?IN$'),
    ('spi_sck', r'^(Q?SPI\d*_?)?(SCK|SCLK|SPC|CLK)$'),
    ('spi_mosi', r'^(SPI\d*_?)?(MOSI|COPI|PICO)\d*$'),           # the controller-out line, whoever owns the pin
    ('spi_miso', r'^(SPI\d*_?)?(MISO|CIPO|POCI)\d*$'),           # the controller-in line
    ('spi_sdi', r'^(SPI\d*_?)?(SDI|DI|SI)$'),                    # data INTO this part
    ('spi_sdo', r'^(SPI\d*_?)?(SDO|DO|SO)$'),                    # data OUT of this part
    ('spi_cs', r'^(SPI\d*_?)?(N?CS|N?SS|CSN|CSB|N?CE|NSS)\d*$'),
    ('usb_dp', r'^(USB_?)?D(P|\+)\d*$|^USB_D\+$'),
    ('usb_dm', r'^(USB_?)?D(M|N|-)\d*$|^USB_D-$'),
    ('led_din', r'^(DIN|DI|SDI|DATA_?IN)$'),
    ('led_dout', r'^(DOUT|DO|SDO|DATA_?OUT)$'),
    ('enable', r'^(EN|CE|ENABLE|SHDN|N?SHUTDOWN|ON/OFF|CHIP_PU|EN/UVLO)\d*$'),
    ('reset', r'^(N?RE?SE?T|NRST|MCLR|RESETN?|RST_?N)$'),
]
_ROLE_RE = [(r, re.compile(p, re.I)) for r, p in _ROLE_PATTERNS]


def guess_role(pin: Pin) -> str:
    c = pin.comp
    is_led = bool(re.search(r'SK68|WS28|APA10|SK98|NEOPIX|LC8812|XL-?\d+RGB', (c.value + ' ' + c.lib_id), re.I))
    for alias in sorted(pin_aliases(pin.name), key=len, reverse=True):
        for role, rx in _ROLE_RE:
            if rx.match(alias):
                if role.startswith('led_') and not is_led:
                    continue
                if is_led and role in ('spi_sdi', 'spi_sdo'):
                    role = 'led_din' if role == 'spi_sdi' else 'led_dout'
                if role in ('spi_sdi', 'spi_sdo') and alias in ('DI', 'DO', 'SI', 'SO') and c.kind != 'IC':
                    continue
                return role
    return ''


def is_series_part(c: Component, max_ohm: float = 1000.0) -> bool:
    """Parts a signal passes through: small series R, ferrite, 0R link, closed 2-pin jumper."""
    if c.dnp or len(c.pins) != 2:
        return False
    if c.kind == 'R':
        return c.num is not None and c.num <= max_ohm
    if c.kind == 'FB':
        return True
    if c.kind == 'JUMPER':
        return bool(c.props.get('_bridged'))
    return False


def signal_group(d: Design, net_name: str, max_ohm: float = 1000.0):
    """Nets joined to ``net_name`` through series parts.  Returns (set of net names, [series comps])."""
    seen, todo, through = {net_name}, [net_name], []
    while todo:
        n = d.nets.get(todo.pop())
        if n is None or n.is_ground or n.is_power:
            continue
        for p in n.pins:
            c = p.comp
            links = (c.model or {}).get('internal_links') if c.model else None
            if links and not c.dnp:
                for grp in links:
                    members = [q for q in c.pins.values() if ('#' + q.number) in grp or q.name in grp]
                    if p in members:
                        for q in members:
                            if q.net and q.net not in seen and not (d.nets[q.net].is_ground or d.nets[q.net].is_power):
                                seen.add(q.net)
                                todo.append(q.net)
                                if c not in through:
                                    through.append(c)
            if is_series_part(c, max_ohm):
                o = c.other_pin(p)
                if o and o.net and o.net not in seen:
                    on = d.nets.get(o.net)
                    if on and (on.is_ground or on.is_power):
                        continue
                    seen.add(o.net)
                    todo.append(o.net)
                    through.append(c)
    return seen, through


def group_pins(d: Design, nets, skip_series=True):
    out = []
    for n in nets:
        for p in d.nets[n].pins:
            if skip_series and is_series_part(p.comp):
                continue
            out.append(p)
    return out


def pulls(d: Design, net_name: str):
    """Resistors from this net (or its series group) to a rail.  Returns (pullups, pulldowns) as
    lists of (Component, rail Net)."""
    ups, downs = [], []
    nets, _ = signal_group(d, net_name)
    for nn in nets:
        for p in d.nets[nn].pins:
            c = p.comp
            if c.kind != 'R' or c.dnp or len(c.pins) != 2 or c.num is None:
                continue
            o = c.other_pin(p)
            on = d.nets.get(o.net) if o and o.net else None
            if on is None or on.name in nets:
                continue
            if on.is_ground:
                downs.append((c, on))
            elif on.is_power:
                ups.append((c, on))
    return ups, downs


def caps_to_ground(d: Design, net_name: str):
    out = []
    n = d.nets.get(net_name)
    for p in (n.pins if n else []):
        c = p.comp
        if c.kind == 'C' and not c.dnp and len(c.pins) == 2:
            o = c.other_pin(p)
            on = d.nets.get(o.net) if o and o.net else None
            if on is not None and on.is_ground:
                out.append((c, p))
    return out


_ANALOG_TOKEN = re.compile(r'^(SENSE?|[VI]SENSE?|SNS|ADC\d*|[A-Z]{0,5}MON|MEAS|AIN\d*|VREF|NTC\d*|TEMP|THERM|POT\d*|MIC|AUDIO)$', re.I)


_DIGITAL_TOKEN = re.compile(r'^(SCK|SCLK|CLK|MISO|MOSI|SDI|SDO|DIN|DOUT|CS\d*|NCS|SS|SDA|SCL|TX|RX|TXD|RXD|IRQ|INT\d*|DRDY|EN|RST|RESET)$', re.I)


def is_analog_name(net_name: str) -> bool:
    """True when a net is named like a measurement node (VBAT_SENSE, ADC1, NTC).  Whole tokens only:
    'Net-(U1-PadC3)' and 'MAIN_EN' must not match."""
    base = (net_name or '').split('/')[-1]
    if base.startswith('Net-('):
        return False
    tokens = [t for t in re.split(r'[^A-Za-z0-9]+', base) if t]
    if any(_DIGITAL_TOKEN.match(t) for t in tokens):
        return False                 # ADC_SCK, ADC_MISO: the SPI lines of an ADC
    return any(_ANALOG_TOKEN.match(t) for t in tokens)
