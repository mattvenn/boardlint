# Checklist coverage

This page maps Andrew Zonenberg's PCB review checklists onto what boardlint checks today. The sources are the [schematic checklist](https://raw.githubusercontent.com/azonenberg/pcb-checklist/master/schematic-checklist.md) and the [layout checklist](https://raw.githubusercontent.com/azonenberg/pcb-checklist/master/layout-checklist.md) from [azonenberg/pcb-checklist](https://github.com/azonenberg/pcb-checklist), `master` branch as fetched on 2026-11-23, BSD 3-Clause, copyright 2018 Andrew Zonenberg. Items are paraphrased here; read the originals for the exact wording.

## How to read the tables

| Status | Meaning |
|---|---|
| `covered` | A boardlint check does what the item asks. |
| `partial` | A check does part of it; the cell says which part. |
| `planned` | Can be automated from the KiCad files plus part models. Not done yet. |
| `needs data` | Can be automated only with data boardlint does not have; the cell names the data. |
| `human` | Judgement or physical inspection. |

Three limits apply to every `covered` and `partial` row:

- Most checks read datasheet facts from a part model. The library holds 26 models. A part without a model gets only the generic rules (one bypass capacitor per supply rail, supply + 0.3 V pin limit, roles guessed from pin names).
- Checks that depend on a rail voltage skip rails whose voltage is unknown. `power.rails` lists them.
- Layout checks need the `.kicad_pcb` file. `power.droop` needs ngspice; `sim.i2c` and `sim.led_chain` need Icarus Verilog.

## Schematic checklist

### General

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| ERC clean, exceptions signed off | `planned` | Run `kicad-cli sch erc`; report violations that have no waiver |
| Symbol pin numbers match datasheet | `needs data` | Full pin number-to-name table per package in each part model |
| Symbol matches package | `covered` | `footprint.pin_map`: every symbol pin number has a pad, every numbered pad has a pin (needs the board file) |
| Thermal pad on the correct rail | `planned` | `pin.requirements` `tie` knows only "ground" or "any supply". Needs a named-rail option and pad entries in models |
| Debug interface not power gated in sleep | `planned` | Debug pin roles in models, then walk the switched-rail graph |
| Cable pinout to other boards | `needs data` | The mating board's project or a connector pin map |

### Passive components

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Power, voltage, tolerance ratings given | `partial` | `ratings.passives`: capacitor voltage rating against its rails, count of capacitors with no rating, power in resistors wired between two rails. Tolerance not checked |
| MLCCs derated for DC bias | `partial` | `decoupling.regulator_caps`, `power.droop`: typical derating by package size, on regulator and charger capacitors only. `ratings.passives` warns above 80 % of rated voltage |
| Polarised parts marked in schematic | `partial` | `polarity.polarised_parts`: + pin of a polarised capacitor on the higher rail. Not done: electrolytic or tantalum values on a non-polarised symbol |

### System power input

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Fuse or reverse-polarity protection at inlet | `planned` | Walk the power path from inlet connectors; look for a fuse, series diode or FET. `power.budget` checks a fuse's rating only when one exists |
| TVS at inlet | `planned` | Look for a TVS-class part from the inlet net to ground |
| Input capacitance and inrush | `partial` | `usb.wiring`: warns above 10 µF directly on VBUS of a Type-C receptacle. Other inlets not checked |

### Regulators

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| UV/OV protection thresholds | `planned` | Threshold fields in regulator models; compute trip points from the divider |
| Rail load against regulator rating | `covered` | `power.regulator`. Loads without a model count as zero and are listed |
| Sense resistor after the output capacitors | `planned` | Find series sense resistors on regulator outputs; check which side the capacitors are on |
| Remote sense on low-voltage or high-current rails | `human` | Whether it is needed is a judgement. `layout.ir_drop` reports the voltage lost in the copper, which informs it |
| LDO or reference stable with output capacitor ESR | `needs data` | Capacitor ESR per part number, and an ESR window in the model. `decoupling.regulator_caps` checks minimum capacitance only |
| Rail sequencing | `planned` | Sequencing rules in part models; derive the order from the enable and power-good chain |

