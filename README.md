# boardlint

Design-review checks for KiCad projects, beyond ERC and DRC.

ERC checks pin types and DRC checks clearances. boardlint checks what the board is *for*: that TX
meets RX, that the I2C bus has pull-ups of a sensible value and no two parts at one address, that
the first addressable LED sees a logic high, that each part gets the decoupling and the supply
voltage its datasheet asks for, that the 3.3 V rail survives the radio's transmit burst, and that
the LED data line does not run alongside a touch electrode.

Status: v0.1, a working framework. 34 checks, 26 part models. Tested on two real boards (one with 26 injected faults, all flagged; one
with a published errata list, both wiring errata found) and on eight public projects with a known fix
commit (six flagged before the fix; the other two cannot be seen in the design files). Read [docs/PROPOSAL.md](docs/PROPOSAL.md) for the design and the roadmap.

## Quick start

```bash
pip install -e .            # needs Python 3.10+ and PyYAML
```

```bash
boardlint check path/to/project            # text summary; exit code 1 if there are errors
```

```bash
boardlint check path/to/project -f md -o review.md     # full report with evidence tables
```

```bash
boardlint parts path/to/project            # which part model matched each component
```

```bash
boardlint rails path/to/project            # supply rails and how each voltage was inferred
```

The simulation checks need `ngspice` and `iverilog` on the path (`apt install ngspice iverilog`).
Without them those checks are skipped and the report says so. KiCad itself is not needed.

## What it checks

| Family | What |
|---|---|
| Protocol | UART TX/RX direction; I2C SDA/SCL crossing, pull-up presence and value (3 mA limit, rise time), pull-up rail against each device's pin limit, address clashes from the strap wiring; SPI MOSI/MISO swaps, undriven clocks, shared chip selects; addressable-LED chain direction, undriven or doubly-driven inputs, logic level at the first LED; USB D+/D- swaps and Type-C CC resistors |
| Signals at MCU / FPGA pins | an audit of every used pin: what arrives there and whether the pin can do it. Analog signals on pins with no ADC (or only the radio-shared ADC2 on ESP32), interrupts on pins that cannot wake the part, signals arriving at pins the design cannot read (ECP5 `CCLK`), fixed peripheral pins used for the wrong line (RP2040) |
| Clock and reset | oscillator outputs reach clock-capable pins; crystals have both load capacitors and sit on oscillator pins; each reset: pull-up, capacitor, time constant, who can drive it, push-pull against a button; strap resistors strong enough against the internal pull |
| Schematic against board | nets, parts and footprints that differ between the two files |
| Switched loads | buzzers, relays, motors: flyback diode present and the right way round; voltage across a buzzer coil |
| Footprints | every symbol pin has a pad of the same number and the reverse; polarised capacitors the right way round |
| Pins | every connection a part model says the datasheet requires (reference resistors, bypass pins, mode straps); floating enable / reset pins; open-drain outputs with no pull-up; boot-strap pins pulled the wrong way |
| Power | rail voltages and where they come from; each part's supply inside its range; no pin above its absolute maximum (dividers, pull-ups, 5 V into 3.3 V); divided-down signals that never reach a logic high; regulator load, dropout and temperature; fuse / FET / switch current; decoupling count, value and distance; regulator capacitors after DC-bias derating |
| Ratings | capacitor voltage, resistor power, FET Vds / Vgs and whether the gate drive turns it on |
| Layout | aggressor / victim coupling (fast nets beside or across touch, analog and high-impedance nets) with an estimated capacitance; fast nets without ground under them; supply track width against current |
| Simulation | ngspice: each LDO rail through its worst load step at minimum and nominal input. Icarus Verilog: an I2C address scan and ID read on the bus as wired; a frame clocked down every LED chain |

`boardlint checks` prints the list. [docs/checklist-coverage.md](docs/checklist-coverage.md) maps
it against Andrew Zonenberg's schematic and layout review checklists.

## How it works

1. **Read the project.** A built-in reader and netlister for `.kicad_sch` (KiCad 6 to 10,
   hierarchical) and a reader for `.kicad_pcb` (pads, tracks, zones, stack-up). If both are present
   the two netlists are compared. KiCad 5 projects work when they have a board: pin names come from
   the `-cache.lib`, nets from the `.kicad_pcb`.
2. **Recognise the parts.** Each component is matched to a *part model*: a YAML file of datasheet
   facts ([schema](docs/part-model-schema.md)). Parts with no model get pin roles guessed from pin
   names, and the report lists them, because fewer checks apply.
3. **Work out the power tree.** Rail voltages from regulator models, net names and your
   `boardlint.yaml`; followed through fuses, FETs, jumpers and diodes.
4. **Run the checks.** Each finding has a severity, the numbers it rests on, the rule's source, and a confidence.

No LLM runs at check time. Part models are written offline, by a person or by an LLM reading the
datasheet with [tools/extract_prompt.md](tools/extract_prompt.md), then reviewed and committed.

## Project configuration

Optional `boardlint.yaml` next to the project file:

```yaml
rails:                       # declare what cannot be inferred
  +BATT: {vmin: 3.3, vmax: 4.2}
  VIN:   {v: 12}
sources:
  +BATT: {r: 0.08}           # source resistance for the droop simulation, ohms
ambient_c: 40
decoupling: {max_mm: 6}
net_classes:
  aggressor: [PWM_FAN]
  victim: [THERMISTOR]
sim: {keep_dir: build/boardlint-sim, load_tr_us: 10}
waive:
  - {check: "power.budget", refs: [F1], reason: "firmware limits the LEDs to 30 %"}
```

Extra part models: `--parts-dir my_parts/`.

## Testing

```bash
python3 -m pytest -q
```

```bash
BOARDLINT_DINO=/path/to/dino-board BOARDLINT_ECP5=/path/to/basic-ecp5-pcb/hardware python3 -m pytest -q
```

Unit tests need nothing else. The end-to-end tests use the
[DinoLight board](https://github.com/mo-seph/dino-board) as a reference design (not vendored here)
at commit `4da182c` and inject 26 classic mistakes into it in memory, requiring each to be flagged:

```bash
python3 tools/fault_report.py /path/to/dino-board
```

Historical bugs in public repositories (clones them into the directory you give):

```bash
python3 tools/regress.py /tmp/boardlint-regress
```

## Limits to know about

- A clean report means "none of these mistakes", not "the board works".
- Findings are only as good as the part models. Each says whether its model was verified.
- Current budgets add every part's maximum. Real duty cycles are lower; record them as waivers.
- Coupling and droop numbers are closed-form estimates and simple circuit models. They rank
  problems; they do not replace a field solver or a bench measurement.
- KiCad 5 legacy schematics are not netlisted: a KiCad 5 project needs its board file.
- Buses in the schematic (bus wires and bus entries) are not expanded by the built-in netlister.
  When a board file exists its netlist is used, so this only affects schematic-only runs.
- Switching regulators, differential-pair impedance, antenna keep-outs, creepage and thermal design are not checked yet.

## Layout of the repository

```
boardlint/
  sexpr.py  kicad_sch.py  kicad_pcb.py  loader.py    reading KiCad files
  model.py  classify.py  power.py                    design model and analysis
  library/  parts/*.yaml                             part models
  checks/                                            one module per family
  sim/      ngspice.py  busgen.py  verilog/*.v       simulation
  engine.py  report.py  cli.py  faults.py
docs/       PROPOSAL.md  prior-art.md  part-model-schema.md  simulation.md  ...
tools/      extract_prompt.md  fault_report.py
tests/
```
