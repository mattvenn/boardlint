# Proposal: a design-review checker for KiCad projects

## The problem

A KiCad project that passes ERC and DRC can still come back from fab with TX wired to TX, a 5 V
pull-up on a 3.3 V pin, a regulator that drops out when the radio transmits, or an LED strip whose
first pixel never sees a logic high. ERC knows pin types, DRC knows clearances; neither knows what
the parts are, what the buses are for, or what the datasheets require.

These mistakes are obvious in hindsight because each one is a simple fact about a part combined
with a simple fact about the netlist. That makes them checkable.

## What already exists

Full survey: [prior-art.md](prior-art.md). The short version:

- **kicad-happy** (MIT) is the closest. It already does I2C pull-up sizing, decoupling, a power
  tree, derating, ngspice testbenches and EMC rules, with LLM skills on top.
- **kisi**, **kicad-irdrop**, **padne** do scriptable PDN / IR-drop / crosstalk estimates on a board file.
- KiCad's own custom DRC rules (master) have a `return_path` constraint.
- Commercial tools (Siemens Schematic Analysis, HyperLynx DRC, CADY, AllSpice DRCY) do
  voltage-aware per-net checks from large proprietary part-model libraries, or LLM datasheet review.

Nothing open-source was found for: UART direction, I2C address clashes, SPI role mismatches,
addressable-LED chain direction, simulation of the wired buses with digital models, or a curated
per-part model library that is version-controlled and reviewed.

## What this proposal is

**boardlint**: a command-line tool that reads a KiCad project and reports findings, each with the
numbers it rests on and where the rule came from.

Three decisions shape it:

1. **Deterministic checks, no LLM at run time.** Same input, same report, no API key. It can run in CI.
2. **Datasheet facts live in reviewed YAML part models.** An LLM reads the datasheet *offline* and
   writes the model; a person reviews it; it is committed. Every finding says which model it used
   and whether that model was verified against the datasheet.
3. **Simulate only where simulation adds something.** Static checks catch a swapped pin. ngspice
   answers "how far does the rail sag"; Verilog answers "with these straps, supplies and mode pins,
   does the part actually answer on the bus".

```
 .kicad_sch ─┐                        ┌─ protocol checks (UART, I2C, SPI, LED chains, USB)
 .kicad_pcb ─┼─> Design model ──┬────>├─ pin requirements, straps, floating controls
 boardlint.yaml                 │     ├─ decoupling, rails, regulators, budget, ratings
                                │     ├─ layout: coupling, return path, track current
 part models (YAML) ────────────┤     ├─ ngspice: rail droop
   ^                            │     └─ iverilog: bus simulation
   └─ offline: datasheet + LLM  │
      + human review            └──> report (text / Markdown / JSON), exit code
```

### The design model

- **Schematic reader and netlister** (`kicad_sch.py`): pure Python, KiCad 6 to 10, hierarchical
  sheets, labels, power symbols. No KiCad install needed. It reproduces the board's netlist
  exactly on six of the seven projects tried that have both files (up to 165 nets over nine
  sheets); the seventh differs in 3 of 351 net groups. Schematic buses are not expanded.
- **Board reader** (`kicad_pcb.py`): pads with positions, tracks, vias, filled zones, copper polygons, stack-up.
- When both exist the board supplies positions and (by default) nets, the schematic supplies pin
  names and types, and the two netlists are compared.
- **Classification** without models: component kinds, passive values, pin roles from pin names,
  ground and supply nets, signal groups through series resistors.
- **Power analysis**: rail voltages from regulator models, net names and `boardlint.yaml`;
  propagation through fuses, FETs, jumpers and diodes; divider voltages; which way is downstream.

### Part models

Schema: [part-model-schema.md](part-model-schema.md). A model holds supply ranges, absolute
maxima, currents, required decoupling, per-pin roles and required connections, I2C address straps,
regulator and FET parameters, a simulation binding, and known errata. Extraction prompt:
`tools/extract_prompt.md`.

Sixteen models were extracted for the test board in about twelve minutes of unattended work.
Fourteen are marked verified (every number read from the datasheet in the repository); two had no
datasheet and say so. A seventeenth (RP2040 pin functions) was written from memory and is marked unverified.

### Honest findings

Every finding carries: severity, the parts and nets, an evidence table (the numbers), a basis (the
rule and the model it came from), and a confidence. Estimates say they are estimates. A check that
cannot run says why in the coverage table. Unmodelled ICs are listed, because "no finding" on an
unmodelled part means "not checked".