### Decoupling

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Decoupling on every IC | `covered` | `decoupling.per_part`. Without a model: one capacitor of 10 nF or more per IC supply rail |
| Meets vendor recommendation | `covered` | `decoupling.per_part` (count, value, distance from the model), `pin.requirements` (bypass-pin capacitors) |
| Bulk capacitance at the PSU | `covered` | `decoupling.regulator_caps`: model `cin_min` and `cout_min`, within 10 mm when a board is given |

### Power supply: general

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Each supply pin gets the right voltage | `covered` | `power.supply_range`, `power.rails` |
| Power discretes and passives rated for load | `partial` | `power.budget` (fuse, switch, FET current), `ratings.fets` (Vds, Vgs, gate drive), `ratings.passives`. Not checked: diodes, inductor saturation, connectors, dissipation |
| Analog rails filtered or isolated | `planned` | Flag analog supply pins that share a net with digital loads with no series bead, inductor or resistor |

### Errata

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Errata read for major devices | `partial` | The report lists `errata` entries from part models (no check id). They are not evaluated against the design |
| STM32: JTRST not used as I/O | `planned` | An STM32 model and a "not usable as GPIO" pin rule |

### Digital signals

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Logic levels suit the input | `partial` | `power.pin_voltage` (over-voltage), `power.logic_level` (VIH on resistor-divided nets only), `led.chain`, `i2c.bus`. No general driver VOH against receiver VIH/VIL comparison |
| Pull-ups on open-drain outputs | `covered` | `pin.floating_control`, `i2c.bus` (also sizes I2C pull-ups) |
| Pull-downs on PECL outputs | `planned` | Output-standard field in models, then look for the resistors |
| Termination on high-speed signals | `planned` | Net-class list plus a series or parallel resistor search. Today only `led.chain` notes a missing series resistor |
| AC coupling on gigabit transceivers | `planned` | Transceiver pin roles; require a series capacitor per line |
| TX/RX paired correctly | `partial` | `uart.direction`, `spi.bus` (MOSI/MISO, QSPI lane order), `sim.i2c`. No transceiver pairs |
| Differential pair polarity and pairing | `partial` | `usb.wiring`: USB D+/D- only |
| Enable polarity correct | `partial` | `pin.floating_control`: an enable or reset pin hard-tied to its inactive level. Not done: polarity of a pin driven by logic |
| FPGA I/O banking rules | `needs data` | Vendor bank and I/O-standard tables per device and package |
| Auto-sensing level shifter against receiver pulls | `planned` | Model flag for auto-direction shifters; flag pull resistors on either side |

### Analog signals

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Attenuator RC against ADC sampling | `needs data` | ADC acquisition time and sample rate (a firmware setting) |
| RF response across the band | `needs data` | S-parameter files and the intended operating band |
| Op-amp feedback polarity | `planned` | Trace the feedback network to the inverting or non-inverting input, from symbol pin names |

### Clocks

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Oscillator jitter and tolerance | `needs data` | Oscillator specifications and each consumer's requirement |
| Crystal load capacitors | `partial` | `clock.source`: both capacitors present; computed load capacitance compared with a value stated in the schematic. Untested on a real board; crystal models would give the specified CL |
| Crystal only on a pin with an oscillator driver | `partial` | `clock.source`: by pin name (XIN, XTAL, OSC). Untested on a real board |
| FPGA clock-capable input rules | `partial` | `clock.source`: an oscillator must arrive at a clock-capable pin, by the model's `clock_pattern` (ECP5) or by pin name (PCLK, GCLK, MRCC, SRCC). Not done: which clock regions a pin reaches |
| Xilinx: single-ended clock on the P pin | `planned` | Xilinx symbol pin names carry P/N and clock capability |
| Trial place-and-route of clocks | `human` | Needs the vendor toolchain |

