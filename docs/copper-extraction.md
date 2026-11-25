# Copper extraction: resistance, current and impedance from the routed board

This note describes how boardlint turns the copper in a `.kicad_pcb` file into numbers: the
resistance between two pads, the current in each track segment, the voltage lost on the way to each
load, and the impedance and delay of fast nets. It was written by Claude (Anthropic's AI model),
which also wrote the code. None of the numbers below has been compared with a measurement or with
a field solver at the time of writing.

## The problem

Until 2026-11-25 the layout checks used rough figures. Supply resistance was the straight-line
distance between two pads times 1.4, at the average track width. Track current was the whole
net's load against its narrowest segment. I2C bus capacitance was 0.06 pF for every millimetre of
track. These rank problems, but they are wrong in both directions: a net with one thin stub to a
test point was reported as too narrow, and a rail routed the long way round was reported as short.

## What is done now

### 1. The copper of a net becomes a resistor network

`boardlint/extract.py` builds one network per net:

| Copper | In the network |
|---|---|
| Track segment | A resistor, `R = ρ L / (w t)`, with copper resistivity ρ = 1.72 × 10⁻⁵ Ω·mm at 20 °C. A segment is split wherever another track end, a via or a pad lands on it, so T-junctions join |
| Via and through-hole pad | The barrel between each pair of layers it spans: a tube of 20 µm plating around the drill |
| Filled zone (pour) | A square mesh of sheet resistance `ρ / t` per square, made by rasterising the filled polygons that KiCad saved. The mesh pitch is chosen so that a net has about 20 000 cells (6 000 without numpy), and never below 0.4 mm |
| Piece of pour too small to hold a mesh point | One node. Without this, a pad on a small fragment of pour was reported as unconnected (seen on the Density board) |
| Pad | A node on each of its layers. It joins any track end or via within its own size, and pour copper of its net within about 1 mm |

The solve is nodal analysis: the source pad is held at 0 V, each load pad draws its current, and
the node voltages come from a conjugate-gradient solve (numpy if installed, plain Python if not).
Nodes that are the same piece of copper are merged first. An early version tied them with a
0.1 µΩ resistor instead, and on one net the solver stopped before it had converged: it reported a
segment carrying 907 mA on a net whose total load was 811 mA. Every solve now records its residual,
and a unit test checks that the current in a trunk equals the sum of its branches.

### 2. Where the current goes

For each supply net (`boardlint/checks/copper.py`):

- **Source:** the regulator output pin, the fuse, transistor, jumper or diode that feeds the net
  from the rail before it, a module's supply pin, or the connector.
- **Loads:** every part's maximum current from its model, shared between its supply pins, plus
  the total load of anything fed onwards through a regulator, fuse or switch.
- **Return:** the same currents are solved through the ground net, from each load's ground pad
  back to the ground pad of the source (followed upstream through fuses and switches to a part
  that has one).

### 3. Checks that use it

| Check | Reports |
|---|---|
| `layout.ir_drop` | Voltage lost to the worst load on each rail, supply side and ground return. Warning above 3 % of the rail or 100 mV, whichever is larger. Loads with no copper path to the source. Ground in separate pieces |
| `layout.track_current` | The current each segment actually carries against IPC-2221 for a 10 °C rise (inner layers use the inner-layer constant). A warning needs at least 3 mm over the limit; a shorter neck is a note |
| `power.droop` | The ngspice model's series resistance and inductance between the regulator and its largest load now come from the extraction, ground return included |
| `layout.impedance` | See below |
| `i2c.bus` | Bus capacitance from the line model instead of 0.06 pF per millimetre |
| `layout.coupling` | Plane distances from the stack-up instead of board thickness divided by layer count |

### 4. Impedance and delay

`boardlint/tline.py` reads the stack-up and, for each track segment, looks for plane copper (a
filled zone of a ground or supply net) on the layer above and below its midpoint:

- one plane: microstrip, Hammerstad's formulas with the thickness correction
- two planes: offset stripline, the IPC-2141 form
- none: no impedance is given; a typical partial inductance and 0.035 pF/mm are used for delay

From the impedance Z0 and effective permittivity it derives delay, capacitance and inductance per
millimetre. `layout.impedance` then reports, for each fast net:

- A table of length, width, layer, Z0, delay, capacitance and the share of the length over a plane.
- **Electrically long nets.** A trace acts as a transmission line once its one-way delay is more
  than a sixth of the edge's rise time. The length used is the longest pad-to-pad path through
  the copper, not the total routed length. It is a warning for clocks and addressable-LED data
  with no series resistor, and a note for data lines. I2C is left out, because an open-drain bus
  rises through its pull-up in hundreds of nanoseconds.
- **The USB pair.** Length of each line, the mismatch, and the differential impedance where the two
  are routed side by side over a plane (edge-coupled microstrip, IPC-2141 form).

The rise time is an assumption: 2 ns, or 4 ns for full-speed USB. Set it in `boardlint.yaml`:

```yaml
signals: {rise_ns: 1.0}
track: {temp_rise_c: 20}
```

## Evidence

Cases with a known answer (`tests/test_extract.py`, 12 tests):

| Case | Expected | Got |
|---|---|---|
| 100 mm of 0.5 mm track, 35 µm copper | 98.3 mΩ | 98.3 mΩ |
| A 100 mm track doubled on the other layer, joined by a via at each end | half the track, plus the two barrels | equal to 0.1 % |
| A T-junction that lands mid-segment | joined | joined |
| A pad with no copper | no path | no path |
| A 4 mm × 36 mm strip of pour between two small pads | above the 4.4 mΩ of uniform flow, below twice that | between the two |
| Trunk feeding 300 mA and 200 mA branches | 500 mA in the trunk | 500 mA, to six figures |
| Plain-Python solver against numpy | the same | the same |
| Pad on a fragment of pour smaller than the mesh pitch | connected | connected |
| Pad on thermal relief (no fill under its centre) | connected | connected |

On the four test boards, with every load at its model maximum:

| Board | Rail | Load | Lost in the copper | Notes |
|---|---|---|---|---|
| DinoLight `4da182c` (two layers, draft routing) | +BATT | 1269 mA | 140 mV (3.9 %) | Warning. The old estimate could not see this rail: it is fed through a transistor |
| | +3V3 | 356 mA | 55 mV to the ESP32 module | 156 mΩ, 94 nH. The old estimate was 185 mΩ, 212 nH |
| | VLED | 914 mA | 80 mV to the last LED | |
| | GND | | | In separate pieces: 27 parts have no copper return path. The board's own notes say the same ("79 ground items unconnected") |
| | +3V3, BAT_P1 | | | One load on each has no copper path to its source: unrouted at this commit |
| DinoLight, latest (four layers) | +3V3 | 359 mA | 63 mV | 175 mΩ, 44 nH, ground return 2.4 mΩ through 19 526 cells of pour |
| | +BATT, VLED | 1185 mA, 826 mA | 82 mV, 89 mV | 0.4 mm tracks on an inner layer carry 827 mA for 45 mm and 23 mm; IPC-2221 gives 615 mA there |
| ezbldc | +12V | 386 mA | 12 mV | Motor current is not in the model, so the motor rails are not judged |
| Density | +5V | 811 mA | 115 mV (2.3 %) to the furthest LED | A 0.5 mm inner-layer segment carries the whole 811 mA; IPC-2221 gives 723 mA |

Two faults were added to the injection test: the LED supply routed at 0.15 mm (flagged by
`layout.track_current` and `layout.ir_drop`), and the 3.3 V rail at 0.08 mm (`layout.ir_drop`). The
count is now 28 of 28.

A full run takes about 4 to 7 s on these boards with numpy installed. Most of that is the ground
solve: about 20 000 unknowns and 1 000 to 1 300 iterations.

## Limits, at the time of writing

- **The stack-up is assumed on every board tested.** None of the four board files defines one, so
  a four-layer board is taken as 0.2 mm prepreg, a core, 0.2 mm prepreg, with relative
  permittivity 4.5 and 35 µm copper. Every impedance, and every inner-layer resistance, depends
  on this. The report says "assumed" when it is.
- **Direct current only.** No skin effect, and no loop inductance from a field solve. The
  inductance given to the droop model is the per-length figure of each segment weighted by the
  square of its current.
- **Copper at 20 °C.** At 60 °C resistance is 16 % higher.
- **Thermal-relief spokes are not modelled.** A pad is joined to pour of its own net within about
  1 mm. That can report a connection where the spokes were blocked, and it leaves out the
  resistance of the spokes.
- **The pour mesh is coarse** (0.6 to 1.6 mm on the test boards). Narrow necks in a pour are not
  resolved, so the current in a neck is not checked.
- **Pads join by distance from their centre**, using the pad's longer side. A track that ends
  just off the corner of a long pad can be joined when it does not touch.
- **Loads are model maxima** and all at once. Parts without a model draw nothing.
- **Arcs** in tracks are read as straight segments between their ends.
- **Impedance formulas** are good to several per cent for ordinary shapes. They ignore solder
  mask, etch shape and copper beside the track on the same layer. "Over a plane" is judged at the
  midpoint of each segment.
- **Rise time is assumed**, not taken from a driver model. There is no IBIS (input/output buffer
  information specification) simulation and no reflection waveform.
- **Unfilled zones.** If the board was saved without filling its zones there are no polygons to
  mesh, and loads fed through a pour are reported as not joined.

## What would make it better

In rough order of value: read IBIS models for edge rates and simulate the reflection in ngspice
with a lossless line; model thermal spokes from the zone's settings; refine the mesh where the
current density is high; and compare one board against a measurement, which is the step this note
cannot replace.