## What exists today (v0.1)

28 checks. `python3 -m boardlint checks` lists them.

| Family | Checks | State |
|---|---|---|
| Protocol | `uart.direction`, `i2c.bus`, `spi.bus`, `led.chain`, `usb.wiring`, `mcu.alt_function` | Working. SPI is tested only on synthetic designs. `mcu.alt_function` has one MCU (RP2040) so far. |
| Pins | `pin.requirements`, `pin.floating_control`, `mcu.strapping`, `pin.name_voltage`, `footprint.pin_map` | Working; the first three depend on models. |
| Power | `power.rails`, `power.supply_range`, `power.pin_voltage`, `power.logic_level`, `power.regulator`, `power.budget`, `decoupling.per_part`, `decoupling.regulator_caps` | Working. Currents are worst-case sums of model maxima. |
| Ratings | `ratings.passives`, `ratings.fets`, `polarity.polarised_parts` | Working. Capacitor voltage ratings need a property on the part; most schematics have none. |
| Layout | `layout.coupling`, `layout.return_path`, `layout.track_current` | Working as estimates. Closed-form capacitance, no field solver. |
| Simulation | `power.droop` (ngspice), `sim.i2c`, `sim.led_chain` (Icarus Verilog) | Working for LDOs, I2C targets and single-wire LEDs. |

## How we know it works

Two methods, because a clean report on a good board proves nothing.

1. **Fault injection** (`tools/fault_report.py`, `tests/test_dino.py`). Start from a board believed
   good, apply one classic mistake in memory (swap SDA/SCL, leave off a pull-up, reverse an LED,
   tie both CC pins to one resistor, ...), and require a new finding from the expected check.
   Currently 25 faults, 25 flagged. The first run flagged 20 of 22; the two misses and two
   caught-for-the-wrong-reason cases became fixes.
2. **Historical bugs.** Public KiCad repositories where a commit fixes a real hardware mistake:
   check out the parent, expect a finding; check out the fix, expect it gone. Eight so far
   (`tools/regress.py`): three were flagged on the first, blind run; six after three checks
   were added because of the misses; two cannot be detected from the design files.
   See [regression-corpus.md](regression-corpus.md).

False-positive rate is tracked the same way: every warning on the reference board is triaged by
hand in [dino-board-review.md](dino-board-review.md).

## Roadmap

In order of value per effort.

1. **Grow the model library and make extraction a command.** `boardlint model new <datasheet.pdf>`
   that runs the extraction prompt, validates against the schema, and opens a diff for review.
   Seed MCU pin functions from STM32_open_pin_data and modm-devices; seed passives' rated voltage
   from jlcparts by LCSC number.
2. **More bus knowledge.** MCU alternate-function tables (so "this pin cannot be UART RX" is
   checkable on fixed-function MCUs); QSPI flash; CAN / RS-485 termination and transceiver
   direction; SWD / JTAG header pinouts; SD card; I2S.
3. **Checklist coverage.** Work through [checklist-coverage.md](checklist-coverage.md): crystal
   load capacitance, LED current, test points, connector pin-1 and pinout against known standards,
   footprint pin mapping against the datasheet package drawing.
4. **Better physics where it pays.** Switching regulators in the droop model; PDN impedance against
   a target; hand `layout.coupling` candidates to kisi or openEMS (via gerber2ems) for a real
   number; per-segment current instead of per-net.
5. **Verilog model library.** SPI flash, UART loop-back, and device-specific models for parts with
   known bus errata, so the simulation reproduces the erratum on the board as wired.
6. **Workflow.** KiBot preflight plug-in, GitHub Action with a PR comment, baselines so only new
   findings fail CI (waivers exist already), SARIF output.

## Decisions for you

- **Build on kicad-happy or stay separate?** It overlaps most on power and decoupling and is MIT.
  The parts with no overlap (protocol direction, part models with provenance, bus simulation,
  fault-injection evaluation) could be contributed there, or boardlint could import its analysers.
  Staying separate keeps the "no LLM at run time" property clear. Recommendation: stay separate
  for now, reuse its datasheet-cache format as an import path for models.
- **Licence.** `pyproject.toml` says MIT as a placeholder. Calling GPL tools (kisi, ngspice,
  Icarus) as subprocesses does not constrain it.
- **Where part models live.** In this repository to start. A separate community repository makes
  sense once there are a few hundred.
- **How strict by default.** Today worst-case sums (every LED at full white while the radio
  transmits) produce warnings. A `boardlint.yaml` can record real limits; the alternative is a
  gentler default.