### Strap and init pins

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Defined level on boot-critical signals | `covered` | `pin.floating_control`, `pin.requirements`. `spi.bus` notes chip selects with no pull-up |
| Straps tied to the right rail | `covered` | `mcu.strapping`, `pin.requirements` (`tie`), `i2c.bus` (address straps) |
| JTAG/ICSP connector per programmable device | `planned` | Programming pin roles; check they reach a connector, test point or USB |
| Boot flash where there is no internal flash | `planned` | Model flag, then search for a flash on the boot interface |
| Reference resistors: value and rail | `covered` | `pin.requirements` (`res_to_gnd`, `pullup`, `pulldown`), `usb.wiring` (CC 5.1k) |

### External interface protection

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Power outputs current limited | `planned` | Find connector pins fed from an on-board rail; require a fuse or load switch in the path |
| ESD protection on off-board data lines | `planned` | For each connector signal pin, look for a TVS-class part on the net |

### Debugging and reworkability

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| 0-ohm links on straps | `planned` | Flag strap pins wired straight to a rail |
| Several ground points for probes | `planned` | Count test points and headers on ground |
| Ground beside analog test points | `planned` | Distance from analog test points to the nearest ground point (board) |
| Test points on all rails | `planned` | Each supply net has a test point or connector pin |
| Test points on signals of interest | `human` | Which signals matter is a judgement |

### Thermal

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Power estimates for large ICs | `partial` | `power.regulator`: dissipation for LDOs only |
| Thermal calculations | `partial` | `power.regulator`: LDO junction temperature from theta-JA at a configured ambient |
| Heatsinks specified | `human` | Mechanical design decision |

## Layout checklist

### General

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Schematic review done, pin swaps included | `partial` | `sync.schematic_board`: nets, parts and footprints that differ between schematic and board. Sign-off is human |
| DRC clean | `planned` | Run `kicad-cli pcb drc`; report violations that have no waiver |

