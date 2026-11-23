"""Tool-independent design model that every check works on."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Pin:
    comp: "Component"
    number: str
    name: str = ""              # pin function from the symbol, e.g. "SDA", "IO47"
    etype: str = ""             # KiCad electrical type: input, output, power_in, ...
    net: Optional[str] = None   # None = no pad / not connected
    role: str = ""              # filled by the library/classifier: i2c_sda, uart_tx, ...
    spec: dict = field(default_factory=dict)   # per-pin data from the part model
    pos: Optional[tuple] = None  # absolute pad centre on the board (mm)
    layers: tuple = ()

    @property
    def id(self) -> str:
        return f"{self.comp.ref}.{self.number}"

    @property
    def label(self) -> str:
        n = self.name if self.name and self.name != "~" and self.name != self.number else ""
        return f"{self.comp.ref}.{self.number}" + (f"({n})" if n else "")


@dataclass
class Component:
    ref: str
    value: str = ""
    footprint: str = ""
    lib_id: str = ""
    props: dict = field(default_factory=dict)
    pins: dict = field(default_factory=dict)     # number -> Pin
    dnp: bool = False
    pos: Optional[tuple] = None                  # board position (mm)
    side: str = ""                               # "F" / "B"
    kind: str = ""          # R, C, L, FB, D, LED, Q, IC, CONN, SW, FUSE, TP, JUMPER, XTAL, ...
    num: Optional[float] = None                  # parsed value of a passive (ohm / farad / henry)
    model: Optional[dict] = None                 # matched part model (YAML)
    sheet: str = ""

    @property
    def prefix(self) -> str:
        return self.ref.rstrip("0123456789?")

    def pin_by_name(self, name: str):
        return [p for p in self.pins.values() if p.name == name]

    def other_pin(self, pin: Pin) -> Optional[Pin]:
        """For a two-terminal part, the pin that is not ``pin``."""
        others = [p for p in self.pins.values() if p is not pin]
        return others[0] if len(self.pins) == 2 and others else None

    @property
    def desc(self) -> str:
        return f"{self.ref} ({self.value})" if self.value else self.ref


@dataclass
class Net:
    name: str
    pins: list = field(default_factory=list)
    # filled by power analysis
    is_ground: bool = False
    is_power: bool = False
    vmin: Optional[float] = None
    vmax: Optional[float] = None
    vsrc: str = ""            # how the voltage was inferred (for the report)

    @property
    def vnom(self) -> Optional[float]:
        if self.vmin is None or self.vmax is None:
            return None
        return (self.vmin + self.vmax) / 2


@dataclass
class Track:
    net: str
    layer: str
    x1: float
    y1: float
    x2: float
    y2: float
    width: float

    @property
    def length(self) -> float:
        return ((self.x2 - self.x1) ** 2 + (self.y2 - self.y1) ** 2) ** 0.5


@dataclass
class Via:
    net: str
    x: float
    y: float
    size: float
    drill: float


@dataclass
class Zone:
    net: str
    layer: str
    polys: list            # list of [(x, y), ...] filled polygons
    bbox: tuple = (0, 0, 0, 0)


@dataclass
class Board:
    tracks: list = field(default_factory=list)
    vias: list = field(default_factory=list)
    zones: list = field(default_factory=list)
    copper_layers: list = field(default_factory=list)
    thickness: float = 1.6
    copper_um: float = 35.0
    path: str = ""


@dataclass
class Design:
    name: str = ""
    components: dict = field(default_factory=dict)   # ref -> Component
    nets: dict = field(default_factory=dict)         # name -> Net
    board: Optional[Board] = None
    config: dict = field(default_factory=dict)
    sources: list = field(default_factory=list)
    notes: list = field(default_factory=list)        # loader warnings

    def net_of(self, pin: Pin) -> Optional[Net]:
        return self.nets.get(pin.net) if pin.net else None

    def comps(self, *kinds):
        return [c for c in self.components.values() if c.kind in kinds and not c.dnp]


SEVERITIES = ("error", "warning", "info")


@dataclass
class Finding:
    check: str                 # check id, e.g. "i2c.pullup_missing"
    severity: str              # error | warning | info
    title: str
    detail: str = ""
    refs: list = field(default_factory=list)
    nets: list = field(default_factory=list)
    evidence: dict = field(default_factory=dict)   # numbers the conclusion rests on
    basis: str = ""            # where the rule comes from: datasheet, model file, heuristic
    confidence: str = "medium"  # high: follows from netlist + verified data; low: heuristic

    def key(self):
        return (SEVERITIES.index(self.severity), self.check, self.title)