### Decoupling

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Capacitors close to power pins | `covered` | `decoupling.per_part` (pad-to-pad distance against the model's `max_mm`, 6 mm default), `decoupling.regulator_caps` |
| Low-inductance mounting | `planned` | Vias are parsed; measure pad-to-via track length on capacitor pads |

### DFM and yield

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Rules within fab capability | `needs data` | Fab capability profile (track, space, drill, annular ring) |
| Few features at the fab limit | `needs data` | Same profile; then count tracks and vias near the limit |
| Controlled impedance in fab notes | `human` | Fab notes are free text |
| Impedance calculation includes mask | `human` | Lives in the designer's calculation, not the board file |
| Stackup agreed with fab and in notes | `human` | Agreement with the fab cannot be read from files |
| Board finish specified | `planned` | Read the finish from the board stackup settings |
| Panel position indicators | `human` | The panel is usually not in the project |
| Layer number markers | `planned` | Look for a text item on every copper layer |
| Fiducials on both sides | `planned` | Count fiducial footprints per populated side |
| Asymmetric fiducial pattern | `planned` | Symmetry test on fiducial positions |
| Mask and copper clearance on fiducials | `planned` | Parse pad mask margin and nearby copper |
| Panelisation specified | `human` | Fab documentation |

### Footprints

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Part available in chosen package | `needs data` | Manufacturer or distributor catalogue per part number |
| Part carries the current in that package | `partial` | `power.regulator`, `power.budget`: regulators, fuses, switches, FETs with models. Connectors not checked |
| Symbol matches package | `covered` | `footprint.pin_map` |
| Pinout drawn from top, not bottom | `needs data` | Datasheet pin-to-pad map per package |
| FPC connector entry side and pinout | `needs data` | Contact side of connector and cable, plus the mating board |
| 1:1 paper print against parts | `human` | Physical check |
| 3D models against footprints | `human` | Visual check in the 3D viewer |
| Mask openings on all lands and PTH pads | `planned` | Pad layer lists are already parsed; check for the mask layers |

### Differential pairs

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Routed as a pair | `planned` | Pair nets by role or P/N name; measure the share of length at constant gap |
| Skew matched | `planned` | Sum track length per net of each pair |
| Clearance to other nets | `planned` | Reuse the neighbour search in `layout.coupling` |

### High-speed signals

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Clearance to aggressors | `partial` | `layout.coupling`: fast nets into analog, touch and high-impedance nets within 1.5 mm. Fast nets as victims not checked |
| Length matched | `planned` | Group list in `boardlint.yaml`; sum track lengths |
| No plane splits or layer changes without stitching | `partial` | `layout.return_path`: share of a fast net with no ground copper on the adjacent layer. Layer changes and stitching not checked |
| Fab can plate to the edge for edge launch | `human` | A question for the fab |
| Connector pad width and plane cutouts | `human` | Needs a field solver and judgement |
| Stitching vias in large ground pads | `planned` | Parse pad sizes; count ground vias inside large ground pads |

### Power

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Few plane slots from antipads | `planned` | Find via rows that cut slots in filled zones |
| Copper wide enough for current | `partial` | `layout.track_current`: the current each segment carries, from a resistor-network solve, against IPC-2221 (outer and inner layers). `layout.ir_drop`: voltage lost to each load. Necks in pours and via current not checked |

### Sensitive analog

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Guard rings or shields | `human` | The need depends on the circuit |
| Separated from SMPS and noise | `partial` | `layout.coupling`: capacitive coupling from switch nodes into analog tracks. No placement-distance or magnetic check |
| Microphonic MLCCs | `human` | Depends on the acoustic environment |

### Mechanical

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Connectors meet their mechanical standard | `needs data` | Mechanical drawings of the standard |
| UI parts on the outward face | `planned` | Check LEDs and switches share a side; name the side in `boardlint.yaml` |
| Perimeter and card-guide keep-outs | `planned` | Parse the board outline; component and copper distance to the edge |
| MLCCs clear of break lines, oriented | `planned` | Distance and orientation to the board edge. Mouse-bite positions would need panel data |
| Room for heatsinks and fans | `needs data` | Heatsink and fan dimensions |
| Room for mating connectors | `needs data` | Mating connector and cable envelopes |
| Room for screws at mounting holes | `planned` | Component and track distance to mounting-hole footprints |
| Plane keep-outs under shielded connectors, magnetics | `planned` | Keep-out field in part models; test zone copper under the part |
| Outline and holes match enclosure | `needs data` | Enclosure CAD |
| Mounting hole connection or isolation | `planned` | Report each mounting-hole pad's net; intended net in `boardlint.yaml` |
| No overlapping components | `planned` | Courtyard test; comes with a DRC run |
| Probe room around solder-in test points | `planned` | Distance from test points to neighbouring parts |
| Hole positions suit enclosure rules | `needs data` | Enclosure CAD and its design rules |

### Thermal

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Thermal reliefs on plane connections | `planned` | Parse zone and pad connection settings |
| Solid connection where heatsinking | `planned` | Same data; thermal pads of power parts should connect solid |
| Thermal balance on chip parts | `planned` | Compare the copper attached to each pad of two-pin parts |

### Solder paste

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| No uncapped via in pad | `planned` | Parse pad sizes and via tenting; test for vias inside SMD pads |
| QFN paste segmented | `planned` | Count paste apertures on exposed pads |
| Paste size scaled to pad size | `planned` | Parse pad paste margin and ratio |
| No paste on edge fingers or test points | `planned` | Pad layer lists are already parsed; check for paste layers |

### Solder mask

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| SMD or NSMD pads confirmed | `planned` | Report mask opening against pad size on BGA pads; recommended type in the model |
| Mask clearance around pads | `planned` | Parse pad and board mask margins |

### Silkscreen

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Text size within fab limits | `needs data` | Fab capability profile |
| Text clear of drills and pads | `planned` | Comes with a DRC run |
| Text removed from dense areas | `human` | Judgement |
| Traceability markings | `planned` | Search board text for revision and date |
| Box for serial number | `human` | A blank box is hard to tell from other graphics |
| Bottom text mirrored | `planned` | Check the mirror flag on back-layer text |
| Test points labelled | `planned` | Test-point footprints have visible silk text |

### Flex

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Parts oriented to reduce bending stress | `needs data` | Bend-line locations |
| Teardrops on all connections | `planned` | Read teardrop settings on pads and vias (KiCad 8 and later) |

### CAM production

| Checklist item | Status | Check id(s) or what it would take |
|---|---|---|
| Refill zones and rerun DRC before export | `partial` | The loader notes zones saved unfilled (no check id). Stale fills not detected; DRC not run |
| Gerber and drill exported together | `planned` | Compare creation dates in the Gerber and drill file headers |
| Visual check of CAM files | `human` | Visual inspection |

## Counts

| Checklist | `covered` | `partial` | `planned` | `needs data` | `human` | Total |
|---|---|---|---|---|---|---|
| Schematic | 10 | 15 | 24 | 7 | 4 | 60 |
| Layout | 2 | 7 | 37 | 12 | 14 | 72 |
| Both | 12 | 22 | 61 | 19 | 18 | 132 |

boardlint also runs checks the checklists do not list: I2C address clashes and pull-up sizing, addressable-LED chain order, USB Type-C CC resistors, and rail droop under a load step.

## What to build next

Items 1, 3 and 4 of this list were implemented after it was written (`footprint.pin_map`, `polarity.polarised_parts`, the enable-polarity part of `pin.floating_control`); they are kept here for the reasoning.

The ten `planned` items below are ranked by how often the mistake forces a respin and how little is needed to check it from the netlist or board file.

1. **Symbol matches package** (schematic general, layout footprints). A wrong footprint or pad numbering is the most common cause of a respin. Comparing symbol pin numbers with footprint pad numbers needs no part data and closes two rows.
2. **DRC clean** (layout general). An unrouted net or a stale fill sent to the fab is a certain respin. One call to `kicad-cli pcb drc` with JSON output also closes the component-overlap and silkscreen-overlap rows, and the same wrapper gives ERC.
3. **Polarised parts marked** (passive components). A reversed tantalum or electrolytic fails at first power-up. Rail voltages are already known, so the + pin test is a few lines.
4. **Enable polarity** (digital signals). A regulator or buffer strapped to its inactive level leaves a dead rail. Models already carry `active`; the check compares it with the tie or pull that `pin.floating_control` already finds.
5. **JTAG/ICSP connector per programmable device** (strap and init pins). A board that cannot be programmed cannot be brought up. Needs programming pin roles in MCU models and a reachability walk to a connector, test point or USB.
6. **Thermal pad on the correct rail** (schematic general). A pad on the wrong net shorts a rail or floats the substrate, and cannot be reworked. Needs a named-rail option on `tie` and pad entries in models.
7. **ESD protection on off-board data lines** (external interface protection). Seldom a bring-up failure, often a field failure that forces a new revision. One net walk per connector pin; the library already has a TVS-class model.
8. **Fuse or reverse-polarity protection at inlet** (system power input). The power-path graph and fuse recognition exist. The same walk covers the TVS-at-inlet row.
9. **Crystal load capacitors** (clocks). Wrong values give an oscillator that is off frequency or does not start; the fix is a rework, not a respin, but the check is arithmetic. The same pass covers the crystal-driver row, which is a respin.
10. **Auto-sensing level shifter against receiver pulls** (digital signals). A pull resistor on a TXB-style shifter stops it switching, and the fix is usually a different part. Needs one model flag; `pulls()` does the rest.
